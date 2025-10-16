# pip install requests beautifulsoup4 pandas lxml
import os, re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from collections import OrderedDict
from time import sleep

# ===== 사람마다 여기만 바꿔서 실행 =====
INPUT_CSV  = "bluer_foodV2.csv"      # 상세URL이 들어있는 원본 CSV
URL_COL    = "상세URL"
START      = 1        # 1-based 시작 (포함)
END        = 5     # 1-based 끝   (포함)
OUTPUT_CSV = "차지예_test.csv"    
# ====================================

BASE    = "https://www.bluer.co.kr"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def clean_text(s: str) -> str:
    return " ".join(s.split()) if s else s

def normalize_url(u: str) -> str:
    if not u: return None
    u = u.strip()
    return u if u.startswith("http") else urljoin(BASE, u)

def scrape_detail(url: str) -> pd.DataFrame:
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    rid = urlparse(url).path.rstrip("/").split("/")[-1]

    # 식당명 (여러 후보 중 첫 매칭)
    name = None
    for sel in [".header-title h3", ".restaurant-basic-info h1", "h1, h2, h3"]:
        el = soup.select_one(sel)
        if el and clean_text(el.get_text()):
            name = clean_text(el.get_text()); break

    # 메뉴 컨테이너 (PC/모바일 중 첫 번째만)
    menu_box = soup.select_one(".restaurant-info-menu")
    if not menu_box:
        return pd.DataFrame(columns=["식당ID","식당명","메뉴","가격원문","대표여부","특징","메뉴범위","상세URL"])

    # 상단 가격 범위
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

        key = (menu_name, price_raw)
        if key in seen: 
            continue
        seen.add(key)

        rows.append({
            "식당ID": rid,
            "식당명": name,
            "메뉴": menu_name,
            "가격원문": price_raw,
            "대표여부": "Y" if (badge and "대표" in badge) else "N",
        })

    # 특징 (중복 제거하며 합치기)
    feature_spans   = soup.select(".restaurant-info-feature .content span")
    features_all    = [clean_text(s.get_text()) for s in feature_spans if clean_text(s.get_text())]
    features_unique = list(OrderedDict.fromkeys(features_all))
    features_joined = ", ".join(features_unique) if features_unique else None

    df = pd.DataFrame(rows, columns=["식당ID","식당명","메뉴","가격원문","대표여부"])
    if not df.empty:
        df["특징"]     = features_joined
        df["메뉴범위"] = menu_range_text
        df["상세URL"]  = url
    return df

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
            print(f"[SKIP] {i}: 빈 URL"); continue

        try:
            df = scrape_detail(url)
            if df is None or df.empty:
                print(f"[SKIP] {i}: empty -> {url}"); continue

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
            sleep(0.25)  

if __name__ == "__main__":
    main()
