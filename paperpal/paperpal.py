# Standard library imports
import json
import os
import random
import datetime
import gc
import warnings
import shutil
# Third-party imports
from dotenv import load_dotenv
import json_repair
from tqdm import tqdm
from docling.document_converter import DocumentConverter

# Local application imports
from .communication import GmailCommunication, construct_email_body, upload_video
from .data_processing import ProcessData, PaperDatabase, Paper, Newsletter, Podcast
from .data_processing.data_handling import PaperDatabase, Paper, Newsletter, Logs
from .inference import SentenceTransformerInference
from .podcast import PaperPalPodcastGenerator
# from .pdf import MarkdownParser, ArxivData, parse_pdf_to_markdown
from .prompt import (
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
from .utils import cosine_similarity, get_n_days_ago, TODAY, purge_ollama_cache

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", None)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", None)
GMAIL_SENDER_ADDRESS = os.getenv("GMAIL_SENDER_ADDRESS", None)
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", None)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

INTRO_TEXT = ["This fascinating study sheds light on...",
              "This research shows that...",
              "This paper explores...",
              "This research discusses...",
              "This paper investigates..."]


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
                 head_saw_period=1.5,
                 fade_time=1.5,
                 head_glow_passes=3,
                 head_glow_alpha_decay=50,
                 head_spawn_delay_range=(1.0,3.0),
                 wave_color="#d703fc",
                 trail_colors=["#fc03b6", "#ba03fc", "#ce6bf2"], 
                 glow_passes=3,
                 glow_alpha_decay=40,
                 line_width=6,
                 font_path = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                 verbose=True,
                 generate_email=True,
                 publish_podcast=False,
                 visualizer=False,
                ):
        self.verbose = verbose
        self.generate_email = generate_email
        self.research_interests_path = research_interests_path
        self.error_notified = False
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
                        return datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
                raise ValueError("Dates must be in YYYY-MM-DD or MM-DD-YYYY format")

            self.start_date = try_parse_date(start_date) or get_n_days_ago(n_days)
            self.end_date = try_parse_date(end_date) or TODAY
        self.start_date = get_n_days_ago(n_days)
        self.end_date = TODAY
        self.use_different_models = use_different_models
        self.top_n = top_n
        self.model_type = model_type
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
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
        self.papers_db = PaperDatabase(data_path)
        self.embedding_model_name = embedding_model_name
        self.embedding_model = SentenceTransformerInference(embedding_model_name, remote_code=trust_remote_code)
        self.cosine_similarity_threshold = cosine_similarity_threshold
        self.db_saving = db_saving
        
        # Podcast settings
        self.generate_podcast = generate_podcast
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
        self.head_saw_period = head_saw_period
        self.random_x_jitter = random_x_jitter
        self.fade_time = fade_time
        self.head_glow_passes = head_glow_passes
        self.head_glow_alpha_decay = head_glow_alpha_decay
        self.head_spawn_delay_range = head_spawn_delay_range
        self.wave_color = wave_color
        self.trail_colors = trail_colors
        self.glow_passes = glow_passes
        self.glow_alpha_decay = glow_alpha_decay
        self.line_width = line_width
        self.font_path = font_path
        self.publish_podcast = publish_podcast
        self.visualizer = visualizer
        
        # Load research interests
        try:
            with open(self.research_interests_path, 'r') as file:
                self.research_interests = file.read().strip()
        except FileNotFoundError as e:
            self._log_error(404, e)  # 404 Not Found
            raise
        except IOError as e:
            self._log_error(500, e)  # 500 Internal Server Error
            raise
        # Load inference model/s
        if not use_different_models:
            try:
                with open(orchestration_config, 'r') as f:
                    self.orchestration_config = json.load(f)
                self.inference = self._load_inference_model(self.orchestration_config['newsletter_model']['model_type'],
                                                            self.orchestration_config['newsletter_model']['model_name'],
                                                            self.orchestration_config['newsletter_model']['max_new_tokens'],
                                                            self.orchestration_config['newsletter_model']['temperature'],
                                                            self.orchestration_config['newsletter_model'].get('num_ctx', None))
            except Exception as e:
                warnings.warn(f'Error loading orchestration config: {e}. Using parameters will be deprecated. Use a config file instead with the key "newsletter_model"')
            self.inference = self._load_inference_model(self.model_type, model_name, max_new_tokens, temperature)
        
        if use_different_models:
            with open(orchestration_config, 'r') as f:
                self.orchestration_config = json.load(f)
            self.embedding_model_name = self.orchestration_config['embedding_model']['model_name']
            self.embedding_model = SentenceTransformerInference(embedding_model_name, remote_code=self.orchestration_config['embedding_model']['trust_remote_code'])
            self.judge_model_config = self.orchestration_config['judge_model']
            self.newsletter_model_config = self.orchestration_config['newsletter_model']
            self.content_extraction_model_config = self.orchestration_config['content_extraction_model']
            self.newsletter_sections_model_config = self.orchestration_config['newsletter_sections_model']
            self.newsletter_intro_model_config = self.orchestration_config['newsletter_intro_model']
            self.judge_inference = self._load_inference_model(self.judge_model_config['model_type'],
                                                                self.judge_model_config['model_name'],
                                                                self.judge_model_config['max_new_tokens'],
                                                                self.judge_model_config['temperature'],
                                                                self.judge_model_config.get('num_ctx', None))
            self.newsletter_inference = self._load_inference_model(self.newsletter_model_config['model_type'],
                                                                    self.newsletter_model_config['model_name'],
                                                                    self.newsletter_model_config['max_new_tokens'],
                                                                    self.newsletter_model_config['temperature'],
                                                                    self.newsletter_model_config.get('num_ctx', None))
            self.content_extraction_inference = self._load_inference_model(self.content_extraction_model_config['model_type'],
                                                                    self.content_extraction_model_config['model_name'],
                                                                    self.content_extraction_model_config['max_new_tokens'],
                                                                    self.content_extraction_model_config['temperature'],
                                                                    self.content_extraction_model_config.get('num_ctx', None))
            self.newsletter_sections_inference = self._load_inference_model(self.newsletter_sections_model_config['model_type'],
                                                                    self.newsletter_sections_model_config['model_name'],
                                                                    self.newsletter_sections_model_config['max_new_tokens'],
                                                                    self.newsletter_sections_model_config['temperature'],
                                                                    self.newsletter_sections_model_config.get('num_ctx', None))
            self.newsletter_intro_inference = self._load_inference_model(self.newsletter_intro_model_config['model_type'],
                                                                    self.newsletter_intro_model_config['model_name'],
                                                                    self.newsletter_intro_model_config['max_new_tokens'],
                                                                    self.newsletter_intro_model_config['temperature'],
                                                                    self.newsletter_intro_model_config.get('num_ctx', None))
            if self.generate_podcast:
                self.podcast_inference = self.orchestration_config.get('podcast_model', None)
                if not self.podcast_inference:
                    raise ValueError("Podcast model is not set. Please check your orchestration config file.")
        if self.generate_podcast:
            if self.verbose:
                print("Initializing podcast generator...")
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

    def _log_error(self, status_code: int, error: Exception):
        """
        Helper method to log errors to the database and send error notification.
        
        Args:
            status_code (int): HTTP status code representing the error type
            error (Exception): The exception that was raised
        """
        error_msg = f"{type(error).__name__}: {str(error)}"
        log = Logs(
            status_code=status_code,
            status=error_msg
        )
        self.papers_db.insert_log(log)
        
        # Send error notification email only if we haven't sent one for this error yet
        if not self.error_notified:
            try:
                self.communication.send_error_notification(error_msg)
                self.error_notified = True
            except Exception as e:
                print(f"Failed to send error notification: {str(e)}")

    def _load_inference_model(self, model_type, model_name, max_new_tokens, temperature, num_ctx=None):
        """Load the appropriate inference model based on model type.
        
        Args:
            model_type (str): Type of model to load ('anthropic', 'openai', or 'ollama')
            model_name (str): Name of the specific model to load
            max_new_tokens (int): Maximum number of tokens to generate
            temperature (float): Temperature parameter for generation
            
        Returns:
            The loaded inference model object
            
        Raises:
            ValueError: If model_type is invalid or required API keys are missing
        """
        try:
            model_type = os.getenv("MODEL_TYPE") or model_type
            
            if model_type == "anthropic":
                if ANTHROPIC_API_KEY is None:
                    raise ValueError("Anthropic API key is not set. Please check your .env file and ensure ANTHROPIC_API_KEY is properly configured.")
                from .inference.llm import AnthropicInference
                return AnthropicInference(model_name, max_new_tokens, temperature)
            
            elif model_type == "openai":
                if OPENAI_API_KEY is None:
                    raise ValueError("OpenAI API key is not set. Please check your .env file and ensure OPENAI_API_KEY is properly configured.")
                from .inference.llm import OpenAIInference
                return OpenAIInference(model_name, max_new_tokens, temperature)

            elif model_type == "gemini":
                if GOOGLE_API_KEY is None:
                    raise ValueError("Google API key is not set. Please check your .env file and ensure GOOGLE_API_KEY is properly configured.")
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
                raise ValueError(f"Invalid model type: {model_type}. Must be one of 'local', 'anthropic', 'openai', or 'ollama'.")
        except Exception as e:
            self._log_error(500, e)  # 500 Internal Server Error
            raise
        
        
    def download_and_process_papers(self):
        """
        Downloads papers from PapersWithCode based on research interests and date range.
        """
        if self.verbose:
            print("Downloading and processing papers...")
        try:
            process_data = ProcessData(start_date=self.start_date, end_date=self.end_date)
            
            data_df = process_data.download_and_process_data(start_date=self.start_date, end_date=self.end_date)

            abstracts = list(data_df['abstract'])
            abstract_embeddings = []
            cosine_similarities = []
            reserch_embedding = self.embedding_model.invoke(self.research_interests)
            for abstract in tqdm(abstracts, disable=not self.verbose, desc="Embedding abstracts"):
                abstract_embedding = self.embedding_model.invoke(abstract)
                cosine_sim = cosine_similarity(abstract_embedding, reserch_embedding)
                cosine_similarities.append(cosine_sim)
                abstract_embeddings.append(abstract_embedding)
            
            data_df['cosine_similarity'] = cosine_similarities
            data_df['abstract_embedding'] = abstract_embeddings
            # Filter the dataframe based on cosine similarity threshold
            filtered_df = data_df[data_df['cosine_similarity'] >= self.cosine_similarity_threshold]

            # Reset the index of the filtered dataframe
            filtered_df = filtered_df.reset_index(drop=True)

            # Update data_df with the filtered results
            data_df = filtered_df

            return data_df
        except Exception as e:
            self._log_error(500, e)  # 500 Internal Server Error
            raise
    

    def rank_papers(self, data_df):
        """Evaluates remaining papers and ranks them with the generative model."""
        try:
            abstracts = list(data_df['abstract'])
            scores = []
            related = []
            rationale = []
            for abstract in tqdm(abstracts, disable=not self.verbose, desc="Ranking papers"):
                try:
                    messages = [{"role": "user", "content": research_prompt(self.research_interests, abstract)}]
                    if not self.use_different_models:
                        if self.inference.provider == "ollama":
                            response = self.inference.invoke(messages=messages, system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT, schema=ResearchInterestsPromptData)
                        else:
                            response = self.inference.invoke(messages=messages, system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT)
                    else:
                        if self.judge_inference.provider == "ollama":
                            response = self.judge_inference.invoke(messages=messages, system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT, schema=ResearchInterestsPromptData)
                        elif self.judge_inference.provider == "anthropic":
                            messages.append({"role": "user", "assistant": "{"})
                            response = self.judge_inference.invoke(messages=messages, system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT)
                            response = "{" + response
                        else:
                            response = self.judge_inference.invoke(messages=messages, system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT)
                    response_json = json_repair.loads(response)
                    scores.append(int(response_json['score']))
                    related.append(bool(response_json['related']))
                    rationale.append(response_json['rationale'])
                except Exception as e:
                    self._log_error(500, e)  # 500 Internal Server Error
                    raise
            
            data_df['score'] = scores
            data_df['related'] = related
            data_df['rationale'] = rationale
            # Sort the DataFrame by score in descending order
            data_df = data_df.sort_values(by='score', ascending=False)
            top_n_df = data_df.head(self.top_n)

            # Convert each row of the data_df to a Paper class and place them into a list
            papers = []
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
                papers.append(paper)
                if self.db_saving:
                    self.papers_db.insert_paper(paper)
            return top_n_df
        except Exception as e:
            self._log_error(500, e)  # 500 Internal Server Error
            raise
    

    def generate_newsletter_and_podcast(self, top_n_df):
        """Generates a newsletter from the ranked papers."""
        try:
            # content = []
            sections = []
            urls_and_titles = []
            converter = DocumentConverter()
            total_rows = len(top_n_df)
            for i, (_, row) in enumerate(tqdm(top_n_df.iterrows(), total=total_rows, desc="Generating newsletter sections", disable=not self.verbose)):
                try:
                    intro_text = random.choice(INTRO_TEXT)
                    response = converter.convert(row['url_pdf'])
                    markdown = response.document.export_to_markdown()
                    messages = [{"role": "user", "content": general_summary_prompt(markdown)}]
                    if not self.use_different_models:
                        if self.inference.provider == "ollama":
                            response = self.inference.invoke(messages=messages, system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY, schema=SummaryPromptData)
                        elif self.inference.provider == "anthropic":
                            messages.append({"role": "user", "assistant": "{"})
                            response = self.inference.invoke(messages=messages, system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY)
                            response = "{" + response
                        else:
                            response = self.inference.invoke(messages=messages, system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY)
                    else:
                        if self.content_extraction_inference.provider == "ollama":
                            response = self.content_extraction_inference.invoke(messages=messages, system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY, schema=SummaryPromptData)
                        elif self.content_extraction_inference.provider == "anthropic":
                            messages.append({"role": "user", "assistant": "{"})
                            response = self.content_extraction_inference.invoke(messages=messages, system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY)
                            response = "{" + response
                        else:
                            response = self.content_extraction_inference.invoke(messages=messages, system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY)
                    response_json = json_repair.loads(response)
                    try:
                        summarized_paper = response_json['content']
                    except:
                        summarized_paper = response

                    context = f"Title: {row['title']}\nAbstract: {row['abstract']}\nRationale: {row['rationale']}\nSummary: {summarized_paper}"
                    messages = [{"role": "user", "content": newsletter_context_prompt(self.research_interests, context, intro_text)}]
                    
                    if not self.use_different_models:
                        if self.inference.provider == "ollama":
                            response = self.inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT, schema=NewsletterPromptData)
                        elif self.inference.provider == "anthropic":
                            messages.append({"role": "user", "assistant": "{"})
                            response = self.inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT)
                            response = "{" + response
                        else:
                            response = self.inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT)
                    else:
                        if self.newsletter_sections_inference.provider == "ollama":
                            response = self.newsletter_sections_inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT, schema=NewsletterPromptData)
                        elif self.newsletter_sections_inference.provider == "anthropic":
                            messages.append({"role": "user", "assistant": "{"})
                            response = self.newsletter_sections_inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT)
                            response = "{" + response
                        else:
                            response = self.newsletter_sections_inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT)
                    response_json = json_repair.loads(response)
                    draft = f"## {row['title']}\n\n{response_json['draft']}"
                    sections.append(draft)
                    urls_and_titles.append(f"{row['title']}: {row['url_pdf']}")
                except Exception as e:
                    self._log_error(500, e)  # 500 Internal Server Error
                    raise
            # Format urls and titles as numbered markdown list
            urls_and_titles = "\n".join(f"{i+1}. {title}" for i, title in enumerate(urls_and_titles))
            sections = "\n".join(sections)
            intro_prompt = newsletter_intro_prompt(sections)
            if self.verbose:
                print("Generating newsletter intro...")
            messages = [{"role": "user", "content": intro_prompt}]
            if not self.use_different_models:
                if self.inference.provider == "ollama":
                    newsletter_intro = self.inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT, schema=NewsletterPromptData)
                elif self.inference.provider == "anthropic":
                    messages.append({"role": "user", "assistant": "{"})
                    newsletter_intro = self.inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT)
                    newsletter_intro = "{" + newsletter_intro
                else:
                    newsletter_intro = self.inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT)
            else:
                if self.newsletter_intro_inference.provider == "ollama":
                    newsletter_intro = self.newsletter_intro_inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT, schema=NewsletterPromptData)
                elif self.newsletter_intro_inference.provider == "anthropic":
                    messages.append({"role": "user", "assistant": "{"})
                    newsletter_intro = self.newsletter_intro_inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT)
                    newsletter_intro = "{" + newsletter_intro
                else:
                    newsletter_intro = self.newsletter_intro_inference.invoke(messages=messages, system_prompt=NEWSLETTER_SYSTEM_PROMPT)
            try:
                newsletter_intro_json = json_repair.loads(newsletter_intro)
                newsletter_intro = newsletter_intro_json['draft']
            except:
                newsletter_intro = newsletter_intro
            
            newsletter_content = f"{newsletter_intro}\n{sections}"
            
            newsletter = Newsletter(
                content=newsletter_content,
                start_date=self.start_date.strftime('%Y-%m-%d'),
                end_date=self.end_date.strftime('%Y-%m-%d'),
                date_sent=TODAY.strftime('%Y-%m-%d')
            )
            if self.db_saving:  
                self.papers_db.insert_newsletter(newsletter)
            if self.generate_podcast:
                podcast_content = self.podcast_generator.generate_podcast(
                    pdf_paths=top_n_df['url_pdf'],
                    paperpal_sections=sections,
                    output_format=self.output_format,
                    output_dir=self.output_dir,
                    prefix=self.prefix,
                    final_filename=self.final_filename,
                    verbose=self.verbose,
                    visualizer=self.visualizer,
                    # Visualizer Settings
                    resolution=self.resolution,
                    fps=self.fps,
                    matrix_count=self.matrix_count,
                    matrix_head_color=self.matrix_head_color,   # short hex for bright green
                    matrix_tail_color=self.matrix_tail_color,  # hex for (0,176,0)
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
                    font_path=self.font_path)
                
            if self.visualizer:
                podcast_path = podcast_content['visualizer_path']
            else:
                podcast_path = podcast_content['final_podcast_path']
            
            podcast = Podcast(
                title=self.final_filename,
                date=TODAY.strftime('%Y-%m-%d'),
                script=podcast_content['dialogue'],
                description=podcast_content['description'],
            )
            if self.db_saving:
                self.papers_db.insert_podcast(podcast)
            if self.generate_email:
                if self.verbose:
                    print("Constructing email body...")
                email_body = construct_email_body(newsletter_content, self.start_date.strftime('%Y-%m-%d'), self.end_date.strftime('%Y-%m-%d'), urls_and_titles)
                try:
                    self.communication.compose_message(email_body, self.start_date, self.end_date)
                    self.communication.send_email()
                    # Log successful email sending
                    log = Logs(
                        status_code=200,
                        status=f"Successfully sent newsletter to {self.receiver_address}"
                    )
                    self.papers_db.insert_log(log)
                except Exception as e:
                    self._log_error(500, e)
                    raise
            if self.publish_podcast:
                if self.verbose:
                    print("Publishing podcast to YouTube, this may take a while...")
                response = upload_video(podcast_path, podcast.title, podcast.description)
        except Exception as e:
            self._log_error(500, e)
            raise

    def run(self):
        """Runs the PaperPal system."""
        try:
            data_df = self.download_and_process_papers()
            top_n_df = self.rank_papers(data_df)
            del data_df
            self.embedding_model = None
            gc.collect()
            self.generate_newsletter_and_podcast(top_n_df)
            if self.model_type == "ollama":
                purge_ollama_cache(OLLAMA_URL, self.model_name)
            
            # Log successful completion
            log = Logs(
                status_code=200,  # 200 OK
                status="Successfully completed PaperPal run"
            )
            self.papers_db.insert_log(log)
            
        except Exception as e:
            self._log_error(500, e)  # 500 Internal Server Error
            raise
        finally:
            # Clean up temp_data folder regardless of success or failure
            try:
                temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'temp_data')
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    if self.verbose:
                        print("Cleaned up temp_data directory")
            except Exception as cleanup_error:
                print(f"Warning: Failed to clean up temp_data directory: {cleanup_error}")
                self._log_error(500, cleanup_error)
        
if __name__ == "__main__":
    paperpal = PaperPal(
                 research_interests_path="config/research_interests.txt",
                 n_days=7,
                 top_n=10,
                 model_type="ollama",
                 model_name="hermes3",
                 embedding_model_name="Alibaba-NLP/gte-base-en-v1.5",
                 trust_remote_code=True,
                 receiver_address=None,
                 max_new_tokens=1024,
                 temperature=0.1,
                 cosine_similarity_threshold=0.5,
                 db_saving=True,
                 data_path="data/papers.db",
                 verbose=True)
    paperpal.run()