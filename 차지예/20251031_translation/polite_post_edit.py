
# polite_post_edit.py
from typing import Optional
import re
try:
    from transformers import pipeline
    _TRANS_AVAILABLE = True
except Exception:
    _TRANS_AVAILABLE = False

RULES = [
    (r"\bTell me\b", "Could you please tell me"),
    (r"\bGive me\b", "Could you please provide"),
    (r"\bWhat is\b", "Could you please let me know what"),
    (r"\bsex\b", "gender"),
    (r"\bhot food\b", "spicy food"),
]

def rule_based_polish(text: str) -> str:
    s = text.strip()
    for pat, repl in RULES:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    if s and s[-1] not in ".!?":
        s += "."
    return s

class PolitePostEditor:
    def __init__(self, use_llm: bool = False, model_name: str = "google/flan-t5-large", device: Optional[str] = None):
        self.use_llm = use_llm and _TRANS_AVAILABLE
        self.model_name = model_name
        self.device = device
        if self.use_llm:
            kwargs = {}
            if device == "cpu":
                kwargs["device"] = -1
            self.pipe = pipeline("text2text-generation", model=model_name, **kwargs)
        else:
            self.pipe = None

    def rewrite(self, text: str) -> str:
        s = rule_based_polish(text)
        if not self.use_llm or not self.pipe:
            return s
        prompt = (
            "Rewrite the text in polite, natural English with a friendly, concise service tone. "
            "Keep meaning intact. Use 'please', 'could you', or 'would you mind' when asking. "
            "Replace 'sex' with 'gender'. Prefer 'spicy' (not 'hot') for food spiciness.\n\n"
            f"Text: {s}\n\nRewritten:"
        )
        try:
            out = self.pipe(prompt, max_new_tokens=256, do_sample=False)[0]["generated_text"]
            return out.strip()
        except Exception:
            return s
