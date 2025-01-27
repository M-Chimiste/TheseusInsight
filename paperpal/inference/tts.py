import io
import numpy as np
import os
import platform
import re
import torch
import uuid

from dotenv import load_dotenv
from pathlib import Path
from pydub import AudioSegment

# Load models and voicepacks after making sure your espeak library is set up correctly
from .kokoro import generate
from .models import build_model

load_dotenv()


KOKORO_VOICE_NAME = [
    'af', # Default voice is a 50-50 mix of Bella & Sarah
    'af_bella', 'af_sarah', 'am_adam', 'am_michael',
    'bf_emma', 'bf_isabella', 'bm_george', 'bm_lewis',
    'af_nicole', 'af_sky',
]


def chunk_text_by_sentences(text: str, max_len: int = 4096):
    """
    Splits a text into chunks by sentence, ensuring that
    each chunk does not exceed max_len characters.
    
    If a single sentence is longer than max_len, it will
    be forcibly split into sub-chunks of max_len.
    """
    # Split text by sentence-ending punctuation. This is a simple approach,
    # you may want to refine with a better sentence tokenizer if needed.
    # We'll keep the delimiters so we don't lose them (e.g., '.', '?', '!')
    sentences = re.split(r'([.?!])', text)

    chunks = []
    current_chunk = []

    def flush_current_chunk():
        """Helper to push the current_chunk into chunks list."""
        if current_chunk:
            chunk_text = "".join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)
    
    for i in range(0, len(sentences), 2):
        # sentence[i] is the text up to the punctuation
        # sentence[i+1] (if exists) is the punctuation
        s = sentences[i].strip()
        punct = sentences[i+1] if (i+1 < len(sentences)) else ""

        # Rebuild the sentence
        sentence_with_punct = (s + punct).strip()
        if not sentence_with_punct:
            continue

        # Check if adding this sentence to current_chunk will exceed max_len
        prospective_size = len("".join(current_chunk)) + len(sentence_with_punct)
        if prospective_size <= max_len:
            current_chunk.append(sentence_with_punct)
        else:
            # If current_chunk is not empty, flush it
            flush_current_chunk()
            current_chunk = []

            # If the single sentence itself is longer than max_len, forcibly split
            if len(sentence_with_punct) > max_len:
                # We'll do naive sub-chunking of that single sentence
                start_idx = 0
                while start_idx < len(sentence_with_punct):
                    end_idx = min(start_idx + max_len, len(sentence_with_punct))
                    sub_chunk = sentence_with_punct[start_idx:end_idx]
                    chunks.append(sub_chunk.strip())
                    start_idx = end_idx
            else:
                current_chunk.append(sentence_with_punct)

    # Flush any remaining text
    flush_current_chunk()
    return chunks



class KokoroTTSInference:
    """
    TTSInference is a class that facilitates Text-to-Speech inference using
    a specified model and voicepack.

    Args:
        model_path (str): The path to the Kokoro model file.
        voice_name (str): The name of the voice to use. Defaults to "af".
        speaker_speed (float): The speed multiplier for the speaker's speech rate.
        verbose (bool): Whether to print verbose output.

    Attributes:
        device (str): The device on which Torch computations will be performed ('cuda' or 'cpu').
        model (nn.Module): The loaded Kokoro model.
        voice_name (str): The name of the voice used for inference.
        voicepack (nn.Module): The loaded voicepack for the specified voice.
    """

    def __init__(self, 
                 model_path: str,
                 model_name: str,
                 voice_name: str = "af",
                 speaker_speed: float = 1.0,
                 verbose: bool = False):
        """
        Initializes the TTSInference instance by:
          - Constructing the full model path from model_path and model_name.
          - Loading the model onto the correct device.
          - Loading the requested voicepack from model_path/voices.
        """
        # Moving specialized imports into classes to avoid importing them globally  
        IS_MAC = platform.system() == "Darwin"
        if IS_MAC:
            from phonemizer.backend.espeak.wrapper import EspeakWrapper
            _ESPEAK_LIBRARY = '/opt/homebrew/bin/espeak'  #use the Path to the library.
            EspeakWrapper.set_library(_ESPEAK_LIBRARY)

        self.verbose = verbose
        self.speaker_speed = speaker_speed

        if torch.cuda.is_available():
            self.device = "cuda"
        # MPS is missing an implementation so it wont work yet
        # elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        #     self.device = "mps"
        else:
            self.device = "cpu"
        if self.verbose:
            print(f"Using device: {self.device}")
        full_model_path = os.path.join(model_path, model_name)
        self.model = build_model(full_model_path, self.device)
        self.voice_name = voice_name
        if voice_name not in KOKORO_VOICE_NAME:
            raise ValueError(f"Voice name '{voice_name}' not found. Choose from: {KOKORO_VOICE_NAME}")
        voicepack_path = os.path.join(model_path, "voices", f"{voice_name}.pt")
        self.voicepack = torch.load(voicepack_path, weights_only=True).to(self.device)
        if self.verbose:
            print(f"Loaded voice: {self.voice_name}")

    def invoke(self, text: str, save_file: bool=True, file_path: str|None=None, format: str="wav"):
        """
        Generate speech from text using the loaded model and voicepack, then save it as an MP3 file.

        Args:
            text (str): The text to convert to speech.
            file_location (str): The file path (including .mp3) where the output audio will be saved.

        Returns:
            dict: The phonemes used in the generation process.
        """
        formats = ["mp3", "wav", "ogg", "flac"]
        if format not in formats:
            raise ValueError(f"Format '{format}' not supported. Choose from: {formats}")
        # Generate audio at 24kHz sample rate
        audio, out_ps = generate(self.model, text, self.voicepack, lang=self.voice_name[0], speed=self.speaker_speed)

        # Save audio as an mp3 file (requires FFmpeg installed)
        if save_file:
            if not file_path:
                raise ValueError("file_location must be provided when save_file is True")
            audio_np = (audio * 32767).astype(np.int16)  # if originally float32 in range -1..1
            audio_segment = AudioSegment(
                audio_np.tobytes(), 
                frame_rate=24000,
                sample_width=2,    # 16-bit
                channels=1
            )
            audio_segment.export(file_path, format=format)
        # Return phonemes for reference
        return audio, out_ps


class PollyTTSInference:
    """
    PollyTTSInference is a class that facilitates Text-to-Speech inference using
    Amazon Polly, automatically chunking long text and concatenating the results.

    Environment Variables (via dotenv):
        AWS_ACCESS_KEY_ID
        AWS_SECRET_ACCESS_KEY
        AWS_SESSION_TOKEN (optional)
        REGION_NAME (default: 'us-east-1')

    Args:
        voice_id (str): Name of the Amazon Polly voice (default: "Joanna").
        speaker_speed (float): Speed factor (via SSML <prosody> tag).
        engine (str): Polly engine ("standard" or "neural").
        verbose (bool): Print debug logs if True.
        max_chars (int): Max chunk size in characters. For SSML, 1500 is typical.

    Attributes:
        region (str): AWS region.
        voice_id (str): Polly voice name.
        speaker_speed (float): Speed factor for speech.
        polly_client (boto3.client): Boto3 Polly client.
        engine (str): "standard" or "neural" engine.
        max_chars (int): Maximum number of characters per chunk.
    """

    def __init__(
        self,
        voice_id: str = "Joanna",
        speaker_speed: float = 1.0,
        engine: str = "standard",
        verbose: bool = False,
        max_chars: int = 1500
    ):
        import boto3

        self.verbose = verbose
        self.speaker_speed = speaker_speed
        self.engine = engine
        self.max_chars = max_chars

        # Get AWS credentials & region from environment
        self.access_key = os.getenv("AWS_ACCESS_KEY_ID", None)
        self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", None)
        self.session_token = os.getenv("AWS_SESSION_TOKEN", None)
        self.region = os.getenv("REGION_NAME", "us-east-1")

        # Create a Polly client
        self.polly_client = boto3.client(
            "polly",
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            aws_session_token=self.session_token
        )
        self.voice_id = voice_id

        if self.verbose:
            print(f"[PollyTTS] Initialized. Voice={self.voice_id}, Engine={self.engine}, Region={self.region}")

    def invoke(
        self,
        text: str,
        save_file: bool = True,
        file_path: str | None = None,
        format: str = "wav"
    ):
        """
        Generate speech from `text` using Amazon Polly, automatically chunking
        if the text exceeds `max_chars`.

        Args:
            text (str): The text (input or SSML fragment) to convert to speech.
            save_file (bool): If True, save the final audio to file_path.
            file_path (str | None): File path for the output audio. Required if save_file=True.
            format (str): Output audio format ("wav", "mp3", "ogg", "flac").

        Returns:
            (audio_data, out_ps):
                audio_data: float32 numpy array in range [-1.0, 1.0].
                out_ps: empty dict (Polly doesn't return phoneme data by default).
        """
        # Validate output format
        valid_formats = ["mp3", "wav", "ogg", "flac"]
        if format not in valid_formats:
            raise ValueError(f"Format '{format}' not supported. Use: {valid_formats}")

        # Convert speaker_speed to a rate percentage (Polly SSML trick)
        rate_percent = int(self.speaker_speed * 100)

        # Because we're using <prosody>, we assume SSML in the request
        # => limit is typically 1500 chars. We'll chunk if needed.
        if len(text) > self.max_chars:
            if self.verbose:
                print(f"[PollyTTS] Input text length {len(text)} > {self.max_chars}, chunking by sentences.")
            text_chunks = chunk_text_by_sentences(text, max_len=self.max_chars)
        else:
            text_chunks = [text]

        final_audio_segment = AudioSegment.silent(duration=0)

        for idx, chunk in enumerate(text_chunks):
            if self.verbose:
                print(f"[PollyTTS] Synthesizing chunk {idx+1}/{len(text_chunks)} (length={len(chunk)})...")

            # Wrap each chunk in SSML with <prosody> if using standard or neural
            ssml_text = f"<speak><prosody rate='{rate_percent}%'>{chunk}</prosody></speak>"

            # Create a random temp file name for the chunk
            tmp_mp3_filename = f"polly_tts_{uuid.uuid4()}.mp3"

            try:
                # Call Amazon Polly with SSML
                response = self.polly_client.synthesize_speech(
                    TextType="ssml",
                    Text=ssml_text,
                    VoiceId=self.voice_id,
                    Engine=self.engine,
                    OutputFormat="mp3"
                )
            except Exception as e:
                print("[PollyTTS] Error while calling Polly:", e)
                raise

            # Read the audio stream
            if "AudioStream" not in response:
                raise RuntimeError("Polly response did not contain 'AudioStream'.")

            audio_bytes = response["AudioStream"].read()

            # Convert MP3 bytes to a pydub AudioSegment
            chunk_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")

            # Concatenate
            final_audio_segment += chunk_segment

        # Convert final audio to float32 numpy array in [-1.0, 1.0]
        samples = np.array(final_audio_segment.get_array_of_samples())
        audio_data = samples.astype(np.float32) / 32767.0

        # Optional: Save the final audio
        if save_file:
            if not file_path:
                raise ValueError("Must provide file_path if save_file=True.")
            final_audio_segment.export(file_path, format=format)
            if self.verbose:
                print(f"[PollyTTS] Combined audio saved to {file_path}")

        # Polly does not provide phoneme data in standard calls
        out_ps = {}

        return audio_data, out_ps


class OpenAITTSInference:
    """
    OpenAITTSInference is a class that facilitates Text-to-Speech inference
    using OpenAI's TTS API, with text longer than 4096 chars automatically
    split into sentence-based chunks.

    Args:
        model_name (str): The TTS model to use from OpenAI (e.g., "tts-1").
        voice_name (str): The voice name to use (e.g., "alloy").
        speaker_speed (float): Speed factor for speech (currently no effect in OpenAI TTS).
        verbose (bool): If True, prints debug statements.

    Attributes:
        model_name (str): Model used for TTS (e.g., "tts-1").
        voice_name (str): Voice name (e.g., "alloy").
        speaker_speed (float): Speed factor (not yet supported in OpenAI TTS).
        verbose (bool): Controls debug logging.
        client (OpenAI): The OpenAI client instance.
        max_chars (int): Maximum text length allowed per TTS API call (4096).
    """

    def __init__(
        self,
        model_name: str = "tts-1",
        voice_name: str = "alloy",
        speaker_speed: float = 1.0,
        verbose: bool = False
    ):
        from openai import OpenAI

        self.model_name = model_name
        self.voice_name = voice_name
        self.speaker_speed = speaker_speed  # no direct speed control yet
        self.verbose = verbose
        self.max_chars = 4096  # per TTS docs

        # Initialize the OpenAI client (OPENAI_API_KEY should be in env)
        self.client = OpenAI()

        if self.verbose:
            print(
                f"[OpenAI TTS] Initialized with model='{self.model_name}',"
                f" voice='{self.voice_name}'"
            )

    def invoke(
        self,
        text: str,
        save_file: bool = True,
        file_path: str | None = None,
        format: str = "wav"
    ):
        """
        Generate speech from text using OpenAI's TTS API, returning audio samples
        and an (empty) phoneme dictionary, optionally saving the audio to disk.

        If text is longer than self.max_chars (4096), we split it into chunks
        and concatenate the resulting audio.

        Args:
            text (str): The text to convert to speech.
            save_file (bool): Whether to save the synthesized audio to file.
            file_path (str|None): The file path where output audio is saved.
            format (str): The output audio format. e.g. "wav", "mp3", "ogg", "flac".

        Returns:
            (audio_data, out_ps)
              audio_data: A float32 NumPy array of waveform samples in [-1.0, 1.0].
              out_ps: An empty dict (OpenAI TTS does not provide phoneme data currently).
        """
        formats = ["mp3", "wav", "ogg", "flac"]
        if format not in formats:
            raise ValueError(f"Format '{format}' not supported. Choose from: {formats}")

        # 1. Split text if needed
        if len(text) > self.max_chars:
            if self.verbose:
                print(
                    f"[OpenAI TTS] Text length ({len(text)}) exceeds {self.max_chars};"
                    " splitting into chunks."
                )
            text_chunks = chunk_text_by_sentences(text, max_len=self.max_chars)
        else:
            text_chunks = [text]

        # 2. For each chunk, request TTS from OpenAI and build a final AudioSegment
        final_audio_segment = AudioSegment.silent(duration=0)  # empty audio to start

        for idx, chunk in enumerate(text_chunks):
            if self.verbose:
                print(f"[OpenAI TTS] Synthesizing chunk {idx+1}/{len(text_chunks)} (length={len(chunk)}).")

            # Make a random temporary MP3 path
            tmp_mp3_filename = f"openai_tts_{uuid.uuid4()}.mp3"
            tmp_mp3_path = Path(tmp_mp3_filename).absolute()

            # 2a. Call the TTS API
            try:
                response = self.client.audio.speech.create(
                    model=self.model_name,
                    voice=self.voice_name,
                    input=chunk
                )
            except Exception as e:
                print("[OpenAI TTS] Error calling TTS API:", e)
                raise

            # 2b. Stream the MP3 to disk
            response.stream_to_file(tmp_mp3_path)

            # 2c. Load into pydub & concatenate
            chunk_segment = AudioSegment.from_file(tmp_mp3_path, format="mp3")
            final_audio_segment += chunk_segment

            # Cleanup
            try:
                tmp_mp3_path.unlink()
            except OSError:
                pass

        # 3. Convert combined AudioSegment to float32 NumPy array
        samples = np.array(final_audio_segment.get_array_of_samples(), dtype=np.float32)
        audio_data = samples / 32767.0  # pydub returns int16 samples

        # 4. If requested, save the final concatenated audio
        if save_file:
            if not file_path:
                raise ValueError("Must provide file_path if save_file=True.")
            final_audio_segment.export(file_path, format=format)
            if self.verbose:
                print(f"[OpenAI TTS] Audio saved to {file_path}")

        # 5. Return the final audio data and empty phoneme data
        out_ps = {}
        return audio_data, out_ps