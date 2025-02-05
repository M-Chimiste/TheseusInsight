import os
import json
import gc
import shutil
import pickle
import random
import datetime
import warnings
from tqdm import tqdm
from dotenv import load_dotenv
import json_repair

from docling.document_converter import DocumentConverter

# Local application imports
from paperpal.communication import GmailCommunication, construct_email_body, upload_video
from paperpal.data_processing import ProcessData, PaperDatabase, Paper, Newsletter, Podcast
from paperpal.data_processing.data_handling import PaperDatabase, Paper, Newsletter, Logs
from paperpal.inference import SentenceTransformerInference
from paperpal.podcast import PaperPalPodcastGenerator
from paperpal.prompt import (
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
from paperpal.utils import cosine_similarity, get_n_days_ago, TODAY, purge_ollama_cache

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", None)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", None)
GMAIL_SENDER_ADDRESS = os.getenv("GMAIL_SENDER_ADDRESS", None)
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", None)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

INTRO_TEXT = [
    "This fascinating study sheds light on...",
    "This research shows that...",
    "This paper explores...",
    "This research discusses...",
    "This paper investigates..."
]

class PaperPal:
    def __init__(self,
                 research_interests_path="config/research_interests.txt",
                 n_days=7,
                 top_n=5,
                 start_date=None,
                 end_date=None,
                 use_different_models=True,
                 model_type="ollama",
                 model_name="hermes3",
                 orchestration_config="config/orchestration.json",
                 embedding_model_name="nomic-ai/modernbert-embed-base",
                 trust_remote_code=True,
                 receiver_address=None,
                 max_new_tokens=1024,
                 temperature=0.1,
                 cosine_similarity_threshold=0.5,
                 db_saving=True,
                 data_path="data/papers.db",
                 generate_podcast=True,
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
                 checkpoint_dir="checkpoints"
                ):
        self.verbose = verbose
        self.save_dialogue = save_dialogue
        self.checkpoint_dir = checkpoint_dir
        self.generate_email = generate_email
        self.publish_podcast = publish_podcast
        self.generate_podcast = generate_podcast
        
        # Email/Communication
        if receiver_address:
            if isinstance(receiver_address, str) and ',' in receiver_address:
                self.receiver_address = [addr.strip() for addr in receiver_address.split(',')]
            else:
                self.receiver_address = receiver_address
        else:
            self.receiver_address = None

        self.communication = GmailCommunication(
            sender_address=GMAIL_SENDER_ADDRESS,
            app_password=GMAIL_APP_PASSWORD,
            receiver_address=self.receiver_address
        )

        # Dates
        if start_date is None and end_date is None:
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
                raise ValueError("Dates must be in YYYY-MM-DD or MM-DD-YYYY format")

            self.start_date = try_parse_date(start_date) or get_n_days_ago(n_days)
            self.end_date = try_parse_date(end_date) or TODAY

        self.top_n = top_n
        self.model_type = model_type
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.cosine_similarity_threshold = cosine_similarity_threshold
        self.db_saving = db_saving
        
        # DB
        self.papers_db = PaperDatabase(data_path)
        
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
        with open(research_interests_path, 'r') as f:
            self.research_interests = f.read().strip()
        
        # Inference models
        self.use_different_models = use_different_models
        if use_different_models:
            with open(orchestration_config, 'r') as f:
                self.orchestration_config = json.load(f)

            # 1) Embedding model
            self.embedding_model_name = self.orchestration_config['embedding_model']['model_name']
            self.embedding_model = SentenceTransformerInference(
                self.embedding_model_name, 
                remote_code=self.orchestration_config['embedding_model']['trust_remote_code']
            )
            
            # 2) Load specialized LLMs
            self.judge_model_config = self.orchestration_config['judge_model']
            self.newsletter_model_config = self.orchestration_config['newsletter_model']
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
            self.newsletter_inference = self._load_inference_model(
                self.newsletter_model_config['model_type'],
                self.newsletter_model_config['model_name'],
                self.newsletter_model_config['max_new_tokens'],
                self.newsletter_model_config['temperature'],
                self.newsletter_model_config.get('num_ctx')
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
                self.podcast_generator = PaperPalPodcastGenerator(
                    text_model=self.podcast_inference,
                    tts_provider=self.orchestration_config.get('tts_model', {}).get('tts_provider', 'kokoro'),
                    speaker_1_voice=self.orchestration_config.get('tts_model', {}).get('speaker_1_voice', 'af_bella'),
                    speaker_1_speed=self.orchestration_config.get('tts_model', {}).get('speaker_1_speed', 1.0),
                    speaker_2_voice=self.orchestration_config.get('tts_model', {}).get('speaker_2_voice', 'am_adam'),
                    speaker_2_speed=self.orchestration_config.get('tts_model', {}).get('speaker_2_speed', 1.0),
                    instructions_template=INSTRUCTION_TEMPLATES,
                    intro_music_path=self.intro_music_path,
                    verbose=self.verbose
                )

        else:
            # Single model approach
            from .inference.llm import OllamaInference  # Example if all local
            self.embedding_model = SentenceTransformerInference(
                embedding_model_name,
                remote_code=trust_remote_code
            )
            self.inference = OllamaInference(
                model_name=model_name,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                url=OLLAMA_URL
            )
            # Podcast generator re-using the same inference
            self.podcast_generator = PaperPalPodcastGenerator(
                text_model=self.inference,
                tts_provider='kokoro',  # or your default
                speaker_1_voice='af_bella',
                speaker_1_speed=1.0,
                speaker_2_voice='am_adam',
                speaker_2_speed=1.0,
                instructions_template=INSTRUCTION_TEMPLATES,
                intro_music_path=self.intro_music_path,
                verbose=self.verbose
            )

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
        log = Logs(status_code=status_code, status=error_msg)
        self.papers_db.insert_log(log)

        # Send error notification email only once per run
        if not self.error_notified:
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

    def rank_papers(self, data_df):
        """Given embedded papers, use judge model to score them."""
        try:
            abstracts = list(data_df['abstract'])
            scores, related, rationale = [], [], []
            for abstract in tqdm(abstracts, disable=not self.verbose, desc="Ranking papers"):
                messages = [
                    {"role": "user", "content": research_prompt(self.research_interests, abstract)}
                ]
                # Depending on single-model or multi-model
                if not self.use_different_models:
                    # Example for Ollama only:
                    if self.inference.provider == "ollama":
                        response = self.inference.invoke(
                            messages=messages,
                            system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT,
                            schema=ResearchInterestsPromptData
                        )
                    else:
                        # For other providers
                        response = self.inference.invoke(
                            messages=messages,
                            system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT
                        )
                else:
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

                response_json = json_repair.loads(response)
                scores.append(int(response_json['score']))
                related.append(bool(response_json['related']))
                rationale.append(response_json['rationale'])

            data_df['score'] = scores
            data_df['related'] = related
            data_df['rationale'] = rationale
            data_df = data_df.sort_values(by='score', ascending=False)
            top_n_df = data_df.head(self.top_n)

            # Save all to DB if enabled
            for _, row in data_df.iterrows():
                paper = Paper(
                    title=row['title'],
                    abstract=row['abstract'],
                    url=row['url_pdf'],
                    date_run=TODAY.strftime('%Y-%m-%d'),
                    date=row['date'].strftime('%Y-%m-%d'),
                    score=row['score'],
                    related=row['related'],
                    rationale=row['rationale'],
                    cosine_similarity=row['cosine_similarity'],
                    embedding_model=self.embedding_model_name
                )
                if self.db_saving:
                    self.papers_db.insert_paper(paper)

            return top_n_df
        except Exception as e:
            self._log_error(500, e)
            raise

    def run(self, start_from: str = None):
        """
        Unified pipeline with checkpoints. 
        Harmonizes the old generate_newsletter_and_podcast() features:
         - Save newsletter to DB
         - Send email
         - Generate podcast (audio + optional visualizer)
         - Save dialogue JSON
         - Insert podcast into DB
         - Optionally publish to YouTube
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
            if start_from is None:
                # no stage specified, do we have an existing checkpoint for 'papers_downloaded'?
                data_df = self._load_checkpoint('papers_downloaded')
                if data_df is None:
                    if self.verbose:
                        print("No 'papers_downloaded' checkpoint. Starting fresh: downloading papers.")
                    process_data = ProcessData(start_date=self.start_date, end_date=self.end_date)
                    data_df = process_data.download_and_process_data(self.start_date, self.end_date)
                    self._save_checkpoint('papers_downloaded', data_df)
            else:
                # If we have a forced stage, see if the user wants to skip some
                if start_from == 'papers_downloaded':
                    data_df = self._load_checkpoint('papers_downloaded')
                    if data_df is None:
                        if self.verbose:
                            print("Forcing download stage.")
                        process_data = ProcessData(start_date=self.start_date, end_date=self.end_date)
                        data_df = process_data.download_and_process_data(self.start_date, self.end_date)
                        self._save_checkpoint('papers_downloaded', data_df)

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
                    if self.verbose:
                        print("Embedding papers...")

                    abstracts = list(data_df['abstract'])
                    abstract_embeddings = []
                    cosine_similarities = []
                    reserch_embedding = self.embedding_model.invoke(self.research_interests)

                    for abstract in tqdm(abstracts, disable=not self.verbose, desc="Embedding abstracts"):
                        abstract_embedding = self.embedding_model.invoke(abstract)
                        sim = cosine_similarity(abstract_embedding, reserch_embedding)
                        cosine_similarities.append(sim)
                        abstract_embeddings.append(abstract_embedding)

                    data_df['cosine_similarity'] = cosine_similarities
                    data_df['abstract_embedding'] = abstract_embeddings

                    # Filter by threshold
                    filtered_df = data_df[data_df['cosine_similarity'] >= self.cosine_similarity_threshold]
                    filtered_df = filtered_df.reset_index(drop=True)
                    
                    # Save checkpoint
                    self._save_checkpoint('papers_embedded', filtered_df)
                    embedded_df = filtered_df

            # -----------
            # Stage 3: Rank Papers
            # -----------
            if start_from is None or start_from in ['papers_embedded', 'papers_ranked']:
                top_n_df = self._load_checkpoint('papers_ranked')
                if top_n_df is None:
                    if embedded_df is None:
                        embedded_df = self._load_checkpoint('papers_embedded')
                        if embedded_df is None:
                            raise ValueError("No embedded papers found to rank.")
                    if self.verbose:
                        print("Ranking papers...")

                    top_n_df = self.rank_papers(embedded_df)
                    self._save_checkpoint('papers_ranked', top_n_df)

                # free memory from embeddings if needed
                del embedded_df
                gc.collect()

            # -----------
            # Stage 4: Generate Newsletter Sections
            # -----------
            if start_from is None or start_from in ['papers_ranked', 'newsletter_sections']:
                sections_data = self._load_checkpoint('newsletter_sections')
                if sections_data is None:
                    if top_n_df is None:
                        top_n_df = self._load_checkpoint('papers_ranked')
                        if top_n_df is None:
                            raise ValueError("No ranked papers found to generate newsletter sections.")

                    if self.verbose:
                        print("Generating newsletter sections (paper-by-paper) ...")

                    converter = DocumentConverter()
                    sections = []
                    urls_and_titles = []

                    for _, row in tqdm(top_n_df.iterrows(), total=len(top_n_df), desc="Sections"):
                        intro_text = random.choice(INTRO_TEXT)
                        
                        # Convert PDF to markdown
                        response = converter.convert(row['url_pdf'])
                        markdown = response.document.export_to_markdown()

                        # Summarize the PDF content
                        messages = [{"role": "user", "content": general_summary_prompt(markdown)}]
                        if not self.use_different_models:
                            if self.inference.provider == "ollama":
                                resp = self.inference.invoke(
                                    messages=messages,
                                    system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY,
                                    schema=SummaryPromptData
                                )
                            else:
                                resp = self.inference.invoke(
                                    messages=messages,
                                    system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY
                                )
                        else:
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
                        if not self.use_different_models:
                            if self.inference.provider == "ollama":
                                resp = self.inference.invoke(
                                    messages=messages,
                                    system_prompt=NEWSLETTER_SYSTEM_PROMPT,
                                    schema=NewsletterPromptData
                                )
                            else:
                                resp = self.inference.invoke(
                                    messages=messages,
                                    system_prompt=NEWSLETTER_SYSTEM_PROMPT
                                )
                        else:
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
                        urls_and_titles.append(f"{row['title']}: {row['url_pdf']}")

                    sections_data = {
                        'sections': sections,
                        'urls_and_titles': urls_and_titles
                    }
                    self._save_checkpoint('newsletter_sections', sections_data)

            # -----------
            # Stage 5: Generate Full Newsletter Content
            # -----------
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
                    joined_sections = "\n\n".join(sections)
                    intro_prompt = newsletter_intro_prompt(joined_sections)
                    messages = [{"role": "user", "content": intro_prompt}]

                    # Model call for the newsletter's intro
                    if not self.use_different_models:
                        if self.inference.provider == "ollama":
                            resp = self.inference.invoke(
                                messages=messages,
                                system_prompt=NEWSLETTER_SYSTEM_PROMPT,
                                schema=NewsletterPromptData
                            )
                        else:
                            resp = self.inference.invoke(
                                messages=messages,
                                system_prompt=NEWSLETTER_SYSTEM_PROMPT
                            )
                    else:
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
                        newsletter = Newsletter(
                            content=newsletter_content,
                            start_date=self.start_date.strftime('%Y-%m-%d'),
                            end_date=self.end_date.strftime('%Y-%m-%d'),
                            date_sent=TODAY.strftime('%Y-%m-%d')
                        )
                        self.papers_db.insert_newsletter(newsletter)

            # -----------
            # Stage 6: Send Email (if generate_email=True)
            # -----------
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
                urls_and_titles_bulleted = "\n".join(
                    f"{i+1}. {title}" for i, title in enumerate(sections_data['urls_and_titles'])
                )
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
                    self.papers_db.insert_log(
                        Logs(status_code=200, status=f"Successfully sent newsletter to {self.receiver_address}")
                    )
                except Exception as e:
                    self._log_error(500, e)
                    raise

            # -----------
            # Stage 7: Generate Podcast (if generate_podcast=True)
            # -----------
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
                        pdf_paths=list(top_n_df['url_pdf']),
                        paperpal_sections=sections_data['sections'],
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
                        pdf_paths=list(top_n_df['url_pdf']),
                        paperpal_sections=sections_data['sections'],
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
                        self.papers_db.insert_podcast(podcast)

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

            # -----------
            # Final Step: Mark completion, purge + cleanup
            # -----------
            self._save_checkpoint('newsletter_complete', {'status': 'complete'})
            if self.model_type == "ollama":
                purge_ollama_cache(OLLAMA_URL, self.model_name)

            # Log final success
            self.papers_db.insert_log(Logs(status_code=200, status="Successfully completed PaperPal run"))

            # Optionally remove all checkpoints on success
            self._cleanup_checkpoints()

        except Exception as e:
            self._log_error(500, e)
            raise
        finally:
            self._cleanup_temp_data()