"""
네이버 지도 식당 이미지 크롤러
주의: 개인 학습/프로젝트 용도로만 사용하세요.
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import quote
import os

class NaverMapImageCrawler:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def search_restaurant(self, restaurant_name, address=""):
        """네이버 지도에서 식당 검색"""
        try:
            # 검색어: 식당명 + 주소 (더 정확한 검색)
            query = f"{restaurant_name} {address}".strip()
            encoded_query = quote(query)

            # 네이버 지도 검색 API (비공식)
            search_url = f"https://map.naver.com/v5/search/{encoded_query}"

            print(f"검색 중: {query}")

            # 요청 간격 (중요: 너무 빠르면 차단됨)
            time.sleep(1)

            response = self.session.get(search_url)

            if response.status_code == 200:
                # 실제로는 네이버 지도 API를 사용하거나 Selenium으로 동적 렌더링 필요
                # 여기서는 간단한 예시만 제공
                return self._extract_place_info(response.text)

            return None

        except Exception as e:
            print(f"검색 실패 ({restaurant_name}): {e}")
            return None

    def _extract_place_info(self, html_content):
        """HTML에서 이미지 URL 추출 (실제로는 더 복잡함)"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 네이버 지도는 동적 렌더링이므로 Selenium 필요
            # 여기서는 구조 예시만 제공

            # 이미지 찾기
            img_tag = soup.find('img', class_='place_thumb')
            if img_tag and 'src' in img_tag.attrs:
                return {
                    'image_url': img_tag['src']
                }

            return None

        except Exception as e:
            print(f"정보 추출 실패: {e}")
            return None


class SeleniumNaverMapCrawler:
    """
    Selenium을 사용한 더 정확한 크롤러
    네이버 지도는 JavaScript로 렌더링되므로 Selenium 필요
    """

    def __init__(self):
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options

        # Chrome 옵션 설정
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # 백그라운드 실행
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

    def search_restaurant_image(self, restaurant_name, address=""):
        """네이버 지도에서 식당 이미지 검색"""
        try:
            query = f"{restaurant_name} {address}".strip()
            encoded_query = quote(query)

            # 네이버 지도 검색 페이지로 이동
            url = f"https://map.naver.com/v5/search/{encoded_query}"
            self.driver.get(url)

            # 페이지 로딩 대기
            time.sleep(2)

            # 첫 번째 검색 결과 클릭
            try:
                first_result = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "li.search-item"))
                )
                first_result.click()
                time.sleep(1)

                # iframe 전환 (네이버 지도는 iframe 사용)
                self.driver.switch_to.frame("entryIframe")

                # 이미지 찾기
                img_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.place_thumb img")

                if img_elements:
                    image_url = img_elements[0].get_attribute('src')
                    print(f"✓ 이미지 발견: {restaurant_name}")
                    return image_url

                # iframe 나가기
                self.driver.switch_to.default_content()

            except Exception as e:
                print(f"✗ 검색 결과 없음: {restaurant_name}")
                return None

            return None

        except Exception as e:
            print(f"✗ 크롤링 실패 ({restaurant_name}): {e}")
            return None

    def close(self):
        """브라우저 종료"""
        self.driver.quit()


def update_restaurant_images(csv_path, output_path=None):
    """
    CSV 파일의 식당들에 대해 이미지 URL 추가

    Args:
        csv_path: 입력 CSV 파일 경로
        output_path: 출력 CSV 파일 경로 (없으면 입력 파일에 _with_images 추가)
    """

    # CSV 읽기
    print(f"CSV 파일 읽는 중: {csv_path}")
    df = pd.read_csv(csv_path, encoding='utf-8-sig')

    # 이미지 URL 컬럼이 없으면 추가
    if 'image_url' not in df.columns:
        df['image_url'] = 'N/A'

    # Selenium 크롤러 초기화
    print("크롤러 초기화 중...")
    crawler = SeleniumNaverMapCrawler()

    # 이미지가 없는 식당들만 처리
    no_image_mask = (df['image_url'].isna()) | (df['image_url'] == 'N/A')
    restaurants_to_crawl = df[no_image_mask]

    print(f"\n이미지 없는 식당 개수: {len(restaurants_to_crawl)}")
    print(f"크롤링 시작... (예상 시간: ~{len(restaurants_to_crawl) * 3}초)\n")

    # 진행 상황 추적
    success_count = 0
    fail_count = 0

    # 각 식당에 대해 이미지 검색
    for idx, row in restaurants_to_crawl.iterrows():
        restaurant_name = row.get('식당명') or row.get('name', '')
        address = row.get('상세주소') or row.get('address', '')

        # 진행률 출력
        current = success_count + fail_count + 1
        total = len(restaurants_to_crawl)
        print(f"[{current}/{total}] 검색 중: {restaurant_name}")

        # 이미지 검색
        image_url = crawler.search_restaurant_image(restaurant_name, address)

        if image_url:
            df.at[idx, 'image_url'] = image_url
            success_count += 1
        else:
            fail_count += 1

        # 진행 상황 저장 (10개마다)
        if (success_count + fail_count) % 10 == 0:
            temp_output = output_path or csv_path.replace('.csv', '_temp.csv')
            df.to_csv(temp_output, index=False, encoding='utf-8-sig')
            print(f"  → 임시 저장 완료 (성공: {success_count}, 실패: {fail_count})")

    # 크롤러 종료
    crawler.close()

    # 결과 저장
    if output_path is None:
        output_path = csv_path.replace('.csv', '_with_images.csv')

    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n{'='*60}")
    print(f"완료! 결과 저장: {output_path}")
    print(f"성공: {success_count}개 | 실패: {fail_count}개")
    print(f"{'='*60}")

    return df


if __name__ == "__main__":
    # 사용 예시
    import sys
    import io

    # Windows 인코딩 문제 해결
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    # CSV 파일 경로 설정
    CSV_PATH = "data/restaurant_summaries_output_ALL.csv"

    # 이미지 크롤링 시작
    print("네이버 지도 이미지 크롤러 시작\n")
    print("⚠️  주의사항:")
    print("  1. 개인 학습/프로젝트 용도로만 사용하세요")
    print("  2. 대량 크롤링 시 IP 차단 위험이 있습니다")
    print("  3. 네이버 이용약관을 확인하세요\n")

    # 실행 확인
    response = input("계속하시겠습니까? (y/n): ")

    if response.lower() == 'y':
        try:
            updated_df = update_restaurant_images(CSV_PATH)
            print("\n✓ 모든 작업이 완료되었습니다!")
        except Exception as e:
            print(f"\n✗ 오류 발생: {e}")
    else:
        print("취소되었습니다.")
