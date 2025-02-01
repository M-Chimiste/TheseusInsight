from kokoro.model import KModel
from huggingface_hub import hf_hub_download
from misaki import en, espeak
from numbers import Number
from typing import Generator, List, Optional, Tuple, Union
from loguru import logger
import re
import torch

LANG_CODES = dict(
    # pip install misaki[en]
    a='American English',
    b='British English',

    # espeak-ng
    e='es',
    f='fr-fr',
    h='hi',
    i='it',
    p='pt-br',

    # pip install misaki[ja]
    j='Japanese',

    # pip install misaki[zh]
    z='Mandarin Chinese',
)

class KPipeline:
    '''
    KPipeline is a language-aware support class with 2 main responsibilities:
    1. Perform language-specific G2P, mapping (and chunking) text -> phonemes
    2. Manage and store voices, lazily downloaded from HF if needed

    You are expected to have one KPipeline per language. If you have multiple
    KPipelines, you should reuse one KModel instance across all of them.

    KPipeline is designed to work with a KModel, but this is not required.
    There are 2 ways to pass an existing model into a pipeline:
    1. On init: us_pipeline = KPipeline(lang_code='a', model=model)
    2. On call: us_pipeline(text, voice, model=model)

    By default, KPipeline will automatically initialize its own KModel. To
    suppress this, construct a "quiet" KPipeline with model=False.

    A "quiet" KPipeline yields (graphemes, phonemes, None) without generating
    any audio. You can use this to phonemize and chunk your text in advance.

    A "loud" KPipeline _with_ a model yields (graphemes, phonemes, audio).
    '''
    def __init__(
        self,
        lang_code: str,
        model: Union[KModel, bool] = True,
        trf: bool = False,
        device: Optional[str] = None
    ):
        """Initialize a KPipeline.
        
        Args:
            lang_code: Language code for G2P processing
            model: KModel instance, True to create new model, False for no model
            trf: Whether to use transformer-based G2P
            device: Override default device selection ('cuda' or 'cpu', or None for auto)
                   If None, will auto-select cuda if available
                   If 'cuda' and not available, will explicitly raise an error
        """
        assert lang_code in LANG_CODES, (lang_code, LANG_CODES)
        self.lang_code = lang_code
        self.model = None
        if isinstance(model, KModel):
            self.model = model
        elif model:
            if device == 'cuda' and not torch.cuda.is_available():
                raise RuntimeError("CUDA requested but not available")
            if device is None:
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
            try:
                self.model = KModel().to(device).eval()
            except RuntimeError as e:
                if device == 'cuda':
                    raise RuntimeError(f"""Failed to initialize model on CUDA: {e}. 
                                       Try setting device='cpu' or check CUDA installation.""")
                raise
        self.voices = {}
        if lang_code in 'ab':
            try:
                fallback = espeak.EspeakFallback(british=lang_code=='b')
            except Exception as e:
                logger.warning("EspeakFallback not Enabled: OOD words will be skipped")
                logger.warning({str(e)})
                fallback = None
            self.g2p = en.G2P(trf=trf, british=lang_code=='b', fallback=fallback)
        elif lang_code == 'j':
            try:
                from misaki import ja
                self.g2p = ja.JAG2P()
            except ImportError:
                logger.error("You need to `pip install misaki[ja]` to use lang_code='j'")
                raise
        elif lang_code == 'z':
            try:
                from misaki import zh
                self.g2p = zh.ZHG2P()
            except ImportError:
                logger.error("You need to `pip install misaki[zh]` to use lang_code='z'")
                raise
        else:
            language = LANG_CODES[lang_code]
            logger.warning(f"Using EspeakG2P(language='{language}'). Chunking logic not yet implemented, so long texts may be truncated unless you split them with '\\n'.")
            self.g2p = espeak.EspeakG2P(language=language)

    def load_single_voice(self, voice: str):
        if voice in self.voices:
            return self.voices[voice]
        if voice.endswith('.pt'):
            f = voice
        else:
            f = hf_hub_download(repo_id=KModel.REPO_ID, filename=f'voices/{voice}.pt')
            if not voice.startswith(self.lang_code):
                v = LANG_CODES.get(voice, voice)
                p = LANG_CODES.get(self.lang_code, self.lang_code)
                logger.warning(f'Language mismatch, loading {v} voice into {p} pipeline.')
        pack = torch.load(f, weights_only=True)
        self.voices[voice] = pack
        return pack

    """
    load_voice is a helper function that lazily downloads and loads a voice:
    Single voice can be requested (e.g. 'af_bella') or multiple voices (e.g. 'af_bella,af_jessica').
    If multiple voices are requested, they are averaged.
    Delimiter is optional and defaults to ','.
    """
    def load_voice(self, voice: str, delimiter: str = ",") -> torch.FloatTensor:
        if voice in self.voices:
            return self.voices[voice]
        packs = [self.load_single_voice(v) for v in voice.split(delimiter)]
        if len(packs) == 1:
            return packs[0]
        self.voices[voice] = torch.mean(torch.stack(packs), dim=0)
        return self.voices[voice]

    @classmethod
    def infer(
        cls,
        model: Optional[KModel],
        ps: str,
        pack: torch.FloatTensor,
        speed: Number
    ) -> Optional[torch.FloatTensor]:
        # Here we assume that the “voice pack” (a tensor) is indexed by (len(ps)-1)
        # where ps is the phoneme string for this chunk.
        return model(ps, pack[len(ps)-1], speed) if model else None

    #
    # NEW: Helpers for chunking based on the Kokoro-style logic
    #

    @staticmethod
    def get_vocab() -> dict:
        _pad = "$"
        _punctuation = ';:,.!?¡¿—…"«»“” '
        _letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        _letters_ipa = "ɑɐɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴøɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱʌɣɤʍχʎʏʑʐʒʔʡʕʢǀǁǂǃˈˌːˑʼʴʰʱʲʷˠˤ˞↓↑→↗↘'̩'ᵻ"
        symbols = [_pad] + list(_punctuation) + list(_letters) + list(_letters_ipa)
        return {s: i for i, s in enumerate(symbols)}

    @staticmethod
    def tokenize(ps: str, vocab: dict) -> List[int]:
        # Only keep symbols that exist in the vocabulary.
        return [v for v in map(vocab.get, ps) if v is not None]

    @staticmethod
    def detokenize(tokens: List[int], inv_vocab: dict) -> str:
        return ''.join(inv_vocab[t] for t in tokens if t in inv_vocab)

    def _chunk_phoneme_string(self, ps: str, max_chunk_size: int = 510) -> List[str]:
        """
        Given a phoneme string, use our VOCAB to convert it to token ids.
        If the token list is longer than max_chunk_size, split it into chunks and then
        reassemble a phoneme string from each chunk.
        """
        token_ids = KPipeline.tokenize(ps, KPipeline.VOCAB)
        if len(token_ids) <= max_chunk_size:
            return [ps]
        chunks = []
        for i in range(0, len(token_ids), max_chunk_size):
            chunk_ids = token_ids[i:i + max_chunk_size]
            chunk_str = KPipeline.detokenize(chunk_ids, KPipeline.INV_VOCAB)
            chunks.append(chunk_str)
        return chunks

    @staticmethod
    def _flatten_tokens(tokens) -> List:
        """
        Helper to flatten the list returned by the English G2P (which may contain sublists).
        """
        flat = []
        for t in tokens:
            if isinstance(t, list):
                flat.extend(t)
            else:
                flat.append(t)
        return flat

    def __call__(
        self,
        text: Union[str, List[str]],
        voice: str,
        speed: Number = 1,
        split_pattern: Optional[str] = r'\n+',
        model: Optional[KModel] = None
    ) -> Generator[Tuple[str, str, Optional[torch.FloatTensor]], None, None]:
        """
        Modified __call__ uses new chunking logic:
          1. For each input sentence (separated by split_pattern) it obtains a full phoneme string.
          2. It then converts that string to tokens using a vocabulary and splits it into chunks of at most 510 tokens.
          3. Each chunk is then forwarded (with an appropriate reference index into the voice pack) to generate audio.
        """
        logger.debug(f"Loading voice: {voice}")
        pack = self.load_voice(voice)
        model = model or self.model
        if model:
            pack = pack.to(model.device)
        logger.debug(f"Voice loaded on device: {pack.device if hasattr(pack, 'device') else 'N/A'}")
        if isinstance(text, str):
            text = re.split(split_pattern, text.strip()) if split_pattern else [text]
        for graphemes in text:
            if self.lang_code in 'ab':
                logger.debug(f"Processing English text: {graphemes[:50]}{'...' if len(graphemes) > 50 else ''}")
                # For English, our g2p returns a tuple: (unused, tokens)
                _, tokens = self.g2p(graphemes)
                flat_tokens = KPipeline._flatten_tokens(tokens)
                # Build the full phoneme string from the tokens that have a phonemes attribute
                full_ps = ''.join(t.phonemes for t in flat_tokens if t.phonemes)
                chunks = self._chunk_phoneme_string(full_ps, max_chunk_size=510)
                for chunk in chunks:
                    if not chunk:
                        continue
                    if len(chunk) > 510:
                        logger.warning(f"Chunk length {len(chunk)} > 510, truncating.")
                        chunk = chunk[:510]
                    yield graphemes, chunk, KPipeline.infer(model, chunk, pack, speed)
            else:
                # For non-English, assume g2p returns a phoneme string directly.
                ps = self.g2p(graphemes)
                if not ps:
                    continue
                chunks = self._chunk_phoneme_string(ps, max_chunk_size=510)
                for chunk in chunks:
                    if not chunk:
                        continue
                    if len(chunk) > 510:
                        logger.warning(f'Chunk length {len(chunk)} > 510, truncating.')
                        chunk = chunk[:510]
                    yield graphemes, chunk, KPipeline.infer(model, chunk, pack, speed)

# Initialize class-level vocabulary mappings (so that we only build them once)
KPipeline.VOCAB = KPipeline.get_vocab()
KPipeline.INV_VOCAB = {v: k for k, v in KPipeline.VOCAB.items()}