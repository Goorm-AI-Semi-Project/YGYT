# profile_view.py (수정 완료 - v5: 한글->외국어 번역)
# 프로필 정규화 + 요약문 파싱(정규식) + 카드 렌더 + CSS

import re
from typing import Dict, Any, List, Tuple, Set, Union, Optional

# ⬇️ I18N 텍스트 헬퍼 임포트
from i18n_texts import get_text

# ⬇️ [신규] LLM 유틸리티 임포트
import json
try:
  # (llm_utils.py는 Charlie님이 이전에 업로드하셨습니다)
  from llm_utils import client, GPT_API_NAME
except ImportError:
  print("[profile_view.py] 경고: llm_utils를 임포트할 수 없습니다. 번역 기능이 작동하지 않습니다.")
  client = None
  GPT_API_NAME = "gpt-4.1-mini" # (Fallback)

__all__ = ["normalize_profile", "render_profile_card", "PROFILE_VIEW_CSS"]

def _is_valid(v):
  if v is None: return False
  if isinstance(v, str) and v.strip() == "": return False
  if isinstance(v, (list, tuple, set)) and len(v) == 0: return False
  if isinstance(v, dict) and len(v.keys()) == 0: return False
  return True

def _pretty(v):
  if v is None: return "—"
  if isinstance(v, str): return v.strip() or "—"
  if isinstance(v, (list, tuple, set)):
    vals = [str(x).strip() for x in v if _is_valid(x)]
    return ", ".join(vals) if vals else "—"
  if isinstance(v, dict):
    items = []
    for k, val in v.items():
      if _is_valid(val):
        items.append(f"{k}={_pretty(val)}")
    return "; ".join(items) if items else "—"
  return str(v)

def _find_first(p: dict, candidates: list):
  # 루트
  for k in candidates:
    if k in p and _is_valid(p[k]):
      return p[k]
  # 중첩 노드
  for nest in ("preferences","pref","diet","profile","food","meta","summary_block"):
    node = p.get(nest, {})
    if isinstance(node, dict):
      for k in candidates:
        if k in node and _is_valid(node[k]):
          return node[k]
  return None

# ( ... _infer_from_summary, normalize_profile 함수는 기존과 동일 ... )
# ( ... )

# ⬇️ [수정] 맵의 Value를 한글로 (v2로 롤백)
LIKE_MAP = {
    "korean":"한식","k-food":"한식","한식":"한식","korean food":"한식",
    "japanese":"일식","일식":"일식","sushi":"일식",
    "chinese":"중식","중식":"중식",
    "western":"양식","양식":"양식",
    "seafood":"해산물","해산물":"해산물",
    "beef":"소고기","소고기":"소고기",
    "pork":"돼지고기","돼지고기":"돼지고기",
    "chicken":"치킨","치킨":"치킨","닭":"치킨",
    "noodles":"면","면":"면","국수":"면",
    "potato":"감자","감자":"감자",
    "bbq":"바비큐","바비큐":"바비큐","고기":"고기",
    "dumpling":"만두","만두":"만두",
}
LIKE_PATTERNS = tuple(k.lower() for k in LIKE_MAP.keys())

def _infer_from_summary(text: str) -> dict:
  """자유서술 요약문에서 선호/매운맛 추출 (후순위)"""
  if not isinstance(text, str) or text.strip() == "":
    return {}
  t = text.lower()
  likes = []
  spice = None
  
  for kw in LIKE_PATTERNS:
    if kw in t:
      likes.append(LIKE_MAP.get(kw, kw))
  if re.search(r"(한식).*(좋아|선호)", t):
    likes.append("한식")
    
  # ⬇️ [수정] 반환 값을 한글로 (v2로 롤백)
  if re.search(r"(매운\s*음식\s*.*(못|피하)|맵.*못|not good with spicy|don'?t (handle|eat) spicy|avoid spicy)", t):
    spice = "매운 음식 피함"
  elif re.search(r"(맵.*약|mild spicy|low spicy|little spicy)", t):
    spice = "약하게 선호"
  elif re.search(r"(보통|moderate spicy|medium spicy)", t):
    spice = "보통"
  elif re.search(r"(매운\s*음식\s*좋아|맵.*좋아|love spicy|like spicy|spicy lover)", t):
    spice = "매운 맛 선호"
    
  likes = list(dict.fromkeys([x for x in likes if _is_valid(x)]))
  out = {}
  if likes: out["likes"] = likes
  if spice: out["spice"] = spice
  return out

def normalize_profile(p: dict) -> dict:
  """State의 키를 표준화 + 요약문 보강 (★ 한글 값 추출)"""
  p = p or {}
  summary_text = None
  for k in ["summary","profile_summary","llm_summary","final_summary","요약","프로필요약"]:
    if k in p and isinstance(p[k], str) and p[k].strip():
      summary_text = p[k]; break
  if not summary_text:
    nested = _find_first(p, ["summary","profile_summary","llm_summary","final_summary"])
    if isinstance(nested, str): summary_text = nested
    
  name         = _find_first(p, ["name","user_name","Name","이름"])
  nationality  = _find_first(p, ["nationality","nat","country","국적"])
  age_group    = _find_first(p, ["age","age_group","ageGroup","연령","나이대"])
  gender       = _find_first(p, ["gender","sex","성별"])
  travel_type  = _find_first(p, ["travel_type","party_type","purpose","동행","여행유형"])
  party_size   = _find_first(p, ["party_size","num_people","group_size","인원","동행수"])
  start_area   = _find_first(p, ["start_location", "start_area","user_start_location","origin","출발","출발지"])
  budget       = _find_first(p, ["budget","budget_per_day","daily_budget","예산","하루예산"])
  limits       = _find_first(p, ["avoid_ingredients", "limits","avoid","allergies","dietary_restrictions","제한","알레르기","주의재료","금지"])
  
  structured_likes = []
  cat = _find_first(p, ["food_category"])
  if _is_valid(cat):
    structured_likes.append(str(cat))
  ingr = _find_first(p, ["like_ingredients"])
  if _is_valid(ingr):
    if isinstance(ingr, str):
      structured_likes.extend([s.strip() for s in ingr.split(',') if s.strip()])
    elif isinstance(ingr, list):
      structured_likes.extend(ingr)
      
  if _is_valid(structured_likes):
    likes = list(dict.fromkeys(structured_likes))
  else:
    likes = _find_first(p, ["likes","preferred_cuisines","like_keywords","food_likes","선호","선호음식","좋아하는음식"])
    
  spice_raw = _find_first(p, ["spicy_ok", "spice","spice_level","spicy_pref","spicy_tolerance","매운맛","맵기","맵기선호"])
  spice = None
  if _is_valid(spice_raw):
    val_str = str(spice_raw).upper()
    # ⬇️ [수정] 반환 값을 한글로 (v2로 롤백)
    if val_str == 'X':
      spice = "매운 음식 피함" # (한글로 통일)
    elif val_str == 'O':
      spice = "매운 맛 선호" # (한글로 통일)
    else:
      spice = spice_raw
      
  inferred = _infer_from_summary(summary_text or "")
  if not _is_valid(likes) and "likes" in inferred:
    likes = inferred["likes"] 
  if not _is_valid(spice) and "spice" in inferred:
    spice = inferred["spice"]
    
  # (★ _pretty()를 호출하여 최종 문자열로 만듦 - 이 값들은 한글/원본 값이 됨)
  return {
    "name":        _pretty(name)        if _is_valid(name) else "—",
    "nationality": _pretty(nationality) if _is_valid(nationality) else "—",
    "age_group":   _pretty(age_group)   if _is_valid(age_group) else "—",
    "gender":      _pretty(gender)      if _is_valid(gender) else "—",
    "travel_type": _pretty(travel_type) if _is_valid(travel_type) else "—",
    "party_size":  _pretty(party_size)  if _is_valid(party_size) else "—",
    "start_area":  _pretty(start_area)  if _is_valid(start_area) else "—",
    "budget":      _pretty(budget)      if _is_valid(budget) else "—",
    "likes":       _pretty(likes)       if _is_valid(likes) else "—",
    "limits":      _pretty(limits)      if _is_valid(limits) else "—",
    "spice":       _pretty(spice)       if _is_valid(spice) else "—",
  }

# ⬇️ [수정] LLM 번역기 (한글 -> 외국어)
def _translate_profile_dict_llm(profile_dict_kr: Dict[str, str], target_lang_code: str) -> Dict[str, str]:
  """
  LLM을 이용해 프로필 딕셔너리의 *값*들을 일괄 번역합니다.
  (입력값은 한글이라고 가정)
  """
  # 1. (중요) 번역 대상 언어가 한글(KR)이면 번역 안 함
  if target_lang_code.upper() == "KR":
    return profile_dict_kr
    
  if client is None:
    print("[오류] _translate_profile_dict_llm: OpenAI 클라이언트가 없습니다.")
    return profile_dict_kr # (오류 시 원본 반환)

  lang_map = {"KR": "Korean", "US": "English", "JP": "Japanese", "CN": "Chinese (Simplified)"}
  target_language = lang_map.get(target_lang_code.upper(), "Korean")

  # 2. 입력 딕셔너리를 JSON으로 변환
  try:
    # (번역할 필요 없는 'name'은 제외)
    to_translate = profile_dict_kr.copy()
    name_val = to_translate.pop("name", "—") # 이름은 번역하지 않음
    
    input_json = json.dumps(to_translate, indent=2, ensure_ascii=False)
  except Exception as e:
    print(f"[오류] _translate_profile_dict_llm: JSON 직렬화 실패: {e}")
    return profile_dict_kr

  # ⬇️ [수정] 프롬프트 (Korean -> Target)
  system_prompt = f"""
You are an expert translation API. You will receive a JSON object containing profile values in Korean.
Your task is to translate all *values* in the JSON from Korean into {target_language}.

[RULES]
1.  **NEVER** translate the JSON keys (e.g., "nationality", "budget").
2.  The values might be nationalities, food preferences (comma-separated lists), or short phrases.
3.  For comma-separated lists (like "likes"), translate *each individual item* in the list, keeping the comma structure. (e.g., "돼지고기, 감자" -> "Pork, Potato")
4.  If a value is "—", return "—".
5.  If a value is a number (like "party_size": "1"), return the number as a string.
6.  You MUST respond with *only* the translated JSON object, maintaining the exact same key structure.
"""

  user_prompt = f"""
[Input JSON (Korean)]
{input_json}

[Translated JSON ({target_language})]
"""
  
  try:
    response = client.chat.completions.create(
      model=GPT_API_NAME,
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
      ],
      response_format={"type": "json_object"},
      temperature=0.0
    )
    
    response_content = response.choices[0].message.content
    translated_values = json.loads(response_content)
    
    # (번역된 값 + 원본 'name'을 다시 합침)
    final_profile = profile_dict_kr.copy()
    final_profile.update(translated_values) # 번역된 값으로 덮어쓰기
    final_profile["name"] = name_val # 이름은 원본 유지
    
    # (키 구조가 망가졌는지 확인)
    if final_profile.keys() != profile_dict_kr.keys():
      print("[경고] LLM 번역이 원본 키 구조를 변경했습니다. 원본 반환.")
      return profile_dict_kr
      
    return final_profile

  except Exception as e:
    print(f"[오류] _translate_profile_dict_llm: LLM 호출/파싱 실패 - {e}")
    return profile_dict_kr # (오류 시 원본 반환)


# ⬇️⬇️⬇️ [수정됨] ⬇️⬇️⬇️
def render_profile_card(p_raw: dict, lang_code: str = "KR") -> str:
  """
  정규화된 프로필(p_raw)과 언어 코드(lang_code)를 받아
  다국어가 적용된 HTML 카드 문자열을 반환합니다.
  """
  # 1. 프로필 정규화 (한글/원본 값 추출)
  p_korean = normalize_profile(p_raw)
  
  # 2. [신규] 프로필 값들을 LLM으로 일괄 번역
  try:
    # (lang_code가 'KR'이면 이 함수는 번역을 건너뜀)
    p = _translate_profile_dict_llm(p_korean, lang_code)
  except Exception as e:
    print(f"[오류] render_profile_card에서 번역 실패: {e}")
    p = p_korean # (실패 시 원본 값 사용)
  
  # 3. 다국어 *라벨* 텍스트 가져오기 (기존)
  title_text    = get_text("profile_card_title", lang_code)
  origin_text   = get_text("pc_chip_origin", lang_code)
  budget_text   = get_text("pc_chip_budget", lang_code)
  likes_text    = get_text("pc_grid_likes", lang_code)
  limits_text   = get_text("pc_grid_limits", lang_code)
  age_gen_text  = get_text("pc_grid_age_gender", lang_code)
  spice_text    = get_text("pc_grid_spice", lang_code)
  
  # 4. HTML 렌더링 (번역된 p 변수 사용)
  return f"""
<div class="profile-card">
  <div class="pc-top">
    <div class="pc-title">{title_text}</div>
    <div class="pc-chips">
      <span class="chip">{p['name']}</span>
      <span class="chip">{p['nationality']}</span>
      <span class="chip">{p['travel_type']} · {p['party_size']}</span>
      <span class="chip">{origin_text} · {p['start_area']}</span>
      <span class="chip">{budget_text} · {p['budget']}</span>
    </div>
  </div>
  <div class="pc-grid">
    <div><b>{likes_text}</b><br>{p['likes']}</div>
    <div><b>{limits_text}</b><br>{p['limits']}</div>
    <div><b>{age_gen_text}</b><br>{p['age_group']} / {p['gender']}</div>
    <div><b>{spice_text}</b><br>{p['spice']}</div>
  </div>
</div>
"""
# ⬆️⬆️⬆️ [수정 완료] ⬆️⬆️⬆️


PROFILE_VIEW_CSS = """
.profile-card{
  border-radius: 14px;
  padding: 16px;
  background: #FFFFFF; /* 흰색 배경 */
  border: 1px solid #E5E7EB; /* 밝은 회색 테두리 */
  box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
  color: #111827; /* ★ 카드 내부의 기본 텍스트 색상을 어둡게 변경 */
}
.pc-title{
  font-weight: 700;
  margin-bottom: 8px;
  color: #000000; /* ★ 제목을 완전한 검은색으로 변경 */
}
.pc-chips{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.chip{
  border: 1px solid #D1D5DB; 
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  color: #1F2937; /* ★ 칩 텍스트 색상을 더 어둡게 변경 */
  background: #F9FAFB; 
}
.pc-grid{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  color: #111827; /* ★ 그리드 텍스트 색상을 어둡게 변경 */
}
"""
