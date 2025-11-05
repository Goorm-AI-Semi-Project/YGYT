
# glossary.py
from typing import Dict
import re

DEFAULT_GLOSSARY = {
    "exact_map": {
        "매운 음식": "spicy food",
        "맵다": "spicy",
        "매운": "spicy",
        "웨이팅": "waiting in line",
        "줄 서기": "waiting in line",
        "대기시간": "wait time",
        "성별": "gender",
        "한식": "Korean",
        "일식": "Japanese",
        "디저트": "desserts",
        "반갑습니다": "Nice to meet you!",
        "환영합니다": "Welcome!"
    },
    "normalize_en": {
        r"\bhot\b(?!\s*sauce)": "spicy"
    },
    "forbid": [
        "What’s going on with your sex?",
        "Hi, take it.",
        "solar dishes"
    ],
    "forbid_replace": {
        "What’s going on with your sex?": "What’s your gender?",
        "Hi, take it.": "Nice to meet you!",
        "solar dishes": "Korean/Japanese/desserts"
    }
}

def enforce_glossary_en(text: str, glossary: Dict = DEFAULT_GLOSSARY) -> str:
    for bad in glossary.get("forbid", []):
        if bad in text:
            text = text.replace(bad, glossary.get("forbid_replace", {}).get(bad, ""))
    for pat, repl in glossary.get("normalize_en", {}).items():
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)
    return text
