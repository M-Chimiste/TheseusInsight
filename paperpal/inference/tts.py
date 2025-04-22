# Standard library imports
import io
import os
import random
import re
import uuid
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type
from abc import ABC, abstractmethod

# Third-party imports
import numpy as np
import soundfile as sf
import torch
from dotenv import load_dotenv
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_exponential

# Local imports
from dia.model import Dia
from .pipeline import KPipeline

load_dotenv()

#: Tuple of audio formats accepted by all engines.
SUPPORTED_AUDIO_FORMATS: Tuple[str, ...] = ("wav", "mp3", "ogg", "flac")
_TTS_REGISTRY: Dict[str, Type["TTSInference"]] = {}
_WHISPER_PIPE = None


def _set_global_seed(seed: int) -> None:
    """
    Set Python, NumPy and PyTorch RNGs so that subsequent sampling
    inside Dia / other engines becomes reproducible.

    Args
    ----
    seed : int
        Any deterministic seed value.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def register_tts(name: str):
    """Class decorator to register a TTS engine in the factory.

    Args:
        name: Unique identifier used to retrieve this engine via
            :func:`create_tts`.

    Returns:
        The original class, unmodified.
    """
    def _wrapper(cls: Type["TTSInference"]) -> Type["TTSInference"]:
        _TTS_REGISTRY[name.lower()] = cls
        return cls
    return _wrapper


def _lazy_whisper(lang_hint: Optional[str] = None):
    """Returns a cached Hugging Face Whisper pipeline.
    
    Loads large-v3-turbo model on first call; subsequent calls reuse the same weights.
    
    Args:
        lang_hint: Optional language hint for the model.
        
    Returns:
        A Hugging Face pipeline instance for speech recognition.
    """
    global _WHISPER_PIPE
    if _WHISPER_PIPE is None:
        from transformers import (  # heavy import – keep local
            AutoModelForSpeechSeq2Seq,
            AutoProcessor,
            pipeline,
        )

        model_id = "openai/whisper-large-v3-turbo"
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        if torch.cuda.is_available():
            print(f"[DiaTTS] Loading Whisper ({model_id}) on CUDA …")
        else:
            print(f"[DiaTTS] Loading Whisper ({model_id}) on CPU … "
                  "(may be slow)")

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        ).to(device)

        processor = AutoProcessor.from_pretrained(model_id)

        _WHISPER_PIPE = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=torch_dtype,
            device=device,
        )

    return _WHISPER_PIPE


def _transcribe_with_whisper(audio_path: str, language: Optional[str] = None) -> str:
    """Returns Whisper transcription for the given audio file.
    
    Args:
        audio_path: Path to the audio file (mono or stereo).
        language: Optional language hint for transcription.
        
    Returns:
        Transcribed text as a string.
    """
    pipe = _lazy_whisper(language)
    result = pipe(
        audio_path,
        generate_kwargs={"language": language} if language else None,
    )
    return result["text"].strip()


def chunk_text_by_sentences(text: str, max_len: int = 4096) -> List[str]:
    """Splits a text into chunks by sentence, ensuring each chunk does not exceed max_len characters.
    
    If a single sentence is longer than max_len, it will be forcibly split into sub-chunks of max_len.
    
    Args:
        text: The input text to be chunked.
        max_len: Maximum length of each chunk in characters.
        
    Returns:
        List of text chunks, each not exceeding max_len characters.
    """
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

class TTSInference(ABC):
    """Abstract base class for all PaperPal TTS engines."""

    @abstractmethod
    def invoke(self, text: str, **kwargs):
        """Generate speech from *text*.

        Args:
            text: Input text to synthesise.
            **kwargs: Engine‑specific keyword arguments.

        Returns:
            Tuple of (audio_samples, metadata).
        """
        raise NotImplementedError


def create_tts(engine: str, **kwargs) -> "TTSInference":
    """Factory function returning an initialised TTS engine.

    Args:
        engine: Engine identifier (e.g. ``"kokoro"``, ``"polly"``, ``"openai"``, ``"dia"``).
        **kwargs: Parameters forwarded to the engine’s constructor.

    Raises:
        KeyError: If *engine* is not registered.

    Example:
        >>> tts = create_tts("openai", voice_name="alloy")
        >>> audio_np, _ = tts.invoke("Hello!")
    """
    try:
        cls = _TTS_REGISTRY[engine.lower()]
    except KeyError as exc:
        raise KeyError(
            f"Unknown TTS engine '{engine}'. "
            f"Available: {list(_TTS_REGISTRY)}"
        ) from exc
    return cls(**kwargs)


@register_tts("kokoro")
class KokoroTTSInference(TTSInference):
    """KokoroTTSInference uses the updated KPipeline to perform TTS synthesis.
    
    The new workflow no longer manually loads or builds the model.
    Instead, the model and voice data are managed internally by KPipeline.
    
    The pipeline returns a generator of tuples (graphemes, phoneme_chunk, audio_chunk).
    This class concatenates all the audio chunks into a single audio array and
    also concatenates the phoneme strings.
    
    Args:
        voice_name: Name of the voice to use (default: 'af_heart').
        lang_code: Language code to use (e.g., 'a' for American English).
        speed: Speed factor for synthesis.
        verbose: If True, prints debugging information.
        
    Example:
        pipeline = KPipeline(lang_code='a')  # make sure lang_code matches your voice!
        generator = pipeline(
            text,
            voice='af_heart',
            speed=1,
        )
        # The generator yields chunks; our invoke() method collects and concatenates them.
    """
    def __init__(self,
                voice_name: str = 'af_heart',
                lang_code: str = 'a',
                speed: float = 1.0,
                verbose: bool = False):
        """
        Initializes the TTS inference instance by simply creating a KPipeline.
        
        Args:
            lang_code (str): Language code to use (e.g., 'a' for American English).
            verbose (bool): If True, prints debugging information.
        """
        self.verbose = verbose
        self.voice_name = voice_name
        self.speed = speed
        self.pipeline = KPipeline(lang_code=lang_code)
        if self.verbose:
            print(f"[KokoroTTSInference] Initialized KPipeline with lang_code='{lang_code}'")

    def invoke(
        self,
        text: str,
        voice_name: str = None,
        speed: float = None,
        save_file: bool = False,
        file_path: str | None = None,
        format: str = "mp3"
    ) -> Tuple[np.ndarray, str]:
        """Generates speech from input text using the updated pipeline.
        
        The pipeline handles:
          - Sentence splitting
          - G2P conversion with language-specific logic
          - Tokenization and chunking (each chunk is capped at ~510 tokens)
          - Inference for each chunk
        
        All audio chunks are concatenated into a single audio array.
        
        Args:
            text: The text to be synthesized.
            voice_name: The voice name to use (e.g., 'af_heart'). Must be in KOKORO_VOICE_NAME.
            speed: Speed multiplier for synthesis.
            save_file: If True, saves the concatenated audio to disk.
            file_path: Destination file path (required if save_file=True).
            format: Audio file format for export (e.g., "wav", "mp3").
        
        Returns:
            A tuple containing:
                - final_audio: float32 numpy array (range [-1, 1])
                - final_phoneme_output: concatenated phoneme string
                
        Raises:
            RuntimeError: If no audio was generated by the pipeline.
            ValueError: If file_path is not provided when save_file is True.
        """
        # Validate requested audio format
        if format.lower() not in SUPPORTED_AUDIO_FORMATS:
            raise ValueError(
                f"Format '{format}' not supported. "
                f"Choose from: {SUPPORTED_AUDIO_FORMATS}"
            )
        # Lists to collect audio chunks and phoneme strings.
        audio_chunks = []
        phoneme_outputs = []
        voice_name = voice_name or self.voice_name
        speed = speed or self.speed
        # The pipeline's __call__ returns a generator yielding (graphemes, phoneme_chunk, audio_chunk).
        for i, (gs, ps, audio_chunk) in enumerate(
                self.pipeline(text, voice=voice_name, speed=speed)):
            if self.verbose:
                print(f"[KokoroTTSInference] Chunk {i}:")
                print(f"  Graphemes: {gs}")
                print(f"  Phonemes: {ps}")
            if audio_chunk is not None:
                # Ensure the audio chunk is on CPU and converted to a numpy array.
                if isinstance(audio_chunk, torch.Tensor):
                    audio_np = audio_chunk.cpu().numpy()
                else:
                    audio_np = audio_chunk
                audio_chunks.append(audio_np)
            phoneme_outputs.append(ps)

        if not audio_chunks:
            raise RuntimeError("No audio was generated by the pipeline.")

        # Concatenate all audio chunks along the time dimension.
        final_audio = np.concatenate(audio_chunks, axis=0)
        # Concatenate all phoneme strings (with spaces between chunks).
        final_phoneme_output = " ".join(phoneme_outputs)

        # Convert final audio from float32 (range [-1,1]) to int16 for file export.
        audio_int16 = (final_audio * 32767).astype(np.int16)
        audio_segment = AudioSegment(
            audio_int16.tobytes(),
            frame_rate=24000,
            sample_width=2,  # 16-bit audio
            channels=1
        )

        if save_file:
            if not file_path:
                raise ValueError("file_path must be provided when save_file is True.")
            audio_segment.export(file_path, format=format)
            if self.verbose:
                print(f"[KokoroTTSInference] Saved concatenated audio to {file_path}")

        return final_audio, final_phoneme_output
    

@register_tts("polly")
class PollyTTSInference(TTSInference):
    """PollyTTSInference facilitates Text-to-Speech inference using Amazon Polly.
    
    Automatically chunks long text and concatenates the results.
    
    Args:
        voice_name: Name of the Amazon Polly voice (default: "Joanna").
        speaker_speed: Speed factor (via SSML <prosody> tag).
        engine: Polly engine ("standard" or "neural").
        verbose: Print debug logs if True.
        max_chars: Max chunk size in characters. For SSML, 1500 is typical.
        
    Attributes:
        region: AWS region.
        voice_name: Polly voice name.
        speaker_speed: Speed factor for speech.
        polly_client: Boto3 Polly client.
        engine: "standard" or "neural" engine.
        max_chars: Maximum number of characters per chunk.
        
    Note:
        Requires environment variables (via dotenv):
            AWS_ACCESS_KEY_ID
            AWS_SECRET_ACCESS_KEY
            AWS_SESSION_TOKEN (optional)
            REGION_NAME (default: 'us-east-1')
    """

    def __init__(
        self,
        voice_name: str = "Joanna",
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
        self.voice_name = voice_name

        if self.verbose:
            print(f"[PollyTTS] Initialized. Voice={self.voice_name}, Engine={self.engine}, Region={self.region}")

    def invoke(
        self,
        text: str,
        save_file: bool = True,
        file_path: str | None = None,
        format: str = "wav"
    ) -> Tuple[np.ndarray, Dict]:
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
        if format.lower() not in SUPPORTED_AUDIO_FORMATS:
            raise ValueError(
                f"Format '{format}' not supported. "
                f"Choose from: {SUPPORTED_AUDIO_FORMATS}"
            )

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
                    VoiceId=self.voice_name,
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

        if save_file:
            if not file_path:
                raise ValueError("Must provide file_path if save_file=True.")
            final_audio_segment.export(file_path, format=format)
            if self.verbose:
                print(f"[PollyTTS] Combined audio saved to {file_path}")


        return audio_data, {}


@register_tts("openai")
class OpenAITTSInference(TTSInference):
    """OpenAITTSInference facilitates Text-to-Speech inference using OpenAI's TTS API.
    
    Handles text longer than 4096 chars by automatically splitting into sentence-based chunks.
    Implements exponential backoff retry logic for API rate limits.
    
    Args:
        model_name: The TTS model to use from OpenAI (e.g., "tts-1").
        voice_name: The voice name to use (e.g., "alloy").
        speaker_speed: Speed factor for speech (currently no effect in OpenAI TTS).
        verbose: If True, prints debug statements.
        
    Attributes:
        model_name: Model used for TTS (e.g., "tts-1").
        voice_name: Voice name (e.g., "alloy").
        speaker_speed: Speed factor (not yet supported in OpenAI TTS).
        verbose: Controls debug logging.
        client: The OpenAI client instance.
        max_chars: Maximum text length allowed per TTS API call (4096).
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    def _call_tts_api(self, chunk: str):
        """
        Call the OpenAI TTS API with exponential backoff retry logic.
        Will retry up to 3 times with exponential delays between 4 and 60 seconds.

        Args:
            chunk (str): The text chunk to synthesize.

        Returns:
            The API response.

        Raises:
            Exception: If all retries are exhausted.
        """
        try:
            if self.verbose:
                print("[OpenAI TTS] Calling TTS API...")
            response = self.client.audio.speech.create(
                model=self.model_name,
                voice=self.voice_name,
                input=chunk
            )
            return response
        except Exception as e:
            if self.verbose:
                print(f"[OpenAI TTS] API call failed: {str(e)}, retrying...")
            raise

    def invoke(
        self,
        text: str,
        save_file: bool = True,
        file_path: str | None = None,
        format: str = "wav"
    ) -> Tuple[np.ndarray, Dict]:
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
        # Validate output format
        if format.lower() not in SUPPORTED_AUDIO_FORMATS:
            raise ValueError(
                f"Format '{format}' not supported. "
                f"Choose from: {SUPPORTED_AUDIO_FORMATS}"
            )

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

            # 2a. Call the TTS API with retry logic
            try:
                response = self._call_tts_api(chunk)
            except Exception as e:
                print("[OpenAI TTS] All retry attempts failed:", e)
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

        return audio_data, {}


@register_tts("dia")
class DiaTTSInference(TTSInference):
    """Dia TTS wrapper with optional two-speaker voice cloning.
    
    Args:
        model_name: Name of the Dia model to use.
        speaker_samples: Mapping for "S1"/"S2":
            - "alice.wav" → transcript auto-generated by Whisper
            - ("Hi, I'm Alice.", "alice.wav") → transcript supplied
            - None → no cloning (random Dia voice)
        seed: Optional[int] = 42,
            Global random seed for deterministic sampling (default: 42). Set to None to disable deterministic seeding.
        device: Device to run inference on (e.g., "cuda:0", "cpu").
        verbose: If True, prints debug information.
        max_chars: Maximum characters per chunk.
        whisper_lang_hint: Optional language hint for Whisper transcription.
        
    Example:
        ```python
        tts = DiaTTSInference(
            speaker_samples={"S1": "alice.wav", "S2": ("Hello!", "bob.mp3")},
            verbose=True
        )
        audio_np, _ = tts.invoke(my_script, save_file=True, file_path="out.wav")
        ```
    """

    _TAG_RE = re.compile(r"\[(S[12])\]")

    def __init__(
        self,
        model_name: str = "nari-labs/Dia-1.6B",
        *,
        speaker_samples: Optional[Dict[str, str | Tuple[str, str]]] = None,
        seed: Optional[int] = 42,
        device: Optional[torch.device | str] = None,
        verbose: bool = False,
        max_chars: Optional[int] = None,
        whisper_lang_hint: Optional[str] = None,
    ):
        """Initialize the Dia TTS wrapper.
        
        Args:
            model_name: Name of the Dia model to use.
            speaker_samples: Mapping for speaker voice cloning.
            seed: Optional random seed for deterministic sampling.
            device: Device to run inference on.
            verbose: If True, prints debug information.
            max_chars: Maximum characters per chunk.
            whisper_lang_hint: Optional language hint for Whisper.
        """
        self.verbose = verbose
        # Apply deterministic seed (if provided) **before** any generation happens
        if seed is not None:
            _set_global_seed(seed)
            if self.verbose:
                print(f"[DiaTTS] Global RNG seed set to {seed}")
        self.seed = seed
        self.whisper_lang_hint = whisper_lang_hint
        self.model = Dia.from_pretrained(model_name, device=device)
        self.device = self.model.device
        self.max_chars = max_chars or self.model.config.data.text_length

        # normalise + (if needed) auto‑transcribe cloning samples  -------------
        self.speaker_samples: Dict[str, Optional[Tuple[str, str]]] = {"S1": None, "S2": None}
        if speaker_samples:
            for tag, val in speaker_samples.items():
                if tag not in ("S1", "S2"):
                    warnings.warn(f"[DiaTTS] unknown speaker tag '{tag}' – skipped")
                    continue
                if val is None:
                    self.speaker_samples[tag] = None
                elif isinstance(val, tuple):
                    self.speaker_samples[tag] = val
                else:
                    # val is an audio path → make Whisper transcript
                    trans = _transcribe_with_whisper(val, whisper_lang_hint)
                    if self.verbose:
                        print(f"[DiaTTS] Whisper transcript for {tag}: {trans}")
                    self.speaker_samples[tag] = (trans, val)

        if self.verbose:
            msg = ", ".join(
                f"{k}:{'clone' if v else 'random'}" for k, v in self.speaker_samples.items()
            )
            print(f"[DiaTTS] ready on {self.device} (max_chars={self.max_chars}) – {msg}")

    @staticmethod
    def _split_by_speaker(txt: str) -> List[Tuple[str, str]]:
        """Split text into speaker-tagged segments.
        
        Args:
            txt: Input text with speaker tags [S1] and [S2].
            
        Returns:
            List of tuples (speaker_tag, utterance_text).
        """
        parts = DiaTTSInference._TAG_RE.split(txt)
        seq, cur, buf = [], None, []
        for tok in parts:
            if tok in ("S1", "S2"):
                if cur and buf:
                    seq.append((cur, "".join(buf).strip()))
                    buf = []
                cur = tok
            else:
                buf.append(tok)
        if cur and buf:
            seq.append((cur, "".join(buf).strip()))
        return seq

    @staticmethod
    def _concat_audio(arr: List[np.ndarray]) -> np.ndarray:
        """Concatenate audio arrays.
        
        Args:
            arr: List of numpy arrays containing audio samples.
            
        Returns:
            Single concatenated numpy array.
        """
        return arr[0] if len(arr) == 1 else np.concatenate(arr, 0)

    def invoke(
        self,
        text: str,
        *,
        temperature: float = 1.3,
        top_p: float = 0.95,
        cfg_scale: float = 3.0,
        save_file: bool = False,
        file_path: Optional[str] = None,
        format: str = "wav",
        speaker_samples_override: Optional[Dict[str, str | Tuple[str, str]]] = None
    ) -> Tuple[np.ndarray, Dict]:
        """Generates speech from input text with optional voice cloning.
        
        Args:
            text: The text to synthesize.
            temperature: Sampling temperature (higher = more random).
            top_p: Nucleus sampling probability threshold.
            cfg_scale: Classifier-free guidance scale.
            save_file: If True, saves the audio to disk.
            file_path: Output file path (required if save_file=True).
            format: Audio format ("wav", "mp3", etc.).
            speaker_samples_override: Optional one-shot override of speaker samples.
            
        Returns:
            A tuple containing:
                - final_audio: float32 numpy array of audio samples
                - empty_dict: Currently returns empty dict for compatibility
                
        Raises:
            ValueError: If file_path is not provided when save_file is True.
        """
        # Validate output format
        if format.lower() not in SUPPORTED_AUDIO_FORMATS:
            raise ValueError(
                f"Format '{format}' not supported. "
                f"Choose from: {SUPPORTED_AUDIO_FORMATS}"
            )
        # choose which samples set to use
        if speaker_samples_override is None:
            speaker_samples = self.speaker_samples
        else:
            # light merge – override whatever keys provided
            speaker_samples = {**self.speaker_samples, **speaker_samples_override}

       
        segments: List[np.ndarray] = []
        chunks = (
            chunk_text_by_sentences(text, self.max_chars)
            if len(text) > self.max_chars
            else [text]
        )

        for chunk in chunks:
            blocks = self._split_by_speaker(chunk)
            if not blocks:
                segments.append(
                    self.model.generate(chunk, temperature=temperature, top_p=top_p, cfg_scale=cfg_scale)
                )
                continue

            for spk, utter in blocks:
                sample = speaker_samples.get(spk)
                if sample:
                    trans, wav = sample
                    prompt = f"[{spk}] {trans} {utter}"
                    audio_np = self.model.generate(
                        prompt,
                        temperature=temperature,
                        top_p=top_p,
                        cfg_scale=cfg_scale,
                        audio_prompt_path=wav
                    )
                else:
                    audio_np = self.model.generate(
                        f"[{spk}] {utter}",
                        temperature=temperature,
                        top_p=top_p,
                        cfg_scale=cfg_scale
                    )
                segments.append(audio_np)

        final_audio = self._concat_audio(segments).astype(np.float32)

        if save_file:
            if not file_path:
                raise ValueError("file_path required when save_file=True")
            if format.lower() == "wav":
                sf.write(file_path, final_audio, 44100)
            else:
                int16 = (final_audio * 32767).astype(np.int16)
                AudioSegment(int16.tobytes(), frame_rate=44100, sample_width=2, channels=1).export(
                    file_path, format=format
                )
            if self.verbose:
                print(f"[DiaTTS] saved → {file_path}")

        return final_audio, {}