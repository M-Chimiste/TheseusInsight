import os
import json
import gc
import shutil
import pickle
import random
import datetime
import time
import queue
import multiprocessing as mp
import concurrent.futures as cf
import tempfile
from pathlib import Path
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
import json_repair
from typing import Optional, Callable, List
import yake
import asyncio
import uuid
import requests

# Local application imports
from theseus_insight.communication import GmailCommunication, construct_email_body, upload_video
from theseus_insight.data_processing import ArxivDataProcessor, Paper, Newsletter, Podcast
from theseus_insight.pipeline.checkpoints import CheckpointAdapter
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


def _markitdown_convert_worker(pdf_path: str, result_queue):
    """Convert a local PDF file to markdown in a subprocess so hangs can be terminated."""
    try:
        import re
        from markitdown import MarkItDown

        converter = MarkItDown(enable_plugins=False)
        result = converter.convert(pdf_path)
        markdown = re.sub(r"\n{2,}", "\n", result.text_content or "").strip()
        if not markdown:
            raise ValueError(f"MarkItDown returned empty content for {pdf_path}")
        result_queue.put(("ok", markdown))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _docling_convert_worker(pdf_path: str, result_queue):
    """Convert a local PDF file to markdown with Docling in a subprocess."""
    try:
        from theseus_insight.pdf.processing import DoclingDocProcessor

        processor = DoclingDocProcessor(
            export_tables=False,
            export_figures=False,
            save_text=False,
            remove_md_image_tags=True,
            verbose=False,
        )
        result = processor.process_document(pdf_path)
        markdown = (result.get("processed_data") or "").strip()
        if not markdown:
            raise ValueError(f"Docling returned empty content for {pdf_path}")
        result_queue.put(("ok", markdown))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


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

    def _download_pdf_to_temp_file(self, pdf_url: str) -> str:
        """Download a PDF to a temporary local file with periodic progress logs."""
        temp_pdf_path = None
        downloaded_bytes = 0
        last_log_time = time.time()
        last_logged_bytes = 0
        chunk_size = 256 * 1024

        if self.verbose:
            print(f"   Downloading PDF from {pdf_url}")

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_pdf_path = temp_file.name

            with requests.Session() as session:
                response = session.get(
                    pdf_url,
                    timeout=(15, 60),
                    stream=True,
                    headers={
                        "User-Agent": "TheseusInsight/1.0 PDF fetcher",
                        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
                    },
                )
                response.raise_for_status()

                total_bytes = int(response.headers.get("Content-Length", "0") or 0)

                with open(temp_pdf_path, "wb") as temp_file:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue

                        temp_file.write(chunk)
                        downloaded_bytes += len(chunk)

                        should_log = (
                            downloaded_bytes - last_logged_bytes >= 5 * 1024 * 1024
                            or time.time() - last_log_time >= 10
                        )
                        if self.verbose and should_log:
                            downloaded_mb = downloaded_bytes / (1024 * 1024)
                            if total_bytes > 0:
                                total_mb = total_bytes / (1024 * 1024)
                                pct = (downloaded_bytes / total_bytes) * 100
                                print(
                                    f"   Downloaded {downloaded_mb:.1f}/{total_mb:.1f} MB "
                                    f"({pct:.0f}%)"
                                )
                            else:
                                print(f"   Downloaded {downloaded_mb:.1f} MB")
                            last_log_time = time.time()
                            last_logged_bytes = downloaded_bytes

            if self.verbose:
                final_mb = downloaded_bytes / (1024 * 1024)
                print(f"   PDF download complete ({final_mb:.1f} MB)")

            return temp_pdf_path

        except Exception:
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.unlink(temp_pdf_path)
                except OSError:
                    pass
            raise

    def _run_pdf_parse_worker(
        self,
        worker_target,
        parser_name: str,
        temp_pdf_path: str,
        source_pdf_url: str,
    ) -> str:
        """Run a PDF parser subprocess with a hard timeout and return markdown text."""
        ctx = mp.get_context("spawn")
        result_queue = ctx.Queue(maxsize=1)
        process = ctx.Process(
            target=worker_target,
            args=(temp_pdf_path, result_queue),
            daemon=True,
        )
        if self.verbose:
            print(
                f"   Starting {parser_name} parse for local file "
                f"{Path(temp_pdf_path).name} "
                f"(source: {source_pdf_url}, timeout: {self.pdf_conversion_timeout_sec}s)"
            )
        process.start()
        deadline = time.monotonic() + self.pdf_conversion_timeout_sec

        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"{parser_name} parsing exceeded {self.pdf_conversion_timeout_sec}s for local file "
                        f"{Path(temp_pdf_path).name} (source: {source_pdf_url})"
                    )

                try:
                    status, payload = result_queue.get(timeout=min(1.0, remaining))
                    break
                except queue.Empty:
                    if process.exitcode is not None:
                        raise RuntimeError(
                            "PDF conversion subprocess exited without returning data "
                            f"(exit code: {process.exitcode})"
                        )

            if status == "error":
                raise RuntimeError(payload)

            return payload
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1)
            else:
                process.join(timeout=1)
            result_queue.close()
            result_queue.join_thread()

    def _parse_downloaded_pdf_to_markdown(self, temp_pdf_path: str, source_pdf_url: str) -> str:
        """Convert a downloaded local PDF file to markdown using Docling, then MarkItDown as fallback."""
        parser_attempts = (
            ("Docling", _docling_convert_worker),
            ("MarkItDown", _markitdown_convert_worker),
        )
        parse_errors = []

        for parser_name, worker in parser_attempts:
            try:
                return self._run_pdf_parse_worker(
                    worker_target=worker,
                    parser_name=parser_name,
                    temp_pdf_path=temp_pdf_path,
                    source_pdf_url=source_pdf_url,
                )
            except Exception as exc:
                parse_errors.append(f"{parser_name}: {exc}")
                if self.verbose:
                    print(f"   {parser_name} parse failed, trying next parser if available: {exc}")

        raise RuntimeError("All PDF parsers failed. " + " | ".join(parse_errors))

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
        """Load the appropriate inference model based on model type."""
        try:
            if model_type == "anthropic":
                if ANTHROPIC_API_KEY is None:
                    raise ValueError("Anthropic API key is not set.")
                from LLMFactory.providers import AnthropicInference
                return AnthropicInference(model_name, max_new_tokens, temperature)

            elif model_type == "openai":
                if OPENAI_API_KEY is None:
                    raise ValueError("OpenAI API key is not set.")
                from LLMFactory.providers import OpenAIInference
                return OpenAIInference(model_name, max_new_tokens, temperature)

            elif model_type == "gemini":
                if GOOGLE_API_KEY is None:
                    raise ValueError("Google API key is not set.")
                from LLMFactory.providers import GeminiInference
                return GeminiInference(model_name, max_new_tokens, temperature)

            elif model_type == "ollama":
                from LLMFactory.providers import OllamaInference
                ollama_url = host or OLLAMA_URL
                kwargs = {
                    'model_name': model_name,
                    'max_new_tokens': max_new_tokens,
                    'temperature': temperature,
                    'url': ollama_url
                }
                if num_ctx is not None:
                    kwargs['num_ctx'] = num_ctx
                return OllamaInference(**kwargs)

            elif model_type == "lmstudio":
                from theseus_insight.utils.lmstudio_client import get_lmstudio_client
                # LMStudio needs host parameter instead of url
                # Respect explicit config first, then env, then localhost default
                lmstudio_host = host or os.getenv('LMSTUDIO_HOST', 'localhost:1234')
                return get_lmstudio_client(
                    model_name=model_name,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    host=lmstudio_host,
                    context_length=num_ctx,
                    request_timeout_sec=request_timeout_sec,
                )

            else:
                raise ValueError(f"Invalid model type: {model_type}")
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
        """Optimized ranking that uses existing scores when available, only ranking new papers.

        Args:
            data_df: DataFrame of papers to rank
            return_all_scored: If True, return tuple (top_n_df, all_scored_df) for profile scoring
            progress_callback: Optional callback for progress updates
        """
        try:
            if self.verbose:
                print(f"\n🏃‍♂️ OPTIMIZED RANKING WITH HISTORICAL SCORES")
                print(f"Total papers to process: {len(data_df)}")
                print("="*60)

            # Bulk-fetch existing rows + aggregated profile scores upfront so we
            # don't issue 3686 round-trips classifying "has score" vs "needs scoring".
            # For profile-aware runs the authoritative score lives in
            # paper_profile_scores, NOT papers.score — the latter is only populated by
            # the legacy single-research-interests path and stays NULL for profile mode.
            urls = [row['pdf_url'] for _, row in data_df.iterrows() if row.get('pdf_url')]
            url_to_paper = PaperRepository.get_url_to_id_and_score_map(urls)

            profile_score_map: dict = {}
            using_profile_scores = bool(getattr(self, 'profile_ids_override', None))
            if using_profile_scores:
                from .data_access.profiles import ProfileScoreRepository
                profile_score_map = ProfileScoreRepository.get_aggregated_scores_for_profiles(
                    self.profile_ids_override
                )
                if self.verbose:
                    print(
                        f"📚 Profile-aware resume: found cached scores for "
                        f"{len(profile_score_map)} papers across profiles {self.profile_ids_override}"
                    )

            # Separate papers into those with and without existing scores
            papers_with_scores = []
            papers_without_scores = []

            for idx, row in data_df.iterrows():
                paper_data = row.to_dict()
                pdf_url = row.get('pdf_url')
                existing_paper = url_to_paper.get(pdf_url) if pdf_url else None

                # Profile-aware path: prefer paper_profile_scores. A row in that table
                # means a worker successfully scored this paper for at least one of
                # the active profiles — treat it as historical, no rescore needed.
                profile_score = None
                if using_profile_scores and existing_paper:
                    profile_score = profile_score_map.get(existing_paper['id'])

                if profile_score is not None and profile_score.get('score') is not None:
                    paper_data['score'] = profile_score['score']
                    paper_data['related'] = profile_score.get('related', True)
                    paper_data['rationale'] = profile_score.get('rationale') or 'Historical profile score'
                    papers_with_scores.append(paper_data)
                elif (
                    existing_paper
                    and existing_paper.get('score') is not None
                    and (existing_paper.get('score') or 0) > 0
                ):
                    # Legacy single-interests path: papers.score is populated
                    paper_data['score'] = existing_paper['score']
                    paper_data['related'] = existing_paper.get('related', True)
                    paper_data['rationale'] = existing_paper.get('rationale', 'Historical score')
                    papers_with_scores.append(paper_data)
                else:
                    # Paper needs to be scored
                    papers_without_scores.append(paper_data)

            if self.verbose:
                print(f"📊 Papers with existing scores: {len(papers_with_scores)}")
                print(f"🔄 Papers needing new scores: {len(papers_without_scores)}")
                if using_profile_scores and papers_with_scores:
                    reused_from_profile = sum(
                        1
                        for p in papers_with_scores
                        if isinstance(p.get('rationale'), str)
                        and 'profile' in p['rationale'].lower()
                    )
                    print(f"   ↳ reused from paper_profile_scores: {reused_from_profile}")

            # Create DataFrames
            scored_papers_df = pd.DataFrame(papers_with_scores) if papers_with_scores else pd.DataFrame()
            unscored_papers_df = pd.DataFrame(papers_without_scores) if papers_without_scores else pd.DataFrame()

            # Score the papers that don't have scores yet
            if not unscored_papers_df.empty:
                if self.verbose:
                    print(f"🧠 Running LLM judge on {len(unscored_papers_df)} unscored papers...")
                newly_scored_df = self.rank_papers(unscored_papers_df, progress_callback=progress_callback)
            else:
                if self.verbose:
                    print("⏭️ No new papers required judge inference; reusing historical scores from the database.")
                newly_scored_df = pd.DataFrame()

            # Combine all papers
            if not scored_papers_df.empty and not newly_scored_df.empty:
                combined_df = pd.concat([scored_papers_df, newly_scored_df], ignore_index=True)
            elif not scored_papers_df.empty:
                combined_df = scored_papers_df
            elif not newly_scored_df.empty:
                combined_df = newly_scored_df
            else:
                combined_df = pd.DataFrame()

            if combined_df.empty:
                if self.verbose:
                    print("⚠️ No papers available after scoring")
                if return_all_scored:
                    return pd.DataFrame(), pd.DataFrame()
                return pd.DataFrame()

            # Sort by score
            combined_df = combined_df.sort_values(by='score', ascending=False)

            # Get more papers than needed to allow for PDF conversion failures
            backup_multiplier = 2
            extended_count = min(len(combined_df), self.top_n * backup_multiplier)
            top_n_df = combined_df.head(extended_count)

            if self.verbose:
                print(f"✅ Final ranking complete:")
                print(f"   Total papers ranked: {len(combined_df)}")
                print(f"   Papers with historical scores: {len(papers_with_scores)}")
                print(f"   Papers newly scored: {len(newly_scored_df) if not newly_scored_df.empty else 0}")
                print(f"   Top papers selected: {len(top_n_df)} (target: {self.top_n})")
                if len(top_n_df) > 0:
                    print(f"   Score range: {top_n_df['score'].min():.1f} - {top_n_df['score'].max():.1f}")
                if return_all_scored:
                    print(f"   Returning all {len(combined_df)} scored papers for profile saving")

            # Return both limited and full results if requested (for profile scoring)
            if return_all_scored:
                return top_n_df, combined_df

            return top_n_df
            
        except Exception as e:
            # Surface the underlying error so the caller's traceback isn't the only signal —
            # otherwise a bad fallback shape masks the real failure (e.g. caller unpacks
            # `top_n_df, all_scored_df` and sees only "too many values to unpack").
            print(f"Error in optimized ranking: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to original ranking method. Honor `return_all_scored` so the caller's
            # 2-tuple unpack still works — the fallback's `top_n_df` doubles as "all scored"
            # since we don't have a separate "all" set without re-running the full pipeline.
            fallback_df = self.rank_papers(data_df, progress_callback=progress_callback)
            if return_all_scored:
                return fallback_df, fallback_df
            return fallback_df

    async def rank_papers_async(self, data_df):
        """Async wrapper for rank_papers that supports both single and multi-server modes."""
        if self.use_multi_server_judge:
            return await self._rank_papers_multi_server(data_df)
        else:
            # Run sync rank_papers in thread pool to avoid blocking
            return await asyncio.to_thread(self._rank_papers_single_server, data_df)

    async def _rank_papers_multi_server(self, data_df):
        """Rank papers using multi-server worker pool."""
        from theseus_insight.data_processing.newsletter_scorer import NewsletterScorer

        if self.verbose:
            print(f"\n🚀 MULTI-SERVER JUDGE SCORING")
            print(f"Total papers to score: {len(data_df)}")
            print(f"Using {len(self.judge_server_ids)} inference servers")
            print("="*60)

        # Prepare papers for scoring
        papers = []
        for idx, row in data_df.iterrows():
            papers.append({
                'id': row.get('id'),  # Assuming paper has ID from database
                'title': row.get('title', ''),
                'abstract': row.get('abstract', '')
            })

        # Create newsletter scorer
        scorer = NewsletterScorer(self.orchestration_config)

        # Progress callback
        SCORING_STAGE_START = 20.0
        SCORING_STAGE_END = 30.0

        def progress_callback(status, progress, message=None, metadata=None):
            status_for_callback = status
            adjusted_progress = progress
            metadata_payload = dict(metadata) if isinstance(metadata, dict) else metadata

            if status == 'scoring':
                status_for_callback = 'rank'
                adjusted_progress = SCORING_STAGE_START + (progress / 100.0) * (SCORING_STAGE_END - SCORING_STAGE_START)

            if self.verbose:
                print(
                    f"Scoring progress: raw={progress:.1f}% "
                    f"(overall {adjusted_progress:.1f}% between {SCORING_STAGE_START}-{SCORING_STAGE_END})"
                )

            if isinstance(metadata, dict):
                metadata_payload = dict(metadata)
                metadata_payload['scoring_progress_pct'] = progress
                metadata_payload['overall_progress_pct'] = adjusted_progress

            # Forward to main progress callback if available
            print(f"[DEBUG] progress_callback called: status={status_for_callback}, progress={adjusted_progress}, has_callback={self.progress_callback is not None}")
            if self.progress_callback:
                print(f"[DEBUG] Calling self.progress_callback with metadata: {metadata_payload is not None}")
                try:
                    # If main callback accepts metadata
                    self.progress_callback(status_for_callback, adjusted_progress, message, metadata_payload)
                    print(f"[DEBUG] progress_callback succeeded")
                except TypeError as e:
                    # Fallback for simpler signature
                    print(f"[DEBUG] TypeError in progress_callback, falling back to 2-arg signature: {e}")
                    try:
                        self.progress_callback(status_for_callback, adjusted_progress)
                    except Exception as e2:
                        print(f"[ERROR] Failed to call progress_callback with fallback: {type(e2).__name__}: {e2}")
                        import traceback
                        traceback.print_exc()
                except Exception as e:
                    print(f"[ERROR] Failed to call progress_callback: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[DEBUG] No self.progress_callback set!")

        # Score papers using multi-server worker pool
        # Uses profile-specific scoring like bulk judge, then aggregates across profiles
        results = await scorer.score_papers_multi_server(
            job_id=self.newsletter_job_id,
            papers=papers,
            profile_ids=self.profile_ids_override or [],
            server_ids=self.judge_server_ids,
            progress_callback=progress_callback,
            request_timeout_sec=self.judge_request_timeout_sec,
            max_retries=self.judge_max_retries
        )

        # Convert results back to DataFrame format
        # Create a mapping from paper_id to scores
        score_map = {}
        for result in results:
            score_map[result['paper_id']] = {
                'score': result.get('score', 1),
                'related': result.get('related', False),
                'rationale': result.get('rationale', 'No rationale provided')
            }

        # Add scores to dataframe
        scores, related, rationale = [], [], []
        for idx, row in data_df.iterrows():
            paper_id = row.get('id')
            if paper_id in score_map:
                scores.append(score_map[paper_id]['score'])
                related.append(score_map[paper_id]['related'])
                rationale.append(score_map[paper_id]['rationale'])
            else:
                # Paper not scored (failed) - use defaults
                scores.append(1)
                related.append(False)
                rationale.append('Failed to score')

        data_df['score'] = scores
        data_df['related'] = related
        data_df['rationale'] = rationale
        data_df = data_df.sort_values(by='score', ascending=False)

        # Get more papers than needed to allow for PDF conversion failures
        backup_multiplier = 2
        extended_count = min(len(data_df), self.top_n * backup_multiplier)
        top_n_df = data_df.head(extended_count)

        if self.verbose:
            print(f"✅ Multi-server scoring complete:")
            print(f"   Total papers scored: {len(results)}")
            print(f"   Top papers selected: {len(top_n_df)} (target: {self.top_n})")
            if len(top_n_df) > 0:
                print(f"   Score range: {top_n_df['score'].min():.1f} - {top_n_df['score'].max():.1f}")

        return top_n_df

    def rank_papers(self, data_df, progress_callback=None):
        """Given embedded papers, use judge model to score them (single-server mode)."""
        # If multi-server mode is enabled, delegate to async version
        if self.use_multi_server_judge:
            # Check if we're already in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're inside an event loop - use asyncio.create_task or run in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._rank_papers_multi_server(data_df))
                    return future.result()
            except RuntimeError:
                # Not in an event loop - safe to create one
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                return loop.run_until_complete(self._rank_papers_multi_server(data_df))
        else:
            return self._rank_papers_single_server(data_df, progress_callback=progress_callback)

    def _rank_papers_single_server(self, data_df, progress_callback=None):
        """Single-server sequential scoring (original implementation)."""
        try:
            progress_callback = progress_callback or self.progress_callback
            abstracts = list(data_df['abstract'])
            scores, related, rationale = [], [], []
            failed_papers = []
            consecutive_failures = 0
            
            # Check for partial checkpoint
            partial_checkpoint = self._load_checkpoint('ranking_partial')
            start_index = 0
            if partial_checkpoint is not None:
                scores = partial_checkpoint.get('scores', [])
                related = partial_checkpoint.get('related', [])
                rationale = partial_checkpoint.get('rationale', [])
                failed_papers = partial_checkpoint.get('failed_papers', [])
                start_index = len(scores)
                if self.verbose:
                    print(f"Resuming ranking from paper {start_index + 1}/{len(abstracts)}")
            
            total_papers = len(abstracts)

            def emit_rank_progress(processed_count: int, in_progress_count: int = 0):
                if not progress_callback:
                    return

                successful_count = max(processed_count - len(failed_papers), 0)
                pending_count = max(total_papers - processed_count - in_progress_count, 0)
                progress_pct = 20 + (processed_count / total_papers) * 30 if total_papers > 0 else 30
                current_paper_num = min(processed_count + in_progress_count, total_papers)
                message = (
                    f"Ranking paper {current_paper_num}/{total_papers}"
                    if total_papers > 0 else
                    "Ranking papers"
                )
                scoring_summary = {
                    "completed": successful_count,
                    "failed": len(failed_papers),
                    "pending": pending_count,
                    "in_progress": in_progress_count,
                    "total": total_papers,
                    "pending_plus_in_progress": pending_count + in_progress_count,
                }
                metadata = {
                    "papers_to_score": total_papers,
                    "papers_total": total_papers,
                    "papers_scored": successful_count,
                    "papers_failed": len(failed_papers),
                    "papers_pending": pending_count,
                    "papers_in_progress": in_progress_count,
                    "scoring_summary": scoring_summary,
                }

                try:
                    progress_callback("rank", progress_pct, message, metadata)
                except TypeError:
                    progress_callback("rank", progress_pct, message)
            
            for i, abstract in enumerate(tqdm(abstracts[start_index:], 
                                            disable=not self.verbose, 
                                            desc="Ranking papers",
                                            initial=start_index, 
                                            total=len(abstracts))):
                actual_index = start_index + i
                
                # Progress update
                emit_rank_progress(processed_count=actual_index, in_progress_count=1)

                success = False
                attempts = 0
                max_attempts = 3
                
                while not success and attempts < max_attempts:
                    attempts += 1
                    try:
                        # Clear cache on second attempt if using Ollama
                        if attempts == 2 and consecutive_failures > 2:
                            self._clear_judge_model_cache()
                            
                        messages = [
                            {"role": "user", "content": research_prompt(self.research_interests, abstract)}
                        ]
                        
                        if self.judge_inference.provider == "ollama":
                            response = self.judge_inference.invoke(
                                messages=messages,
                                system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT,
                                schema=ResearchInterestsPromptData
                            )
                        else:
                            # E.g. Anthropic or OpenAI
                            response = self.judge_inference.invoke(
                                messages=messages,
                                system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT
                            )

                        # Parse and validate JSON response
                        try:
                            response_json = json_repair.loads(response)
                            
                            # Ensure response_json is a dictionary
                            if not isinstance(response_json, dict):
                                if self.verbose:
                                    print(f"Paper ranking expected dict, got {type(response_json)} for paper {actual_index+1}, attempt {attempts}")
                                    print(f"Raw response: {response[:200]}...")
                                if attempts == max_attempts:
                                    raise TypeError(f"Expected dict from JSON parsing, got {type(response_json)}")
                                continue
                                
                        except Exception as json_error:
                            if self.verbose:
                                print(f"JSON parsing failed for paper {actual_index+1}, attempt {attempts}: {json_error}")
                                print(f"Raw response: {response[:200]}...")
                            if attempts == max_attempts:
                                raise json_error
                            continue
                        
                        # Validate required keys exist
                        required_keys = ['score', 'related', 'rationale']
                        missing_keys = [key for key in required_keys if key not in response_json]
                        
                        if missing_keys:
                            if self.verbose:
                                print(f"Missing keys {missing_keys} for paper {actual_index+1}, attempt {attempts}")
                                print(f"Response JSON: {response_json}")
                            if attempts == max_attempts:
                                raise KeyError(f"Missing required keys in response: {missing_keys}")
                            continue
                        
                        # Validate and convert values
                        try:
                            score_val = int(response_json['score'])
                            related_val = bool(response_json['related'])
                            rationale_val = str(response_json['rationale'])
                            
                            # Validate score range
                            if not (1 <= score_val <= 10):
                                if self.verbose:
                                    print(f"Invalid score {score_val} for paper {actual_index+1}, attempt {attempts}")
                                if attempts == max_attempts:
                                    score_val = max(1, min(10, score_val))  # Clamp to valid range
                                else:
                                    continue
                            
                            scores.append(score_val)
                            related.append(related_val)
                            rationale.append(rationale_val)
                            success = True
                            consecutive_failures = 0  # Reset counter on success
                            
                        except (ValueError, TypeError) as conversion_error:
                            if self.verbose:
                                print(f"Value conversion failed for paper {actual_index+1}, attempt {attempts}: {conversion_error}")
                                print(f"Response JSON: {response_json}")
                            if attempts == max_attempts:
                                raise conversion_error
                            continue
                            
                    except Exception as e:
                        if self.verbose:
                            print(f"Error processing paper {actual_index+1}, attempt {attempts}: {e}")
                        
                        # Check if this is an LM Studio error - verify model and retry with longer delay
                        provider = getattr(self.judge_inference, 'provider', None)
                        error_str = str(e).lower()
                        is_lmstudio_error = provider == "lmstudio" and (
                            "lm studio" in error_str or 
                            "inference" in error_str or
                            "websocket" in error_str or
                            error_str.strip() == "" or  # Empty error message
                            ": ." in str(e)  # LMStudio SDK empty error pattern
                        )
                        
                        if is_lmstudio_error and attempts < max_attempts:
                            if self.verbose:
                                print(f"LM Studio error detected, verifying model availability...")
                            self._clear_judge_model_cache()  # This verifies LM Studio model
                            time.sleep(3)  # Longer delay for LM Studio recovery
                            continue
                        
                        if attempts == max_attempts:
                            # Use default values for failed paper
                            if self.verbose:
                                print(f"Using default values for failed paper {actual_index+1}")
                            scores.append(1)  # Default low score
                            related.append(False)  # Default not related
                            rationale.append(f"Failed to process: {str(e)[:100]}")
                            failed_papers.append(actual_index)
                            consecutive_failures += 1
                            success = True
                        else:
                            # Add small delay before retry
                            time.sleep(1)

                emit_rank_progress(processed_count=len(scores), in_progress_count=0)

                # Save partial progress every 50 papers
                if (actual_index + 1) % 50 == 0:
                    partial_data = {
                        'scores': scores,
                        'related': related,
                        'rationale': rationale,
                        'failed_papers': failed_papers
                    }
                    self._save_checkpoint('ranking_partial', partial_data)

            if failed_papers and self.verbose:
                print(f"Warning: {len(failed_papers)} papers failed processing and received default scores")
                
            data_df['score'] = scores
            data_df['related'] = related
            data_df['rationale'] = rationale
            data_df = data_df.sort_values(by='score', ascending=False)
            
            # Get more papers than needed to allow for PDF conversion failures
            # We'll take 2x the requested amount as backup
            backup_multiplier = 2
            extended_count = min(len(data_df), self.top_n * backup_multiplier)
            top_n_df = data_df.head(extended_count)
            
            if self.verbose:
                print(f"Selected top {extended_count} papers (target: {self.top_n}) to allow for PDF conversion failures")

            if self.db_saving:
                print("Saving LLM judge scores to paper_profile_scores table")
                # Save scores to paper_profile_scores for each selected profile
                updated_count = 0
                new_count = 0

                # Get the model name for judge_model field
                judge_model_name = getattr(self.judge_inference, 'model_name', 'unknown')

                for _, row in data_df.iterrows():
                    # Check if paper already exists
                    existing_paper = PaperRepository.get_by_url(row['pdf_url'])

                    if existing_paper:
                        # Save scores to paper_profile_scores for each selected profile
                        try:
                            from .db import get_cursor
                            with get_cursor() as cur:
                                # Update date_run in papers table
                                cur.execute("""
                                    UPDATE papers
                                    SET date_run = %s
                                    WHERE url = %s
                                """, (
                                    TODAY.strftime('%Y-%m-%d'),
                                    row['pdf_url']
                                ))

                                # Write scores to paper_profile_scores for each profile
                                profile_ids = self.profile_ids_override or []
                                if not profile_ids:
                                    print("Warning: No profiles selected for newsletter - scores will not be saved")
                                    continue

                                for profile_id in profile_ids:
                                    cur.execute("""
                                        INSERT INTO paper_profile_scores
                                            (paper_id, profile_id, score, related, rationale, judge_model, date_scored)
                                        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                                        ON CONFLICT (paper_id, profile_id)
                                        DO UPDATE SET
                                            score = EXCLUDED.score,
                                            related = EXCLUDED.related,
                                            rationale = EXCLUDED.rationale,
                                            judge_model = EXCLUDED.judge_model,
                                            date_scored = CURRENT_TIMESTAMP
                                    """, (
                                        existing_paper['id'],
                                        profile_id,
                                        row['score'],
                                        row['related'],
                                        row['rationale'],
                                        judge_model_name
                                    ))
                            updated_count += 1
                            
                            # Extract and update keywords
                            try:
                                extractor = getattr(self, '_yake_extractor', None)
                                if extractor is None:
                                    extractor = yake.KeywordExtractor(lan="en", n=1, top=5)
                                    self._yake_extractor = extractor
                                text_kw = f"{row['title']} {row['abstract']}"
                                kw_scores = extractor.extract_keywords(text_kw)
                                keywords = [w for w, _ in kw_scores]
                                if keywords:
                                    PaperRepository.update_keywords(existing_paper['id'], keywords)
                            except Exception:
                                pass
                        except Exception as e:
                            if self.verbose:
                                print(f"Failed to update paper {row['title']}: {e}")
                    else:
                        # Paper doesn't exist yet (shouldn't happen with new flow, but handle gracefully)
                        embedding = row['abstract_embedding']
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
                            score=None,  # Scores are now stored in paper_profile_scores
                            related=None,
                            rationale=None,
                            cosine_similarity=row['cosine_similarity'],
                            embedding_model=self.embedding_model_name,
                            embedding=embedding
                        )

                        was_inserted = PaperRepository.insert_paper(paper, skip_duplicates=True)
                        if was_inserted:
                            new_count += 1

                            # Get the inserted paper to get its ID
                            inserted_paper = PaperRepository.get_by_url(row['pdf_url'])
                            if inserted_paper:
                                # Save scores to paper_profile_scores for each profile
                                try:
                                    from .db import get_cursor
                                    with get_cursor() as cur:
                                        profile_ids = self.profile_ids_override or []
                                        for profile_id in profile_ids:
                                            cur.execute("""
                                                INSERT INTO paper_profile_scores
                                                    (paper_id, profile_id, score, related, rationale, judge_model, date_scored)
                                                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                                                ON CONFLICT (paper_id, profile_id)
                                                DO UPDATE SET
                                                    score = EXCLUDED.score,
                                                    related = EXCLUDED.related,
                                                    rationale = EXCLUDED.rationale,
                                                    judge_model = EXCLUDED.judge_model,
                                                    date_scored = CURRENT_TIMESTAMP
                                            """, (
                                                inserted_paper.id,
                                                profile_id,
                                                row['score'],
                                                row['related'],
                                                row['rationale'],
                                                judge_model_name
                                            ))
                                except Exception as e:
                                    if self.verbose:
                                        print(f"Failed to save scores for paper {row['title']}: {e}")

                            # Extract and cache keywords
                            try:
                                extractor = getattr(self, '_yake_extractor', None)
                                if extractor is None:
                                    extractor = yake.KeywordExtractor(lan="en", n=1, top=5)
                                    self._yake_extractor = extractor
                                text_kw = f"{row['title']} {row['abstract']}"
                                kw_scores = extractor.extract_keywords(text_kw)
                                keywords = [w for w, _ in kw_scores]
                                if inserted_paper and keywords:
                                    PaperRepository.update_keywords(inserted_paper.id, keywords)
                            except Exception:
                                pass
                
                if self.verbose:
                    profile_count = len(self.profile_ids_override) if self.profile_ids_override else 0
                    total_scores = (updated_count + new_count) * profile_count
                    print(f"Database update complete: Saved {total_scores} scores ({updated_count} existing + {new_count} new papers × {profile_count} profiles) to paper_profile_scores")
       
            # Clean up partial checkpoint on success
            partial_checkpoint_path = os.path.join(self.checkpoint_dir, 'ranking_partial_checkpoint.pkl')
            if os.path.exists(partial_checkpoint_path):
                os.remove(partial_checkpoint_path)
                
            return top_n_df
        except Exception as e:
            self._log_error(500, e)
            raise

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
            # Stage 1: Download Papers
            # -----------
            if progress_callback:
                progress_callback("download", 0, "Starting paper download", {"papers_discovered": 0})
                
            if not start_from:
                # no stage specified, do we have an existing checkpoint for 'papers_downloaded'?
                data_df = self._load_checkpoint('papers_downloaded')
                if self.verbose:
                    if data_df is None:
                        print("No 'papers_downloaded' checkpoint. Starting fresh: downloading papers.")
                    else:
                        print(f"⚠️ DEBUG: Loaded 'papers_downloaded' checkpoint with {len(data_df) if hasattr(data_df, '__len__') else 'unknown'} papers")
                
                if data_df is None:
                    process_data = ArxivDataProcessor(start_date=self.start_date, end_date=self.end_date)
                    data_df = process_data.download_and_process_data()
                    
                    # Check if no papers were found and handle gracefully
                    if data_df.empty:
                        self._handle_no_papers_found()
                        return  # Exit early since there's nothing to process
                    
                    self._save_checkpoint('papers_downloaded', data_df)
            else:
                # If we have a forced stage, see if the user wants to skip some
                if start_from == 'papers_downloaded':
                    data_df = self._load_checkpoint('papers_downloaded')
                    if data_df is None:
                        if self.verbose:
                            print("Forcing download stage.")
                        process_data = ArxivDataProcessor(start_date=self.start_date, end_date=self.end_date)
                        data_df = process_data.download_and_process_data()
                        
                        # Check if no papers were found and handle gracefully
                        if data_df.empty:
                            self._handle_no_papers_found()
                            return  # Exit early since there's nothing to process
                        
                        self._save_checkpoint('papers_downloaded', data_df)

            if progress_callback:
                progress_callback("download", 10, "Paper download complete", {"papers_discovered": len(data_df)})

            # -----------
            # Stage 2: Embed Papers
            # -----------
            if start_from is None or start_from in ['papers_downloaded', 'papers_embedded']:
                embedded_df = self._load_checkpoint('papers_embedded')
                if embedded_df is None:
                    if data_df is None:
                        data_df = self._load_checkpoint('papers_downloaded')
                        if data_df is None:
                            raise ValueError("No downloaded papers found to embed.")
                    
                    # Check if we have an empty DataFrame from the download stage
                    if data_df.empty:
                        if self.verbose:
                            print("No papers to embed (empty DataFrame from download stage)")
                        # Create empty embedded DataFrame and continue
                        embedded_df = data_df.copy()
                        embedded_df['cosine_similarity'] = []
                        embedded_df['abstract_embedding'] = []
                        self._save_checkpoint('papers_embedded', embedded_df)
                    else:
                        if progress_callback:
                            progress_callback("embed", 11, "Starting paper embedding")
                            
                        if self.verbose:
                            print("Embedding papers...")

                        # Check for existing papers to avoid unnecessary processing
                        if self.db_saving:
                            # Extract all URLs for bulk checking
                            all_urls = [row['pdf_url'] for _, row in data_df.iterrows()]
                            
                            # Use optimized bulk existence checking
                            existing_urls_set, _ = PaperRepository.bulk_check_existence(urls=all_urls)
                            
                            # Create mask for new papers
                            new_papers_mask = []
                            existing_urls = []
                            for _, row in data_df.iterrows():
                                url = row['pdf_url']
                                if url in existing_urls_set:
                                    existing_urls.append(url)
                                    new_papers_mask.append(False)
                                else:
                                    new_papers_mask.append(True)
                            
                            if existing_urls and self.verbose:
                                print(f"Found {len(existing_urls)} papers already in database, will skip embedding for those")
                                
                            # Filter to only new papers for embedding
                            new_papers_df = data_df[new_papers_mask].reset_index(drop=True)
                            
                            if len(new_papers_df) == 0:
                                if self.verbose:
                                    print("All papers already exist in database - loading existing papers for newsletter generation")
                                
                                # Load existing papers from database instead of exiting
                                # Get papers from the same date range that were downloaded
                                
                                existing_papers_list = []
                                for _, row in data_df.iterrows():
                                    existing_paper = PaperRepository.get_by_url(row['pdf_url'])
                                    if existing_paper:
                                        # Convert database row to expected format
                                        paper_data = {
                                            'id': existing_paper.get('id'),  # Include database ID for multi-server scoring
                                            'title': existing_paper['title'],
                                            'abstract': existing_paper['abstract'],
                                            'pdf_url': existing_paper['url'],
                                            'date': existing_paper['date'],
                                            'cosine_similarity': existing_paper.get('cosine_similarity', 0.0),
                                            'abstract_embedding': existing_paper.get('embedding', [])
                                        }
                                        existing_papers_list.append(paper_data)
                                
                                if existing_papers_list:
                                    # Create DataFrame from existing papers
                                    filtered_df = pd.DataFrame(existing_papers_list)
                                    if self.verbose:
                                        print(f"✅ Loaded {len(filtered_df)} existing papers for newsletter generation")
                                else:
                                    # Still no papers - this shouldn't happen but handle gracefully
                                    if self.verbose:
                                        print("No existing papers found in database")
                                    self._handle_no_papers_found(reason="all_duplicates")
                                    return
                            else:
                                # Process only new papers
                                abstracts = list(new_papers_df['abstract'])
                                abstract_embeddings = []
                                cosine_similarities = []
                                reserch_embedding = self.embedding_model.invoke(self.research_interests)

                                for abstract in tqdm(abstracts, disable=not self.verbose, desc="Embedding abstracts"):
                                    abstract_embedding = self.embedding_model.invoke(abstract, show_progress_bar=False)
                                    sim = cosine_similarity(abstract_embedding, reserch_embedding)
                                    cosine_similarities.append(sim)
                                    abstract_embeddings.append(abstract_embedding)

                                new_papers_df['cosine_similarity'] = cosine_similarities
                                new_papers_df['abstract_embedding'] = abstract_embeddings

                                # Save ALL embedded papers to database first (before filtering)
                                if self.db_saving:
                                    if self.verbose:
                                        print(f"Saving {len(new_papers_df)} papers to database (before filtering)...")
                                    saved_count = 0
                                    paper_ids = []
                                    for idx, row in tqdm(new_papers_df.iterrows(), total=len(new_papers_df), 
                                                      desc="Saving papers to DB", disable=not self.verbose):
                                        embedding = row['abstract_embedding']
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
                                            score=0.0,  # Not yet scored by LLM
                                            related=False,  # Not yet scored
                                            rationale='Not yet scored by LLM',
                                            cosine_similarity=row['cosine_similarity'],
                                            embedding_model=self.embedding_model_name,
                                            embedding=embedding
                                        )
                                        
                                        was_inserted = PaperRepository.insert_paper(paper, skip_duplicates=True)
                                        if was_inserted:
                                            saved_count += 1
                                        
                                        # Get the paper ID from database (whether newly inserted or existing)
                                        existing_paper = PaperRepository.get_by_url(row['pdf_url'])
                                        if existing_paper:
                                            paper_ids.append(existing_paper['id'])
                                        else:
                                            paper_ids.append(None)
                                    
                                    # Add IDs to dataframe for multi-server scoring
                                    new_papers_df['id'] = paper_ids
                                    
                                    if self.verbose:
                                        print(f"✅ Saved {saved_count} new papers to database")
                                        print(f"✅ Retrieved {len([pid for pid in paper_ids if pid is not None])} paper IDs for scoring")

                                # Filter by threshold for LLM scoring and newsletter generation
                                filtered_df = new_papers_df[new_papers_df['cosine_similarity'] >= self.cosine_similarity_threshold]
                                filtered_df = filtered_df.reset_index(drop=True)
                                
                                # Check if no papers meet the threshold criteria
                                if len(filtered_df) == 0:
                                    if self.verbose:
                                        print(f"No new papers meet the cosine similarity threshold ({self.cosine_similarity_threshold})")
                                        print("Loading existing papers from database for newsletter generation...")
                                    
                                    # Load existing papers from database instead of exiting
                                    existing_papers = PaperRepository.get_papers_in_date_range(
                                        start_date=self.start_date.strftime('%Y-%m-%d'),
                                        end_date=self.end_date.strftime('%Y-%m-%d')
                                    )
                                    
                                    if existing_papers:
                                        # Convert to DataFrame format expected by newsletter generation
                                        papers_list = []
                                        for paper in existing_papers:
                                            papers_list.append({
                                                'id': paper.get('id'),  # Include database ID for multi-server scoring
                                                'title': paper['title'],
                                                'abstract': paper['abstract'],
                                                'pdf_url': paper['url'],
                                                'date': paper['date'],
                                                'cosine_similarity': paper.get('cosine_similarity', 0.0),
                                                'abstract_embedding': paper.get('embedding', [])
                                            })
                                        
                                        filtered_df = pd.DataFrame(papers_list)
                                        if self.verbose:
                                            print(f"✅ Loaded {len(filtered_df)} existing papers for newsletter generation")
                                    else:
                                        # No existing papers found - this is the real "no papers" case
                                        if self.verbose:
                                            print("No existing papers found in database for date range")
                                        self._handle_no_papers_found(reason="threshold_not_met")
                                        return
                        else:
                            # Original behavior when not saving to DB
                            abstracts = list(data_df['abstract'])
                            abstract_embeddings = []
                            cosine_similarities = []
                            reserch_embedding = self.embedding_model.invoke(self.research_interests)

                            for abstract in tqdm(abstracts, disable=not self.verbose, desc="Embedding abstracts"):
                                abstract_embedding = self.embedding_model.invoke(abstract, show_progress_bar=False)
                                sim = cosine_similarity(abstract_embedding, reserch_embedding)
                                cosine_similarities.append(sim)
                                abstract_embeddings.append(abstract_embedding)

                            data_df['cosine_similarity'] = cosine_similarities
                            data_df['abstract_embedding'] = abstract_embeddings

                            # Note: When not saving to DB, we can only work with papers in memory
                            # Filter by threshold for processing
                            filtered_df = data_df[data_df['cosine_similarity'] >= self.cosine_similarity_threshold]
                            filtered_df = filtered_df.reset_index(drop=True)
                            
                            # Check if no papers meet the threshold criteria
                            if len(filtered_df) == 0:
                                if self.verbose:
                                    print(f"No new papers meet the cosine similarity threshold ({self.cosine_similarity_threshold})")
                                    print("Loading existing papers from database for newsletter generation...")
                                
                                # Load existing papers from database instead of exiting
                                existing_papers = PaperRepository.get_papers_in_date_range(
                                    start_date=self.start_date.strftime('%Y-%m-%d'),
                                    end_date=self.end_date.strftime('%Y-%m-%d')
                                )
                                
                                if existing_papers:
                                    # Convert to DataFrame format expected by newsletter generation
                                    papers_list = []
                                    for paper in existing_papers:
                                        papers_list.append({
                                            'title': paper['title'],
                                            'abstract': paper['abstract'],
                                            'pdf_url': paper['url'],
                                            'date': paper['date'],
                                            'cosine_similarity': paper.get('cosine_similarity', 0.0),
                                            'abstract_embedding': paper.get('embedding', [])
                                        })
                                    
                                    filtered_df = pd.DataFrame(papers_list)
                                    if self.verbose:
                                        print(f"✅ Loaded {len(filtered_df)} existing papers for newsletter generation")
                                else:
                                    # No existing papers found - this is the real "no papers" case
                                    if self.verbose:
                                        print("No existing papers found in database for date range")
                                    self._handle_no_papers_found(reason="threshold_not_met")
                                    return
                        
                        # Ensure filtered_df is always defined (safety check)
                        if 'filtered_df' not in locals():
                            if self.verbose:
                                print("Warning: filtered_df was not defined, creating empty dataframe")
                            filtered_df = data_df.iloc[0:0].copy()  # Empty dataframe with same columns
                            filtered_df['cosine_similarity'] = []
                            filtered_df['abstract_embedding'] = []
                        
                        # Save checkpoint
                        await self._save_checkpoint_async('papers_embedded', filtered_df)
                        embedded_df = filtered_df

            if progress_callback:
                progress_callback("embed", 15, "Paper embedding complete")

            # -----------
            # Stage 3: Rank Papers (or Get Profile Papers)
            # -----------
            if progress_callback:
                progress_callback("rank", 20, "Starting paper ranking")

            if start_from is None or start_from in ['papers_embedded', 'papers_ranked']:
                top_n_df = await self._load_checkpoint_async('papers_ranked')
                if top_n_df is None:
                    # Check if we should use profile-based paper scoring
                    if self.profile_ids_override:
                        if self.verbose:
                            print(f"Profile newsletter generation for profiles: {self.profile_ids_override}")
                            print("Using freshly downloaded papers and scoring for profile...")
                        top_n_df = self.get_and_score_profile_papers(
                            profile_ids=self.profile_ids_override,
                            embedded_df=embedded_df,
                            progress_callback=progress_callback
                        )
                    else:
                        # Use traditional embedding-based approach
                        if embedded_df is None:
                            embedded_df = self._load_checkpoint('papers_embedded')
                            if embedded_df is None:
                                raise ValueError("No embedded papers found to rank.")
                        
                        # Check if we have any papers to rank
                        if len(embedded_df) == 0:
                            if self.verbose:
                                print("No new papers to rank (all papers already exist in database)")
                                print("Loading existing papers from database for newsletter generation...")
                            
                            # Load existing papers from database within date range for newsletter generation
                            existing_papers = PaperRepository.get_papers_in_date_range(
                                start_date=self.start_date.strftime('%Y-%m-%d'),
                                end_date=self.end_date.strftime('%Y-%m-%d')
                            )
                            
                            if existing_papers:
                                # Convert to DataFrame format expected by newsletter generation
                                papers_list = []
                                for paper in existing_papers:
                                    papers_list.append({
                                        'title': paper['title'],
                                        'abstract': paper['abstract'],
                                        'pdf_url': paper['url'],
                                        'date': paper['date'],
                                        'score': paper.get('score', 5.0),  # Use existing score or default
                                        'related': paper.get('related', True),
                                        'rationale': paper.get('rationale', 'Previously scored paper'),
                                        'cosine_similarity': paper.get('cosine_similarity', 0.0),
                                        'abstract_embedding': paper.get('embedding', [])
                                    })
                                
                                df = pd.DataFrame(papers_list)
                                # Sort by score if available, otherwise by date
                                if 'score' in df.columns:
                                    df = df.sort_values('score', ascending=False)
                                else:
                                    df = df.sort_values('date', ascending=False)
                                
                                # Get more papers than needed to allow for PDF conversion failures
                                backup_multiplier = 2
                                extended_count = min(len(df), self.top_n * backup_multiplier)
                                top_n_df = df.head(extended_count)
                                
                                if self.verbose:
                                    print(f"✅ Loaded {len(top_n_df)} existing papers for newsletter generation")
                            else:
                                # No papers found in database for date range
                                top_n_df = embedded_df.copy()  # Empty dataframe with same structure
                                if self.verbose:
                                    print("No existing papers found in database for date range")
                        else:
                            if self.verbose:
                                print("Ranking papers...")
                            top_n_df = self.rank_papers_with_historical_scores(embedded_df, progress_callback=progress_callback)

                    # Only checkpoint a non-empty result. Persisting an empty df here
                    # would poison subsequent retries: load_checkpoint returns the
                    # (empty) df, the `if top_n_df is None` guard sees a non-None
                    # value, and the whole scoring stage gets skipped.
                    if top_n_df is not None and len(top_n_df) > 0:
                        await self._save_checkpoint_async('papers_ranked', top_n_df)
                    elif self.verbose:
                        print("Skipping papers_ranked checkpoint (empty result — retry will re-attempt scoring)")

                # free memory from embeddings if needed
                del embedded_df
                gc.collect()
            if progress_callback:
                progress_callback("rank", 30, "Paper ranking complete")

            # -----------
            # Stage 4: Generate Newsletter Sections
            # -----------
            if progress_callback:
                progress_callback("newsletter", 40, "Starting newsletter sections generation")
            if start_from is None or start_from in ['papers_ranked', 'newsletter_sections']:
                sections_data = await self._load_checkpoint_async('newsletter_sections')
                if sections_data is None:
                    if top_n_df is None:
                        top_n_df = await self._load_checkpoint_async('papers_ranked')
                        if top_n_df is None:
                            raise ValueError("No ranked papers found to generate newsletter sections.")

                    # Check if we have any papers to process
                    if len(top_n_df) == 0:
                        if self.verbose:
                            print("No papers available for newsletter generation (none met criteria)")
                        sections_data = {
                            'sections': [],
                            'urls_and_titles': []
                        }
                        await self._save_checkpoint_async('newsletter_sections', sections_data)
                    else:
                        if self.verbose:
                            print("Generating newsletter sections (paper-by-paper) ...")

                        sections = []
                        urls_and_titles = []
                        successful_sections = 0
                        target_sections = self.top_n
                        papers_processed = 0
                        candidate_rows = [row.to_dict() for _, row in top_n_df.iterrows()]

                        if self.verbose:
                            print(f"Processing papers to generate {target_sections} newsletter sections...")
                            print(f"Available papers: {len(top_n_df)}")
                            print(
                                f"✅ Docling -> MarkItDown parser fallback enabled "
                                f"(parse timeout: {self.pdf_conversion_timeout_sec}s, "
                                f"download workers: {self.pdf_download_max_workers})"
                            )

                        with tqdm(total=len(candidate_rows), desc="Sections") as section_progress:
                            download_executor = cf.ThreadPoolExecutor(
                                max_workers=min(self.pdf_download_max_workers, len(candidate_rows))
                            )
                            download_futures: dict[cf.Future, dict] = {}
                            processed_futures = set()
                            next_candidate_index = 0

                            def submit_next_download():
                                nonlocal next_candidate_index
                                if next_candidate_index >= len(candidate_rows):
                                    return
                                row = candidate_rows[next_candidate_index]
                                next_candidate_index += 1
                                future = download_executor.submit(self._download_pdf_to_temp_file, row['pdf_url'])
                                download_futures[future] = row

                            try:
                                for _ in range(min(self.pdf_download_max_workers, len(candidate_rows))):
                                    submit_next_download()

                                while download_futures and successful_sections < target_sections:
                                    done, _ = cf.wait(
                                        list(download_futures.keys()),
                                        return_when=cf.FIRST_COMPLETED,
                                    )

                                    for future in done:
                                        if successful_sections >= target_sections:
                                            break
                                        row = download_futures.pop(future)
                                        processed_futures.add(future)
                                        papers_processed += 1
                                        intro_text = random.choice(INTRO_TEXT)
                                        temp_pdf_path = None
                                        markdown = None
                                        pdf_conversion_failed = False

                                        try:
                                            temp_pdf_path = future.result()
                                            if self.verbose:
                                                print(f"Converting PDF {papers_processed}/{len(candidate_rows)}: {row['title'][:50]}...")
                                            markdown = self._parse_downloaded_pdf_to_markdown(temp_pdf_path, row['pdf_url'])
                                            if self.verbose:
                                                print("✅ PDF conversion successful")
                                        except Exception as pdf_error:
                                            pdf_conversion_failed = True
                                            if self.verbose:
                                                print(f"❌ PDF conversion error for {row['title']}: {pdf_error}")
                                                print(f"   PDF URL: {row['pdf_url']}")
                                                print("   Skipping this paper and trying next one...")
                                        finally:
                                            if temp_pdf_path and os.path.exists(temp_pdf_path):
                                                try:
                                                    os.unlink(temp_pdf_path)
                                                except OSError:
                                                    if self.verbose:
                                                        print(f"Warning: Failed to remove temporary PDF: {temp_pdf_path}")

                                        if pdf_conversion_failed:
                                            if self.verbose:
                                                print(
                                                    f"📝 Skipped paper {papers_processed} - "
                                                    f"{successful_sections}/{target_sections} sections completed"
                                                )
                                            section_progress.update(1)
                                            submit_next_download()
                                            continue

                                        # Summarize the PDF content (or abstract if PDF failed)
                                        messages = [{"role": "user", "content": general_summary_prompt(markdown)}]
                                        
                                        if self.content_extraction_inference.provider == "ollama":
                                            resp = self.content_extraction_inference.invoke(
                                                messages=messages,
                                                system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY,
                                                schema=SummaryPromptData
                                            )
                                        else:
                                            resp = self.content_extraction_inference.invoke(
                                                messages=messages,
                                                system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY
                                            )

                                        # Parse JSON response with error handling
                                        try:
                                            resp_json = json_repair.loads(resp)
                                            
                                            # Ensure resp_json is a dictionary
                                            if not isinstance(resp_json, dict):
                                                if self.verbose:
                                                    print(f"Warning: Content extraction expected dict, got {type(resp_json)}")
                                                    print(f"Raw response: {resp[:200]}...")
                                                # Fallback: use the raw response
                                                summarized_paper = resp
                                            else:
                                                # Extract content from JSON response
                                                summarized_paper = resp_json.get('content', resp)
                                                
                                        except Exception as json_error:
                                            if self.verbose:
                                                print(f"Content extraction JSON parsing failed for paper: {row['title']}")
                                                print(f"Error: {json_error}")
                                                print(f"Raw response: {resp[:200]}...")
                                            # Fallback: use the raw response
                                            summarized_paper = resp

                                        # Now produce the "newsletter section" for that paper
                                        context = (
                                            f"Title: {row['title']}\n"
                                            f"Abstract: {row['abstract']}\n"
                                            f"Rationale: {row['rationale']}\n"
                                            f"Summary: {summarized_paper}"
                                        )
                                        messages = [
                                            {"role": "user", 
                                             "content": newsletter_context_prompt(self.research_interests, context, intro_text)}
                                        ]
                                     
                                        if self.newsletter_sections_inference.provider == "ollama":
                                            resp = self.newsletter_sections_inference.invoke(
                                                messages=messages,
                                                system_prompt=NEWSLETTER_SYSTEM_PROMPT,
                                                schema=NewsletterPromptData
                                            )
                                        else:
                                            resp = self.newsletter_sections_inference.invoke(
                                                messages=messages,
                                                system_prompt=NEWSLETTER_SYSTEM_PROMPT
                                            )

                                        # Parse JSON response with error handling
                                        try:
                                            resp_json = json_repair.loads(resp)
                                            
                                            # Ensure resp_json is a dictionary
                                            if not isinstance(resp_json, dict):
                                                if self.verbose:
                                                    print(f"Warning: Expected dict from JSON parsing, got {type(resp_json)}")
                                                    print(f"Raw response: {resp[:200]}...")
                                                # Fallback: use the raw response as the draft
                                                draft = f"## {row['title']}\n\n{resp}"
                                            else:
                                                # Extract draft from JSON response
                                                draft_content = resp_json.get('draft', resp)
                                                draft = f"## {row['title']}\n\n{draft_content}"
                                                
                                        except Exception as json_error:
                                            if self.verbose:
                                                print(f"JSON parsing failed for paper: {row['title']}")
                                                print(f"Error: {json_error}")
                                                print(f"Raw response: {resp[:200]}...")
                                            # Fallback: use the raw response as the draft
                                            draft = f"## {row['title']}\n\n{resp}"
                                        
                                        sections.append(draft)
                                        urls_and_titles.append(f"{row['title']}: {row['pdf_url']}")
                                        successful_sections += 1
                                        
                                        if self.verbose:
                                            print(
                                                f"✅ Successfully processed paper {papers_processed} - "
                                                f"{successful_sections}/{target_sections} sections completed"
                                            )

                                        section_progress.update(1)

                                        if successful_sections < target_sections:
                                            submit_next_download()

                                        if successful_sections >= target_sections and self.verbose:
                                            print(f"✅ Reached target of {target_sections} sections, stopping")

                            finally:
                                download_executor.shutdown(wait=False, cancel_futures=True)

                                for future, row in download_futures.items():
                                    if future.cancel():
                                        continue
                                    if future.done():
                                        try:
                                            temp_pdf_path = future.result()
                                        except Exception:
                                            continue
                                        if temp_pdf_path and os.path.exists(temp_pdf_path):
                                            try:
                                                os.unlink(temp_pdf_path)
                                            except OSError:
                                                if self.verbose:
                                                    print(f"Warning: Failed to remove temporary PDF: {temp_pdf_path}")

                        # Final summary
                        if self.verbose:
                            print(f"\n📊 Newsletter section generation summary:")
                            print(f"   Target sections: {target_sections}")
                            print(f"   Successful sections: {successful_sections}")
                            print(f"   Papers processed: {papers_processed}")
                            print(f"   Papers available: {len(top_n_df)}")
                            if successful_sections < target_sections:
                                print(f"   ⚠️ Only generated {successful_sections}/{target_sections} sections due to PDF conversion failures")
                            else:
                                print(f"   ✅ Successfully generated all {successful_sections} target sections")

                        sections_data = {
                            'sections': sections,
                            'urls_and_titles': urls_and_titles
                        }
                        await self._save_checkpoint_async('newsletter_sections', sections_data)
            if progress_callback:
                progress_callback("newsletter", 50, "Newsletter sections generation complete")

            # -----------
            # Stage 5: Generate Full Newsletter Content
            # -----------
            if progress_callback:
                progress_callback("newsletter", 60, "Starting newsletter content generation")
            if start_from is None or start_from in ['newsletter_sections', 'newsletter_content']:
                newsletter_content = await self._load_checkpoint_async('newsletter_content')
                if newsletter_content is None:
                    if sections_data is None:
                        sections_data = await self._load_checkpoint_async('newsletter_sections')
                        if sections_data is None:
                            raise ValueError("No newsletter sections found to build the final newsletter.")
                    
                    if self.verbose:
                        print("Building the final newsletter content + intro ...")

                    sections = sections_data['sections']
                    
                    # Handle case where there are no sections
                    if len(sections) == 0:
                        newsletter_content = "No new papers found for this newsletter period. No papers met the criteria for inclusion."
                        if self.verbose:
                            print("No sections available - generating empty newsletter message")
                    else:
                        joined_sections = "\n\n".join(sections)
                        intro_prompt = newsletter_intro_prompt(joined_sections)
                        messages = [{"role": "user", "content": intro_prompt}]

                        # Model call for the newsletter's intro with retry logic
                        # Gemini API can throw 504 Deadline Exceeded errors on long requests
                        max_retries = 3
                        retry_delay = 5  # seconds
                        resp = None
                        last_error = None
                        
                        for attempt in range(max_retries):
                            try:
                                if attempt > 0:
                                    if self.verbose:
                                        print(f"Retrying newsletter intro generation (attempt {attempt + 1}/{max_retries}) after {retry_delay}s...")
                                    await asyncio.sleep(retry_delay)
                                    retry_delay *= 2  # Exponential backoff
                                
                                if self.newsletter_intro_inference.provider == "ollama":
                                    resp = self.newsletter_intro_inference.invoke(
                                        messages=messages,
                                        system_prompt=NEWSLETTER_SYSTEM_PROMPT,
                                        schema=NewsletterPromptData
                                    )
                                else:
                                    resp = self.newsletter_intro_inference.invoke(
                                        messages=messages,
                                        system_prompt=NEWSLETTER_SYSTEM_PROMPT
                                    )
                                break  # Success, exit retry loop
                                
                            except Exception as invoke_error:
                                last_error = invoke_error
                                error_str = str(invoke_error)
                                # Check if this is a retryable error (timeout, deadline exceeded, etc.)
                                is_retryable = any(term in error_str.lower() for term in 
                                    ['deadline', 'timeout', '504', '503', '502', 'unavailable', 'overloaded'])
                                
                                if self.verbose:
                                    print(f"Newsletter intro generation failed (attempt {attempt + 1}/{max_retries}): {error_str}")
                                
                                if not is_retryable or attempt == max_retries - 1:
                                    # Non-retryable error or last attempt - re-raise
                                    raise
                        
                        if resp is None:
                            raise last_error or RuntimeError("Newsletter intro generation failed with no response")

                        try:
                            resp_json = json_repair.loads(resp)
                            
                            # Ensure resp_json is a dictionary
                            if not isinstance(resp_json, dict):
                                if self.verbose:
                                    print(f"Warning: Newsletter intro expected dict, got {type(resp_json)}")
                                    print(f"Raw response: {resp[:200]}...")
                                intro_text = resp
                            else:
                                intro_text = resp_json.get('draft', resp)
                                
                        except Exception as json_error:
                            if self.verbose:
                                print(f"Newsletter intro JSON parsing failed")
                                print(f"Error: {json_error}")
                                print(f"Raw response: {resp[:200]}...")
                            intro_text = resp

                        # Final newsletter
                        newsletter_content = intro_text + "\n\n" + joined_sections
                    await self._save_checkpoint_async('newsletter_content', newsletter_content)

                    # Save to DB
                    if self.db_saving:
                        print("Saving newsletter to DB")
                        newsletter = Newsletter(
                            content=newsletter_content,
                            start_date=self.start_date.strftime('%Y-%m-%d'),
                            end_date=self.end_date.strftime('%Y-%m-%d'),
                            date_sent=TODAY.strftime('%Y-%m-%d')
                        )
                        NewsletterRepository.insert(newsletter)
            if progress_callback:
                progress_callback("newsletter", 80, "Newsletter content generation complete")

            # -----------
            # Stage 6: Send Email (if generate_email=True)
            # -----------
            if progress_callback:
                progress_callback("newsletter", 85, "Starting newsletter email sending")
            if self.generate_email:
                if newsletter_content is None:
                    newsletter_content = await self._load_checkpoint_async('newsletter_content')
                    if newsletter_content is None:
                        raise ValueError("Cannot send email: no newsletter content found.")

                if sections_data is None:
                    sections_data = await self._load_checkpoint_async('newsletter_sections')
                    if sections_data is None:
                        raise ValueError("No sections data found to build email links.")

                if self.verbose:
                    print("Sending newsletter email...")

                # Construct a simple bulleted list of links
                if len(sections_data['urls_and_titles']) > 0:
                    urls_and_titles_bulleted = "\n".join(
                        f"{i+1}. {title}" for i, title in enumerate(sections_data['urls_and_titles'])
                    )
                else:
                    urls_and_titles_bulleted = "No new papers found for this period."
                email_body = construct_email_body(
                    newsletter_content,
                    self.start_date.strftime('%Y-%m-%d'),
                    self.end_date.strftime('%Y-%m-%d'),
                    urls_and_titles_bulleted
                )
                try:
                    self.communication.compose_message(email_body, self.start_date, self.end_date)
                    self.communication.send_email()
                    # Log successful email
                    LogsRepository.upsert(
                        task_id=self.task_id, 
                        status=f"EMAIL_SUCCESS: Successfully sent newsletter to {self.receiver_address}",
                        datetime_run=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    )
                except Exception as e:
                    self._log_error(500, e)
                    raise
            if progress_callback and not self.generate_podcast:
                progress_callback("newsletter", 100, "Newsletter email sending complete")
            if progress_callback and self.generate_podcast:
                progress_callback("newsletter", 90, "Newsletter email sending complete")

            # -----------
            # Stage 7: Generate Podcast (if generate_podcast=True)
            # -----------
            if progress_callback:
                progress_callback("podcast", 90, "Starting podcast generation")
            if self.generate_podcast:
                # Part A: Generate Podcast Script + Audio
                podcast_content = await self._load_checkpoint_async('podcast_script')
                if podcast_content is None:
                    # If we haven't built any script yet, let's do it
                    if self.verbose:
                        print("Generating podcast script & audio...")

                    if top_n_df is None:
                        top_n_df = await self._load_checkpoint_async('papers_ranked')
                        if top_n_df is None:
                            raise ValueError("Cannot generate podcast: no ranked papers found.")
                    if sections_data is None:
                        sections_data = await self._load_checkpoint_async('newsletter_sections')
                        if sections_data is None:
                            raise ValueError("Cannot generate podcast: no newsletter sections found.")

                    podcast_content = self.podcast_generator.generate_podcast(
                        pdf_paths=list(top_n_df['pdf_url']),
                        output_format=self.output_format,
                        output_dir=self.output_dir,
                        prefix=self.prefix,
                        final_filename=self.final_filename,
                        verbose=self.verbose,
                        visualizer=False  # We'll do visualization in next step
                    )
                    await self._save_checkpoint_async('podcast_script', podcast_content)

                # Part B: Visualization (if visualizer=True)
                visualized_podcast = await self._load_checkpoint_async('podcast_visualized')
                if self.visualizer and visualized_podcast is None:
                    if self.verbose:
                        print("Generating podcast visualization...")

                    # We re-run generate_podcast with visualizer=True
                    # so it merges the final audio with the animation
                    podcast_content = self.podcast_generator.generate_podcast(
                        pdf_paths=list(top_n_df['pdf_url']),
                        output_format=self.output_format,
                        output_dir=self.output_dir,
                        prefix=self.prefix,
                        final_filename=self.final_filename,
                        verbose=self.verbose,
                        visualizer=True,
                        resolution=self.resolution,
                        fps=self.fps,
                        matrix_count=self.matrix_count,
                        matrix_head_color=self.matrix_head_color,
                        matrix_tail_color=self.matrix_tail_color,
                        matrix_char_size=self.matrix_char_size,
                        head_step_time=self.head_step_time,
                        random_x_jitter=self.random_x_jitter,
                        fade_time=self.fade_time,
                        head_glow_passes=self.head_glow_passes,
                        head_glow_alpha_decay=self.head_glow_alpha_decay,
                        head_spawn_delay_range=self.head_spawn_delay_range,
                        head_saw_period=self.head_saw_period,
                        wave_color=self.wave_color,
                        trail_colors=self.trail_colors,
                        glow_passes=self.glow_passes,
                        glow_alpha_decay=self.glow_alpha_decay,
                        line_width=self.line_width,
                        font_path=self.font_path
                    )
                    await self._save_checkpoint_async('podcast_visualized', podcast_content)
                
                # Save the final script / transcript in DB and optional JSON
                if podcast_content:
                    if self.save_dialogue:
                        if self.verbose:
                            print("Saving podcast dialogue to JSON...")
                        dialogue_path = os.path.join(self.output_dir, f"{self.prefix}_dialogue.json")
                        with open(dialogue_path, "w", encoding="utf-8") as f:
                            json.dump({
                                "dialogue": podcast_content['dict_transcript'],
                                "description": podcast_content['description']
                            }, f, ensure_ascii=False, indent=2)

                    # Insert a record in the DB for the final podcast
                    if self.db_saving:
                        podcast = Podcast(
                            title=self.final_filename,
                            date=TODAY.strftime('%Y-%m-%d'),
                            script=json.dumps(podcast_content['dict_transcript']),
                            description=podcast_content['description']
                        )
                        PodcastRepository.insert(podcast)

                    # Part C: Publish to YouTube if requested
                    if self.publish_podcast:
                        video_path = (podcast_content['visualizer_path']
                                      if self.visualizer else
                                      podcast_content['final_podcast_path'])
                        if self.verbose:
                            print("Publishing to YouTube, this may take a while...")
                        try:
                            upload_video(
                                video_path,
                                title=self.final_filename,
                                description=podcast_content['description']
                            )
                        except Exception as up_e:
                            self._log_error(500, up_e)
                            raise
            if progress_callback:
                progress_callback("podcast", 100, "Podcast generation complete")

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
        """
        Run paper ingestion pipeline for profiles feature - stores ALL papers without LLM scoring.
        
        This method downloads papers, embeds them, and stores them all in the database
        without applying LLM judge filtering. Papers can be scored later per profile.
        """
        try:
            # Force Kaggle download for bulk operations to handle large date ranges efficiently
            import os
            old_force_kaggle = os.environ.get('FORCE_KAGGLE', '')
            os.environ['FORCE_KAGGLE'] = 'true'
            
            if self.verbose:
                print("🚀 STARTING PROFILES-AWARE PAPER INGESTION")
                print("="*60)
                print("Note: This pipeline stores ALL papers without LLM judge filtering")
                print("Papers will be scored later on a per-profile basis")
                print("Using Kaggle dataset for bulk download (4GB file)")
                print("="*60)
            
            # Check existing papers BEFORE downloading
            existing_urls = set()
            existing_titles = set()
            if self.verbose:
                print("\n🔍 PRE-DOWNLOAD CHECK")
                print("="*40)
                print("Checking existing papers in database before download...")
            
            # Get papers in the date range from the database
            existing_papers = PaperRepository.get_papers_in_date_range(
                start_date=self.start_date.strftime('%Y-%m-%d'),
                end_date=self.end_date.strftime('%Y-%m-%d')
            )
            
            existing_urls = {p['url'] for p in existing_papers}
            existing_titles = {p['title'] for p in existing_papers}
            
            if self.verbose:
                print(f"📊 Found {len(existing_papers)} existing papers in date range")
                print(f"   - {len(existing_urls)} unique URLs")
                print(f"   - {len(existing_titles)} unique titles")
                
                # If we have most papers already, we might skip download entirely
                if len(existing_papers) > 0:
                    print(f"💡 Tip: {len(existing_papers)} papers already exist - download will skip these")
            
            # -----------
            # Stage 1: Download Papers
            # -----------
            if progress_callback:
                progress_callback("download", 0, "Starting paper download")
                
            data_df = self._load_checkpoint('papers_downloaded')
            if data_df is None:
                if self.verbose:
                    print("\n📥 STAGE 1: DOWNLOADING PAPERS")
                    print("="*40)
                
                # Get ArXiv categories from orchestration config
                arxiv_config = self.orchestration_config.get('arxiv_search_categories', {})
                
                # Debug: Let's see what's in the config
                if self.verbose:
                    print(f"[DEBUG] arxiv_config: {arxiv_config}")
                
                category = arxiv_config.get('main_category', 'cs')
                subcategories = arxiv_config.get('filter_categories', ['cs.ai', 'cs.cl', 'cs.lg', 'cs.ir', 'cs.ma', 'cs.cv'])
                
                # If categories are explicitly set to None, download all papers
                if 'filter_categories' in arxiv_config and arxiv_config['filter_categories'] is None:
                    category = None
                    subcategories = None
                    if self.verbose:
                        print("📋 Downloading ALL ArXiv categories (no filtering)")
                else:
                    if self.verbose:
                        print(f"📋 Category: {category}, Subcategories: {subcategories}")
                
                process_data = ArxivDataProcessor(
                    start_date=self.start_date, 
                    end_date=self.end_date,
                    category=category,
                    subcategories=subcategories
                )
                data_df = process_data.download_and_process_data()
                
                # Check if no papers were found and handle gracefully
                if data_df.empty:
                    self._handle_no_papers_found()
                    return  # Exit early since there's nothing to process
                
                # Early optimization: Check if all downloaded papers already exist
                quick_check_urls = set(data_df['pdf_url'].tolist())
                quick_check_titles = set(data_df['title'].tolist())
                
                if quick_check_urls.issubset(existing_urls) or quick_check_titles.issubset(existing_titles):
                    if self.verbose:
                        print("🎯 OPTIMIZATION: All downloaded papers already exist in database!")
                        print("   Skipping download and processing stages")
                    return {
                        'saved_count': 0,
                        'duplicate_count': len(data_df),
                        'total_processed': len(data_df)
                    }
                
                self._save_checkpoint('papers_downloaded', data_df)
                if self.verbose:
                    print(f"✅ Downloaded {len(data_df)} papers from ArXiv")
            else:
                if self.verbose:
                    print(f"📥 Using cached papers: {len(data_df)} papers")

            if progress_callback:
                progress_callback("download", 20, "Paper download complete")

            # -----------
            # Stage 2: Embed Papers
            # -----------
            if progress_callback:
                progress_callback("embed", 21, "Starting paper embedding")
                
            embedded_df = self._load_checkpoint('papers_embedded')
            if embedded_df is None:
                if self.verbose:
                    print("\n🧠 STAGE 2: EMBEDDING PAPERS")
                    print("="*40)
                
                # Filter out papers with missing abstracts first
                original_count = len(data_df)
                abstract_mask = data_df['abstract'].notna() & (data_df['abstract'].str.strip() != '')
                data_df = data_df[abstract_mask].reset_index(drop=True)
                
                if self.verbose and original_count != len(data_df):
                    filtered_out = original_count - len(data_df)
                    print(f"⚠️ Filtered out {filtered_out} papers with missing/empty abstracts")
                
                if data_df.empty:
                    if self.verbose:
                        print("❌ No papers with valid abstracts to process")
                    return
                
                # Check for existing papers using pre-loaded data
                new_mask = []
                if self.verbose:
                    print("🔍 Filtering out existing papers using pre-loaded data...")
                
                # Use the pre-loaded existing URLs and titles for faster checking
                for _, row in tqdm(data_df.iterrows(), total=len(data_df), 
                                  desc="Checking existing papers", disable=not self.verbose):
                    exists = (row["pdf_url"] in existing_urls or row["title"] in existing_titles)
                    new_mask.append(not exists)
                
                new_df = data_df[new_mask].reset_index(drop=True)
                
                if self.verbose:
                    existing_count = len(data_df) - len(new_df)
                    print(f"📝 Found {existing_count} existing papers, {len(new_df)} new papers to process")

                if new_df.empty:
                    if self.verbose:
                        print("✅ All papers already exist in database")
                    return {
                        'saved_count': 0,
                        'duplicate_count': len(data_df),
                        'total_processed': len(data_df)
                    }
                
                # Create job checkpoint for UI tracking
                from .services.embedding_service import EmbeddingJobCheckpoint
                from uuid import uuid4
                job_id = uuid4()
                checkpoint_mgr = EmbeddingJobCheckpoint()
                
                # Initialize checkpoint
                checkpoint_mgr.save(
                    job_id=job_id,
                    operation="profile_aware_embed",
                    parameters={
                        "start_date": self.start_date.strftime('%Y-%m-%d'),
                        "end_date": self.end_date.strftime('%Y-%m-%d'),
                        "model_name": self.embedding_model.model_name if hasattr(self.embedding_model, 'model_name') else "unknown"
                    },
                    progress={
                        "total_papers": len(new_df),
                        "processed_papers": 0,
                        "offset": 0
                    },
                    statistics={
                        "papers_embedded": 0,
                        "papers_failed": 0
                    }
                )
                
                if self.verbose:
                    print(f"📋 Created embedding job for UI tracking: {job_id}")
                
                # Embed abstracts in batches to avoid memory issues
                batch_size = getattr(self, 'batch_size', 100)
                all_embeddings = []
                processed_count = 0
                
                try:
                    for i in tqdm(range(0, len(new_df), batch_size), 
                                 desc="Embedding batches", disable=not self.verbose):
                        batch_df = new_df.iloc[i:i+batch_size]
                        abstracts = list(batch_df['abstract'])
                        batch_embeddings = self.embedding_model.invoke(abstracts)
                        all_embeddings.extend(batch_embeddings)
                        
                        processed_count += len(batch_df)
                        
                        # Update checkpoint every 500 papers for more frequent UI updates
                        if processed_count % 500 == 0:
                            checkpoint_mgr.save(
                                job_id=job_id,
                                operation="profile_aware_embed",
                                parameters={
                                    "start_date": self.start_date.strftime('%Y-%m-%d'),
                                    "end_date": self.end_date.strftime('%Y-%m-%d'),
                                    "model_name": self.embedding_model.model_name if hasattr(self.embedding_model, 'model_name') else "unknown"
                                },
                                progress={
                                    "total_papers": len(new_df),
                                    "processed_papers": processed_count,
                                    "offset": processed_count
                                },
                                statistics={
                                    "papers_embedded": processed_count,
                                    "papers_failed": 0
                                }
                            )
                    
                    embeddings = all_embeddings
                    
                    # Convert 2D embeddings array to list of 1D arrays for pandas
                    if hasattr(embeddings, 'tolist'):
                        embeddings_list = embeddings.tolist()
                    elif isinstance(embeddings, list):
                        embeddings_list = embeddings
                    else:
                        # Handle numpy arrays or other tensor types
                        import numpy as np
                        embeddings_array = np.array(embeddings)
                        embeddings_list = [embeddings_array[i] for i in range(len(embeddings_array))]
                    
                    new_df['abstract_embedding'] = embeddings_list
                    
                    # Final checkpoint update
                    checkpoint_mgr.save(
                        job_id=job_id,
                        operation="profile_aware_embed",
                        parameters={
                            "start_date": self.start_date.strftime('%Y-%m-%d'),
                            "end_date": self.end_date.strftime('%Y-%m-%d'),
                            "model_name": self.embedding_model.model_name if hasattr(self.embedding_model, 'model_name') else "unknown"
                        },
                        progress={
                            "total_papers": len(new_df),
                            "processed_papers": len(new_df),
                            "offset": len(new_df)
                        },
                        statistics={
                            "papers_embedded": len(new_df),
                            "papers_failed": 0
                        }
                    )
                    
                    # Clean up checkpoint after successful completion
                    checkpoint_mgr.delete(job_id)
                    
                    if self.verbose:
                        print(f"✅ Embedded {len(new_df)} papers")
                        print(f"🗑️  Cleaned up job checkpoint: {job_id}")
                        
                except Exception as e:
                    # On failure, update checkpoint but DON'T delete
                    checkpoint_mgr.save(
                        job_id=job_id,
                        operation="profile_aware_embed",
                        parameters={
                            "start_date": self.start_date.strftime('%Y-%m-%d'),
                            "end_date": self.end_date.strftime('%Y-%m-%d'),
                            "model_name": self.embedding_model.model_name if hasattr(self.embedding_model, 'model_name') else "unknown",
                            "error": str(e)
                        },
                        progress={
                            "total_papers": len(new_df),
                            "processed_papers": processed_count,
                            "offset": processed_count
                        },
                        statistics={
                            "papers_embedded": processed_count,
                            "papers_failed": len(new_df) - processed_count
                        }
                    )
                    
                    if self.verbose:
                        print(f"❌ Embedding failed at {processed_count}/{len(new_df)} papers")
                        print(f"💾 Job checkpoint preserved for debugging: {job_id}")
                    
                    # Re-raise the exception
                    raise
                
                # Calculate cosine similarity with research interests
                if self.research_interests and self.research_interests.strip():
                    research_embedding = self.embedding_model.invoke(self.research_interests)
                    if hasattr(research_embedding, 'tolist'):
                        research_embedding = research_embedding.tolist()
                    
                    similarities = []
                    for embedding in embeddings:
                        if hasattr(embedding, 'tolist'):
                            embedding = embedding.tolist()
                        sim = cosine_similarity(research_embedding, embedding)
                        similarities.append(sim)
                    
                    new_df['cosine_similarity'] = similarities
                else:
                    new_df['cosine_similarity'] = [0.0] * len(new_df)
                
                embedded_df = new_df
                self._save_checkpoint('papers_embedded', embedded_df)
                
                if self.verbose:
                    print(f"✅ Embedded {len(embedded_df)} new papers")
            else:
                if self.verbose:
                    print(f"🧠 Using cached embeddings: {len(embedded_df)} papers")

            if progress_callback:
                progress_callback("embed", 60, "Paper embedding complete")

            # -----------
            # Stage 3: Store Papers (No Scoring)
            # -----------
            if progress_callback:
                progress_callback("store", 61, "Storing papers to database")
                
            storage_result = self._load_checkpoint('papers_stored')
            if storage_result is None:
                storage_result = self.store_papers_without_scoring(embedded_df)
                self._save_checkpoint('papers_stored', storage_result)
            else:
                if self.verbose:
                    print(f"💾 Using cached storage result: {storage_result}")

            if progress_callback:
                progress_callback("store", 100, "Paper storage complete")

            # Clean up checkpoints after successful completion
            self._cleanup_checkpoints()
            
            if self.verbose:
                print("\n🎉 PROFILES PIPELINE COMPLETE!")
                print("="*60)
                print(f"✅ Processed {storage_result['total_processed']} papers")
                print(f"💾 Saved {storage_result['saved_count']} new papers")
                print(f"🔄 Skipped {storage_result['duplicate_count']} duplicates")
                print("📝 Papers are ready for profile-specific scoring")
                
            return storage_result
            
        except Exception as e:
            self._log_error(500, e)
            raise
        finally:
            # Restore original FORCE_KAGGLE setting
            if old_force_kaggle is not None:
                os.environ['FORCE_KAGGLE'] = old_force_kaggle
            else:
                os.environ.pop('FORCE_KAGGLE', None)

    def run_embedding_only_pipeline(self, progress_callback: Callable[[str, float, str], None]|None = None):
        """
        Run embedding-only pipeline for bulk data preparation.
        
        This method downloads papers, embeds them, and stores them all in the database
        without any profile-specific filtering or scoring. This is useful for bulk
        data preparation where scoring will be done later.
        """
        try:
            # Force Kaggle download for bulk operations to handle large date ranges efficiently
            import os
            old_force_kaggle = os.environ.get('FORCE_KAGGLE', '')
            os.environ['FORCE_KAGGLE'] = 'true'
            
            if self.verbose:
                print("🚀 STARTING BULK EMBEDDING PIPELINE")
                print("="*60)
                print("Note: This pipeline stores ALL papers with embeddings")
                print("No profile filtering or LLM scoring will be performed")
                print("Using Kaggle dataset for bulk download (4GB file)")
                print("="*60)
            
            # -----------
            # Stage 1: Download Papers
            # -----------
            if progress_callback:
                progress_callback("download", 0, "Starting paper download")
                
            data_df = self._load_checkpoint('papers_downloaded')
            if data_df is None:
                if self.verbose:
                    print("📥 STAGE 1: DOWNLOADING PAPERS")
                    print("="*40)
                
                # Get ArXiv categories from orchestration config
                arxiv_config = self.orchestration_config.get('arxiv_search_categories', {})
                
                # Debug: Let's see what's in the config
                if self.verbose:
                    print(f"[DEBUG] arxiv_config: {arxiv_config}")
                
                category = arxiv_config.get('main_category', 'cs')
                subcategories = arxiv_config.get('filter_categories', ['cs.ai', 'cs.cl', 'cs.lg', 'cs.ir', 'cs.ma', 'cs.cv'])
                
                # If categories are explicitly set to None, download all papers
                if 'filter_categories' in arxiv_config and arxiv_config['filter_categories'] is None:
                    category = None
                    subcategories = None
                    if self.verbose:
                        print("📋 Downloading ALL ArXiv categories (no filtering)")
                else:
                    if self.verbose:
                        print(f"📋 Category: {category}, Subcategories: {subcategories}")
                
                process_data = ArxivDataProcessor(
                    start_date=self.start_date, 
                    end_date=self.end_date,
                    category=category,
                    subcategories=subcategories
                )
                data_df = process_data.download_and_process_data()
                
                # Check if no papers were found and handle gracefully
                if data_df.empty:
                    if self.verbose:
                        print("❌ No papers found for the specified date range")
                    return {
                        'saved_count': 0,
                        'embedded_count': 0,
                        'skipped_count': 0,
                        'total_processed': 0
                    }
                
                self._save_checkpoint('papers_downloaded', data_df)
                if self.verbose:
                    print(f"✅ Downloaded {len(data_df)} papers from ArXiv")
            else:
                if self.verbose:
                    print(f"📥 Using cached papers: {len(data_df)} papers")

            if progress_callback:
                progress_callback("download", 25, f"Downloaded {len(data_df)} papers")

            # -----------
            # Stage 2: Check Existing & Filter
            # -----------
            if progress_callback:
                progress_callback("filter", 26, "Checking for existing papers")
                
            # Filter out papers with missing abstracts
            original_count = len(data_df)
            abstract_mask = data_df['abstract'].notna() & (data_df['abstract'].str.strip() != '')
            data_df = data_df[abstract_mask].reset_index(drop=True)
            
            if self.verbose and original_count != len(data_df):
                filtered_out = original_count - len(data_df)
                print(f"⚠️ Filtered out {filtered_out} papers with missing/empty abstracts")
            
            if data_df.empty:
                if self.verbose:
                    print("❌ No papers with valid abstracts to process")
                return {
                    'saved_count': 0,
                    'embedded_count': 0,
                    'skipped_count': original_count,
                    'total_processed': original_count
                }
            
            # Check for existing papers if skip_existing is enabled
            papers_to_embed = data_df
            skipped_count = 0
            
            if getattr(self, 'skip_existing', True):
                if self.verbose:
                    print("🔍 Checking for existing papers in database...")
                
                new_mask = []
                already_embedded_mask = []
                
                for _, row in tqdm(data_df.iterrows(), total=len(data_df), 
                                  desc="Checking existing papers", disable=not self.verbose):
                    existing_paper = PaperRepository.get_by_url(row["pdf_url"])
                    if existing_paper:
                        new_mask.append(False)
                        # Check if paper already has embedding (must have both embedding and valid model name)
                        has_embedding = (
                            existing_paper.get('embedding') is not None and 
                            existing_paper.get('embedding_model') is not None and
                            existing_paper.get('embedding_model') not in ['pending', '']
                        )
                        already_embedded_mask.append(has_embedding)
                    else:
                        new_mask.append(True)
                        already_embedded_mask.append(False)
                
                # Papers that need to be embedded (new papers + existing without embeddings)
                needs_embedding_mask = [new_mask[i] or not already_embedded_mask[i] for i in range(len(data_df))]
                papers_to_embed = data_df[needs_embedding_mask].reset_index(drop=True)
                skipped_count = sum(already_embedded_mask)
                
                if self.verbose:
                    new_count = sum(new_mask)
                    existing_without_embedding = sum(not new and not embedded for new, embedded in zip(new_mask, already_embedded_mask))
                    print(f"📝 Found {new_count} new papers")
                    print(f"📝 Found {existing_without_embedding} existing papers without embeddings")
                    print(f"📝 Skipping {skipped_count} papers that already have embeddings")

            if progress_callback:
                progress_callback("filter", 35, f"Filtered to {len(papers_to_embed)} papers needing embeddings")

            # -----------
            # Stage 3: Embed Papers (Memory-Safe with Chunking)
            # -----------
            embedded_count = 0
            if len(papers_to_embed) > 0:
                if progress_callback:
                    progress_callback("embed", 36, "Starting paper embedding")
                    
                embedded_df = self._load_checkpoint('papers_embedded')
                if embedded_df is None:
                    if self.verbose:
                        print(f"\n🧠 STAGE 3: EMBEDDING {len(papers_to_embed)} PAPERS (Memory-Safe)")
                        print("="*40)
                    
                    # Create job checkpoint for UI tracking
                    from .services.embedding_service import EmbeddingJobCheckpoint
                    from uuid import uuid4
                    job_id = uuid4()
                    checkpoint_mgr = EmbeddingJobCheckpoint()
                    
                    # Initialize checkpoint
                    checkpoint_mgr.save(
                        job_id=job_id,
                        operation="profile_aware_embed",
                        parameters={
                            "start_date": self.start_date,
                            "end_date": self.end_date,
                            "model_name": self.embedding_model.model_name if hasattr(self.embedding_model, 'model_name') else "unknown"
                        },
                        progress={
                            "total_papers": len(papers_to_embed),
                            "processed_papers": 0,
                            "offset": 0
                        },
                        statistics={
                            "papers_embedded": 0,
                            "papers_failed": 0
                        }
                    )
                    
                    if self.verbose:
                        print(f"📋 Created embedding job for UI tracking: {job_id}")
                    
                    # Use chunked processing to avoid memory issues
                    batch_size = getattr(self, 'batch_size', 100)
                    chunk_size = 10000  # Process 10K papers per chunk, then flush
                    all_embeddings = []
                    papers_to_save = []
                    processed_count = 0
                    
                    try:
                        for i in tqdm(range(0, len(papers_to_embed), batch_size), 
                                     desc="Embedding batches", disable=not self.verbose):
                            batch = papers_to_embed.iloc[i:i+batch_size]
                            abstracts = batch['abstract'].tolist()
                            
                            # Embed batch
                            embeddings = self.embedding_model.invoke(abstracts)
                            
                            # Store embeddings with paper data
                            for j, (idx, row) in enumerate(batch.iterrows()):
                                embedding = embeddings[j]
                                all_embeddings.append(embedding)
                                papers_to_save.append((idx, embedding))
                            
                            processed_count += len(batch)
                            
                            # Update checkpoint every 1000 papers for UI
                            if processed_count % 1000 == 0:
                                checkpoint_mgr.save(
                                    job_id=job_id,
                                    operation="profile_aware_embed",
                                    parameters={
                                        "start_date": self.start_date,
                                        "end_date": self.end_date,
                                        "model_name": self.embedding_model.model_name if hasattr(self.embedding_model, 'model_name') else "unknown"
                                    },
                                    progress={
                                        "total_papers": len(papers_to_embed),
                                        "processed_papers": processed_count,
                                        "offset": processed_count
                                    },
                                    statistics={
                                        "papers_embedded": processed_count,
                                        "papers_failed": 0
                                    }
                                )
                            
                            # Flush to disk periodically to free memory
                            if len(papers_to_save) >= chunk_size:
                                # Create partial dataframe with embeddings
                                indices = [idx for idx, _ in papers_to_save]
                                embs = [emb for _, emb in papers_to_save]
                                papers_to_embed.loc[indices, 'abstract_embedding'] = embs
                                papers_to_embed.loc[indices, 'cosine_similarity'] = [0.0] * len(embs)
                                
                                if self.verbose:
                                    print(f"💾 Flushed {len(papers_to_save)} papers to memory")
                                
                                # Clear buffers
                                papers_to_save = []
                                
                                # Force garbage collection to free memory
                                import gc
                                gc.collect()
                            
                            # Update progress
                            if progress_callback:
                                embed_progress = 36 + (i / len(papers_to_embed)) * 40
                                progress_callback("embed", embed_progress, f"Embedded {min(i+batch_size, len(papers_to_embed))}/{len(papers_to_embed)} papers")
                        
                        # Flush any remaining papers
                        if papers_to_save:
                            indices = [idx for idx, _ in papers_to_save]
                            embs = [emb for _, emb in papers_to_save]
                            papers_to_embed.loc[indices, 'abstract_embedding'] = embs
                            papers_to_embed.loc[indices, 'cosine_similarity'] = [0.0] * len(embs)
                        
                        # Final assignment
                        embedded_df = papers_to_embed
                        embedded_count = len(embedded_df)
                        self._save_checkpoint('papers_embedded', embedded_df)
                        
                        # Final checkpoint update
                        checkpoint_mgr.save(
                            job_id=job_id,
                            operation="profile_aware_embed",
                            parameters={
                                "start_date": self.start_date,
                                "end_date": self.end_date,
                                "model_name": self.embedding_model.model_name if hasattr(self.embedding_model, 'model_name') else "unknown"
                            },
                            progress={
                                "total_papers": len(papers_to_embed),
                                "processed_papers": embedded_count,
                                "offset": embedded_count
                            },
                            statistics={
                                "papers_embedded": embedded_count,
                                "papers_failed": 0
                            }
                        )
                        
                        # Clean up checkpoint after successful completion
                        checkpoint_mgr.delete(job_id)
                        
                        if self.verbose:
                            print(f"✅ Embedded {embedded_count} papers")
                            print(f"🗑️  Cleaned up job checkpoint: {job_id}")
                            
                    except Exception as e:
                        # On failure, update checkpoint but DON'T delete
                        # This allows the UI to show the hung job and where it stopped
                        checkpoint_mgr.save(
                            job_id=job_id,
                            operation="profile_aware_embed",
                            parameters={
                                "start_date": self.start_date,
                                "end_date": self.end_date,
                                "model_name": self.embedding_model.model_name if hasattr(self.embedding_model, 'model_name') else "unknown",
                                "error": str(e)  # Include error in parameters for debugging
                            },
                            progress={
                                "total_papers": len(papers_to_embed),
                                "processed_papers": processed_count,
                                "offset": processed_count
                            },
                            statistics={
                                "papers_embedded": processed_count,
                                "papers_failed": len(papers_to_embed) - processed_count
                            }
                        )
                        
                        if self.verbose:
                            print(f"❌ Embedding failed at {processed_count}/{len(papers_to_embed)} papers")
                            print(f"💾 Job checkpoint preserved for debugging: {job_id}")
                        
                        # Re-raise the exception
                        raise
                else:
                    embedded_count = len(embedded_df)
                    if self.verbose:
                        print(f"🧠 Using cached embeddings: {embedded_count} papers")
            else:
                embedded_df = pd.DataFrame()
                if self.verbose:
                    print("ℹ️ No papers need embedding")

            if progress_callback:
                progress_callback("embed", 76, "Embedding complete")

            # -----------
            # Stage 4: Store Papers
            # -----------
            saved_count = 0
            if len(embedded_df) > 0:
                if progress_callback:
                    progress_callback("store", 77, "Storing papers to database")
                    
                storage_result = self._load_checkpoint('papers_stored')
                if storage_result is None:
                    # Debug logging to understand the data
                    if self.verbose:
                        print(f"\n💾 STORING {len(embedded_df)} PAPERS WITHOUT SCORING")
                        print("="*60)
                        if not embedded_df.empty:
                            print("Sample data columns:", embedded_df.columns.tolist())
                            print("First row sample:")
                            first_row = embedded_df.iloc[0]
                            for col in ['title', 'abstract', 'pdf_url', 'date', 'cosine_similarity']:
                                if col in embedded_df.columns:
                                    print(f"  {col}: {first_row[col][:100] if isinstance(first_row[col], str) else first_row[col]}")
                    
                    storage_result = self.store_papers_without_scoring(embedded_df)
                    self._save_checkpoint('papers_stored', storage_result)
                    saved_count = storage_result['saved_count']
                else:
                    saved_count = storage_result['saved_count']
                    if self.verbose:
                        print(f"💾 Using cached storage result: {storage_result}")
            
            if progress_callback:
                progress_callback("store", 100, "Storage complete")

            # Clean up checkpoints after successful completion
            self._cleanup_checkpoints()
            
            total_result = {
                'saved_count': saved_count,
                'embedded_count': embedded_count,
                'skipped_count': skipped_count,
                'total_processed': len(data_df)
            }
            
            if self.verbose:
                print("\n🎉 BULK EMBEDDING PIPELINE COMPLETE!")
                print("="*60)
                print(f"✅ Total papers processed: {total_result['total_processed']}")
                print(f"🧠 Papers embedded: {total_result['embedded_count']}")
                print(f"💾 New papers saved: {total_result['saved_count']}")
                print(f"⏭️  Papers skipped (already embedded): {total_result['skipped_count']}")
                print("📝 Papers are ready for profile-specific scoring")
                
            return total_result
            
        except Exception as e:
            self._log_error(500, e)
            raise
        finally:
            # Restore original FORCE_KAGGLE setting
            if old_force_kaggle is not None:
                os.environ['FORCE_KAGGLE'] = old_force_kaggle
            else:
                os.environ.pop('FORCE_KAGGLE', None)
