# pip install requests beautifulsoup4 pandas lxml
import os, re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from time import sleep

# ===== 사람마다 여기만 바꿔서 실행 =====
INPUT_CSV  = "bluer_foodV2.csv"   # 상세URL이 들어있는 원본 CSV
URL_COL    = "상세URL"
START      = 1                     # 1-based 시작 (포함)
END        = 10                 # 1-based 끝   (포함)
OUTPUT_CSV = "차지예_test.csv"  # 
# ====================================

BASE    = "https://www.bluer.co.kr"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def clean_text(s: str) -> str:
    return " ".join(s.split()) if s else s

def normalize_url(u: str) -> str:
    """상대경로('/restaurants/30639')도 절대경로로 보정."""
    if not u: 
        return None
    u = u.strip()
    return u if u.startswith("http") else urljoin(BASE, u)

def split_option_price(price_raw: str):
    """
    'A 290000원', 'M 180,000원', '990000원', '₩180,000' 등에서
    (opt, amount_text) 반환. opt가 없으면 None.
    amount_text는 '숫자+원' 형태('290000원', '180,000원')로 정리.
    """
    if not price_raw:
        return None, None
    txt = price_raw.replace("\xa0", " ").replace("₩", "")  # nbsp, 통화기호 제거
    txt = " ".join(txt.split())  # 공백 정리

    # 옵션 + 금액 (예: A 290000원 / M 180,000원 / 특 250000원)
    m = re.match(r"^(?P<opt>[A-Za-z가-힣]+)\s*(?P<amt>[0-9][0-9,]*)\s*원?$", txt)
    if m:
        opt = m.group("opt")
        amt = m.group("amt")
        return opt, f"{amt}원"

    # 금액만 (예: 990000원 / 180,000원)
    m = re.match(r"^(?P<amt>[0-9][0-9,]*)\s*원?$", txt)
    if m:
        amt = m.group("amt")
        return None, f"{amt}원"

    # 위 패턴과 다르면 원문 그대로
    return None, price_raw

def scrape_detail(url: str) -> pd.DataFrame:
    """상세 페이지 1개에서 메뉴/메뉴범위를 DataFrame으로 반환."""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    rid = urlparse(url).path.rstrip("/").split("/")[-1]  # '30639' 등

    # 식당명(여러 후보 중 첫 매칭)
    name = None
    for sel in [".header-title h3", ".restaurant-basic-info h1", "h1, h2, h3"]:
        el = soup.select_one(sel)
        if el and clean_text(el.get_text()):
            name = clean_text(el.get_text())
            break

    # 메뉴 컨테이너(PC/모바일 중 첫 번째만 사용)
    menu_box = soup.select_one(".restaurant-info-menu")
    if not menu_box:
        return pd.DataFrame(columns=["식당ID","식당명","메뉴","가격원문","대표여부","메뉴범위"])

    # 상단 가격 범위(예: ₩180,000 ~ ₩990,000)
    menu_range_el   = menu_box.select_one(".header .price")
    menu_range_text = clean_text(menu_range_el.get_text()) if menu_range_el else None

    # 메뉴 수집 (중복 방지)
    rows, seen = [], set()
    for li in menu_box.select("ul.restaurant-menu-list > li"):
        title_el = li.select_one(".content .title")
        price_el = li.select_one(".content .price")
        badge_el = li.select_one(".title-icon")  # '대표' 텍스트 있을 수 있음

        menu_name = clean_text(title_el.get_text()) if title_el else None
        price_raw = clean_text(price_el.get_text()) if price_el else None
        badge     = clean_text(badge_el.get_text()) if badge_el else None

        # 옵션/가격 분리 → 메뉴명에 옵션 붙이기, 가격은 숫자+원만
        opt, amount_text = split_option_price(price_raw)
        menu_display  = f"{menu_name} {opt}".strip() if opt else menu_name
        price_display = amount_text or price_raw

        # 중복 방지 키(동일 메뉴표시+가격표시는 한 번만)
        key = (menu_display, price_display)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "식당ID": rid,
            "식당명": name,
            "메뉴": menu_display,       # 예: 다이닝마코스 A
            "가격원문": price_display,   # 예: 290000원
            "대표여부": "Y" if (badge and "대표" in badge) else "N",
            "메뉴범위": menu_range_text,
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

    # 이어쓰기 모드: 기존 결과가 있으면 헤더 생략
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

            # 결과를 '추가' 저장 (덮어쓰기 아님)
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
            sleep(0.25)  # 서버 배려

if __name__ == "__main__":
    main()
