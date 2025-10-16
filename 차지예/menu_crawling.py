# pip install requests beautifulsoup4 pandas lxml
import os, re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from time import sleep

# ===== 팀원별로 여기만 바꿔 실행 =====
INPUT_CSV  = "bluer_foodV2.csv"   # 상세URL이 들어있는 원본 CSV
URL_COL    = "상세URL"
START      = 1                     # 1-based 시작 (포함)
END        = 32                    # 1-based 끝   (포함)
OUTPUT_CSV = "result_part_01.csv"  # 각자 다른 파일명
# ====================================

BASE    = "https://www.bluer.co.kr"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def clean_text(s: str) -> str:
    return " ".join(s.split()) if s else s

def normalize_url(u: str) -> str:
    if not u:
        return None
    u = u.strip()
    return u if u.startswith("http") else urljoin(BASE, u)

# --- 핵심: 옵션/가격 파서 (정규식) ---
OPT_PATTERN = r"(?:[A-Za-z]{1,3}|[0-9]+(?:g|G|kg|KG|인분?|명))"
AMT_PATTERN = r"([0-9][0-9,]*)\s*원"

def parse_option_and_amount_from_price_el(price_el):
    """
    가격 영역에서 (옵션/중량/사이즈)와 금액을 분리해서 (opt, amount_text) 반환.
    - 먼저 텍스트를 정규화(₩ 제거, \xa0→space, 다중 공백 축약)
    - 정규식으로 '옵션? + 금액'을 찾되, **마지막 매치**를 신뢰
    - 옵션은: A/B/C 같은 문자 1~3, 또는 200g/1인/2인분/3명 등만 허용(숫자만은 제외)
    - 금액은 콤마 제거 → '원' 붙여 표준화 (예: 28,000원 → 28000원)
    """
    if price_el is None:
        return None, None

    html = price_el.decode_contents() if hasattr(price_el, "decode_contents") else price_el.text
    txt = BeautifulSoup(html.replace("&nbsp;", " "), "lxml").get_text()
    txt = txt.replace("\xa0", " ").replace("₩", "")
    txt = re.sub(r"\s+", " ", txt).strip()

    # 모든 후보를 찾아 마지막 매치 사용
    # 예: "A 290000원", "200g 110000원", "1인 50,000원", "2, 8000원" 등
    pattern = re.compile(rf"(?:\b(?P<opt>{OPT_PATTERN})\s*)?\b(?P<amt>{AMT_PATTERN})")
    matches = list(pattern.finditer(txt))
    if not matches:
        # 금액만 있는 경우라도 잡아보자
        m = re.search(AMT_PATTERN, txt)
        if m:
            amt = m.group(1).replace(",", "")
            return None, f"{amt}원"
        return None, None

    m = matches[-1]
    opt = m.group("opt")
    # m.group("amt")에는 캡처가 중첩이라 첫 그룹만 필요
    amt_num = re.search(r"[0-9][0-9,]*", m.group(0)).group(0)
    amt = amt_num.replace(",", "")
    return (opt or None), f"{amt}원"

def scrape_detail(url: str) -> pd.DataFrame:
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    rid = urlparse(url).path.rstrip("/").split("/")[-1]

    # 식당명(여러 후보 중 첫 매칭)
    name = None
    for sel in [".header-title h3", ".restaurant-basic-info h1", "h1, h2, h3"]:
        el = soup.select_one(sel)
        if el and clean_text(el.get_text()):
            name = clean_text(el.get_text())
            break

    # 메뉴 컨테이너(PC/모바일 중 첫 번째)
    menu_box = soup.select_one(".restaurant-info-menu")
    if not menu_box:
        return pd.DataFrame(columns=["식당ID","식당명","메뉴","가격원문","대표여부","메뉴범위"])

    # 상단 가격 범위(예: ₩180,000 ~ ₩990,000) — 원문 유지
    range_el = menu_box.select_one(".header .price")
    price_range_text = clean_text(range_el.get_text()) if range_el else None

    rows, seen = [], set()
    for li in menu_box.select("ul.restaurant-menu-list > li"):
        title_el = li.select_one(".content .title")
        price_el = li.select_one(".content .price")
        badge_el = li.select_one(".title-icon")  # '대표' 텍스트 있을 수 있음

        menu_name = clean_text(title_el.get_text()) if title_el else None
        opt, amount_text = parse_option_and_amount_from_price_el(price_el)
        badge = clean_text(badge_el.get_text()) if badge_el else None

        # 메뉴명 + (옵션)  ← 옵션이 있으면 괄호로 감싸 붙이기
        menu_display  = f"{menu_name} ({opt})".strip() if (menu_name and opt) else menu_name
        price_display = amount_text  # 숫자만 + '원' 표준화

        # 중복 방지
        key = (menu_display, price_display)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "식당ID": rid,
            "식당명": name,
            "메뉴": menu_display,      # 예: '삼선짬뽕' 또는 '다이닝마코스 (A)' 또는 '한우양념갈비구이정식 (200g)'
            "가격원문": price_display,  # 예: '28000원' / '290000원' / '110000원'
            "대표여부": "Y" if (badge and "대표" in badge) else "N",
            "메뉴범위": price_range_text,
        })

    return pd.DataFrame(rows, columns=["식당ID","식당명","메뉴","가격원문","대표여부","메뉴범위"])

def main():
    # 입력 CSV 읽기 (인코딩 자동 대응)
    try:
        src = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    except Exception:
        src = pd.read_csv(INPUT_CSV, encoding="cp949")

    if URL_COL not in src.columns:
        raise ValueError(f"'{URL_COL}' 컬럼이 없습니다.")

    # 범위 슬라이스 (1-based → 0-based)
    s = max(1, START); e = min(END, len(src))
    part = src.iloc[s-1:e].copy()

    # 이어쓰기: 기존 파일 있으면 헤더 생략
    header_needed = not os.path.exists(OUTPUT_CSV)

    for i, u in enumerate(part[URL_COL].astype(str), start=s):
        url = normalize_url(u)
        if not url:
            print(f"[SKIP] {i}: 빈 URL"); 
            continue

        try:
            df = scrape_detail(url)
            if df is None or df.empty:
                print(f"[SKIP] {i}: empty -> {url}")
                continue

            df.to_csv(
                OUTPUT_CSV,
                index=False,
                encoding="utf-8-sig",
                mode="a",
                header=header_needed
            )
            header_needed = False
            print(f"[OK] {i}: {url} -> +{len(df)} rows")

        except Exception as e:
            print(f"[ERR] {i}: {url} -> {e}")
        finally:
            sleep(0.25) 

if __name__ == "__main__":
    main()
