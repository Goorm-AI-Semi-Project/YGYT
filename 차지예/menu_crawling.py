# pip install requests beautifulsoup4 pandas lxml
import os, re, random
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from time import sleep

# ===== 팀원별로 여기만 바꿔 실행 =====
INPUT_CSV  = "bluer_foodV2.csv"   # 상세URL이 들어있는 원본 CSV
URL_COL    = "상세URL"
START      = 1                     # 1-based 시작 (포함)
END        = 2000                  # 1-based 끝   (포함)
OUTPUT_CSV = "result_part_01.csv"  # 각자 다른 파일명 권장
# ====================================

BASE    = "https://www.bluer.co.kr"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 요청 사이 약간의 지터(너무 빠르지 않게)
DELAY_RANGE = (1.2, 2.4)

def clean_text(s: str) -> str:
    return " ".join(s.split()) if s else s

def normalize_url(u: str) -> str:
    if not u:
        return None
    u = u.strip()
    return u if u.startswith("http") else urljoin(BASE, u)

# 옵션 토큰: A/B/C, S/M/L, 200g, 0.5kg, 500ml, 1인/2인분/3명, 세트 등
OPT_TOKEN_RE = re.compile(
    r"(?:"
    r"[A-Za-z]{1,3}"                  # A, B, C, S, M, L ...
    r"|[0-9]+(?:\.[0-9]+)?(?:g|kg|KG|ml|mL|l|L)"  # 200g, 0.5kg, 500ml, 1L ...
    r"|\d+(?:인분?|명|세트)"           # 1인, 2인분, 3명, 2세트
    r")$"
)

AMOUNT_RE = re.compile(r"([0-9][0-9,]*)\s*원")

def parse_menu_option_and_amount(price_el):
    """
    price 엘리먼트에서:
      - 금액: '숫자+원' 패턴들의 **마지막 것**을 금액으로 사용 (예: 17000원, 28,000원)
      - 옵션: 그 금액 앞부분의 **마지막 토큰**이 OPT_TOKEN_RE에 맞으면 옵션으로 사용 (예: 180g, A, 1인)
    반환: (opt_or_None, amount_text)  # amount_text는 콤마 제거한 '숫자원'
    """
    if price_el is None:
        return None, None

    html = price_el.decode_contents() if hasattr(price_el, "decode_contents") else price_el.text
    # 텍스트 정규화
    txt = BeautifulSoup(html.replace("&nbsp;", " "), "lxml").get_text(" ", strip=True)
    txt = txt.replace("\xa0", " ").replace("₩", "")
    txt = re.sub(r"\s+", " ", txt).strip()

    # 1) 금액 후보 전부 찾고 **마지막 것**을 사용
    amt_matches = list(AMOUNT_RE.finditer(txt))
    if not amt_matches:
        return None, None

    last_amt_m = amt_matches[-1]
    amt_num = last_amt_m.group(1).replace(",", "")
    amount_text = f"{amt_num}원"

    # 2) 옵션: 금액 앞부분에서 마지막 토큰 1개만 검사
    left_text = txt[:last_amt_m.start()].strip()
    left_text = re.sub(r"[,\s]+$", "", left_text)   # 끝 쉼표/공백 제거
    last_token = left_text.split()[-1] if left_text else ""
    opt = last_token if last_token and OPT_TOKEN_RE.fullmatch(last_token) else None

    return opt, amount_text

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
        opt, amount_text = parse_menu_option_and_amount(price_el)
        badge = clean_text(badge_el.get_text()) if badge_el else None

        # 메뉴명 + (옵션)  ← 옵션 있으면 괄호로
        menu_display  = f"{menu_name} ({opt})".strip() if (menu_name and opt) else menu_name
        price_display = amount_text  # '숫자원' (콤마 제거)

        # 중복 방지
        key = (menu_display, price_display)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "식당ID": rid,
            "식당명": name,
            "메뉴": menu_display,      # 예: '생오겹살 (180g)'
            "가격원문": price_display,  # 예: '17000원'
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
            print(f"[SKIP] {i}: 빈 URL")
            continue

        try:
            df = scrape_detail(url)
            if df is None or df.empty:
                print(f"[SKIP] {i}: empty -> {url}")
                # 다음 URL 전 짧은 지터
                sleep(random.uniform(*DELAY_RANGE))
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

        # 다음 요청 전 지터
        sleep(random.uniform(*DELAY_RANGE))

if __name__ == "__main__":
    main()
