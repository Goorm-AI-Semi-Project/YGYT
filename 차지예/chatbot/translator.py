"""
translator.py
- NLLB-200 기반 다국어 ↔ 한국어 번역 모듈
- 긴 텍스트는 자동으로 잘라서 여러 번 번역 후 이어붙임
"""

from functools import lru_cache
from typing import Literal, List

from langdetect import detect
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline

# 사용할 HuggingFace 모델
NLLB_MODEL_NAME = "facebook/nllb-200-distilled-600M"

# 우리 서비스에서 쓸 언어 코드 → NLLB 언어 코드 매핑
LANG_CODE_MAP = {
    "ko": "kor_Hang",
    "en": "eng_Latn",
    "ja": "jpn_Jpan",
    "zh": "zho_Hans",  # 중국어 간체
}

UserLang = Literal["ko", "en", "ja", "zh"]


@lru_cache(maxsize=1)
def get_nllb_pipeline():
    """
    NLLB 파이프라인을 lazy 로딩 + 캐시 (프로세스당 한 번만 로드)
    max_length는 모델 기본값을 쓰고, 대신 긴 텍스트는 우리가 직접 잘라서 보냄.
    """
    tokenizer = AutoTokenizer.from_pretrained(NLLB_MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL_NAME)
    pipe = pipeline(
        "translation",
        model=model,
        tokenizer=tokenizer,
        # max_length를 굳이 작게 지정하지 않고, 모델 기본값 사용
        # 긴 텍스트는 아래 _split_long_text 에서 잘라서 처리
    )
    return pipe


def _split_long_text(text: str, max_chunk_chars: int = 400) -> List[str]:
    """
    너무 긴 텍스트를 여러 chunk로 나누기 (문단/문장 기준)
    - 문자 기준으로 자르지만, 400자 정도면 대부분 512 토큰 아래로 들어감
    """
    text = text or ""
    if len(text) <= max_chunk_chars:
        return [text]

    chunks: List[str] = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    # 1차: 문단 단위로 자르기
    paragraphs = text.split("\n\n")
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 문단이 너무 길면 문장 단위로 더 쪼갠다
        if len(para) > max_chunk_chars:
            sentence_buf = ""
            for ch in para:
                sentence_buf += ch
                # 문장 끝으로 볼 수 있는 문자들
                if ch in ".!?。？！\n" and len(sentence_buf) >= max_chunk_chars:
                    chunks.append(sentence_buf.strip())
                    sentence_buf = ""
            if sentence_buf.strip():
                chunks.append(sentence_buf.strip())
        else:
            # 현재 버퍼에 더해도 되면 더하고, 아니면 flush 후 새로 시작
            if len(current) + len(para) + 2 > max_chunk_chars:
                flush()
            current += para + "\n\n"

    flush()

    # 혹시라도 공백 chunk가 섞여 있으면 제거
    return [c for c in chunks if c.strip()]


def translate_text(
    text: str,
    src_lang: UserLang,
    tgt_lang: UserLang,
) -> str:
    """
    ko/en/ja/zh 사이 번역.
    - src_lang == tgt_lang 이면 그대로 반환
    - 너무 긴 텍스트는 여러 조각으로 나눠서 번역 후 다시 이어붙임
    """
    if not text:
        return text

    if src_lang == tgt_lang:
        return text

    if src_lang not in LANG_CODE_MAP or tgt_lang not in LANG_CODE_MAP:
        # 지원하지 않는 경우에는 원문 그대로
        return text

    pipe = get_nllb_pipeline()
    src = LANG_CODE_MAP[src_lang]
    tgt = LANG_CODE_MAP[tgt_lang]

    # 🔹 긴 텍스트 분할
    chunks = _split_long_text(text, max_chunk_chars=400)
    translated_chunks: List[str] = []

    try:
        # 한 번에 여러 chunk를 넣어서 batch 번역
        outputs = pipe(chunks, src_lang=src, tgt_lang=tgt)
        for out in outputs:
            translated_chunks.append(out["translation_text"])
    except Exception as e:
        print(f"[translator] 번역 오류: {e}")
        # 에러가 나면 안전하게 원문을 돌려준다
        return text

    return "\n\n".join(translated_chunks)


def detect_lang_simple(text: str) -> UserLang:
    """
    자동 감지가 필요할 때 쓸 수 있는 간단한 감지기.
    (지금 구조에서는 보통 '선택된 언어'를 쓰기 때문에 자주 쓰이진 않음)
    """
    if not text or len(text.strip()) == 0:
        return "ko"

    try:
        code = detect(text)
    except Exception:
        return "en"

    if code.startswith("zh"):
        return "zh"
    if code == "ja":
        return "ja"
    if code == "ko":
        return "ko"
    return "en"
