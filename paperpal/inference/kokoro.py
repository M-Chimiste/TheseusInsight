# https://huggingface.co/hexgrad/Kokoro-82M/blob/main/kokoro.py
import phonemizer
import re
import torch
import platform
import numpy as np
if platform.system() == "Darwin":
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    _ESPEAK_LIBRARY = '/opt/homebrew/bin/espeak'  #use the Path to the library.
    EspeakWrapper.set_library(_ESPEAK_LIBRARY)

def split_num(num):
    num = num.group()
    if '.' in num:
        return num
    elif ':' in num:
        h, m = [int(n) for n in num.split(':')]
        if m == 0:
            return f"{h} o'clock"
        elif m < 10:
            return f'{h} oh {m}'
        return f'{h} {m}'
    year = int(num[:4])
    if year < 1100 or year % 1000 < 10:
        return num
    left, right = num[:2], int(num[2:4])
    s = 's' if num.endswith('s') else ''
    if 100 <= year % 1000 <= 999:
        if right == 0:
            return f'{left} hundred{s}'
        elif right < 10:
            return f'{left} oh {right}{s}'
    return f'{left} {right}{s}'

def flip_money(m):
    m = m.group()
    bill = 'dollar' if m[0] == '$' else 'pound'
    if m[-1].isalpha():
        return f'{m[1:]} {bill}s'
    elif '.' not in m:
        s = '' if m[1:] == '1' else 's'
        return f'{m[1:]} {bill}{s}'
    b, c = m[1:].split('.')
    s = '' if b == '1' else 's'
    c = int(c.ljust(2, '0'))
    coins = f"cent{'' if c == 1 else 's'}" if m[0] == '$' else ('penny' if c == 1 else 'pence')
    return f'{b} {bill}{s} and {c} {coins}'

def point_num(num):
    a, b = num.group().split('.')
    return ' point '.join([a, ' '.join(b)])

def normalize_text(text):
    text = text.replace(chr(8216), "'").replace(chr(8217), "'")
    text = text.replace('«', chr(8220)).replace('»', chr(8221))
    text = text.replace(chr(8220), '"').replace(chr(8221), '"')
    text = text.replace('(', '«').replace(')', '»')
    for a, b in zip('、。！，：；？', ',.!,:;?'):
        text = text.replace(a, b+' ')
    text = re.sub(r'[^\S \n]', ' ', text)
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'(?<=\n) +(?=\n)', '', text)
    text = re.sub(r'\bD[Rr]\.(?= [A-Z])', 'Doctor', text)
    text = re.sub(r'\b(?:Mr\.|MR\.(?= [A-Z]))', 'Mister', text)
    text = re.sub(r'\b(?:Ms\.|MS\.(?= [A-Z]))', 'Miss', text)
    text = re.sub(r'\b(?:Mrs\.|MRS\.(?= [A-Z]))', 'Mrs', text)
    text = re.sub(r'\betc\.(?! [A-Z])', 'etc', text)
    text = re.sub(r'(?i)\b(y)eah?\b', r"\1e'a", text)
    text = re.sub(r'\d*\.\d+|\b\d{4}s?\b|(?<!:)\b(?:[1-9]|1[0-2]):[0-5]\d\b(?!:)', split_num, text)
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    text = re.sub(r'(?i)[$£]\d+(?:\.\d+)?(?: hundred| thousand| (?:[bm]|tr)illion)*\b|[$£]\d+\.\d\d?\b', flip_money, text)
    text = re.sub(r'\d*\.\d+', point_num, text)
    text = re.sub(r'(?<=\d)-(?=\d)', ' to ', text)
    text = re.sub(r'(?<=\d)S', ' S', text)
    text = re.sub(r"(?<=[BCDFGHJ-NP-TV-Z])'?s\b", "'S", text)
    text = re.sub(r"(?<=X')S\b", 's', text)
    text = re.sub(r'(?:[A-Za-z]\.){2,} [a-z]', lambda m: m.group().replace('.', '-'), text)
    text = re.sub(r'(?i)(?<=[A-Z])\.(?=[A-Z])', '-', text)
    return text.strip()

def get_vocab():
    _pad = "$"
    _punctuation = ';:,.!?¡¿—…"«»“” '
    _letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    _letters_ipa = "ɑɐɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴøɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱʌɣɤʍχʎʏʑʐʒʔʡʕʢǀǁǂǃˈˌːˑʼʴʰʱʲʷˠˤ˞↓↑→↗↘'̩'ᵻ"
    symbols = [_pad] + list(_punctuation) + list(_letters) + list(_letters_ipa)
    dicts = {}
    for i in range(len((symbols))):
        dicts[symbols[i]] = i
    return dicts

VOCAB = get_vocab()
def tokenize(ps):
    return [i for i in map(VOCAB.get, ps) if i is not None]

phonemizers = dict(
    a=phonemizer.backend.EspeakBackend(language='en-us', preserve_punctuation=True, with_stress=True),
    b=phonemizer.backend.EspeakBackend(language='en-gb', preserve_punctuation=True, with_stress=True),
)
def phonemize(text, lang, norm=True):
    if norm:
        text = normalize_text(text)
    ps = phonemizers[lang].phonemize([text])
    ps = ps[0] if ps else ''
    # https://en.wiktionary.org/wiki/kokoro#English
    ps = ps.replace('kəkˈoːɹoʊ', 'kˈoʊkəɹoʊ').replace('kəkˈɔːɹəʊ', 'kˈəʊkəɹəʊ')
    ps = ps.replace('ʲ', 'j').replace('r', 'ɹ').replace('x', 'k').replace('ɬ', 'l')
    ps = re.sub(r'(?<=[a-zɹː])(?=hˈʌndɹɪd)', ' ', ps)
    ps = re.sub(r' z(?=[;:,.!?¡¿—…"«»“” ]|$)', 'z', ps)
    if lang == 'a':
        ps = re.sub(r'(?<=nˈaɪn)ti(?!ː)', 'di', ps)
    ps = ''.join(filter(lambda p: p in VOCAB, ps))
    return ps.strip()

def length_to_mask(lengths):
    mask = torch.arange(lengths.max()).unsqueeze(0).expand(lengths.shape[0], -1).type_as(lengths)
    mask = torch.gt(mask+1, lengths.unsqueeze(1))
    return mask

@torch.no_grad()
def forward(model, tokens, ref_s, speed):
    device = ref_s.device
    tokens = torch.LongTensor([[0, *tokens, 0]]).to(device)
    input_lengths = torch.LongTensor([tokens.shape[-1]]).to(device)
    text_mask = length_to_mask(input_lengths).to(device)
    bert_dur = model.bert(tokens, attention_mask=(~text_mask).int())
    d_en = model.bert_encoder(bert_dur).transpose(-1, -2)
    s = ref_s[:, 128:]
    d = model.predictor.text_encoder(d_en, s, input_lengths, text_mask)
    x, _ = model.predictor.lstm(d)
    duration = model.predictor.duration_proj(x)
    duration = torch.sigmoid(duration).sum(axis=-1) / speed
    pred_dur = torch.round(duration).clamp(min=1).long()
    pred_aln_trg = torch.zeros(input_lengths, pred_dur.sum().item())
    c_frame = 0
    for i in range(pred_aln_trg.size(0)):
        pred_aln_trg[i, c_frame:c_frame + pred_dur[0,i].item()] = 1
        c_frame += pred_dur[0,i].item()
    en = d.transpose(-1, -2) @ pred_aln_trg.unsqueeze(0).to(device)
    F0_pred, N_pred = model.predictor.F0Ntrain(en, s)
    t_en = model.text_encoder(tokens, input_lengths, text_mask)
    asr = t_en @ pred_aln_trg.unsqueeze(0).to(device)
    return model.decoder(asr, F0_pred, N_pred, ref_s[:, :128]).squeeze().cpu().numpy()

def split_into_sentences(text):
    """
    Splits text on sentence boundaries (naive approach). 
    Captures the punctuation delimiters and reattaches them.
    """
    # If the text has no sentence punctuation, return as a single "sentence"
    if not re.search(r'[.?!]', text):
        return [text.strip()]

    # Split on sentence enders but keep them in the result
    parts = re.split(r'([.?!])', text)

    # Reconstruct each sentence by pairing the text with the delimiter
    sentences = []
    current = []
    for part in parts:
        if not part.strip():
            # ignore empty strings/spaces
            continue
        current.append(part)
        # If part is one of the delimiters, finalize the sentence
        if re.match(r'[.?!]', part):
            sentence = "".join(current).strip()
            # remove any trailing spaces, newlines, etc.
            sentences.append(sentence)
            current = []
    # Catch any leftover text that doesn't end with punctuation
    if current:
        leftover = "".join(current).strip()
        if leftover:
            sentences.append(leftover)

    return sentences

def build_chunk_strings(words, lang='a', max_chunk_size=510):
    """
    Splits a list of words into chunks of text, ensuring that each chunk does not exceed a specified maximum number of tokens.
    Args:
        words (list of str): The list of words to be chunked.
        lang (str, optional): The language code for phonemization. Defaults to 'a'.
        max_chunk_size (int, optional): The maximum number of tokens allowed in each chunk. Defaults to 510.
    Returns:
        list of str: A list of chunked text strings, each of which does not exceed the specified maximum number of tokens.
    """

    chunk_strings = []
    current_words = []
    
    # This function repeatedly attempts to add a word to the current chunk.
    # If adding the new word leads to > max_chunk_size tokens, we finalize
    # the current chunk (minus that last word), then start a new chunk.
    for i, w in enumerate(words):
        # Test what happens if we add this word to current_words
        test_words = current_words + [w]
        test_text = join_words_for_chunk(test_words)
        
        # Phonemize & tokenize the test string
        test_phonemes = phonemize(test_text, lang, norm=False)
        test_tokens = tokenize(test_phonemes)
        
        if len(test_tokens) <= max_chunk_size:
            # If it fits, accept
            current_words.append(w)
        else:
            # If adding this word causes the chunk to exceed 510 tokens,
            # then finalize the current chunk (minus that word).
            if current_words:
                finalized_text = join_words_for_chunk(current_words)
                chunk_strings.append(finalized_text)
            
            # Start a new chunk with this word as the first
            current_words = [w]
    
    # Flush any leftover words into the last chunk
    if current_words:
        final_text = join_words_for_chunk(current_words)
        chunk_strings.append(final_text)
    
    return chunk_strings

def chunk_sentence_tokens(sentence_text, lang='a', max_chunk_size=510):
    """
    Phonemize + tokenize the entire sentence.
    If it exceeds max_chunk_size tokens, break it up by word boundaries
    until each chunk is <= max_chunk_size tokens.

    Returns:
      A list of chunks (each chunk is a list of token ids).
    """
    # 1) Split sentence into words/punctuation
    #    We'll do the same "wordlike" approach as before
    word_pattern = r"[A-Za-z0-9]+|[^\sA-Za-z0-9]+"
    words = re.findall(word_pattern, sentence_text)

    # 2) Rebuild chunk text word by word, checking token length as we go
    chunks = []
    current_words = []

    def phonemize_and_tokenize(text):
        ph = phonemize(text, lang=lang, norm=False)
        return tokenize(ph)

    for w in words:
        test_phrase = join_words_for_chunk(current_words + [w])
        test_tokens = phonemize_and_tokenize(test_phrase)
        if len(test_tokens) <= max_chunk_size:
            # Fits in the chunk
            current_words.append(w)
        else:
            # Finalize the current chunk if it exists
            if current_words:
                chunk_text = join_words_for_chunk(current_words)
                chunks.append(phonemize_and_tokenize(chunk_text))
            # Start a new chunk with this word
            current_words = [w]

    # Flush remaining words
    if current_words:
        chunk_text = join_words_for_chunk(current_words)
        chunks.append(phonemize_and_tokenize(chunk_text))
    
    return chunks

def join_words_for_chunk(words):
    """
    Join words (including punctuation) into a string.
    We remove the leading space before punctuation if we want it flush.
    This is a naive approach that can be refined.
    """
    chunk_str = ""
    for i, w in enumerate(words):
        # If it's the first token, just place it
        if i == 0:
            chunk_str += w
        else:
            # Check if w is pure punctuation
            if re.match(r"^[^\w]+$", w):
                # punctuation, attach without leading space
                chunk_str += w
            else:
                chunk_str += " " + w
    return chunk_str

def chunk_sentence_tokens_once(sentence_text, lang='a', max_chunk_size=510):
    # Single phonemization
    ph = phonemize(sentence_text, lang=lang, norm=False)
    tkns = tokenize(ph)
    # If length <= 510, just one chunk
    if len(tkns) <= max_chunk_size:
        return [tkns]

    # Otherwise chunk by slicing every 510 tokens
    # (We won't break mid-word because we've already
    #  turned it into a phoneme stream, but that might
    #  cause less natural breaks. It's up to preference.)
    return [tkns[i : i + max_chunk_size] for i in range(0, len(tkns), max_chunk_size)]

def generate(model, text, voicepack, lang='a', speed=1, max_chunk_size=510):
    """
    1. Split text into sentences
    2. For each sentence:
       - Convert to tokens
       - If needed, chunk further
       - Inference on each chunk, then stitch
    3. Concatenate all sentence-level audio
    """
    # 1) Split text into sentences
    sentences = split_into_sentences(text)
    if not sentences:
        return None
    
    final_audio_chunks = []
    final_phoneme_strs = []

    for sent in sentences:
        # 2) If you want to chunk at the word level:
        # sub_chunks = chunk_sentence_tokens(sent, lang, max_chunk_size)
        
        # OR if you prefer chunking by token index once:
        sub_chunks = chunk_sentence_tokens_once(sent, lang, max_chunk_size)

        sentence_audio_chunks = []
        sentence_ph_strs = []

        for chunk_tkns in sub_chunks:
            if not chunk_tkns:
                continue
            # 3) Prepare reference speaker embedding
            ref_s = voicepack[len(chunk_tkns)]
            # 4) Forward pass
            out_audio = forward(model, chunk_tkns, ref_s, speed)
            sentence_audio_chunks.append(out_audio)

            # Rebuild phonemes for logging (optional)
            chunk_phonemes = "".join(
                next(k for k, v in VOCAB.items() if i == v) for i in chunk_tkns
            )
            sentence_ph_strs.append(chunk_phonemes)

        # Combine chunks for this sentence
        if sentence_audio_chunks:
            sentence_audio = np.concatenate(sentence_audio_chunks, axis=0)
            final_audio_chunks.append(sentence_audio)
            final_phoneme_strs.append(" ".join(sentence_ph_strs))

    # Concatenate all sentence-level audio
    if final_audio_chunks:
        final_audio = np.concatenate(final_audio_chunks, axis=0)
    else:
        final_audio = None
    
    # Combine all phoneme strings
    final_ph = " ".join(final_phoneme_strs)

    return final_audio, final_ph

