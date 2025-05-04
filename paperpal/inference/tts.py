# Standard library imports
import io
import os
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
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_exponential



#: Tuple of audio formats accepted by all engines.
SUPPORTED_AUDIO_FORMATS: Tuple[str, ...] = ("wav", "mp3", "ogg", "flac")
_TTS_REGISTRY: Dict[str, Type["TTSInference"]] = {}
_WHISPER_PIPE = None



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
    """Return a cached Whisper automatic-speech-recognition pipeline.

    The first call downloads and initialises the
    ``openai/whisper-large-v3-turbo`` checkpoint (preferring CUDA, then
    Metal, then CPU).  The resulting Hugging Face pipeline object is stored
    globally, so subsequent calls are essentially free.

    Args:
        lang_hint (str | None): Optional BCP-47 language tag that tells
            Whisper which language to expect in the input audio.  If
            ``None``, Whisper will perform language detection.

    Returns:
        transformers.pipelines.audio_utils.AudioPipeline: Ready-to-use
        Whisper pipeline for speech-to-text inference.
    """
    global _WHISPER_PIPE
    if _WHISPER_PIPE is None:
        from transformers import (  # heavy import – keep local
            AutoModelForSpeechSeq2Seq,
            AutoProcessor,
            pipeline,
        )

        model_id = "openai/whisper-large-v3-turbo"
        # Prefer CUDA → MPS → CPU
        if torch.cuda.is_available():
            device_for_model = torch.device("cuda")
            device_for_pipeline = 0               # HF pipeline convention
            torch_dtype = torch.float16
            backend = "CUDA"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device_for_model = torch.device("mps")
            device_for_pipeline = torch.device("mps")
            torch_dtype = torch.float16
            backend = "MPS"
        else:
            device_for_model = torch.device("cpu")
            device_for_pipeline = -1              # CPU
            torch_dtype = torch.float32
            backend = "CPU"

        print(f"[DiaTTS] Loading Whisper ({model_id}) on {backend} …"
              + (" (may be slow)" if backend == "CPU" else ""))

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        ).to(device_for_model)

        processor = AutoProcessor.from_pretrained(model_id)

        _WHISPER_PIPE = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=torch_dtype,
            device=device_for_pipeline,
        )

    return _WHISPER_PIPE


def _transcribe_with_whisper(audio_path: str, language: Optional[str] = None) -> str:
    """Transcribe an audio file with Whisper.

    Args:
        audio_path (str): Path to a mono or stereo audio file.  Any format
            supported by ffmpeg/torchaudio is accepted.
        language (str | None): Optional BCP‑47 language hint.  Passed through
            to :func:`_lazy_whisper`.

    Returns:
        str: The transcription text with leading/trailing whitespace removed.
    """
    pipe = _lazy_whisper(language)
    result = pipe(
        audio_path,
        generate_kwargs={"language": language} if language else None,
    )
    return result["text"].strip()


def chunk_text_by_sentences(text: str, max_len: int = 4096) -> List[str]:
    """Split *text* into chunks no longer than *max_len* characters.

    The algorithm tokenises by sentence terminators (``. ? !``).  If a single
    sentence still exceeds *max_len*, the sentence itself is broken into
    contiguous sub‑strings.

    Args:
        text (str): Input text.
        max_len (int, optional): Maximum chunk length in characters.
            Defaults to ``4096``.

    Returns:
        list[str]: List of sentence‑level chunks, each stripped of leading
        and trailing whitespace.
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



# ---------------------------------------------------------------------------
@register_tts("orpheus")
class OrpheusTTSInference(TTSInference):
    """Inference wrapper for the open-source **Orpheus** TTS model.

    It supports:
      • **Named voices** - e.g. ``"tara"``, ``"leo"``.
      • **Zer-shot voice cloning** - pass one or more reference WAV paths
        via *clone_voice_samples*.

    The class streams audio from :class:`orpheus_tts.OrpheusModel`,
    concatenates the int-16 chunks, converts them to a ``float32`` NumPy
    array in the range ``[-1, 1]``, and optionally writes the result to
    disk.
    """

    def __init__(
        self,
        model_name: str = "canopylabs/orpheus-tts-0.1-finetune-prod",
        voice_name: str = "tara",
        sample_rate: int = 24_000,
        verbose: bool = False,
        **engine_kwargs,
    ):
        from orpheus_tts import OrpheusModel
        self.sample_rate = sample_rate
        self.voice_name = voice_name
        self.verbose = verbose

        # Lazily load the Orpheus backend (vLLM + SNAC decoder under the hood)
        self.engine = OrpheusModel(model_name=model_name, **engine_kwargs)

    # ------------------------------------------------------------------ #
    def invoke(
        self,
        text: str,
        voice_name: str | None = None,
        clone_voice_samples: Optional[List[str]] = None,
        clone_transcripts: Optional[List[str]] = None,
        save_file: bool = False,
        file_path: str | None = None,
        format: str = "wav",
        **generation_kwargs,
    ) -> Tuple[np.ndarray, Dict]:
        """Generate speech from *text*.

        Parameters
        ----------
        text:
            The text to synthesise.
        voice_name:
            One of the built-in Orpheus voices (defaults to *self.voice_name*).
        clone_voice_samples:
            Optional list of WAV paths for zero-shot voice cloning.
        save_file:
            If *True*, export the final audio to *file_path*.
        file_path:
            Destination path used when *save_file* is *True*.
        format:
            Output audio container (``wav``, ``mp3``, ``ogg``, ``flac``).
        **generation_kwargs:
            Extra keyword arguments forwarded to
            :py:meth:`orpheus_tts.OrpheusModel.generate_speech`.

        Returns
        -------
        audio_data:
            ``float32`` NumPy array, mono, normalised to ``[-1, 1]``.
        metadata:
            Empty ``dict`` (reserved for future extensions).
        """
        if format.lower() not in SUPPORTED_AUDIO_FORMATS:
            raise ValueError(
                f"Format '{format}' not supported. "
                f"Choose from: {SUPPORTED_AUDIO_FORMATS}"
            )

        voice_name = voice_name or self.voice_name

        # ------------------------------------------------------------------
        # Handle voice‑cloning references
        if clone_voice_samples:
            # Normalise transcripts list length to match samples list length.
            transcripts: List[str] = clone_transcripts[:] if clone_transcripts else []
            if len(transcripts) < len(clone_voice_samples):
                if self.verbose:
                    print("[OrpheusTTS] Auto‑transcribing reference audio with Whisper…")
                for i, wav_path in enumerate(clone_voice_samples[len(transcripts):], start=len(transcripts)):
                    try:
                        tr_text = _transcribe_with_whisper(wav_path)
                    except Exception as exc:
                        warnings.warn(f"Whisper failed on '{wav_path}': {exc}")
                        tr_text = ""
                    transcripts.append(tr_text)

            if len(transcripts) != len(clone_voice_samples):
                raise ValueError(
                    "clone_voice_samples and clone_transcripts must have the same length "
                    f"(got {len(clone_voice_samples)} samples vs {len(transcripts)} transcripts)."
                )

            # Add to generation kwargs expected by OrpheusModel
            gen_kwargs = {
                "prompt": text,
                "voice": voice_name,
                **generation_kwargs,
            }
            gen_kwargs["clone_voice_samples"] = clone_voice_samples
            gen_kwargs["clone_transcripts"] = transcripts
        else:
            # Build argument dict understood by OrpheusModel
            gen_kwargs: Dict[str, any] = {
                "prompt": text,
                "voice": voice_name,
                **generation_kwargs,
            }

        if self.verbose:
            print(f"[OrpheusTTS] Synthesising with voice='{voice_name}'…")

        # Collect streamed audio chunks (each chunk is raw int16 bytes)
        audio_chunks: List[bytes] = []
        for chunk in self.engine.generate_speech(**gen_kwargs):
            audio_chunks.append(chunk)

        if not audio_chunks:
            raise RuntimeError("Orpheus produced no audio.")

        audio_bytes = b''.join(audio_chunks)

        # Convert to float32 numpy array in [-1, 1]
        samples_i16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_data = samples_i16.astype(np.float32) / 32767.0

        # Optionally save to disk
        if save_file:
            if not file_path:
                raise ValueError("file_path must be provided when save_file=True.")
            segment = AudioSegment(
                audio_bytes,
                frame_rate=self.sample_rate,
                sample_width=2,   # 16‑bit
                channels=1,
            )
            segment.export(file_path, format=format)
            if self.verbose:
                print(f"[OrpheusTTS] Saved audio to {file_path}")

        return audio_data, {}

@register_tts("orpheus-cpp")
class OrpheusCppInference(TTSInference):
    """TTS wrapper for **orpheus-cpp** (llama.cpp backend, Metal-friendly).

    *No voice-cloning yet* – only built-in voices like ``"tara"`` or ``"leo"``.
    """

    def __init__(
        self,
        voice_name: str = "tara",
        lang: str = "en",
        sample_rate: int = 24_000,
        verbose: bool = False,
        **engine_kwargs,
    ):
        from orpheus_cpp import OrpheusCpp
        self.voice_name = voice_name
        self.lang = lang
        self.sample_rate = sample_rate
        self.verbose = verbose

        # OrpheusCpp automatically chooses MPS on Apple Silicon or CPU.
        self.engine = OrpheusCpp(verbose=verbose, lang=lang, **engine_kwargs)

    # ------------------------------------------------------------------ #
    def invoke(
        self,
        text: str,
        voice_name: str | None = None,
        save_file: bool = False,
        file_path: str | None = None,
        format: str = "wav",
        **generation_kwargs,
    ) -> Tuple[np.ndarray, Dict]:
        """Generate speech from *text* using the **orpheus‑cpp** backend.

        Args:
            text (str): Text to be synthesised.
            voice_name (str | None): Built‑in Orpheus voice ID.  If
                ``None``, the instance default is used.
            save_file (bool, optional): If ``True``, the generated audio is
                written to *file_path*.  Defaults to ``False``.
            file_path (str | None, optional): Destination path when
                *save_file* is ``True``.  Ignored otherwise.
            format (str, optional): Output container (``'wav'``,
                ``'mp3'``, ``'ogg'`` or ``'flac'``).  Defaults to ``'wav'``.
            **generation_kwargs: Extra keyword arguments forwarded to
                :py:meth:`orpheus_cpp.OrpheusCpp.stream_tts_sync`.

        Returns:
            tuple[np.ndarray, dict]: A two‑tuple ``(audio, meta)`` where
            ``audio`` is a **float32** NumPy array normalised to ``[-1, 1]``
            and ``meta`` is an empty dictionary (reserved for future
            extensions).

        Raises:
            ValueError: If *format* is unsupported or *file_path* is missing
                when *save_file* is ``True``.
            RuntimeError: If the backend returns no audio chunks.
        """
        if format.lower() not in SUPPORTED_AUDIO_FORMATS:
            raise ValueError(
                f"Format '{format}' not supported. "
                f"Choose from: {SUPPORTED_AUDIO_FORMATS}"
            )

        voice_id = voice_name or self.voice_name
        if self.verbose:
            print(f"[OrpheusCpp] Synthesising with voice_id='{voice_id}'…")

        # Collect streamed int-16 chunks
        chunks: list[np.ndarray] = []
        for sr, chunk in self.engine.stream_tts_sync(
            text, options={"voice_id": voice_id, **generation_kwargs}
        ):
            self.sample_rate = sr  # backend tells us
            chunks.append(chunk)

        if not chunks:
            raise RuntimeError("OrpheusCpp produced no audio.")

        audio_i16 = np.concatenate(chunks, axis=1).squeeze()
        audio_f32 = audio_i16.astype(np.float32) / 32767.0

        if save_file:
            if not file_path:
                raise ValueError("file_path must be provided when save_file=True.")
            AudioSegment(
                audio_i16.tobytes(),
                frame_rate=self.sample_rate,
                sample_width=2,
                channels=1,
            ).export(file_path, format=format)
            if self.verbose:
                print(f"[OrpheusCpp] Saved audio to {file_path}")

        return audio_f32, {}