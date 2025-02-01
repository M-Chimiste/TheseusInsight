import os
import re
import time
import json_repair
from pathlib import Path
from typing import List, Literal, Dict, Optional
from pydantic import ValidationError
from pydub import AudioSegment
from tqdm import tqdm
from ..inference import (KokoroTTSInference,
                         PollyTTSInference,
                         OpenAITTSInference,
                        LLMModelFactory)
from .visualizer import generate_visualizer_video
from ..prompt import (INSTRUCTION_TEMPLATES, 
                      PODCAST_SUMMARY_SYSTEM_PROMPT,
                      podcast_description)
from ..data_model import (Dialogue,
                          DialogueItem,
                          DialogueOutput,
                          PodcastDescription)
from ..pdf import SpacyLayoutDocProcessor
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()


class PaperPalPodcastGenerator:
    def __init__(
        self,
        text_model: dict = {
            "model_name": "claude-3-5-sonnet-20240620",
            "model_type": "anthropic",       # 'anthropic', 'ollama', 'openai', or 'gemini'
            "max_new_tokens": 8192,
            "temperature": 0.1,
            "num_ctx": 131072
        },
        tts_provider: str = "kokoro",        # 'kokoro', 'polly', or 'openai'
        tts_model_path: str = "models/Kokoro-82M",
        tts_model_name: str = "kokoro-v0_19.pth",
        speaker_1_voice: str = "af_bella",
        speaker_1_speed: float = 1.15,
        speaker_2_voice: str = "am_adam",
        speaker_2_speed: float = 1.15,
        instructions_template: dict = INSTRUCTION_TEMPLATES,
        intro_music_path: str = None,
        verbose: bool = False
    ):
        """
        Set up the class with your default settings.
        
        Args:
            text_model (dict): Configuration for the text generation model
            tts_provider (str): TTS provider to use ('kokoro', 'polly', or 'openai')
            tts_model_path (str): Path to Kokoro model (only used if tts_provider is 'kokoro')
            tts_model_name (str): Name of Kokoro model file (only used if tts_provider is 'kokoro')
            speaker_1_voice (str): Voice ID for speaker 1 (provider-specific)
            speaker_1_speed (float): Speed factor for speaker 1
            speaker_2_voice (str): Voice ID for speaker 2 (provider-specific)
            speaker_2_speed (float): Speed factor for speaker 2
            instructions_template (dict): Instructions template to use for prompting
            verbose (bool): Whether to print verbose output
        """
        self.verbose = verbose
        self.text_model_config = text_model
        self.tts_provider = tts_provider.lower()
        self.instructions_template = instructions_template
        self.intro_music_path = intro_music_path
        self.intro, self.section, self.outro = self._parse_prompts(instructions_template)
        
        # Validate TTS provider
        valid_providers = ['kokoro', 'polly', 'openai']
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
        if self.tts_provider == 'kokoro':
            self.tts_speaker_1 = KokoroTTSInference(
                model_path=tts_model_path,
                model_name=tts_model_name,
                voice_name=speaker_1_voice,
                speaker_speed=speaker_1_speed,
                verbose=self.verbose
            )
            self.tts_speaker_2 = KokoroTTSInference(
                model_path=tts_model_path,
                model_name=tts_model_name,
                voice_name=speaker_2_voice,
                speaker_speed=speaker_2_speed,
                verbose=self.verbose
            )
        elif self.tts_provider == 'polly':
            self.tts_speaker_1 = PollyTTSInference(
                voice_id=speaker_1_voice,
                speaker_speed=speaker_1_speed,
                verbose=self.verbose
            )
            self.tts_speaker_2 = PollyTTSInference(
                voice_id=speaker_2_voice,
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
        Parse the prompts from the instructions template
        """
        intro = template["podcast_into"]
        section = template["podcast_section"]
        outro = template["podcast_outro"]
        return intro, section, outro
    
    def _get_podcast_description(self, text: str) -> str:
        """
        Get the podcast description from the text
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
        
        else:
            if self.text_inference.provider == "anthropic":
                messages.append({"role": "assistant", "content": "{"})
            raw_response = self.text_inference.invoke(messages, system_prompt=system_prompt)
            if self.text_inference.provider == "anthropic":
                raw_response = "{" + raw_response

        data = json_repair.loads(raw_response)
        return data["podcast_episode_description"]

    def _get_dialogue(
        self,
        text: str,
        template_instructions: str,
    ) -> Dialogue:
        """
        Generates a dialogue based on the provided text and instructions.
        Args:
            text (str): The original input text.
            template_instructions (str): Instructions for the introduction.
        Returns:
            Dialogue: A validated Dialogue object containing the generated dialogue.
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
        dialogue_obj = self._validate_dialogue_data(data)
        if self.verbose:
            print(f"Dialogue object validated")
        return dialogue_obj
    

    def _validate_dialogue_data(self, data: dict):
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
        
        if "dialogue" not in data or not isinstance(data["dialogue"], list):
            return None
        
        valid_items = []
        for item in data["dialogue"]:
            try:
                di = DialogueItem(**item)
                valid_items.append(di)
            except ValidationError as ve:
                print(f"Skipping invalid dialogue line: {item}\nError: {ve}")
                continue
        
        if not valid_items:
            return None
        
        
        # Create the pydantic model
        try:
            # We pass the validated items, plus a scratchpad
            dialogue_obj = Dialogue(
                dialogue=valid_items
            )
            return dialogue_obj
        except ValidationError as ve:
            print(f"Could not build final Dialogue object: {ve}")
            return None

    def _process_pdf(self, pdf_path: str) -> str:
        """
        Process a PDF file and return the text.
        """
        pdf_processor = self.pdf_processor
        pdf_text = pdf_processor.process_document(pdf_path)
        return pdf_text["processed_data"]

    def generate_podcast(
        self,
        pdf_paths: List[str] | str,
        paperpal_sections: List[str] | str,
        output_format: str = "mp3",
        output_dir: str = "output_audio",
        prefix: str = "podcast_segment",
        final_filename: str = "podcast_final",
        verbose: bool = None,
        visualizer: bool = False,
        # Visualizer Settings
        resolution: tuple = (1920, 1080),
        fps: int = 30,
        matrix_count=200,
        matrix_head_color="#e0ffe7",   # short hex for bright green
        matrix_tail_color="0x00b000",  # hex for (0,176,0)
        matrix_char_size=24,
        head_step_time=0.25,
        random_x_jitter=2.0,
        fade_time=5.0,
        head_glow_passes=3,
        head_glow_alpha_decay=50,
        head_spawn_delay_range=(1.0,3.0),
        wave_color="#d703fc",
        trail_colors=["#fc03b6", "#ba03fc", "#ce6bf2"], 
        glow_passes=3,
        glow_alpha_decay=40,
        line_width=6,
    ) -> Dict[str, str]:
        """
        Generates a podcast from a list of PDF files and paperpal sections.

        This method processes a list of PDF files, extracts the text, and 
        generates a podcast script based on the provided paperpal sections. 
        It then uses a TTS engine to convert the script into audio segments, 
        which are combined into a final podcast file. Optionally, a visualizer 
        video can be generated.

        Args:
            pdf_paths (List[str] | str): A list of paths to PDF files or a single PDF file path.
            paperpal_sections (List[str] | str): A list of paperpal sections or a single paperpal section.
            output_format (str, optional): The format of the output audio file. Defaults to "mp3".
            output_dir (str, optional): The directory where the output audio files will be saved. Defaults to "output_audio".
            prefix (str, optional): The prefix for the output audio file names. Defaults to "podcast_segment".
            final_filename (str, optional): The name of the final combined podcast file. Defaults to "podcast_final".
            verbose (bool, optional): If True, prints verbose output. Defaults to None.
            visualizer (bool, optional): If True, generates a visualizer video. Defaults to False.
            resolution (tuple, optional): The resolution of the visualizer video. Defaults to (1920, 1080).
            fps (int, optional): The frames per second of the visualizer video. Defaults to 30.
            matrix_count (int, optional): The number of matrices in the visualizer. Defaults to 200.
            matrix_head_color (str, optional): The color of the matrix head. Defaults to "#e0ffe7".
            matrix_tail_color (str, optional): The color of the matrix tail. Defaults to "#00b000".
            matrix_char_size (int, optional): The size of the matrix characters. Defaults to 24.
            head_step_time (float, optional): The time between head steps. Defaults to 0.25.
            random_x_jitter (float, optional): The amount of random jitter in the x-axis. Defaults to 2.0.
            fade_time (float, optional): The time for the fade effect. Defaults to 5.0.
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
        verbose = self.verbose or verbose
        scripts = [] # list of scripts

        # 1) Process the PDFs
        texts = []
        if isinstance(pdf_paths, str):
            pdf_paths = [pdf_paths]
        for pdf_path in tqdm(pdf_paths, desc="Processing PDFs", disable=not verbose):
            text = self._process_pdf(pdf_path)
            texts.append(text)
       
        # 2) Create the intro procast script
        if isinstance(paperpal_sections, list):
            paperpal_sections = "\n".join(paperpal_sections)
        if verbose:
            print(f"Creating intro script")
        intro_script = self._get_dialogue(
            paperpal_sections,
            template_instructions=self.intro
        )
        scripts.append(intro_script)
        # 3) Create the section scripts
        for text in tqdm(texts, desc="Creating section scripts", disable=not verbose):
            section_script = self._get_dialogue(
                text,
                template_instructions=self.section
            )
            scripts.append(section_script)
        # 4) Create the outro script
        if verbose:
            print(f"Creating outro script")
        outro_script = self._get_dialogue(
            text,
            template_instructions=self.outro
        )
        scripts.append(outro_script)

        # 5) Merge the scripts
        merged_script = Dialogue.merge_outputs(scripts)

        # 6) For each item in the dialogue, call TTS with either speaker-1 or speaker-2
        Path(output_dir).mkdir(exist_ok=True, parents=True)

        segments = []
        full_transcript = []

        for idx, item in enumerate(merged_script.dialogue):
            speaker = item.speaker.lower().strip()
            line_text = item.text.strip()

            # Choose TTS object
            if speaker == "speaker-1":
                tts = self.tts_speaker_1
            elif speaker == "speaker-2":
                tts = self.tts_speaker_2
            else:
                # You could default or raise an error
                print(f"Unknown speaker: {speaker}")
                tts = self.tts_speaker_1

            # Prepare filename
            
            file_name = f"{prefix}_{idx}.{output_format}"
            out_path = os.path.join(output_dir, file_name)
            if verbose:
                print(f"Processing line {idx} for speaker {speaker}")
                print(f"Saving to: {out_path}")

            # TTS call
            tts.invoke(
                text=line_text,
                save_file=True,
                file_path=out_path,
                format=output_format
            )

            segments.append(out_path)
            full_transcript.append(f"{speaker}: {line_text}")

        # Build final transcript string
        transcript_text = "\n".join(full_transcript)

        # Define the single-file output name
        final_podcast_filename = f"{final_filename}.{output_format}"
        final_podcast_path = os.path.join(output_dir, final_podcast_filename)

        # Combine segments and cleanup

        self._combine_audio_segments(segments, final_podcast_path, output_format)
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
            "dict_transcript": merged_script.model_dump(),
            "segments": ", ".join(segments),
            "final_podcast_path": final_podcast_path,
            "visualizer_path": output_filepath,

        }

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
        # Visualizer Settings
        resolution: tuple = (1920, 1080),
        fps: int = 30,
        matrix_count=200,
        matrix_head_color="#e0ffe7",   # short hex for bright green
        matrix_tail_color="0x00b000",  # hex for (0,176,0)
        matrix_char_size=24,
        head_step_time=0.25,
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
        dialogue_obj = self._validate_dialogue_data(dialogue_dict)
        if not dialogue_obj:
            raise ValueError("Invalid dialogue dictionary format")

        # Create temporary TTS instances if we're overriding voices or speeds
        if any([speaker_1_voice, speaker_2_voice, speaker_1_speed, speaker_2_speed]):
            if self.tts_provider == 'kokoro':
                tts_speaker_1 = KokoroTTSInference(
                    model_path=self.tts_model_path,
                    model_name=self.tts_model_name,
                    voice_name=speaker_1_voice or self.tts_speaker_1.voice_name,
                    speaker_speed=speaker_1_speed or self.tts_speaker_1.speaker_speed,
                    verbose=self.verbose
                )
                tts_speaker_2 = KokoroTTSInference(
                    model_path=self.tts_model_path,
                    model_name=self.tts_model_name,
                    voice_name=speaker_2_voice or self.tts_speaker_2.voice_name,
                    speaker_speed=speaker_2_speed or self.tts_speaker_2.speaker_speed,
                    verbose=self.verbose
                )
            elif self.tts_provider == 'polly':
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

        segments = []
        full_transcript = []

        # Generate audio for each dialogue line
        for idx, item in enumerate(dialogue_obj.dialogue):
            speaker = item.speaker.lower().strip()
            line_text = item.text.strip()

            # Choose TTS object
            if speaker == "speaker-1":
                tts = tts_speaker_1
            elif speaker == "speaker-2":
                tts = tts_speaker_2
            else:
                print(f"Unknown speaker: {speaker}, defaulting to speaker-1")
                tts = tts_speaker_1

            # Prepare filename
            file_name = f"{prefix}_{idx}.{output_format}"
            out_path = os.path.join(output_dir, file_name)
            
            if self.verbose:
                print(f"Processing line {idx} for speaker {speaker}")
                print(f"Saving to: {out_path}")

            # TTS call
            tts.invoke(
                text=line_text,
                save_file=True,
                file_path=out_path,
                format=output_format
            )

            segments.append(out_path)
            full_transcript.append(f"{speaker}: {line_text}")

        # Build final transcript string
        transcript_text = "\n".join(full_transcript)

        description = self._get_podcast_description(transcript_text)

        # Define the single-file output name
        final_podcast_filename = f"{prefix}_final.{output_format}"
        final_podcast_path = os.path.join(output_dir, final_podcast_filename)

        # Combine segments and cleanup
        self._combine_audio_segments(segments, final_podcast_path, output_format)
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
            "segments": ", ".join(segments),
            "final_podcast_path": final_podcast_path,
            "visualizer_path": output_filepath,
            "description": description,
        }

    def _cleanup_segments(self, segments: List[str]):
        """
        Clean up individual audio segments after combining them.
        
        Args:
            segments (List[str]): List of paths to segment files to delete
        """
        for segment_path in segments:
            try:
                if os.path.exists(segment_path):
                    os.remove(segment_path)
                    if self.verbose:
                        print(f"Cleaned up segment: {segment_path}")
            except Exception as e:
                if self.verbose:
                    print(f"Failed to clean up segment {segment_path}: {e}")

    def _combine_audio_segments(self, segments: List[str], output_path: str, output_format: str) -> None:
        """
        Combine audio segments and clean up individual files.
        
        Args:
            segments (List[str]): List of paths to audio segments
            output_path (str): Path to save the combined audio
            output_format (str): Audio format (mp3, wav, etc.)
        """
        
        combined_audio = AudioSegment.empty()
        if self.intro_music_path:
            combined_audio += AudioSegment.from_file(self.intro_music_path, format=output_format)
        # Combine all segments
        for seg_path in segments:
            combined_audio += AudioSegment.from_file(seg_path, format=output_format)
        
        # Export combined audio
        combined_audio.export(output_path, format=output_format)
        
        # Clean up individual segments
        self._cleanup_segments(segments)
