#!pip install selenium beautifulsoup4 pandas requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import requests, os, re, time, mimetypes

START_URL = "https://www.bluer.co.kr/search?query=&zone1=%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%B6%81"
BASE = "https://www.bluer.co.kr"
IMG_DIR = "images"  # 이미지 저장 폴더

def clean_text(s: str) -> str:
    return " ".join(s.split()) if s else s

def yesno(flag: bool) -> str:
    return "Y" if flag else "N"

def wait_cards(driver, timeout=15):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.rl-col.restaurant-thumb-item"))
    )
    time.sleep(0.4)

def get_total_pages(driver) -> int:
    try:
        pager = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.pagination.bootpag"))
        )
    except:
        return 1
    last = pager.find_elements(By.CSS_SELECTOR, "li.last[data-lp]")
    if last:
        try:
            return int(last[0].get_attribute("data-lp"))
        except:
            pass
    nums = pager.find_elements(By.CSS_SELECTOR, "li[data-lp]")
    return max([int(li.get_attribute("data-lp")) for li in nums] + [1])

def go_to_page(driver, page: int, timeout=12) -> bool:
    old_first = None
    try:
        old_first = driver.find_element(By.CSS_SELECTOR, "li.rl-col.restaurant-thumb-item")
    except:
        pass
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.2)
    btn = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, f'ul.pagination.bootpag li[data-lp="{page}"] a'))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    time.sleep(0.1)
    btn.click()
    WebDriverWait(driver, timeout).until(
        lambda d: (d.find_element(By.CSS_SELECTOR, "ul.pagination.bootpag li.active")
                   .get_attribute("data-lp") == str(page))
    )
    if old_first:
        try:
            WebDriverWait(driver, 6).until(EC.staleness_of(old_first))
        except:
            pass
    wait_cards(driver, timeout=timeout)
    return True 

def extract_cards(driver):
    rows = []
    cards = driver.find_elements(By.CSS_SELECTOR, "li.rl-col.restaurant-thumb-item")
    for card in cards:
        name = address = None
        food_types_joined = None
        ribbon_count = 0
        labels_joined = None
        has_red = False
        has_seoul2025 = False
        rid = None
        image_url = None
        desc = None

        # id
        try: rid = card.get_attribute("data-id")
        except: pass

        # 이름
        try:
            h3 = card.find_element(By.CSS_SELECTOR, ".header-title h3")
            name = clean_text(h3.text) or clean_text(h3.get_attribute("innerText"))
        except: pass

        # 주소
        try:
            addr_el = card.find_element(By.CSS_SELECTOR, ".thumb-caption .info .info-item .content-info.juso-info")
            address = clean_text(addr_el.text) or clean_text(addr_el.get_attribute("innerText"))
        except: pass

        # 카테고리(다중)
        try:
            ft_els = card.find_elements(By.CSS_SELECTOR, ".header-status .foodtype li")
            food_types = [clean_text(el.text) for el in ft_els if clean_text(el.text)]
            food_types_joined = ", ".join(food_types) if food_types else None
        except: pass

        # 리본
        try:
            ribbon_count = len(card.find_elements(By.CSS_SELECTOR, ".header-title .ribbons .img-ribbon"))
        except: ribbon_count = 0

        # 라벨/플래그
        try:
            label_els = card.find_elements(By.CSS_SELECTOR, ".header-title .header-labels li")
            labels = [clean_text(el.text) for el in label_els if clean_text(el.text)]
            labels_joined = " ".join(labels) if labels else None
            has_red = any("레드리본 선정" in t for t in labels)
            has_seoul2025 = any("서울 2025 선정" in t for t in labels)
        except: pass

        # 이미지 URL (background-image)
        try:
            bg = card.find_element(By.CSS_SELECTOR, ".thumb-restaurant-img .embed-responsive-item.bg-cover")
            style = bg.get_attribute("style") or ""
            m = re.search(r'background-image\s*:\s*url\((["\']?)(.*?)\1\)', style)
            if m:
                image_url = m.group(2)
                image_url = urljoin(BASE, image_url)
        except: pass

        # 소개
        try:
            desc_el = card.find_element(By.CSS_SELECTOR, ".thumb-caption .content")
            desc = clean_text(desc_el.text) or clean_text(desc_el.get_attribute("innerText"))
        except: pass

        # 보조 파싱
        if not (name and address and (image_url or desc)):
            html = card.get_attribute("innerHTML")
            soup = BeautifulSoup(html, "html.parser")
            if not name:
                el = soup.select_one(".header-title h3, .clearfix > h3")
                name = clean_text(el.get_text()) if el else name
            if not address:
                el = soup.select_one(".content-info.juso-info")
                address = clean_text(el.get_text()) if el else address
            if food_types_joined is None:
                fts = [clean_text(li.get_text()) for li in soup.select(".header-status .foodtype li") if clean_text(li.get_text())]
                food_types_joined = ", ".join(fts) if fts else None
            if ribbon_count == 0:
                ribbon_count = len(soup.select(".header-title .ribbons .img-ribbon"))
            if labels_joined is None:
                labs = [clean_text(li.get_text()) for li in soup.select(".header-title .header-labels li")]
                labels_joined = " ".join(labs) if labs else None
                has_red = any("레드리본 선정" in t for t in labs)
                has_seoul2025 = any("서울 2025 선정" in t for t in labs)
            if image_url is None:
                bg = soup.select_one(".thumb-restaurant-img .embed-responsive-item.bg-cover")
                if bg and bg.has_attr("style"):
                    m = re.search(r'background-image\s*:\s*url\((["\']?)(.*?)\1\)', bg["style"])
                    if m:
                        image_url = urljoin(BASE, m.group(2))
            if desc is None:
                el = soup.select_one(".thumb-caption .content")
                desc = clean_text(el.get_text()) if el else desc

        if name or address:
            rows.append({
                "id": rid,
                "가게": name,
                "주소": address,
                "카테고리": food_types_joined,
                "리본개수": ribbon_count,
                "레드리본 선정": yesno(has_red),
                "서울 2025 선정": yesno(has_seoul2025),
                "라벨": labels_joined,
                "이미지URL": image_url,  # 원본 URL도 남겨둠
                "소개": desc,
            })
    return rows

# ---------- 이미지 다운로드 유틸 ----------

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def ext_from_resp(resp, fallback=".jpg"):
    ct = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    # 예: image/jpeg, image/png, image/webp
    if ct.startswith("image/"):
        ext = mimetypes.guess_extension(ct) or fallback
        # 일부 환경에서 .jpe가 나오는 경우 .jpg로 정규화
        return ".jpg" if ext in (".jpe",) else ext
    # URL 끝 확장자 추정
    return fallback

def sanitize_filename(s: str) -> str:
    # 파일명에 쓸 수 없는 문자 제거
    return re.sub(r'[\\/:*?"<>|]+', "_", s)

def build_image_filename(row):
    # id_가게명.jpg 형태 권장
    rid = row.get("id") or "noid"
    name = row.get("가게") or "noname"
    base = f"{rid}_{sanitize_filename(name)}"
    return base

def transfer_cookies_to_session(driver, session: requests.Session):
    # Selenium 쿠키 → requests 세션으로 복사 (동일 도메인 접근 필요 시)
    for c in driver.get_cookies():
        # requests 쿠키 필드: name, value, domain, path
        domain = c.get("domain")
        # 도메인이 없으면 START_URL의 도메인 사용
        if not domain:
            domain = urlparse(BASE).netloc
        session.cookies.set(name=c["name"], value=c["value"], domain=domain, path=c.get("path", "/"))

def download_images(driver, rows, img_dir=IMG_DIR, throttle=0.05):
    ensure_dir(img_dir)
    ses = requests.Session()
    ses.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": START_URL
    })
    # 쿠키 전송(로그인 필요 없으면 생략 가능)
    transfer_cookies_to_session(driver, ses)

    saved_paths = []
    for row in rows:
        url = row.get("이미지URL")
        if not url:
            saved_paths.append(None)
            continue

        fname_base = build_image_filename(row)
        # 먼저 HEAD/GET으로 확장자 판별
        try:
            resp = ses.get(url, stream=True, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[IMG] fail: {url} -> {e}")
            saved_paths.append(None)
            continue

        ext = ext_from_resp(resp, fallback=os.path.splitext(urlparse(url).path)[1] or ".jpg")
        # webp도 엑셀에서 보려면 확장자 유지 권장 (변환은 별도 라이브러리 필요)
        fname = f"{fname_base}{ext}"
        out_path = os.path.join(img_dir, fname)

        # 중복 방지
        i = 1
        stem, eext = os.path.splitext(out_path)
        while os.path.exists(out_path):
            out_path = f"{stem}_{i}{eext}"
            i += 1

        # 저장
        try:
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            saved_paths.append(out_path)
            time.sleep(throttle)
        except Exception as e:
            print(f"[IMG] save error: {out_path} -> {e}")
            saved_paths.append(None)

    return saved_paths

# ---------- 메인 루틴 ----------

def crawl_all_pages_click(start_url=START_URL, headless=False, out_csv="bluer_gangbuk.csv"):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,2200")
    driver = webdriver.Chrome(options=opts)

    all_rows, seen = [], set()
    try:
        driver.get(start_url)
        wait_cards(driver)

        total = get_total_pages(driver)
        print(f"[INFO] total pages: {total}")

        cur = 1
        try:
            cur = int(driver.find_element(By.CSS_SELECTOR, "ul.pagination.bootpag li.active").get_attribute("data-lp"))
        except:
            pass

        for page in range(cur, total + 1):
            if page != cur:
                go_to_page(driver, page)

            page_rows = extract_cards(driver)
            print(f"[PAGE {page}] rows: {len(page_rows)}")

            for r in page_rows:
                key = (r["가게"], r["주소"])
                if key in seen:
                    continue
                seen.add(key)
                all_rows.append(r)

    finally:
        # 이미지 다운로드는 드라이버가 살아있는 동안 쿠키를 가져오기 쉬움
        # 하지만 아래처럼 finally 바깥으로 뺄 거면 transfer_cookies_to_session 전에 driver를 종료하지 마세요.
        pass

    # ----- 이미지 저장 -----
    print("[INFO] downloading images...")
    img_paths = download_images(driver, all_rows, img_dir=IMG_DIR)
    # 이제 드라이버 종료
    driver.quit()

    # CSV 저장 (이미지파일 컬럼 추가)
    df = pd.DataFrame(all_rows)
    df["이미지파일"] = img_paths
    cols = ["id", "가게", "주소", "카테고리", "리본개수", "레드리본 선정", "서울 2025 선정", "라벨", "이미지URL", "이미지파일", "소개"]
    df = df[cols]
    # 한글 엑셀 호환
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    # 원하면 xlsx도:
    # df.to_excel(out_csv.replace(".csv", ".xlsx"), index=False)
    print(f"saved: {out_csv} ({len(df)} rows), images in ./{IMG_DIR}")
    return df

if __name__ == "__main__":
    crawl_all_pages_click(headless=False)
