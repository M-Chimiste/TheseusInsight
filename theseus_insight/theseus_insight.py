import os
import json
import gc
import shutil
import pickle
import random
import datetime
import time
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
import json_repair
from typing import Optional, Callable, List
import yake

from docling.document_converter import DocumentConverter

# Local application imports
from theseus_insight.communication import GmailCommunication, construct_email_body, upload_video
from theseus_insight.data_processing import ArxivDataProcessor, Paper, Newsletter, Podcast
from theseus_insight.data_access import (
    PaperRepository, LogsRepository, NewsletterRepository, 
    PodcastRepository, SettingsRepository
)
from theseus_insight.inference import SentenceTransformerInference
from theseus_insight.podcast import PodcastGenerator
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
                 send_error_notifications=True):
        
        # Store task_id for logging
        self.task_id = task_id or f"theseus_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.verbose = verbose
        self.save_dialogue = save_dialogue
        self.checkpoint_dir = checkpoint_dir
        self.generate_email = generate_email
        self.publish_podcast = publish_podcast
        self.generate_podcast = generate_podcast
        
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

        # Ensure arxiv_search_categories exists with defaults if not present
        if 'arxiv_search_categories' not in self.orchestration_config:
            self.orchestration_config['arxiv_search_categories'] = {
                "main_category": "cs",
                "filter_categories": ["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"]
            }

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
            self.judge_model_config.get('num_ctx')
        )
        self.content_extraction_inference = self._load_inference_model(
            self.content_extraction_model_config['model_type'],
            self.content_extraction_model_config['model_name'],
            self.content_extraction_model_config['max_new_tokens'],
            self.content_extraction_model_config['temperature'],
            self.content_extraction_model_config.get('num_ctx')
        )
        self.newsletter_sections_inference = self._load_inference_model(
            self.newsletter_sections_model_config['model_type'],
            self.newsletter_sections_model_config['model_name'],
            self.newsletter_sections_model_config['max_new_tokens'],
            self.newsletter_sections_model_config['temperature'],
            self.newsletter_sections_model_config.get('num_ctx')
        )
        self.newsletter_intro_inference = self._load_inference_model(
            self.newsletter_intro_model_config['model_type'],
            self.newsletter_intro_model_config['model_name'],
            self.newsletter_intro_model_config['max_new_tokens'],
            self.newsletter_intro_model_config['temperature'],
            self.newsletter_intro_model_config.get('num_ctx')
        )

        # 3) Podcast model
        if self.generate_podcast:
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
        self.send_error_notifications = send_error_notifications
        self.error_notified = False

    def _load_inference_model(self, model_type, model_name, max_new_tokens, temperature, num_ctx=None):
        """Load the appropriate inference model based on model type."""
        try:
            if model_type == "anthropic":
                if ANTHROPIC_API_KEY is None:
                    raise ValueError("Anthropic API key is not set.")
                from .inference.llm import AnthropicInference
                return AnthropicInference(model_name, max_new_tokens, temperature)
            
            elif model_type == "openai":
                if OPENAI_API_KEY is None:
                    raise ValueError("OpenAI API key is not set.")
                from .inference.llm import OpenAIInference
                return OpenAIInference(model_name, max_new_tokens, temperature)

            elif model_type == "gemini":
                if GOOGLE_API_KEY is None:
                    raise ValueError("Google API key is not set.")
                from .inference.llm import GeminiInference
                return GeminiInference(model_name, max_new_tokens, temperature)

            elif model_type == "ollama":
                from .inference.llm import OllamaInference
                kwargs = {
                    'model_name': model_name,
                    'max_new_tokens': max_new_tokens,
                    'temperature': temperature,
                    'url': OLLAMA_URL
                }
                if num_ctx is not None:
                    kwargs['num_ctx'] = num_ctx
                return OllamaInference(**kwargs)

            else:
                raise ValueError(f"Invalid model type: {model_type}")
        except Exception as e:
            self._log_error(500, e)
            raise

    def _log_error(self, status_code: int, error: Exception):
        """Helper to log errors to the database and optionally send an email."""
        error_msg = f"{type(error).__name__}: {str(error)}"
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

    def _save_checkpoint(self, stage: str, data: any):
        """Save a checkpoint for the given pipeline stage."""
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        checkpoint_path = os.path.join(self.checkpoint_dir, f"{stage}_checkpoint.pkl")
        checkpoint_data = {
            'data': data,
            'timestamp': datetime.datetime.now().isoformat(),
            'stage': stage
        }
        with open(checkpoint_path, 'wb') as f:
            pickle.dump(checkpoint_data, f)
        if self.verbose:
            print(f"Saved checkpoint for stage: {stage}")

    def _load_checkpoint(self, stage: str) -> any:
        """Load a checkpoint for the given pipeline stage."""
        checkpoint_path = os.path.join(self.checkpoint_dir, f"{stage}_checkpoint.pkl")
        if os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, 'rb') as f:
                    checkpoint = pickle.load(f)
                if self.verbose:
                    print(f"Loaded checkpoint for stage: {stage} from {checkpoint['timestamp']}")
                return checkpoint['data']
            except Exception as e:
                if self.verbose:
                    print(f"Error loading checkpoint for stage {stage}: {str(e)}")
                return None
        if self.verbose:
            print(f"No checkpoint found for stage: {stage}")
        return None

    def _cleanup_checkpoints(self):
        """Remove all checkpoint files after successful completion."""
        if os.path.exists(self.checkpoint_dir):
            try:
                shutil.rmtree(self.checkpoint_dir)
                if self.verbose:
                    print("Cleaned up all checkpoints")
            except Exception as e:
                if self.verbose:
                    print(f"Error cleaning up checkpoints: {str(e)}")

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
        """Clear Ollama cache for the judge model to resolve potential context issues."""
        try:
            if (hasattr(self, 'judge_inference') and 
                hasattr(self.judge_inference, 'provider') and 
                self.judge_inference.provider == "ollama"):
                model_name = self.judge_model_config.get('model_name')
                if model_name:
                    if self.verbose:
                        print(f"Clearing Ollama cache for judge model: {model_name}")
                    purge_ollama_cache(OLLAMA_URL, model_name)
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

    def rank_papers(self, data_df):
        """Given embedded papers, use judge model to score them."""
        try:
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
            
            for i, abstract in enumerate(tqdm(abstracts[start_index:], 
                                            disable=not self.verbose, 
                                            desc="Ranking papers",
                                            initial=start_index, 
                                            total=len(abstracts))):
                actual_index = start_index + i
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
            top_n_df = data_df.head(self.top_n)

            if self.db_saving:
                print("Saving papers to DB")
                # Save all to DB if enabled, tracking duplicates
                saved_count = 0
                duplicate_count = 0
                duplicate_urls = []
                
                for _, row in data_df.iterrows():
                    # Convert numpy array to list if needed for embedding
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
                        score=row['score'],
                        related=row['related'],
                        rationale=row['rationale'],
                        cosine_similarity=row['cosine_similarity'],
                        embedding_model=self.embedding_model_name,
                        embedding=embedding
                    )
                    
                    # Try to insert paper, tracking duplicates
                    was_inserted = PaperRepository.insert_paper(paper, skip_duplicates=True)
                    if was_inserted:
                        saved_count += 1
                        # Extract and cache keywords
                        try:
                            extractor = getattr(self, '_yake_extractor', None)
                            if extractor is None:
                                extractor = yake.KeywordExtractor(lan="en", n=1, top=5)
                                self._yake_extractor = extractor  # cache for reuse
                            text_kw = f"{row['title']} {row['abstract']}"
                            kw_scores = extractor.extract_keywords(text_kw)
                            keywords = [w for w, _ in kw_scores]
                            # Retrieve inserted paper ID via URL lookup
                            inserted_paper = PaperRepository.get_by_url(row['pdf_url'])
                            if inserted_paper and keywords:
                                PaperRepository.update_keywords(inserted_paper['id'], keywords)
                        except Exception:
                            pass
                    else:
                        duplicate_count += 1
                        duplicate_urls.append(row['pdf_url'])
                        if self.verbose:
                            print(f"Skipped duplicate paper: {row['title']}")
                
                if self.verbose:
                    print(f"Database save complete: {saved_count} new papers saved, {duplicate_count} duplicates skipped")
                
                # Keep all top_n papers for newsletter generation, including duplicates
                if duplicate_count > 0 and self.verbose:
                    duplicate_in_top_n = len([url for url in duplicate_urls if url in top_n_df['pdf_url'].values])
                    print(f"Newsletter will use {len(top_n_df)} papers (including {duplicate_in_top_n} duplicates from top papers)")
                    print("Note: Duplicates are kept in newsletter but were not re-saved to database")
       
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
            
            from .data_access import PaperRepository
            from .db import get_cursor
            import pandas as pd
            
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
                """, (profile_ids, min_score, self.start_date, self.end_date, self.top_n * 3))  # Get more than needed for ranking
                
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
            
            # Take top N papers by profile score
            top_df = df.head(self.top_n)
            
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
            
            for _, row in tqdm(data_df.iterrows(), total=len(data_df), 
                              desc="Storing papers", disable=not self.verbose):
                # Convert numpy array to list if needed for embedding
                embedding = row['abstract_embedding']
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                elif not isinstance(embedding, list):
                    embedding = list(embedding)
                
                paper = Paper(
                    title=row['title'],
                    abstract=row['abstract'],
                    url=row['pdf_url'],
                    date_run=None,  # No judge run date yet
                    date=row['date'].strftime('%Y-%m-%d'),
                    score=None,  # No score yet - will be added per profile
                    related=None,  # No related flag yet - will be added per profile
                    rationale=None,  # No rationale yet - will be added per profile
                    cosine_similarity=row['cosine_similarity'],
                    embedding_model=self.embedding_model_name,
                    embedding=embedding
                )
                
                # Try to insert paper, tracking duplicates
                was_inserted = PaperRepository.insert_paper(paper, skip_duplicates=True)
                if was_inserted:
                    saved_count += 1
                    
                    # Extract and cache keywords if YAKE is available
                    if extractor:
                        try:
                            text_kw = f"{row['title']} {row['abstract']}"
                            kw_scores = extractor.extract_keywords(text_kw)
                            keywords = [w for w, _ in kw_scores]
                            
                            # Retrieve inserted paper ID via URL lookup
                            inserted_paper = PaperRepository.get_by_url(row['pdf_url'])
                            if inserted_paper and keywords:
                                PaperRepository.update_keywords(inserted_paper['id'], keywords)
                        except Exception as e:
                            if self.verbose:
                                print(f"Warning: Failed to extract keywords for {row['title']}: {e}")
                else:
                    duplicate_count += 1
                    duplicate_urls.append(row['pdf_url'])
                    if self.verbose and duplicate_count <= 10:  # Only show first 10 duplicates
                        print(f"Skipped duplicate paper: {row['title']}")
            
            if self.verbose:
                print(f"✅ Storage complete: {saved_count} new papers saved, {duplicate_count} duplicates skipped")
                if duplicate_count > 10:
                    print(f"... and {duplicate_count - 10} more duplicates skipped")
                
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
        
        try:
            # -----------
            # Stage 1: Download Papers
            # -----------
            if progress_callback:
                progress_callback("download", 0, "Starting paper download")
                
            if not start_from:
                # no stage specified, do we have an existing checkpoint for 'papers_downloaded'?
                data_df = self._load_checkpoint('papers_downloaded')
                if data_df is None:
                    if self.verbose:
                        print("No 'papers_downloaded' checkpoint. Starting fresh: downloading papers.")
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
                progress_callback("download", 10, "Paper download complete")

            # -----------
            # Stage 2: Embed Papers
            # -----------
            if progress_callback:
                progress_callback("embed", 11, "Starting paper embedding")
                
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
                        if self.verbose:
                            print("Embedding papers...")

                        # Check for existing papers to avoid unnecessary processing
                        if self.db_saving:
                            existing_urls = []
                            new_papers_mask = []
                            for _, row in data_df.iterrows():
                                if PaperRepository.exists_by_url(row['pdf_url']):
                                    existing_urls.append(row['pdf_url'])
                                    new_papers_mask.append(False)
                                else:
                                    new_papers_mask.append(True)
                            
                            if existing_urls and self.verbose:
                                print(f"Found {len(existing_urls)} papers already in database, will skip embedding for those")
                                
                            # Filter to only new papers for embedding
                            new_papers_df = data_df[new_papers_mask].reset_index(drop=True)
                            
                            if len(new_papers_df) == 0:
                                if self.verbose:
                                    print("All papers already exist in database - no new papers to process")
                                # Handle no new papers case and exit early
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

                                # Filter by threshold
                                filtered_df = new_papers_df[new_papers_df['cosine_similarity'] >= self.cosine_similarity_threshold]
                                filtered_df = filtered_df.reset_index(drop=True)
                                
                                # Check if no papers meet the threshold criteria
                                if len(filtered_df) == 0:
                                    if self.verbose:
                                        print(f"No papers meet the cosine similarity threshold ({self.cosine_similarity_threshold})")
                                    # Handle no papers meeting criteria and exit early
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

                            # Filter by threshold
                            filtered_df = data_df[data_df['cosine_similarity'] >= self.cosine_similarity_threshold]
                            filtered_df = filtered_df.reset_index(drop=True)
                            
                            # Check if no papers meet the threshold criteria
                            if len(filtered_df) == 0:
                                if self.verbose:
                                    print(f"No papers meet the cosine similarity threshold ({self.cosine_similarity_threshold})")
                                # Handle no papers meeting criteria and exit early
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
                        self._save_checkpoint('papers_embedded', filtered_df)
                        embedded_df = filtered_df

            if progress_callback:
                progress_callback("embed", 15, "Paper embedding complete")

            # -----------
            # Stage 3: Rank Papers (or Get Profile Papers)
            # -----------
            if progress_callback:
                progress_callback("rank", 20, "Starting paper ranking")

            if start_from is None or start_from in ['papers_embedded', 'papers_ranked']:
                top_n_df = self._load_checkpoint('papers_ranked')
                if top_n_df is None:
                    # Check if we should use profile-based paper retrieval
                    if self.profile_ids_override:
                        if self.verbose:
                            print(f"Using profile-based paper retrieval for profiles: {self.profile_ids_override}")
                        top_n_df = self.get_profile_papers(
                            profile_ids=self.profile_ids_override,
                            min_score=0.5  # Configurable threshold
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
                            # Create empty top_n_df
                            top_n_df = embedded_df.copy()  # Empty dataframe with same structure
                        else:
                            if self.verbose:
                                print("Ranking papers...")
                            top_n_df = self.rank_papers(embedded_df)
                    
                    self._save_checkpoint('papers_ranked', top_n_df)

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
                sections_data = self._load_checkpoint('newsletter_sections')
                if sections_data is None:
                    if top_n_df is None:
                        top_n_df = self._load_checkpoint('papers_ranked')
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
                        self._save_checkpoint('newsletter_sections', sections_data)
                    else:
                        if self.verbose:
                            print("Generating newsletter sections (paper-by-paper) ...")

                        converter = DocumentConverter()
                        sections = []
                        urls_and_titles = []

                        for _, row in tqdm(top_n_df.iterrows(), total=len(top_n_df), desc="Sections"):
                            intro_text = random.choice(INTRO_TEXT)
                            
                            # Convert PDF to markdown
                            response = converter.convert(row['pdf_url'])
                            markdown = response.document.export_to_markdown()

                            # Summarize the PDF content
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

                            resp_json = json_repair.loads(resp)
                            summarized_paper = resp_json.get('content', resp)

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

                            resp_json = json_repair.loads(resp)
                            draft = f"## {row['title']}\n\n{resp_json['draft']}"
                            sections.append(draft)
                            urls_and_titles.append(f"{row['title']}: {row['pdf_url']}")

                        sections_data = {
                            'sections': sections,
                            'urls_and_titles': urls_and_titles
                        }
                        self._save_checkpoint('newsletter_sections', sections_data)
            if progress_callback:
                progress_callback("newsletter", 50, "Newsletter sections generation complete")

            # -----------
            # Stage 5: Generate Full Newsletter Content
            # -----------
            if progress_callback:
                progress_callback("newsletter", 60, "Starting newsletter content generation")
            if start_from is None or start_from in ['newsletter_sections', 'newsletter_content']:
                newsletter_content = self._load_checkpoint('newsletter_content')
                if newsletter_content is None:
                    if sections_data is None:
                        sections_data = self._load_checkpoint('newsletter_sections')
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

                        # Model call for the newsletter's intro
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

                        try:
                            resp_json = json_repair.loads(resp)
                            intro_text = resp_json['draft']
                        except:
                            intro_text = resp

                                                 # Final newsletter
                        newsletter_content = intro_text + "\n\n" + joined_sections
                    self._save_checkpoint('newsletter_content', newsletter_content)

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
                    newsletter_content = self._load_checkpoint('newsletter_content')
                    if newsletter_content is None:
                        raise ValueError("Cannot send email: no newsletter content found.")

                if sections_data is None:
                    sections_data = self._load_checkpoint('newsletter_sections')
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
                podcast_content = self._load_checkpoint('podcast_script')
                if podcast_content is None:
                    # If we haven't built any script yet, let's do it
                    if self.verbose:
                        print("Generating podcast script & audio...")

                    if top_n_df is None:
                        top_n_df = self._load_checkpoint('papers_ranked')
                        if top_n_df is None:
                            raise ValueError("Cannot generate podcast: no ranked papers found.")
                    if sections_data is None:
                        sections_data = self._load_checkpoint('newsletter_sections')
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
                    self._save_checkpoint('podcast_script', podcast_content)

                # Part B: Visualization (if visualizer=True)
                visualized_podcast = self._load_checkpoint('podcast_visualized')
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
                    self._save_checkpoint('podcast_visualized', podcast_content)
                
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
            self._save_checkpoint('newsletter_complete', {'status': 'complete'})
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

            # Optionally remove all checkpoints on success
            self._cleanup_checkpoints()

        except Exception as e:
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
                category = arxiv_config.get('main_category', 'cs')
                subcategories = arxiv_config.get('filter_categories', ['cs.ai', 'cs.cl', 'cs.lg', 'cs.ir', 'cs.ma', 'cs.cv'])
                
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
                
                # Check for existing papers to avoid duplicate processing
                new_mask = []
                if self.verbose:
                    print("🔍 Checking for existing papers in database...")
                
                for _, row in tqdm(data_df.iterrows(), total=len(data_df), 
                                  desc="Checking existing papers", disable=not self.verbose):
                    exists = (PaperRepository.exists_by_url(row["pdf_url"]) or 
                             PaperRepository.exists_by_title(row["title"]))
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
                
                # Embed abstracts
                abstracts = list(new_df['abstract'])
                embeddings = self.embedding_model.batch_invoke(abstracts)
                new_df['abstract_embedding'] = embeddings
                
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
                category = arxiv_config.get('main_category', 'cs')
                subcategories = arxiv_config.get('filter_categories', ['cs.ai', 'cs.cl', 'cs.lg', 'cs.ir', 'cs.ma', 'cs.cv'])
                
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
                        # Check if paper already has embedding
                        already_embedded_mask.append(existing_paper.get('embedding_model') is not None)
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
            # Stage 3: Embed Papers
            # -----------
            embedded_count = 0
            if len(papers_to_embed) > 0:
                if progress_callback:
                    progress_callback("embed", 36, "Starting paper embedding")
                    
                embedded_df = self._load_checkpoint('papers_embedded')
                if embedded_df is None:
                    if self.verbose:
                        print(f"\n🧠 STAGE 3: EMBEDDING {len(papers_to_embed)} PAPERS")
                        print("="*40)
                    
                    # Process in batches
                    batch_size = getattr(self, 'batch_size', 100)
                    all_embeddings = []
                    
                    for i in tqdm(range(0, len(papers_to_embed), batch_size), 
                                 desc="Embedding batches", disable=not self.verbose):
                        batch = papers_to_embed.iloc[i:i+batch_size]
                        abstracts = batch['abstract'].tolist()
                        
                        # Embed batch
                        embeddings = self.embedding_model.invoke(abstracts)
                        all_embeddings.extend(embeddings)
                        
                        # Update progress
                        if progress_callback:
                            embed_progress = 36 + (i / len(papers_to_embed)) * 40
                            progress_callback("embed", embed_progress, f"Embedded {min(i+batch_size, len(papers_to_embed))}/{len(papers_to_embed)} papers")
                    
                    # Add embeddings to dataframe
                    papers_to_embed['abstract_embedding'] = all_embeddings
                    papers_to_embed['cosine_similarity'] = [0.0] * len(papers_to_embed)  # No similarity calculation needed
                    
                    embedded_df = papers_to_embed
                    embedded_count = len(embedded_df)
                    self._save_checkpoint('papers_embedded', embedded_df)
                    
                    if self.verbose:
                        print(f"✅ Embedded {embedded_count} papers")
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