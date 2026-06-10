import os
import json
import gc
import shutil
import pickle
import random
import datetime
import time
import concurrent.futures as cf
from pathlib import Path
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
import json_repair
from typing import Optional, Callable, List
import yake
import asyncio
import uuid

# Local application imports
from theseus_insight.communication import GmailCommunication, construct_email_body, upload_video
from theseus_insight.data_processing import ArxivDataProcessor, Paper, Newsletter, Podcast
from theseus_insight.pipeline.checkpoints import CheckpointAdapter
from theseus_insight.pipeline.model_loading import load_inference_model
from theseus_insight.pipeline import embedding_pipeline, profiles_pipeline, ranking
from theseus_insight.pipeline.stages import download as download_stage
from theseus_insight.pipeline.stages import email as email_stage
from theseus_insight.pipeline.stages import embed as embed_stage
from theseus_insight.pipeline.stages import rank as rank_stage
from theseus_insight.pipeline.stages import newsletter_content as newsletter_content_stage
from theseus_insight.pipeline.stages import newsletter_sections as newsletter_sections_stage
from theseus_insight.pipeline.stages import podcast as podcast_stage
from theseus_insight.pdf.markdown_extraction import (
    download_pdf_to_temp_file, pdf_to_markdown,
)
from theseus_insight.data_access import (
    PaperRepository, LogsRepository, NewsletterRepository, 
    PodcastRepository, SettingsRepository
)
from theseus_insight.db import get_connection_pool
from theseus_insight.inference import SentenceTransformerInference
from theseus_insight.prompt import (
    NEWSLETTER_SYSTEM_PROMPT,
    RESEARCH_INTERESTS_SYSTEM_PROMPT,
    SYSTEM_CONTENT_EXTRACTION_SUMMARY,
    INSTRUCTION_TEMPLATES,
    general_summary_prompt,
    research_prompt,
    newsletter_context_prompt,
    newsletter_intro_prompt,
    SummaryPromptData,
    ResearchInterestsPromptData,
    NewsletterPromptData
)
from theseus_insight.utils import cosine_similarity, get_n_days_ago, TODAY, purge_ollama_cache
from theseus_insight.constants import INTRO_TEXT

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", None)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", None)
GMAIL_SENDER_ADDRESS = os.getenv("GMAIL_SENDER_ADDRESS", None)
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", None)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
PDF_CONVERSION_TIMEOUT_SEC = int(os.getenv("PDF_CONVERSION_TIMEOUT_SEC", "120"))
PDF_DOWNLOAD_MAX_WORKERS = int(os.getenv("PDF_DOWNLOAD_MAX_WORKERS", "4"))


def _parse_optional_timeout_env(name: str, default: Optional[float]) -> Optional[float]:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"0", "none", "off", "false", "no"}:
        return None

    return float(raw_value)


NEWSLETTER_INTRO_REQUEST_TIMEOUT_SEC = _parse_optional_timeout_env(
    "NEWSLETTER_INTRO_REQUEST_TIMEOUT_SEC",
    1200.0,
)


class TheseusInsight:
    def __init__(self,
                 research_interests_path="config/research_interests.txt",
                 n_days=7,
                 top_n=5,
                 start_date_override=None,
                 end_date_override=None,
                 orchestration_config="config/orchestration.json",
                 receiver_address_override=None,
                 research_interests_override=None,
                 profile_ids_override=None,
                 max_new_tokens=1024,
                 temperature=0.1,
                 cosine_similarity_threshold=0.5,
                 db_saving=True,
                 data_path=os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/theseus"),
                 generate_podcast=False,
                 intro_music_path=None,
                 output_format: str = "mp3",
                 output_dir: str = "output_audio",
                 prefix: str = "podcast_segment",
                 final_filename: str = "podcast_final",
                 resolution: tuple = (1920, 1080),
                 fps: int = 30,
                 matrix_count=200,
                 matrix_head_color="#e0ffe7",   # short hex for bright green
                 matrix_tail_color="0x00b000",  # hex for (0,176,0)
                 matrix_char_size=24,
                 head_step_time=0.25,
                 random_x_jitter=2.0,
                 fade_time=1.5,
                 head_glow_passes=3,
                 head_glow_alpha_decay=50,
                 head_spawn_delay_range=(1.0,3.0),
                 head_saw_period=1.5,
                 wave_color="#d703fc",
                 trail_colors=["#fc03b6", "#ba03fc", "#ce6bf2"], 
                 glow_passes=3,
                 glow_alpha_decay=40,
                 line_width=6,
                 font_path = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                 verbose=True,
                 generate_email=True,
                 publish_podcast=False,
                 visualizer=True,
                 save_dialogue=True,
                 checkpoint_dir="checkpoints",
                 task_id=None,
                 send_error_notifications=True,
                 use_database_checkpoints=True,
                 use_multi_server_judge=False,
                 judge_server_ids=None,
                 newsletter_job_id=None,
                 judge_request_timeout_sec=None,
                 judge_max_retries=None,
                 progress_callback: Optional[Callable[[str, float, str], None]] = None):
        
        # Store task_id for logging
        self.task_id = task_id or f"theseus_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.verbose = verbose
        self.progress_callback = progress_callback
        self.save_dialogue = save_dialogue
        self.checkpoint_dir = checkpoint_dir
        self.generate_email = generate_email
        self.publish_podcast = publish_podcast
        self.generate_podcast = generate_podcast
        self.use_database_checkpoints = use_database_checkpoints

        # Multi-server judge configuration
        self.use_multi_server_judge = use_multi_server_judge
        self.judge_server_ids = judge_server_ids
        self.newsletter_job_id = newsletter_job_id
        self.judge_request_timeout_sec = judge_request_timeout_sec
        self.judge_max_retries = judge_max_retries

        # Set error notification flag early (before any operations that might fail)
        self.send_error_notifications = send_error_notifications
        self.error_notified = False
        
        # Checkpoint persistence (file + optional DB) — see pipeline/checkpoints.py
        self._checkpoints = CheckpointAdapter(
            self.checkpoint_dir,
            use_database_checkpoints=use_database_checkpoints,
            verbose=verbose,
        )
        
        # Email/Communication
        final_receiver_address = None
        if receiver_address_override is not None:
            final_receiver_address = receiver_address_override
        
        if final_receiver_address:
            if isinstance(final_receiver_address, str) and ',' in final_receiver_address:
                self.receiver_address = [addr.strip() for addr in final_receiver_address.split(',')]
            elif isinstance(final_receiver_address, list):
                self.receiver_address = final_receiver_address
            else: # Should be a single string email
                self.receiver_address = [final_receiver_address] if isinstance(final_receiver_address, str) else []

        else:
            self.receiver_address = None

        self.communication = GmailCommunication(
            sender_address=GMAIL_SENDER_ADDRESS,
            app_password=GMAIL_APP_PASSWORD,
            receiver_address=self.receiver_address
        )

        # Dates
        if start_date_override is None and end_date_override is None:
            self.start_date = get_n_days_ago(n_days)
            self.end_date = TODAY
        else:
            def try_parse_date(date_str):
                if not date_str:
                    return None
                formats = ["%Y-%m-%d", "%m-%d-%Y"]
                for fmt in formats:
                    try:
                        return datetime.datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
                # If it's already a date object, return it
                if isinstance(date_str, datetime.date):
                    return date_str
                raise ValueError("Dates must be in YYYY-MM-DD or MM-DD-YYYY format or a date object")

            self.start_date = try_parse_date(start_date_override) if start_date_override else get_n_days_ago(n_days)
            self.end_date = try_parse_date(end_date_override) if end_date_override else TODAY

        self.top_n = top_n
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.cosine_similarity_threshold = cosine_similarity_threshold
        self.db_saving = db_saving
        
        # Store data_path for reference (repositories handle their own connections)
        self.data_path = data_path
        
        # Podcast settings
        self.intro_music_path = intro_music_path
        self.output_format = output_format
        self.output_dir = output_dir
        self.prefix = prefix
        self.final_filename = final_filename
        self.resolution = resolution
        self.fps = fps
        self.matrix_count = matrix_count
        self.matrix_head_color = matrix_head_color
        self.matrix_tail_color = matrix_tail_color
        self.matrix_char_size = matrix_char_size
        self.head_step_time = head_step_time
        self.random_x_jitter = random_x_jitter
        self.fade_time = fade_time
        self.head_glow_passes = head_glow_passes
        self.head_glow_alpha_decay = head_glow_alpha_decay
        self.head_spawn_delay_range = head_spawn_delay_range
        self.head_saw_period = head_saw_period
        self.wave_color = wave_color
        self.trail_colors = trail_colors
        self.glow_passes = glow_passes
        self.glow_alpha_decay = glow_alpha_decay
        self.line_width = line_width
        self.font_path = font_path
        self.visualizer = visualizer
        
        # Load research interests
        if research_interests_override is not None:
            self.research_interests = research_interests_override
        else:
            with open(research_interests_path, 'r') as f:
                self.research_interests = f.read().strip()
        
        # Store profile filtering context
        self.profile_ids_override = profile_ids_override
        
        # Inference models
        if isinstance(orchestration_config, str):
            # first see if this is a json string or a path to a file
            if orchestration_config.startswith('{') and orchestration_config.endswith('}'):
                self.orchestration_config = json.loads(orchestration_config)
            else:
                with open(orchestration_config, 'r') as f:
                    self.orchestration_config = json.load(f)
        elif isinstance(orchestration_config, dict):
            self.orchestration_config = orchestration_config
        else:
            raise ValueError("Invalid orchestration config")

        # Debug: Check the orchestration config before any modifications
        if self.verbose:
            print(f"[DEBUG] TheseusInsight received orchestration_config: {self.orchestration_config.get('arxiv_search_categories', 'NOT SET')}")
        
        # Ensure arxiv_search_categories exists with defaults if not present
        if 'arxiv_search_categories' not in self.orchestration_config:
            if self.verbose:
                print("[DEBUG] arxiv_search_categories not found, setting defaults")
            self.orchestration_config['arxiv_search_categories'] = {
                "main_category": "cs",
                "filter_categories": ["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"]
            }
        else:
            if self.verbose:
                print("[DEBUG] arxiv_search_categories already exists, keeping current values")

        # 1) Embedding model
        self.embedding_model_name = self.orchestration_config['embedding_model']['model_name']
        self.embedding_model = SentenceTransformerInference(
            self.embedding_model_name, 
            remote_code=self.orchestration_config['embedding_model']['trust_remote_code']
        )
        
        # 2) Load specialized LLMs
        self.judge_model_config = self.orchestration_config['judge_model']
        self.content_extraction_model_config = self.orchestration_config['content_extraction_model']
        self.newsletter_sections_model_config = self.orchestration_config['newsletter_sections_model']
        self.newsletter_intro_model_config = self.orchestration_config['newsletter_intro_model']

        self.judge_inference = self._load_inference_model(
            self.judge_model_config['model_type'],
            self.judge_model_config['model_name'],
            self.judge_model_config['max_new_tokens'],
            self.judge_model_config['temperature'],
            self.judge_model_config.get('num_ctx'),
            host=self.judge_model_config.get('host')
        )
        self.content_extraction_inference = self._load_inference_model(
            self.content_extraction_model_config['model_type'],
            self.content_extraction_model_config['model_name'],
            self.content_extraction_model_config['max_new_tokens'],
            self.content_extraction_model_config['temperature'],
            self.content_extraction_model_config.get('num_ctx'),
            host=self.content_extraction_model_config.get('host')
        )
        self.newsletter_sections_inference = self._load_inference_model(
            self.newsletter_sections_model_config['model_type'],
            self.newsletter_sections_model_config['model_name'],
            self.newsletter_sections_model_config['max_new_tokens'],
            self.newsletter_sections_model_config['temperature'],
            self.newsletter_sections_model_config.get('num_ctx'),
            host=self.newsletter_sections_model_config.get('host')
        )
        self.newsletter_intro_inference = self._load_inference_model(
            self.newsletter_intro_model_config['model_type'],
            self.newsletter_intro_model_config['model_name'],
            self.newsletter_intro_model_config['max_new_tokens'],
            self.newsletter_intro_model_config['temperature'],
            self.newsletter_intro_model_config.get('num_ctx'),
            host=self.newsletter_intro_model_config.get('host'),
            request_timeout_sec=(
                NEWSLETTER_INTRO_REQUEST_TIMEOUT_SEC
                if self.newsletter_intro_model_config['model_type'] == "lmstudio"
                else None
            ),
        )

        # 3) Podcast model
        if self.generate_podcast:
            from theseus_insight.podcast.generator import PodcastGenerator
            self.podcast_inference = self.orchestration_config.get('podcast_model', None)
            if not self.podcast_inference:
                raise ValueError("Podcast model not set in orchestration config.")
            self.podcast_generator = PodcastGenerator(
                text_model=self.podcast_inference,
                tts_provider=self.orchestration_config.get('tts_model', {}).get('tts_provider', 'kokoro'),
                speaker_1_voice=self.orchestration_config.get('tts_model', {}).get('speaker_1_voice', 'af_bella'),
                speaker_1_speed=self.orchestration_config.get('tts_model', {}).get('speaker_1_speed', 1.0),
                speaker_2_voice=self.orchestration_config.get('tts_model', {}).get('speaker_2_voice', 'am_adam'),
                speaker_2_speed=self.orchestration_config.get('tts_model', {}).get('speaker_2_speed', 1.0),
                instructions_template=INSTRUCTION_TEMPLATES,
                intro_music_path=self.intro_music_path,
                verbose=self.verbose,
                db_url=data_path  # Pass the database URL
            )
        # 4) Arxiv search categories
        self.arxiv_main_category = self.orchestration_config['arxiv_search_categories']['main_category']
        self.arxiv_filter_categories = self.orchestration_config['arxiv_search_categories']['filter_categories']
        self.pdf_conversion_timeout_sec = PDF_CONVERSION_TIMEOUT_SEC
        self.pdf_download_max_workers = max(PDF_DOWNLOAD_MAX_WORKERS, 1)

    # PDF download/parse mechanics live in pdf/markdown_extraction.py (B8).
    def _download_pdf_to_temp_file(self, pdf_url: str) -> str:
        return download_pdf_to_temp_file(pdf_url, verbose=self.verbose)

    def _parse_downloaded_pdf_to_markdown(self, temp_pdf_path: str, source_pdf_url: str) -> str:
        return pdf_to_markdown(
            temp_pdf_path,
            source_pdf_url,
            timeout_sec=self.pdf_conversion_timeout_sec,
            verbose=self.verbose,
        )

    def _load_inference_model(
        self,
        model_type,
        model_name,
        max_new_tokens,
        temperature,
        num_ctx=None,
        host=None,
        request_timeout_sec=None,
    ):
        """Load the appropriate inference model (pipeline/model_loading.py, B8)."""
        try:
            return load_inference_model(
                model_type,
                model_name,
                max_new_tokens,
                temperature,
                num_ctx=num_ctx,
                host=host,
                request_timeout_sec=request_timeout_sec,
            )
        except Exception as e:
            self._log_error(500, e)
            raise

    def _log_error(self, status_code: int, error: Exception):
        """Helper to log errors to the database and optionally send an email."""
        import traceback
        error_msg = f"{type(error).__name__}: {str(error)}"
        
        # Log the full stack trace to console for debugging
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"ERROR {status_code}: {error_msg}")
            print(f"{'='*60}")
            print("Full stack trace:")
            traceback.print_exc()
            print(f"{'='*60}\n")
        
        LogsRepository.upsert(
            task_id=self.task_id, 
            status=f"ERROR_{status_code}",
            datetime_run=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        # Send error notification email only once per run (if enabled)
        if self.send_error_notifications and not self.error_notified:
            try:
                self.communication.send_error_notification(error_msg)
                self.error_notified = True
            except Exception as e:
                print(f"Failed to send error notification: {str(e)}")

    async def _init_checkpoint_manager(self):
        """Initialize the checkpoint manager and create/resume job."""
        await self._checkpoints.init_db_job({
            "start_date": str(self.start_date),
            "end_date": str(self.end_date),
            "top_n": self.top_n,
            "cosine_threshold": self.cosine_similarity_threshold,
            "profile_ids": self.profile_ids_override,
            "task_id": self.task_id
        })

    # Checkpoint mechanics live in pipeline/checkpoints.py (B8); these
    # delegates keep the ~48 internal call sites unchanged.
    async def _save_checkpoint_async(self, stage: str, data: any):
        await self._checkpoints.save_async(stage, data)

    def _save_checkpoint(self, stage: str, data: any):
        self._checkpoints.save(stage, data)

    async def _load_checkpoint_async(self, stage: str) -> any:
        return await self._checkpoints.load_async(stage)

    def _load_checkpoint(self, stage: str) -> any:
        return self._checkpoints.load(stage)

    async def _cleanup_checkpoints_async(self):
        await self._checkpoints.cleanup_async()

    def _cleanup_checkpoints(self):
        self._checkpoints.cleanup()

    def _cleanup_temp_data(self):
        """Clean up temp_data folder (if it exists)."""
        try:
            temp_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'temp_data'
            )
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                if self.verbose:
                    print("Cleaned up temp_data directory")
        except Exception as cleanup_error:
            print(f"Warning: Failed to clean up temp_data directory: {cleanup_error}")
            self._log_error(500, cleanup_error)

    def _clear_judge_model_cache(self):
        """Clear model cache to resolve potential context issues (Ollama or LM Studio)."""
        try:
            if not hasattr(self, 'judge_inference'):
                return
                
            provider = getattr(self.judge_inference, 'provider', None)
            
            if provider == "ollama":
                model_name = self.judge_model_config.get('model_name')
                if model_name:
                    if self.verbose:
                        print(f"Clearing Ollama cache for judge model: {model_name}")
                    purge_ollama_cache(OLLAMA_URL, model_name)
                    
            elif provider == "lmstudio":
                # For LM Studio, verify the model is still loaded
                # SDK singleton can't be reset, so we just verify connection
                from theseus_insight.utils.lmstudio_client import verify_model_loaded
                model_name = self.judge_model_config.get('model_name')
                lmstudio_host = os.getenv('LMSTUDIO_HOST', 'localhost:1234')
                
                if self.verbose:
                    print(f"Verifying LM Studio model availability: {model_name}")
                    
                if not verify_model_loaded(host=lmstudio_host, model_name=model_name):
                    if self.verbose:
                        print(f"⚠️ LM Studio model {model_name} may not be loaded. Please check LM Studio.")
                    # Wait a bit for potential auto-reload
                    time.sleep(3)
                else:
                    if self.verbose:
                        print(f"✓ LM Studio model verified")
                        
        except Exception as e:
            if self.verbose:
                print(f"Failed to clear judge model cache: {e}")

    def _handle_no_papers_found(self, reason="no_papers_from_arxiv"):
        """Handle the case where no papers were found from ArXiv or all papers were duplicates."""
        
        if reason == "all_duplicates":
            if self.verbose:
                print("All papers already exist in database - no new papers to process.")
            log_status = "NO_NEW_PAPERS_ALL_DUPLICATES"
            email_message = f"""
No New Research Papers - Theseus Insight

Dear Subscriber,

We retrieved research papers from ArXiv for the period {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}, but all papers found were already processed in previous runs.

This means:
• ArXiv papers were successfully retrieved for your specified categories
• All papers have been previously analyzed and included in earlier newsletters
• No new research papers were published in your areas of interest during this period

Search Parameters:
• Date Range: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}
• Categories: {getattr(self, 'arxiv_filter_categories', 'Not specified')}

We'll continue monitoring for new papers in your next scheduled run.

Best regards,
Theseus Insight
            """.strip()
        elif reason == "threshold_not_met":
            if self.verbose:
                print("No papers met the relevance threshold.")
            log_status = "NO_PAPERS_MEET_THRESHOLD"
            email_message = f"""
No Relevant Research Papers - Theseus Insight

Dear Subscriber,

We retrieved research papers from ArXiv for the period {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}, but none of the papers met your relevance criteria.

This means:
• ArXiv papers were successfully retrieved for your specified categories
• After analyzing each paper's relevance to your research interests, none scored above the minimum threshold
• The papers published during this period may not align closely with your specified research focus

Search Parameters:
• Date Range: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}
• Categories: {getattr(self, 'arxiv_filter_categories', 'Not specified')}
• Relevance Threshold: {getattr(self, 'cosine_similarity_threshold', 'Not specified')}

Consider lowering your relevance threshold if you'd like to receive papers with broader relevance to your interests.

Best regards,
Theseus Insight
            """.strip()
        else:
            if self.verbose:
                print("No papers found from ArXiv for the specified date range and categories.")
            log_status = "NO_PAPERS_FOUND"
            email_message = f"""
No Research Papers Found - Theseus Insight

Dear Subscriber,

We attempted to retrieve research papers from ArXiv for the period {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}, but no papers were found matching your criteria.

This could be due to:
• ArXiv API temporary unavailability (503 errors)
• No new papers published in your specified categories during this period
• Network connectivity issues

Search Parameters:
• Date Range: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}
• Categories: {getattr(self, 'arxiv_filter_categories', 'Not specified')}

We'll try again during the next scheduled run. If this issue persists, please check the ArXiv status or contact support.

Best regards,
Theseus Insight Team
            """.strip()
        
        # Log the event
        LogsRepository.upsert(
            task_id=self.task_id, 
            status=log_status,
            datetime_run=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # Send notification email if email generation is enabled
        if self.generate_email and self.receiver_address:
            try:
                
                # Compose the email message
                self.communication.compose_message(
                    content=email_message,
                    start_date=self.start_date,
                    end_date=self.end_date
                )
                # Replace the subject to indicate no papers found (remove existing and set new)
                if self.communication.email_message:
                    del self.communication.email_message['Subject']
                    if reason == "all_duplicates":
                        self.communication.email_message['Subject'] = "Theseus Insight - No New Papers"
                    elif reason == "threshold_not_met":
                        self.communication.email_message['Subject'] = "Theseus Insight - No Relevant Papers"
                    else:
                        self.communication.email_message['Subject'] = "Theseus Insight - No Papers Found"
                self.communication.send_email()
                
                if self.verbose:
                    print(f"Sent 'no papers found' notification to {self.receiver_address}")
                    
                # Log successful email notification
                if reason == "all_duplicates":
                    notification_type = "NO_NEW_PAPERS"
                elif reason == "threshold_not_met":
                    notification_type = "NO_RELEVANT_PAPERS"
                else:
                    notification_type = "NO_PAPERS_FOUND"
                LogsRepository.upsert(
                    task_id=self.task_id, 
                    status=f"EMAIL_{notification_type}_NOTIFICATION: Sent to {self.receiver_address}",
                    datetime_run=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                
            except Exception as e:
                if self.verbose:
                    print(f"Failed to send 'no papers found' notification: {e}")
                self._log_error(500, e)

    def rank_papers_with_historical_scores(self, data_df, return_all_scored=False, progress_callback=None):
        """Delegates to pipeline/ranking.py (B9)."""
        return ranking.rank_papers_with_historical_scores(
            self, data_df, return_all_scored=return_all_scored, progress_callback=progress_callback)

    async def rank_papers_async(self, data_df):
        """Delegates to pipeline/ranking.py (B9)."""
        return await ranking.rank_papers_async(self, data_df)

    async def _rank_papers_multi_server(self, data_df):
        """Delegates to pipeline/ranking.py (B9)."""
        return await ranking.rank_papers_multi_server(self, data_df)

    def rank_papers(self, df, progress_callback=None):
        """Delegates to pipeline/ranking.py (B9)."""
        return ranking.rank_papers(self, df, progress_callback=progress_callback)

    def _rank_papers_single_server(self, df, progress_callback=None):
        """Delegates to pipeline/ranking.py (B9)."""
        return ranking.rank_papers_single_server(self, df, progress_callback=progress_callback)

    def get_profile_papers(self, profile_ids: List[int], min_score: float = 0.5) -> pd.DataFrame:
        """
        Retrieve papers scored by specific profiles for newsletter generation.
        
        Args:
            profile_ids: List of profile IDs to filter by
            min_score: Minimum profile score threshold
            
        Returns:
            DataFrame with papers formatted for newsletter generation
        """
        try:
            if self.verbose:
                print(f"\n📋 RETRIEVING PROFILE PAPERS")
                print(f"Profile IDs: {profile_ids}")
                print(f"Min score: {min_score}")
                print("="*60)
            
            from .db import get_cursor
            
            # Get papers with profile scores
            papers_data = []
            with get_cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT p.*, pps.score, pps.related, pps.rationale
                    FROM papers p
                    INNER JOIN paper_profile_scores pps ON p.id = pps.paper_id
                    WHERE pps.profile_id = ANY(%s)
                      AND pps.score >= %s
                      AND p.date >= %s
                      AND p.date <= %s
                    ORDER BY pps.score DESC, p.date DESC
                    LIMIT %s
                """, (profile_ids, min_score, self.start_date, self.end_date, self.top_n * 4))  # Get 4x more than needed for PDF failures
                
                papers_data = cur.fetchall()
            
            if not papers_data:
                if self.verbose:
                    print("No papers found for the specified profiles and criteria")
                return pd.DataFrame()
            
            # Convert to DataFrame format expected by newsletter generation
            papers_list = []
            for paper in papers_data:
                papers_list.append({
                    'title': paper['title'],
                    'abstract': paper['abstract'],
                    'pdf_url': paper['url'],
                    'date': paper['date'],
                    'score': paper['score'],  # Use profile score
                    'related': paper['related'],
                    'rationale': paper['rationale'],
                    'cosine_similarity': 1.0,  # Set high since profile already filtered
                    'abstract_embedding': None  # Not needed for profile-based approach
                })
            
            df = pd.DataFrame(papers_list)
            
            # Take more papers than needed to allow for PDF conversion failures
            backup_multiplier = 2
            extended_count = min(len(df), self.top_n * backup_multiplier)
            top_df = df.head(extended_count)
            
            if self.verbose:
                print(f"✅ Retrieved {len(top_df)} profile-scored papers")
                if len(top_df) > 0:
                    print(f"Score range: {top_df['score'].min():.2f} - {top_df['score'].max():.2f}")
            
            return top_df
            
        except Exception as e:
            if self.verbose:
                print(f"Error retrieving profile papers: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def get_and_score_profile_papers(
        self,
        profile_ids: List[int],
        embedded_df: pd.DataFrame = None,
        progress_callback: Optional[Callable[[str, float, str, dict], None]] = None
    ) -> pd.DataFrame:
        """
        Get papers from database in date range and score them for the profile.
        This ensures newsletter generation works even if profile hasn't scored papers yet.
        
        Args:
            profile_ids: List of profile IDs to score for
            embedded_df: Optional DataFrame with freshly downloaded papers to use instead of database query
            
        Returns:
            DataFrame with top-scored papers for newsletter generation
        """
        try:
            if self.verbose:
                print(f"\n🎯 SCORING PAPERS FOR PROFILE NEWSLETTER")
                print(f"Profile IDs: {profile_ids}")
                print(f"Date range: {self.start_date} to {self.end_date}")
                print("="*60)
            
            from .data_access import ProfileRepository, ProfileInterestsRepository
            from .db import get_cursor
            
            # Get research interests for the profile
            research_interests_list = []
            for profile_id in profile_ids:
                interests = ProfileInterestsRepository.get_by_profile(profile_id)
                for interest in interests:
                    research_interests_list.append(interest["interest_text"])
            
            if not research_interests_list:
                if self.verbose:
                    print("⚠️ No research interests found for profile(s)")
                return pd.DataFrame()
            
            research_interests_text = "\n".join(research_interests_list)
            if self.verbose:
                print(f"Research interests: {research_interests_text[:200]}...")
            
            # Use embedded_df if provided (freshly downloaded papers), otherwise query database
            if embedded_df is not None and not embedded_df.empty:
                if self.verbose:
                    print(f"📊 Using {len(embedded_df)} freshly downloaded papers from current session")
                
                # Convert DataFrame to the format expected by scoring
                papers_list = []
                for _, row in embedded_df.iterrows():
                    papers_list.append({
                        'id': row.get('id'),  # Include database ID for multi-server scoring
                        'title': row['title'],
                        'abstract': row['abstract'],
                        'pdf_url': row['pdf_url'],
                        'date': row['date'],
                        'cosine_similarity': 1.0,  # Will be set during scoring
                        'abstract_embedding': row['abstract_embedding']  # Use existing embedding
                    })
                
                df = pd.DataFrame(papers_list)
            else:
                # Fall back to database query (existing logic)
                # Get papers from database in date range (up to 100 to ensure we have enough to score)
                papers_data = []
                with get_cursor() as cur:
                    # First, let's check what date range we have in the database
                    cur.execute("""
                        SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(*) as total_papers
                        FROM papers
                    """)
                    date_info = cur.fetchone()
                    if self.verbose and date_info:
                        print(f"📊 Database contains {date_info['total_papers']} papers")
                        print(f"   Date range: {date_info['min_date']} to {date_info['max_date']}")
                    
                    cur.execute("""
                        SELECT * FROM papers 
                        WHERE date >= %s AND date <= %s
                        ORDER BY date DESC 
                        LIMIT 100
                    """, (self.start_date, self.end_date))
                    
                    papers_data = cur.fetchall()
                
                if not papers_data:
                    if self.verbose:
                        print("No papers found in database for the date range")
                        # Let's also check if there are any papers close to this date range
                        with get_cursor() as cur:
                            cur.execute("""
                                SELECT date, COUNT(*) as count 
                                FROM papers 
                                WHERE date >= %s AND date <= %s
                                GROUP BY date 
                                ORDER BY date DESC 
                                LIMIT 10
                            """, (
                                self.start_date - datetime.timedelta(days=30),
                                self.end_date + datetime.timedelta(days=30)
                            ))
                            nearby_papers = cur.fetchall()
                            if nearby_papers:
                                print(f"📅 Papers found within ±30 days:")
                                for row in nearby_papers:
                                    print(f"   {row['date']}: {row['count']} papers")
                            else:
                                print("📅 No papers found within ±30 days of target range")
                    return pd.DataFrame()
                
                if self.verbose:
                    print(f"📊 Found {len(papers_data)} papers in date range")
                
                # Convert to DataFrame for scoring
                papers_list = []
                for paper in papers_data:
                    papers_list.append({
                        'id': paper.get('id'),  # Include database ID for multi-server scoring
                        'title': paper['title'],
                        'abstract': paper['abstract'],
                        'pdf_url': paper['url'],
                        'date': paper['date'],
                        'cosine_similarity': 1.0,  # Will be set during scoring
                        'abstract_embedding': None  # Not needed for judge scoring
                    })
                
                df = pd.DataFrame(papers_list)
            
            if self.verbose:
                print(f"🧠 Starting scoring process with judge model...")

            # Temporarily override research interests for profile-specific scoring
            original_research_interests = self.research_interests
            self.research_interests = research_interests_text

            try:
                # Score papers using the optimized ranking method
                # Get both top_n for newsletter AND all scored papers for profile saving
                top_n_df, all_scored_df = self.rank_papers_with_historical_scores(
                    df,
                    return_all_scored=True,
                    progress_callback=progress_callback
                )
            finally:
                # Restore original research interests
                self.research_interests = original_research_interests

            # Save ALL scored papers to paper_profile_scores table (not just top_n)
            if self.db_saving and not all_scored_df.empty:
                from .data_access.profiles import ProfileScoreRepository
                
                if self.verbose:
                    print(f"💾 Saving profile scores for {len(profile_ids)} profile(s)...")

                saved_scores = 0
                papers_inserted = 0
                for profile_id in profile_ids:
                    # Save ALL scored papers, not just top_n
                    for _, row in all_scored_df.iterrows():
                        # Get the paper ID from database using URL
                        existing_paper = PaperRepository.get_by_url(row['pdf_url'])
                        
                        # If paper doesn't exist, insert it first (shouldn't normally happen but handle gracefully)
                        if not existing_paper:
                            if self.verbose:
                                print(f"⚠️ Paper not found in database, inserting: {row['title'][:50]}...")
                            
                            # Get or create embedding
                            embedding = row.get('abstract_embedding')
                            if embedding is None:
                                # Generate embedding if not present
                                embedding = self.embedding_model.invoke(row['abstract'])
                            
                            if hasattr(embedding, 'tolist'):
                                embedding = embedding.tolist()
                            elif not isinstance(embedding, list):
                                embedding = list(embedding)
                            
                            paper = Paper(
                                title=row['title'],
                                abstract=row['abstract'],
                                url=row['pdf_url'],
                                date_run=TODAY.strftime('%Y-%m-%d'),
                                date=row['date'].strftime('%Y-%m-%d'),
                                score=row['score'],
                                related=row['related'],
                                rationale=row['rationale'],
                                cosine_similarity=row.get('cosine_similarity', 0.0),
                                embedding_model=self.embedding_model_name,
                                embedding=embedding
                            )
                            
                            was_inserted = PaperRepository.insert_paper(paper, skip_duplicates=True)
                            if was_inserted:
                                papers_inserted += 1
                                existing_paper = PaperRepository.get_by_url(row['pdf_url'])
                        
                        if existing_paper:
                            # Save profile score
                            success = ProfileScoreRepository.create_or_update_score(
                                paper_id=existing_paper['id'],
                                profile_id=profile_id,
                                score=int(row['score']),
                                related=bool(row['related']),
                                rationale=str(row['rationale']),
                                judge_model=getattr(self.judge_inference, 'model_name', 'unknown')
                            )
                            if success:
                                saved_scores += 1
                
                if self.verbose:
                    print(f"✅ Saved {saved_scores} profile scores")
                    if papers_inserted > 0:
                        print(f"✅ Inserted {papers_inserted} missing papers into database")
            
            # Return the limited top_n_df for newsletter generation
            # (all_scored_df was already saved to database above)
            top_df = top_n_df

            if self.verbose:
                print(f"✅ Returning top {len(top_df)} papers for newsletter generation (target: {self.top_n})")
                print(f"✅ Saved {len(all_scored_df)} total papers to paper_profile_scores")
            
            if self.verbose:
                print(f"✅ Scored and selected top {len(top_df)} papers")
                if len(top_df) > 0:
                    print(f"Score range: {top_df['score'].min():.2f} - {top_df['score'].max():.2f}")
                    related_count = sum(top_df['related'])
                    print(f"Related papers: {related_count}/{len(top_df)}")
            
            return top_df
            
        except Exception as e:
            if self.verbose:
                print(f"Error scoring profile papers: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def store_papers_without_scoring(self, data_df):
        """Store all papers without LLM judge scoring for profiles feature."""
        try:
            if self.verbose:
                print(f"\n💾 STORING {len(data_df)} PAPERS WITHOUT SCORING")
                print("="*60)
                
            # Save all papers to DB with null scores for later profile-specific scoring
            saved_count = 0
            duplicate_count = 0
            duplicate_urls = []
            
            # Use YAKE keyword extractor
            try:
                extractor = getattr(self, '_yake_extractor', None)
                if extractor is None:
                    import yake
                    extractor = yake.KeywordExtractor(lan="en", n=1, top=5)
                    self._yake_extractor = extractor  # cache for reuse
            except ImportError:
                extractor = None
                if self.verbose:
                    print("YAKE not available, skipping keyword extraction")
            
            # Collect all papers and their embeddings for bulk update
            updates = []
            new_papers = []
            
            for _, row in tqdm(data_df.iterrows(), total=len(data_df), 
                              desc="Preparing embeddings", disable=not self.verbose):
                # Check if paper already exists
                existing_paper = PaperRepository.get_by_url(row['pdf_url'])
                
                # Convert numpy array to list if needed for embedding
                embedding = row['abstract_embedding']
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                elif not isinstance(embedding, list):
                    embedding = list(embedding)
                
                if existing_paper:
                    # Update existing paper's embedding
                    updates.append((existing_paper['id'], embedding))
                    duplicate_count += 1
                else:
                    # For new papers, create and insert
                    paper = Paper(
                        title=row['title'],
                        abstract=row['abstract'],
                        url=row['pdf_url'],
                        date_run='1970-01-01',  # Placeholder date - will be updated when scored
                        date=row['date'].strftime('%Y-%m-%d'),
                        score=0.0,  # Placeholder score - will be updated when scored
                        related=False,  # Placeholder - will be updated when scored
                        rationale='Not yet scored',  # Placeholder - will be updated when scored
                        cosine_similarity=row['cosine_similarity'],
                        embedding_model=self.embedding_model_name,
                        embedding=embedding
                    )
                    new_papers.append(paper)
            
            # Bulk insert new papers
            if new_papers:
                if self.verbose:
                    print(f"\n💾 Inserting {len(new_papers)} new papers...")
                stats = PaperRepository.bulk_insert(new_papers, skip_duplicates=True)
                saved_count += stats.get('imported', 0)
            
            # Bulk update embeddings for existing papers
            if updates:
                if self.verbose:
                    print(f"\n💾 Updating embeddings for {len(updates)} existing papers...")
                PaperRepository.bulk_update_embeddings(updates, embedding_model=self.embedding_model_name)
                # Note: These are updates, not new insertions
            
            if self.verbose:
                print(f"✅ Storage complete: {saved_count} new papers saved, {len(updates)} papers updated with embeddings")
                
            return {
                'saved_count': saved_count,
                'duplicate_count': duplicate_count,
                'total_processed': len(data_df)
            }
            
        except Exception as e:
            self._log_error(500, e)
            raise

    def run(self, 
            start_from: str | None = None, 
            progress_callback: Callable[[str, float, str], None]|None = None
           ):
        """Synchronous wrapper for the async run method."""
        if progress_callback:
            self.progress_callback = progress_callback
        return asyncio.run(self.run_async(start_from, progress_callback))
    
    async def run_async(self, 
                       start_from: str | None = None, 
                       progress_callback: Callable[[str, float, str], None]|None = None
                      ):
        """
        Unified pipeline with checkpoints. 
        Harmonizes the old generate_newsletter_and_podcast() features:
         - Save newsletter to DB
         - Send email
         - Generate podcast (audio + optional visualizer)
         - Save dialogue JSON
         - Insert podcast into DB
        """
        data_df = None
        embedded_df = None
        top_n_df = None
        sections_data = None
        newsletter_content = None
        podcast_content = None
        
        if self.verbose:
            print(f"\n{'='*80}")
            print(f"🚀 STARTING NEWSLETTER PIPELINE")
            print(f"   Task ID: {self.task_id}")
            print(f"   Use multi-server: {self.use_multi_server_judge}")
            print(f"   Date range: {self.start_date} to {self.end_date}")
            print(f"{'='*80}\n")
        
        try:
            # Initialize checkpoint manager if using database checkpoints
            await self._init_checkpoint_manager()
            
            # -----------
            # Stage 1: Download Papers (pipeline/stages/download.py, B9)
            # -----------
            data_df, exit_early = await download_stage.run(self, start_from, progress_callback)
            if exit_early:
                return

            # -----------
            # Stage 2: Embed Papers (pipeline/stages/embed.py, B9)
            # -----------
            embedded_df, exit_early = await embed_stage.run(self, data_df, start_from, progress_callback)
            if exit_early:
                return

            # -----------
            # Stage 3: Rank Papers (pipeline/stages/rank.py, B9)
            # -----------
            top_n_df = await rank_stage.run(self, embedded_df, start_from, progress_callback)
            embedded_df = None  # the stage releases embeddings; drop our reference too

            # -----------
            # Stage 4: Newsletter Sections (pipeline/stages/newsletter_sections.py, B9)
            # -----------
            sections_data = await newsletter_sections_stage.run(self, top_n_df, start_from, progress_callback)

            # -----------
            # Stage 5: Newsletter Content (pipeline/stages/newsletter_content.py, B9)
            # -----------
            newsletter_content, sections_data = await newsletter_content_stage.run(
                self, sections_data, start_from, progress_callback
            )

            # -----------
            # Stage 6: Send Email (pipeline/stages/email.py, B9)
            # -----------
            newsletter_content, sections_data = await email_stage.run(
                self, newsletter_content, sections_data, progress_callback
            )

            # -----------
            # Stage 7: Podcast (pipeline/stages/podcast.py, B9)
            # -----------
            await podcast_stage.run(self, top_n_df, sections_data, progress_callback)

            # -----------
            # Final Step: Mark completion, purge + cleanup
            # -----------
            await self._save_checkpoint_async('newsletter_complete', {'status': 'complete'})
            # Try to purge the cache for all Ollama models used in the orchestration config
            try:
                # Collect all unique Ollama model names from the orchestration config
                ollama_models = set()
                for key, cfg in self.orchestration_config.items():
                    if isinstance(cfg, dict) and cfg.get('model_type', '').lower() == 'ollama':
                        model_name = cfg.get('model_name')
                        if model_name:
                            ollama_models.add(model_name)
                for model_name in ollama_models:
                    purge_ollama_cache(OLLAMA_URL, model_name)
            except Exception as e:
                if self.verbose:
                    print(f"Failed to purge Ollama cache for some models: {e}")

            # Log final success
            LogsRepository.upsert(
                task_id=self.task_id,
                status="COMPLETED: Successfully completed Theseus Insight run",
                datetime_run=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            # Only purge checkpoints when the run actually produced a newsletter.
            # An empty top_n_df means scoring failed silently or no papers met
            # criteria; keeping the file checkpoints lets a manual retry resume
            # from the closest viable stage instead of re-ingesting from scratch.
            produced_papers = (
                'top_n_df' in locals()
                and top_n_df is not None
                and len(top_n_df) > 0
            )
            if produced_papers:
                self._cleanup_checkpoints()
            elif self.verbose:
                print(
                    "Skipping checkpoint cleanup: run completed with no papers ranked. "
                    "Checkpoints retained so a retry can resume."
                )

        except Exception as e:
            # Mark job as failed if using database checkpoints
            try:
                await self._checkpoints.fail_job(str(e))
            except Exception as checkpoint_error:
                if self.verbose:
                    print(f"Failed to mark job as failed: {checkpoint_error}")
            
            self._log_error(500, e)
            raise
        finally:
            self._cleanup_temp_data()

    def run_profiles_pipeline(self, progress_callback: Callable[[str, float, str], None]|None = None):
        """Delegates to pipeline/profiles_pipeline.py (B9)."""
        return profiles_pipeline.run(self, progress_callback)

    def run_embedding_only_pipeline(self, progress_callback: Callable[[str, float, str], None]|None = None):
        """Delegates to pipeline/embedding_pipeline.py (B9)."""
        return embedding_pipeline.run(self, progress_callback)
