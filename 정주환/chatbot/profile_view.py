# profile_view.py (수정 완료)
# 프로필 정규화 + 요약문 파싱(정규식) + 카드 렌더 + CSS

import re
from typing import Dict, Any, List, Tuple, Set, Union, Optional

# ⬇️ I18N 텍스트 헬퍼 임포트
from i18n_texts import get_text

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
  """State의 (한/영 혼용) 키를 표준화 + 요약문 보강"""
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
    if val_str == 'X':
      spice = "매운 음식 피함"
    elif val_str == 'O':
      spice = "매운 맛 선호"
    else:
      spice = spice_raw
      
  inferred = _infer_from_summary(summary_text or "")
  if not _is_valid(likes) and "likes" in inferred:
    likes = inferred["likes"] 
  if not _is_valid(spice) and "spice" in inferred:
    spice = inferred["spice"]
    
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

# ⬇️⬇️⬇️ [수정됨] ⬇️⬇️⬇️
def render_profile_card(p_raw: dict, lang_code: str = "KR") -> str:
  """
  정규화된 프로필(p_raw)과 언어 코드(lang_code)를 받아
  다국어가 적용된 HTML 카드 문자열을 반환합니다.
  """
  # 1. 프로필 정규화 (기존과 동일)
  p = normalize_profile(p_raw)
  
  # 2. 다국어 텍스트 가져오기 (신규)
  title_text    = get_text("profile_card_title", lang_code)
  origin_text   = get_text("pc_chip_origin", lang_code)
  budget_text   = get_text("pc_chip_budget", lang_code)
  likes_text    = get_text("pc_grid_likes", lang_code)
  limits_text   = get_text("pc_grid_limits", lang_code)
  age_gen_text  = get_text("pc_grid_age_gender", lang_code)
  spice_text    = get_text("pc_grid_spice", lang_code)
  
  # 3. HTML 렌더링 (텍스트 변수 사용)
  return f"""
<div class="profile-card">
  <div class="pc-top">
    <div class="pc-title">{title_text}</div>
    <div class="pc-chips">
      <span class="chip">{p['name']}</span>
      <span class="chip">{p['nationality']}</span>
      <span class="chip">{p['travel_type']} · {p['party_size']}</span>
      <span class="chip">{origin_text} {p['start_area']}</span>
      <span class="chip">{budget_text} {p['budget']}</span>
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
