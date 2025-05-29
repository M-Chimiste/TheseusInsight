import os
import json_repair
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from pydantic import ValidationError
from pydub import AudioSegment
from tqdm import tqdm
from ..inference import (
                         PollyTTSInference,
                         OpenAITTSInference,
                        LLMModelFactory)
from .visualizer import generate_visualizer_video
from ..prompt import (INSTRUCTION_TEMPLATES, 
                      PODCAST_SUMMARY_SYSTEM_PROMPT,
                      SUMMARY_SYSTEM_PROMPT,
                      summary_prompt,
                      podcast_description)
from ..data_model import (Dialogue,
                          DialogueItem,
                          DialogueOutput,
                          PodcastDescription,
                          ContentSummary)
from ..data_model.data_handling import PaperDatabase, Podcast
from ..pdf import SpacyLayoutDocProcessor
from datetime import datetime, date


@dataclass
class SegmentInfo:
    """
    Metadata for a rendered speech chunk.
    label: 'intro', 'segment_1'…'segment_n', or 'outro'
    path : file path on disk
    """
    label: str
    path: str


class PodcastGenerator:
    def __init__(
        self,
        text_model: dict = {
            "model_name": "gemini-2.0-flash",
            "model_type": "gemini",       # 'anthropic', 'ollama', 'openai', or 'gemini'
            "max_new_tokens": 8192,
            "temperature": 0.1,
            "num_ctx": 131072
        },
        tts_provider: str = "openai",        #  'polly', or 'openai'
        speaker_1_voice: str = "sage",
        speaker_1_speed: float = 1.15,
        speaker_2_voice: str = "ash",
        speaker_2_speed: float = 1.15,
        instructions_template: dict = INSTRUCTION_TEMPLATES,
        intro_music_path: str = None,
        pause_duration: float = 0.5,
        verbose: bool = False,
        db_url: str = None
    ):
        """
        Set up the class with your default settings.
        
        Args:
            text_model (dict): Configuration for the text generation model
            tts_provider (str): TTS provider to use ( 'polly', or 'openai')
            speaker_1_voice (str): Voice ID for speaker 1 (provider-specific)
            speaker_1_speed (float): Speed factor for speaker 1
            speaker_2_voice (str): Voice ID for speaker 2 (provider-specific)
            speaker_2_speed (float): Speed factor for speaker 2
            instructions_template (dict): Instructions template to use for prompting
            intro_music_path (str): Path to intro music file
            pause_duration (float): Duration of silence in seconds to add between major segments
            verbose (bool): Whether to print verbose output
            db_url (str): PostgreSQL database connection URL
        """
        self.verbose = verbose
        self.text_model_config = text_model
        self.tts_provider = tts_provider.lower()
        self.instructions_template = instructions_template
        self.intro_music_path = intro_music_path
        self.pause_duration = pause_duration
        self.intro, self.section, self.outro = self._parse_prompts(instructions_template)
        self.db_url = db_url
        if self.db_url:
            self.db = PaperDatabase(self.db_url)
        else:
            self.db = None
        # Validate TTS provider
        valid_providers = ['polly', 'openai']
        if self.tts_provider not in valid_providers:
            raise ValueError(f"Invalid TTS provider: {tts_provider}. Must be one of {valid_providers}")
        
        self.pdf_processor = SpacyLayoutDocProcessor(language="en",
                table_format='csv',
                verbose=self.verbose,
                export_tables=False, 
                export_figures=False,
                save_text=False,
                remove_md_image_tags=True)
        
        # Initialize text inference model
        model_type = self.text_model_config["model_type"]
        model_params = {
            "model_name": self.text_model_config["model_name"],
            "max_new_tokens": self.text_model_config["max_new_tokens"],
            "temperature": self.text_model_config["temperature"]
        }
        
        if model_type == "ollama" and "num_ctx" in self.text_model_config:
            model_params["num_ctx"] = self.text_model_config["num_ctx"]
        
        self.text_inference = LLMModelFactory.create_model(model_type, **model_params)

        # Initialize TTS models based on provider
       
        if self.tts_provider == 'polly':
            self.tts_speaker_1 = PollyTTSInference(
                voice_name=speaker_1_voice,
                speaker_speed=speaker_1_speed,
                verbose=self.verbose
            )
            self.tts_speaker_2 = PollyTTSInference(
                voice_name=speaker_2_voice,
                speaker_speed=speaker_2_speed,
                verbose=self.verbose
            )
        else:  # openai
            self.tts_speaker_1 = OpenAITTSInference(
                voice_name=speaker_1_voice,
                speaker_speed=speaker_1_speed,
                verbose=self.verbose
            )
            self.tts_speaker_2 = OpenAITTSInference(
                voice_name=speaker_2_voice,
                speaker_speed=speaker_2_speed,
                verbose=self.verbose
            )

    def _parse_prompts(self, template: dict):
        """
        Parses the given template dictionary to extract the intro, section, and outro prompts for the podcast.

        This method takes a template dictionary as input and extracts the intro, section, and outro prompts for the podcast. It returns these prompts as a tuple of three strings.

        Args:
            template (dict): A dictionary containing the template information for the podcast.

        Returns:
            tuple: A tuple containing the intro, section, and outro prompts as strings.
        """
        intro = template["podcast_into"]
        section = template["podcast_section"]
        outro = template["podcast_outro"]
        return intro, section, outro
    
    def _get_podcast_description(self, text: str) -> str:
        """
        Extracts a podcast description from the provided text.

        This method takes a text input and generates a podcast description based on it. It leverages the text inference model to generate a summary of the text, which is then returned as the podcast description.

        Args:
            text (str): The text from which to extract the podcast description.

        Returns:
            str: A summary of the text, serving as the podcast description.
        """
        system_prompt = PODCAST_SUMMARY_SYSTEM_PROMPT
        user_prompt = podcast_description(text)
        messages = [{"role": "user", "content": user_prompt}]

        if self.text_inference.provider == "ollama":
            raw_response = self.text_inference.invoke(
                messages, 
                system_prompt=system_prompt,
                schema=PodcastDescription
            )
        elif self.text_inference.provider == "anthropic":
            messages.append({"role": "assistant", "content": "{"})
            raw_response = self.text_inference.invoke(messages, system_prompt=system_prompt)
            raw_response = "{" + raw_response
        else:
            raw_response = self.text_inference.invoke(
                messages, 
                system_prompt=system_prompt
            )
        try:
            data = json_repair.loads(raw_response)
            return data["description"]
        except Exception as e:
            print(f"Error parsing description JSON: {str(e)}")
            return "A podcast episode generated by Theseus Insight."
    

    def _get_dialogue(
        self,
        text: str,
        template_instructions: str,
        section_type: str
    ) -> Dialogue:
        """
        Generates dialogue for a podcast episode based on provided text and template instructions.

        This method takes in text, template instructions, and a section type to generate dialogue for a podcast episode. It leverages the text inference model to generate a dialogue structure based on the provided text and template instructions. The generated dialogue is then returned as a Dialogue object.

        Args:
            text (str): The text from which to generate the dialogue.
            template_instructions (str): The template instructions to guide the dialogue generation.
            section_type (str): The type of section for which the dialogue is being generated (e.g., intro, section, outro).

        Returns:
            Dialogue: A Dialogue object containing the generated dialogue.
        """
        system_prompt = """
You are an advanced assistant that returns a JSON with the structure:
{"dialogue":[{"speaker":"speaker-1","text":"some text"}, ... ]}
No other text outside JSON. There are only two speakers on the podcast: speaker-1 and speaker-2.
        """.strip()

        # Build a single "user" message from all the instructions
        # If you prefer multiple steps, you can do that. 
        user_content = (
            f"{template_instructions}\n"
            f"Here is your input text:\n{text}\n"
        )

        messages = [{"role": "user", "content": user_content}]
        if self.verbose:
            print(f"Sending messages to LLM")
        # Use schema for Ollama, standard generation for others
        if self.text_inference.provider == "ollama":
            raw_response = self.text_inference.invoke(
                messages, 
                system_prompt=system_prompt,
                schema=DialogueOutput
            )
        else:
            if self.text_inference.provider == "anthropic":
                messages.append({"role": "assistant", "content": "{"})
            raw_response = self.text_inference.invoke(messages, system_prompt=system_prompt)
            if self.text_inference.provider == "anthropic":
                raw_response = "{" + raw_response

        data = json_repair.loads(raw_response)
        if self.verbose:
            print("LLM response received")
        # Validate with Pydantic
        dialogue_obj = self._validate_dialogue_data(data, section_type)
        if self.verbose:
            print(f"Dialogue object validated")
        return dialogue_obj
    

    def _validate_dialogue_data(self, data: dict, section_type: str):
        """
        Validates and processes dialogue data from a given dictionary.
        This method checks if the provided data contains a "dialogue" key with a list of dialogue items.
        Each item in the list is validated and converted into a DialogueItem object. If any item is invalid,
        it is skipped, and an error message is printed. If no valid items are found, the method returns None.
        Additionally, the method handles an optional "scratchpad" value from the data dictionary.
        Args:
            data (dict): The dictionary containing dialogue data to be validated.
        Returns:
            Dialogue: A Dialogue object containing the validated dialogue items and scratchpad value,
                      or None if validation fails.
        """
        try:
            if "dialogue" not in data or not isinstance(data["dialogue"], list):
                return None
            
            valid_items = []
            for item in data["dialogue"]:
                try:
                    # Pass segment_label as section_type
                    di = DialogueItem(
                        text=item["text"],
                        speaker=item["speaker"],
                        segment_label=section_type
                    )
                    valid_items.append(di)
                except ValidationError as ve:
                    import traceback
                    print(f"Skipping invalid dialogue line: {item}\nError: {ve}\nTraceback:\n{traceback.format_exc()}")
                    continue
            
            if not valid_items:
                return None
            
            # Create the pydantic model
            try:
                # We pass the validated items plus the section type
                dialogue_obj = Dialogue(
                    dialogue=valid_items,
                    section_type=section_type
                )
                return dialogue_obj
            except ValidationError as ve:
                import traceback
                error_msg = f"Could not build final Dialogue object: {ve}\nTraceback:\n{traceback.format_exc()}"
                print(error_msg)
                return None
        except Exception as e:
            import traceback
            error_msg = f"Error in _validate_dialogue_data: {str(e)}\nTraceback:\n{traceback.format_exc()}"
            print(error_msg)
            return None

    def _process_pdf(self, pdf_path: str) -> str:
        """
        This method processes a PDF file.

        It takes a path to a PDF file as input and uses the pdf_processor to process the document. The processed data is then returned.

        Args:
            pdf_path (str): The path to the PDF file to be processed.

        Returns:
            str: The processed data from the PDF file.
        """
        pdf_processor = self.pdf_processor
        pdf_text = pdf_processor.process_document(pdf_path)
        return pdf_text["processed_data"]
    
    def _get_text_summary(self, text: str) -> str:
        """
        Generates a summary of the given text.

        This method takes a text input and uses the configured text inference model to generate a summary of the text. The summary is then returned.

        Args:
            text (str): The text to be summarized.

        Returns:
            str: A summary of the input text.
        """
        system_prompt = SUMMARY_SYSTEM_PROMPT
        user_prompt = summary_prompt(text)
        messages = [{"role": "user", "content": user_prompt}]
        if self.text_inference.provider == "ollama":
            raw_response = self.text_inference.invoke(
                messages, 
                system_prompt=system_prompt,
                schema=ContentSummary
            )
        elif self.text_inference.provider == "anthropic":
            messages.append({"role": "assistant", "content": "{"})
            raw_response = self.text_inference.invoke(messages, system_prompt=system_prompt)
            if self.text_inference.provider == "anthropic":
                raw_response = "{" + raw_response
        else:
            raw_response = self.text_inference.invoke(messages, system_prompt=system_prompt)
        data = json_repair.loads(raw_response)
        return data.get("summary", "")

    def generate_podcast(
        self,
        pdf_paths: List[str] | str,
        output_format: str = "mp3",
        output_dir: str = "output_audio",
        prefix: str = "podcast_segment",
        final_filename: str = "podcast_final",
        verbose: bool = None,
        visualizer: bool = False,
        intro_music_path: str = None,
        # Visualizer Settings
        resolution: tuple = (1920, 1080),
        fps: int = 30,
        matrix_count=200,
        matrix_head_color="#e0ffe7",   # short hex for bright green
        matrix_tail_color="0x00b000",  # hex for (0,176,0)
        matrix_char_size=24,
        head_step_time=0.25,
        random_x_jitter=2.0,
        fade_time=3.0,
        head_glow_passes=3,
        head_glow_alpha_decay=50,
        head_spawn_delay_range=(1.0,3.0),
        head_saw_period=1.5,
        wave_color="#d703fc",
        trail_colors=["#fc03b6", "#ba03fc", "#ce6bf2"], 
        glow_passes=3,
        glow_alpha_decay=40,
        line_width=6,
        font_path=None,
        progress_callback=None
    ) -> Dict[str, str]:
        """
        Generate a podcast from a given set of PDFs.

        This method takes a list of PDF paths or a single PDF path as input and generates a podcast based on the provided settings.
        It supports various output formats, including MP3, and allows for customization of the output directory, 
        filename prefix, and final filename. Additionally, it provides options for speaker voices and speeds, 
        as well as visualizer settings.

        Args:
            pdf_paths (List[str] | str): A list of PDF paths or a single PDF path.
            output_format (str, optional): The output format of the podcast. Defaults to "mp3".
            output_dir (str, optional): The directory where the output files will be saved. Defaults to "output_audio".
            prefix (str, optional): The prefix to use for the output filenames. Defaults to "podcast_segment".
            final_filename (str, optional): The final filename for the podcast. Defaults to "podcast_final".
            verbose (bool, optional): Whether to print verbose output. Defaults to None.
            visualizer (bool, optional): Whether to generate a visualizer video. Defaults to False.
            intro_music_path (str, optional): The path to the intro music file. Defaults to None.
            resolution (tuple, optional): The resolution of the visualizer video. Defaults to (1920, 1080).
            fps (int, optional): The frames per second of the visualizer video. Defaults to 30.
            matrix_count (int, optional): The number of matrices in the visualizer. Defaults to 200.
            matrix_head_color (str, optional): The color of the matrix head. Defaults to "#e0ffe7".
            matrix_tail_color (str, optional): The color of the matrix tail. Defaults to "0x00b000".
            matrix_char_size (int, optional): The size of the matrix characters. Defaults to 24.
            head_step_time (float, optional): The time between head steps. Defaults to 0.25.
            random_x_jitter (float, optional): The amount of random jitter in the x-axis. Defaults to 2.0.
            fade_time (float, optional): The time it takes for characters to fade. Defaults to 3.0.
            head_glow_passes (int, optional): The number of glow passes for the head. Defaults to 3.
            head_glow_alpha_decay (int, optional): The alpha decay for the head glow. Defaults to 50.
            head_spawn_delay_range (tuple, optional): The range of delay times for head spawning. Defaults to (1.0, 3.0).
            head_saw_period (float, optional): The period of the saw wave for the head. Defaults to 1.5.
            wave_color (str, optional): The color of the wave. Defaults to "#d703fc".
            trail_colors (list, optional): A list of colors for the trail. Defaults to ["#fc03b6", "#ba03fc", "#ce6bf2"].
            glow_passes (int, optional): The number of glow passes. Defaults to 3.
            glow_alpha_decay (int, optional): The alpha decay for the glow. Defaults to 40.
            line_width (int, optional): The width of the line. Defaults to 6.
            font_path (str, optional): The path to the font file. Defaults to None.
            progress_callback (callable, optional): A callback function to report progress. Defaults to None.

        Returns:
            Dict[str, str]: A dictionary containing the transcript, dictionary transcript, segments, final podcast path, and visualizer path.
        """
        intro_music_path = intro_music_path or self.intro_music_path
        try:
            # Create output directory if it doesn't exist
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            if progress_callback:
                progress_callback("Processing PDFs", 0)
                
            # 1) Process PDFs / Extract text and summaries
            if isinstance(pdf_paths, str):
                pdf_paths = [pdf_paths]
           
                
            texts = []
            summaries = []
            for i, pdf_path in enumerate(pdf_paths):
                if progress_callback:
                    progress_callback("Processing PDFs", (i / len(pdf_paths)) * 20)
                text = self._process_pdf(pdf_path)
                texts.append(text)
                summary = self._get_text_summary(text)
                summaries.append(summary)
            
            if progress_callback:
                progress_callback("Generating podcast description", 25)
                
            # 2) Get podcast description
            description = self._get_podcast_description("\n".join(summaries))
            
            if progress_callback:
                progress_callback("Generating dialogue", 30)
            
            # 3) Generate dialogue
            sections = []
            for i, text in enumerate(texts):
                dialogue = self._get_dialogue(text=text, template_instructions= self.section, section_type=f"section_{i}")
                sections.append(dialogue)

            # 4) Create podcast introduction
            introduction = self._get_dialogue(text="\n".join(summaries), template_instructions=self.intro, section_type="intro")

            scripts = []
            scripts.append(introduction)
            scripts.extend(sections)

            merged_dialogue = Dialogue.merge_outputs(scripts)

            # 5) Create podcast outro
            outro = self._get_dialogue(text=str(merged_dialogue), template_instructions=self.outro, section_type="outro")
            
            # 6) Merge scripts
            scripts.append(outro)

            dialogue = Dialogue.merge_outputs(scripts)
            if not dialogue:
                raise ValueError("Failed to generate dialogue")
            
            if progress_callback:
                progress_callback("Converting text to speech", 50)
                
            # Convert dialogue to audio segments
            segments: List[SegmentInfo] = []
            full_transcript: List[str] = []
            total_lines = len(dialogue.dialogue)
            for i, item in enumerate(dialogue.dialogue):
                if progress_callback:
                    progress = 50 + ((i + 1) / total_lines) * 30
                    progress_callback("Converting text to speech", progress)

                speaker = item.speaker.lower().strip()
                text = item.text.strip()
                tts = self.tts_speaker_1 if speaker == "speaker-1" else self.tts_speaker_2
                out_path = os.path.join(str(output_dir), f"{prefix}_{i:03}.{output_format}")
                tts.invoke(text=text, save_file=True, file_path=out_path, format=output_format)

                # Use the actual segment_label from the DialogueItem instead of inferring from position
                label = item.segment_label

                segments.append(SegmentInfo(label=label, path=out_path))
                # Include segment_label in transcript for clarity
                full_transcript.append(f"{speaker} [{item.segment_label}]: {text}")

            if progress_callback:
                progress_callback("Combining audio segments", 85)

            # Combine segments
            final_audio_path = f"{output_dir}/{final_filename}.{output_format}"
            self._combine_audio_segments(segments, final_audio_path, output_format, intro_music_path)
            
            if visualizer:
                if progress_callback:
                    progress_callback("Generating visualizer", 90)
                    
                # Generate visualizer video
                final_video_path = f"{output_dir}/{final_filename}.mp4"
                generate_visualizer_video(
                    audio_filepath=final_audio_path,
                    output_filepath=final_video_path,
                    resolution=resolution,
                    fps=fps,
                    matrix_count=matrix_count,
                    matrix_head_color=matrix_head_color,
                    matrix_tail_color=matrix_tail_color,
                    matrix_char_size=matrix_char_size,
                    head_step_time=head_step_time,
                    random_x_jitter=random_x_jitter,
                    fade_time=fade_time,
                    head_glow_passes=head_glow_passes,
                    head_glow_alpha_decay=head_glow_alpha_decay,
                    head_spawn_delay_range=head_spawn_delay_range,
                    head_saw_period=head_saw_period,
                    wave_color=wave_color,
                    trail_colors=trail_colors,
                    glow_passes=glow_passes,
                    glow_alpha_decay=glow_alpha_decay,
                    line_width=line_width,
                    font_path=font_path,
                    progress_callback=lambda step, prog: progress_callback("Generating visualizer", 90 + prog * 0.1) if progress_callback else None
                )
            
            if progress_callback:
                progress_callback("Completed", 100)
            
            if self.db:
                self._insert_podcast_record(dialog=dialogue, description=description)
            
            return {
                "output_file": final_audio_path,
                "visualizer_file": final_video_path if visualizer else None,
                "description": description,
                "dialogue": dialogue.model_dump(),
                "segments": ", ".join([s.path for s in segments]),
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
        
        except Exception as e:
            import traceback
            error_msg = f"Error in generate_podcast: {str(e)}\nTraceback:\n{traceback.format_exc()}"
            print(error_msg)
            raise Exception(error_msg) from e
        
    def _insert_podcast_record(self, dialog, description):
        """
        Insert a podcast record into the database.
        """
        today = date.today()
        try:
            # Convert dialog to proper format for database storage
            if hasattr(dialog, 'model_dump'):
                # If it's a Pydantic model, get the dialogue data
                script_data = dialog.model_dump()['dialogue']
            elif hasattr(dialog, 'dialogue'):
                # If it's a Dialogue object with dialogue attribute
                script_data = [item.model_dump() if hasattr(item, 'model_dump') else item for item in dialog.dialogue]
            else:
                # Assume it's already in the right format
                script_data = dialog
            
            podcast_record = Podcast(
                title=f"Theseus Insight Podcast Episode {today.strftime('%m-%d-%Y')}",
                date=datetime.now().strftime("%Y-%m-%d"),
                description=description,
                script=script_data,  # This will be properly serialized by the insert_podcast method
            )
            self.db.insert_podcast(podcast_record)
            if self.verbose:
                print(f"Successfully inserted podcast record into database")
        except Exception as e:
            print(f"Error inserting podcast record: {e}")
            import traceback
            if self.verbose:
                traceback.print_exc()


    def regenerate_podcast_from_script(
        self,
        dialogue_dict: Dict,
        output_format: str = "mp3",
        output_dir: str = "output_audio",
        prefix: str = "podcast_segment",
        speaker_1_voice: str = None,
        speaker_2_voice: str = None,
        speaker_1_speed: float = None,
        speaker_2_speed: float = None,
        final_filename: str = "podcast_final",
        visualizer: bool = False,
        intro_music_path: str = None,
        # Visualizer Settings
        resolution: tuple = (1920, 1080),
        fps: int = 30,
        matrix_count=200,
        matrix_head_color="#e0ffe7",   # short hex for bright green
        matrix_tail_color="0x00b000",  # hex for (0,176,0)
        matrix_char_size=24,
        head_step_time=0.25,
        head_saw_period=1.5,
        random_x_jitter=2.0,
        fade_time=5.0,
        head_glow_passes=3,
        head_glow_alpha_decay=50,
        head_spawn_delay_range=(1.0,3.0),
        wave_color="#d703fc",
        trail_colors=["#fc03b6", "#ba03fc", "#ce6bf2"], 
        glow_passes=3,
        glow_alpha_decay=40,
        line_width=6
    ) -> Dict[str, str]:
        """
        Regenerates a podcast from a given dialogue dictionary.

        This method takes a dialogue dictionary as input and regenerates a podcast based on the provided settings.
        It supports various output formats, including MP3, and allows for customization of the output directory, 
        filename prefix, and final filename. Additionally, it provides options for speaker voices and speeds, 
        as well as visualizer settings.

        Args:
            dialogue_dict (Dict): A dictionary containing the dialogue data.
            output_format (str, optional): The output format of the podcast. Defaults to "mp3".
            output_dir (str, optional): The directory where the output files will be saved. Defaults to "output_audio".
            prefix (str, optional): The prefix to use for the output filenames. Defaults to "podcast_segment".
            speaker_1_voice (str, optional): The voice to use for speaker 1. Defaults to None.
            speaker_2_voice (str, optional): The voice to use for speaker 2. Defaults to None.
            speaker_1_speed (float, optional): The speed factor for speaker 1's voice. Defaults to None.
            speaker_2_speed (float, optional): The speed factor for speaker 2's voice. Defaults to None.
            final_filename (str, optional): The final filename for the podcast. Defaults to "podcast_final".
            visualizer (bool, optional): Whether to generate a visualizer video. Defaults to False.
            intro_music_path (str, optional): The path to the intro music file. Defaults to None.
            resolution (tuple, optional): The resolution of the visualizer video. Defaults to (1920, 1080).
            fps (int, optional): The frames per second of the visualizer video. Defaults to 30.
            matrix_count (int, optional): The number of matrices in the visualizer. Defaults to 200.
            matrix_head_color (str, optional): The color of the matrix head. Defaults to "#e0ffe7".
            matrix_tail_color (str, optional): The color of the matrix tail. Defaults to "0x00b000".
            matrix_char_size (int, optional): The size of the matrix characters. Defaults to 24.
            head_step_time (float, optional): The time between head steps. Defaults to 0.25.
            random_x_jitter (float, optional): The amount of random jitter in the x-axis. Defaults to 2.0.
            fade_time (float, optional): The time it takes for characters to fade. Defaults to 5.0.
            head_glow_passes (int, optional): The number of glow passes for the head. Defaults to 3.
            head_glow_alpha_decay (int, optional): The alpha decay for the head glow. Defaults to 50.
            head_spawn_delay_range (tuple, optional): The range of delay times for head spawning. Defaults to (1.0, 3.0).
            wave_color (str, optional): The color of the wave. Defaults to "#d703fc".
            trail_colors (list, optional): A list of colors for the trail. Defaults to ["#fc03b6", "#ba03fc", "#ce6bf2"].
            glow_passes (int, optional): The number of glow passes. Defaults to 3.
            glow_alpha_decay (int, optional): The alpha decay for the glow. Defaults to 40.
            line_width (int, optional): The width of the line. Defaults to 6.

        Returns:
            Dict[str, str]: A dictionary containing the transcript, dictionary transcript, segments, final podcast path, and visualizer path.
        """
        intro_music_path = intro_music_path or self.intro_music_path
        dialogue_obj = self._validate_dialogue_data(dialogue_dict)
        if not dialogue_obj:
            raise ValueError("Invalid dialogue dictionary format")

        # Create temporary TTS instances if we're overriding voices or speeds
        if any([speaker_1_voice, speaker_2_voice, speaker_1_speed, speaker_2_speed]):
            
            if self.tts_provider == 'polly':
                tts_speaker_1 = PollyTTSInference(
                    voice_id=speaker_1_voice or self.tts_speaker_1.voice_id,
                    speaker_speed=speaker_1_speed or self.tts_speaker_1.speaker_speed,
                    verbose=self.verbose
                )
                tts_speaker_2 = PollyTTSInference(
                    voice_id=speaker_2_voice or self.tts_speaker_2.voice_id,
                    speaker_speed=speaker_2_speed or self.tts_speaker_2.speaker_speed,
                    verbose=self.verbose
                )
            else:  # openai
                tts_speaker_1 = OpenAITTSInference(
                    voice_name=speaker_1_voice or self.tts_speaker_1.voice_name,
                    speaker_speed=speaker_1_speed or self.tts_speaker_1.speaker_speed,
                    verbose=self.verbose
                )
                tts_speaker_2 = OpenAITTSInference(
                    voice_name=speaker_2_voice or self.tts_speaker_2.voice_name,
                    speaker_speed=speaker_2_speed or self.tts_speaker_2.speaker_speed,
                    verbose=self.verbose
                )
        else:
            tts_speaker_1 = self.tts_speaker_1
            tts_speaker_2 = self.tts_speaker_2

        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(exist_ok=True, parents=True)

        segments: List[SegmentInfo] = []
        full_transcript: List[str] = []

        for idx, item in enumerate(dialogue_obj.dialogue):
            speaker = item.speaker.lower().strip()
            text    = item.text.strip()

            tts = tts_speaker_1 if speaker == "speaker-1" else tts_speaker_2
            out_path = os.path.join(output_dir, f"{prefix}_{idx:03}.{output_format}")
            tts.invoke(text=text, save_file=True, file_path=out_path, format=output_format)

            # Use the actual segment_label from the DialogueItem instead of inferring from position
            label = item.segment_label

            segments.append(SegmentInfo(label=label, path=out_path))
            # Include segment_label in transcript for clarity
            full_transcript.append(f"{speaker} [{item.segment_label}]: {text}")

        # Build final transcript string
        transcript_text = "\n".join(full_transcript)

        description = self._get_podcast_description(transcript_text)

        # Define the single-file output name
        final_podcast_filename = f"{prefix}_final.{output_format}"
        final_podcast_path = os.path.join(output_dir, final_podcast_filename)

        # Combine segments and cleanup
        self._combine_audio_segments(segments, final_podcast_path, output_format, intro_music_path)
        if visualizer:
            output_filepath=f"{final_filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_visualizer.mp4"
            generate_visualizer_video(
                audio_filepath=final_podcast_path,
                output_filepath=output_filepath,
                resolution=resolution,
                fps=fps,
                matrix_count=matrix_count,
                matrix_head_color=matrix_head_color,
                matrix_tail_color=matrix_tail_color,
                matrix_char_size=matrix_char_size,
                head_step_time=head_step_time,
                random_x_jitter=random_x_jitter,
                fade_time=fade_time,
                head_glow_passes=head_glow_passes,
                head_glow_alpha_decay=head_glow_alpha_decay,
                head_spawn_delay_range=head_spawn_delay_range,
                head_saw_period=head_saw_period,
                wave_color=wave_color,
                trail_colors=trail_colors, 
                glow_passes=glow_passes,
                glow_alpha_decay=glow_alpha_decay,
                line_width=line_width,
            )
        else:
            output_filepath = "No Visualizer Output"
        return {
            "transcript": transcript_text,
            "dict_transcript": dialogue_obj.model_dump(),
            "segments": ", ".join([s.path for s in segments]),
            "final_podcast_path": final_podcast_path,
            "visualizer_path": output_filepath,
            "description": description,
        }

    def _cleanup_segments(self, segments: List[SegmentInfo]) -> None:
        """
        Cleans up temporary audio segments after processing.

        This method iterates through the list of SegmentInfo objects, checks if each segment's file exists, and attempts to remove it. If a segment file cannot be removed, an error message is logged.

        Args:
            segments (List[SegmentInfo]): A list of SegmentInfo objects representing the audio segments to be cleaned up.
        """
        for seg in segments:
            try:
                if os.path.exists(seg.path):
                    os.remove(seg.path)
                    if self.verbose:
                        print(f"Removed temp file: {seg.path}")
            except Exception as e:
                if self.verbose:
                    print(f"Could not delete {seg.path}: {e}")

    def _combine_audio_segments(
        self,
        segments: List[SegmentInfo],
        output_path: str,
        output_format: str,
        intro_music_path: str | None = None,
    ) -> None:
        """
        Combines multiple audio segments into a single audio file.

        This method takes a list of audio segments, each represented by a SegmentInfo object, and combines them into a single audio file. The segments are combined in the order they are provided, with optional fade-in and fade-out effects applied between segments. If an intro music path is provided, it is crossfaded with the last intro segment.

        Args:
            segments (List[SegmentInfo]): A list of SegmentInfo objects representing the audio segments to be combined.
            output_path (str): The path where the combined audio file will be saved.
            output_format (str): The format of the output audio file.
            intro_music_path (str | None, optional): The path to the intro music file. If provided, it will be crossfaded with the last intro segment. Defaults to None.

        Raises:
            Exception: If an error occurs during the audio segment combination process.
        """
        intro_music_path = intro_music_path or self.intro_music_path
        combined = AudioSegment.empty()
        CROSSFADE_START_MS = 2000  # Start crossfade 2 seconds before end of speech
        FADE_DURATION_MS = 3000  # Make the fade duration longer for slower fade

        # Find the last index where label == 'intro'
        last_intro_idx = -1
        for idx, seg in enumerate(segments):
            if seg.label == "intro":
                last_intro_idx = idx

        # Track music length to ensure it plays all the way through
        music_length_ms = 0
        music_start_position_ms = 0
        if intro_music_path and last_intro_idx >= 0:
            music = AudioSegment.from_file(intro_music_path, format=output_format)
            music_length_ms = len(music)

        for idx, seg in enumerate(segments):
            speech = AudioSegment.from_file(seg.path, format=output_format)

            # Track where music starts in the combined audio
            if idx == last_intro_idx and intro_music_path:
                music_start_position_ms = len(combined) + len(speech) - CROSSFADE_START_MS

            # If this is the last intro segment and intro music is provided, crossfade music in
            if (
                intro_music_path
                and idx == last_intro_idx
            ):
                music = AudioSegment.from_file(intro_music_path, format=output_format)
                
                # Use the smaller of: speech length, crossfade start position, or music length
                crossfade_start_pos = max(0, len(speech) - CROSSFADE_START_MS)
                crossfade_duration = min(FADE_DURATION_MS, len(speech) - crossfade_start_pos, len(music))
                
                if crossfade_duration > 0:
                    # Split speech into pre-crossfade and crossfade portions
                    speech_before_fade = speech[:crossfade_start_pos] if crossfade_start_pos > 0 else AudioSegment.silent(0)
                    speech_crossfade = speech[crossfade_start_pos:crossfade_start_pos + crossfade_duration]
                    
                    # Keep speech at full volume (no fade out)
                    speech_full_volume = speech_crossfade
                    
                    # Apply gradual fade in to music, but limit max volume to ~50% (-6dB)
                    music_crossfade = music[:crossfade_duration]
                    # First fade in the music from 0 to full volume
                    music_faded = music_crossfade.fade_in(crossfade_duration)
                    # Then reduce overall volume to 50% (-6dB reduction)
                    music_at_50_percent = music_faded - 6  # -6dB is approximately 50% volume
                    
                    # Overlay the 50% volume music on the full-volume speech
                    overlay_section = speech_full_volume.overlay(music_at_50_percent)
                    
                    # Reconstruct the speech with crossfade
                    speech = speech_before_fade + overlay_section
                    
                    # Continue with the rest of the music after the crossfade at 50% volume
                    remaining_music = music[crossfade_duration:] - 6  # Keep music at 50% volume
                    speech += remaining_music
                else:
                    # If crossfade duration is 0 or negative, just append music after speech at 50% volume
                    music_at_50_percent = music - 6  # Reduce to 50% volume
                    speech += music_at_50_percent
                    
            combined += speech

            # Only add pause between logical blocks if we're not in the middle of playing music
            # and this isn't the very last segment
            if idx < len(segments) - 1:
                current_position_ms = len(combined)
                music_end_position_ms = music_start_position_ms + music_length_ms
                
                # Only add pause if music isn't currently playing or if music has finished
                if (music_length_ms == 0 or  # No music at all
                    current_position_ms < music_start_position_ms or  # Music hasn't started yet
                    current_position_ms >= music_end_position_ms):  # Music has finished
                    combined += AudioSegment.silent(int(self.pause_duration * 1000))

        combined.export(output_path, format=output_format)
        self._cleanup_segments(segments)

