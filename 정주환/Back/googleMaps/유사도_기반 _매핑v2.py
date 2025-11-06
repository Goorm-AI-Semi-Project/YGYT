import pandas as pd
from rapidfuzz import process, fuzz
import sys
import re

# tqdm 라이브러리 설정
try:
    from tqdm import tqdm
    tqdm.pandas(desc="[초강력 전처리] 매핑 진행 중")
    USE_TQDM = True
except ImportError:
    USE_TQDM = False

# --- 1. 사용자 설정 ---
REVIEW_FILE = 'all_reviews_processed.csv'
BLUERIBBON_FILE = '20251016_서울시_음식점_목록_GPS.csv'
REVIEW_ID_COL = 'place_id'
REVIEW_NAME_COL = 'place_name'
BLUERIBBON_NAME_COL = '가게'
BLUERIBBON_ID_COL = 'id'
# 전처리가 강력하므로 임계값을 95점으로 높여 오매칭 방지
SCORE_CUTOFF = 95
OUTPUT_FILE = 'final_mapped_aggressive_cleaning.csv'

# -----------------------

def aggressive_clean(name):
    """
    초강력 전처리 함수: 한글, 영문, 숫자만 남기고 모두 제거
    예: "비스트로 드 욘트빌 (청담점)" -> "비스트로드욘트빌청담점"
    """
    if pd.isna(name): return None
    # 한글(가-힣), 영문(a-zA-Z), 숫자(0-9)를 제외한 모든 문자 제거
    name = re.sub(r'[^가-힣a-zA-Z0-9]', '', str(name))
    return name.lower() # 소문자화

print("초강력 전처리 기반 매핑을 시작합니다...")

# 1. 데이터 로드
try:
    df_reviews = pd.read_csv(REVIEW_FILE)
    df_blueribbon = pd.read_csv(BLUERIBBON_FILE)
except Exception as e:
    print(f"[오류] 파일 로드 실패: {e}")
    sys.exit()

# 2. 블루리본 참조 데이터 준비 (초강력 전처리 적용)
df_blueribbon['clean_name'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(aggressive_clean)
# 참조용 사전 생성 (중복 제거)
blueribbon_names = list(df_blueribbon['clean_name'].dropna().unique())

print(f"블루리본 데이터 {len(blueribbon_names)}개 로드 및 전처리 완료.")

# 3. 고유 place_id 추출
unique_shops = df_reviews.groupby(REVIEW_ID_COL)[REVIEW_NAME_COL].first().reset_index()
unique_shops['clean_name'] = unique_shops[REVIEW_NAME_COL].apply(aggressive_clean)

print(f"고유한 리뷰 가게 {len(unique_shops)}개에 대해 매핑 시작...")

# 4. 매핑 함수
def find_match_aggressive(target_clean):
    if not target_clean: return None, 0, None
    
    # 초강력 전처리된 상태에서는 단순 WRatio가 더 효과적일 수 있음
    match = process.extractOne(
        target_clean, 
        blueribbon_names, 
        scorer=fuzz.WRatio, 
        score_cutoff=SCORE_CUTOFF
    )
    
    if match:
        matched_clean, score, _ = match
        # 원본 정보 찾기
        info = df_blueribbon[df_blueribbon['clean_name'] == matched_clean].iloc[0]
        return info[BLUERIBBON_NAME_COL], score, info[BLUERIBBON_ID_COL]
    return None, 0, None

# 5. 실행
if USE_TQDM:
    results = unique_shops['clean_name'].progress_apply(find_match_aggressive)
else:
    results = unique_shops['clean_name'].apply(find_match_aggressive)

unique_shops[['matched_name', 'match_score', 'matched_id']] = pd.DataFrame(results.tolist(), index=unique_shops.index)

# 6. 결과 병합
print("결과 병합 중...")
df_merged = pd.merge(df_reviews, unique_shops[[REVIEW_ID_COL, 'matched_name', 'match_score', 'matched_id']], on=REVIEW_ID_COL, how='left')
final_df = pd.merge(df_merged, df_blueribbon.drop(columns=['clean_name']), left_on='matched_id', right_on=BLUERIBBON_ID_COL, how='left', suffixes=('', '_br'))

# 7. 저장 및 요약
final_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

total_shops = len(unique_shops)
matched_shops = unique_shops['matched_id'].notna().sum()
print(f"\n[최종 결과] 고유 가게 {total_shops}개 중 {matched_shops}개 매핑 성공 ({matched_shops/total_shops*100:.1f}%)")
print(f"저장 완료: {OUTPUT_FILE}")