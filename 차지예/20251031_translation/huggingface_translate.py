
# huggingface_translate.py
import os, json, hashlib, threading
from typing import List, Optional
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline

_CACHE_LOCK = threading.Lock()

def _hash(text: str, model: str, src: Optional[str], tgt: Optional[str]) -> str:
    h = hashlib.sha256()
    h.update(model.encode()); h.update(b"\x00")
    h.update((src or "").encode()); h.update(b"\x00")
    h.update((tgt or "").encode()); h.update(b"\x00")
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()[:24]

class HFTranslator:
    def __init__(self, model_name="Helsinki-NLP/opus-mt-ko-en", src_lang=None, tgt_lang=None,
                 cache_path="i18n_cache_hf.json", device=None, max_length=512):
        self.model_name = model_name
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.cache_path = cache_path
        self.max_length = max_length

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.pipe = pipeline(
            "translation", model=self.model, tokenizer=self.tokenizer,
            device_map="auto" if device is None else None,
            device=0 if (device == "cuda") else (-1 if device == "cpu" else None),
            max_length=max_length,
        )

        self._cache = {}
        self._load_cache()

    def _load_cache(self):
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}

    def _save_cache(self):
        try:
            with _CACHE_LOCK:
                with open(self.cache_path, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _get_cache(self, text: str) -> Optional[str]:
        return self._cache.get(_hash(text, self.model_name, self.src_lang, self.tgt_lang))

    def _set_cache(self, text: str, out: str):
        self._cache[_hash(text, self.model_name, self.src_lang, self.tgt_lang)] = out

    def translate(self, text: str) -> str:
        if not text:
            return text
        cached = self._get_cache(text)
        if cached is not None:
            return cached
        kwargs = {}
        if self.src_lang: kwargs["src_lang"] = self.src_lang
        if self.tgt_lang: kwargs["tgt_lang"] = self.tgt_lang
        try:
            out = self.pipe(text, **kwargs)
            translated = out[0]["translation_text"]
        except Exception:
            translated = text
        self._set_cache(text, translated); self._save_cache()
        return translated

    def translate_list(self, texts: List[str]) -> List[str]:
        results = []
        to_run_idx, to_run_texts = [], []
        for i, t in enumerate(texts):
            if not t:
                results.append(t); continue
            cached = self._get_cache(t)
            if cached is not None:
                results.append(cached)
            else:
                results.append(None); to_run_idx.append(i); to_run_texts.append(t)

        if to_run_texts:
            kwargs = {}
            if self.src_lang: kwargs["src_lang"] = self.src_lang
            if self.tgt_lang: kwargs["tgt_lang"] = self.tgt_lang
            try:
                outs = self.pipe(to_run_texts, **kwargs)
                for i, o in zip(to_run_idx, outs):
                    tr = o["translation_text"]
                    results[i] = tr
                    self._set_cache(texts[i], tr)
                self._save_cache()
            except Exception:
                for i, t in zip(to_run_idx, to_run_texts):
                    results[i] = self.translate(t)
        return [r if r is not None else "" for r in results]
