import pandas as pd
from rapidfuzz import process, fuzz
import sys
import re

# tqdm 라이브러리 설정
try:
    from tqdm import tqdm
    tqdm.pandas(desc="[place_id 기반] 매핑 진행 중")
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
SCORE_CUTOFF = 90

# 결과 파일명 설정
OUTPUT_FILE_ALL = 'final_mapped_all_reviews.csv'
OUTPUT_FILE_SUCCESS = 'mapped_reviews_success.csv'
OUTPUT_FILE_FAILED = 'mapped_reviews_failed.csv'

# -----------------------

def clean_name(name):
    if pd.isna(name): return None
    return re.sub(r'\s+', ' ', str(name)).strip().lower()

print("매핑 작업을 시작합니다...")

# 1. 데이터 로드
try:
    df_reviews = pd.read_csv(REVIEW_FILE)
    df_blueribbon = pd.read_csv(BLUERIBBON_FILE)
except Exception as e:
    print(f"[오류] 파일 로드 실패: {e}")
    sys.exit()

# 2. 블루리본 참조 데이터 준비
df_blueribbon['clean_name'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(clean_name)
blueribbon_names = list(df_blueribbon['clean_name'].dropna().unique())
print(f"로드 완료: 리뷰 {len(df_reviews)}건, 블루리본 가게 {len(blueribbon_names)}개")

# 3. 고유 가게 목록 추출
unique_shops = df_reviews.groupby(REVIEW_ID_COL)[REVIEW_NAME_COL].first().reset_index()
unique_shops['clean_name'] = unique_shops[REVIEW_NAME_COL].apply(clean_name)
total_unique_shops = len(unique_shops)
print(f"고유한 place_id {total_unique_shops}개에 대해 매핑을 시작합니다...")

# 4. 매핑 함수
def find_match(target_clean_name):
    if pd.isna(target_clean_name): return None, 0, None
    match = process.extractOne(
        target_clean_name, 
        blueribbon_names, 
        scorer=fuzz.token_set_ratio,
        score_cutoff=SCORE_CUTOFF
    )
    if match:
        matched_clean, score, _ = match
        info = df_blueribbon[df_blueribbon['clean_name'] == matched_clean].iloc[0]
        return info[BLUERIBBON_NAME_COL], score, info[BLUERIBBON_ID_COL]
    return None, 0, None

# 5. 매핑 실행
if USE_TQDM:
    results = unique_shops['clean_name'].progress_apply(find_match)
else:
    results = unique_shops['clean_name'].apply(find_match)

unique_shops[['matched_name', 'match_score', 'matched_id']] = pd.DataFrame(results.tolist(), index=unique_shops.index)

# 6. 원본 리뷰 데이터에 병합
df_merged = pd.merge(
    df_reviews,
    unique_shops[[REVIEW_ID_COL, 'matched_name', 'match_score', 'matched_id']],
    on=REVIEW_ID_COL,
    how='left'
)

# 7. 최종 병합 (블루리본 상세 정보 추가)
final_df = pd.merge(
    df_merged,
    df_blueribbon.drop(columns=['clean_name']),
    left_on='matched_id',
    right_on=BLUERIBBON_ID_COL,
    how='left',
    suffixes=('', '_blueribbon')
)

# --- 8. 결과 분리 및 저장 (핵심 수정 부분) ---
print("\n결과를 분리하여 저장합니다...")

# 성공한 리뷰만 필터링
df_success = final_df[final_df['matched_id'].notna()]
df_success.to_csv(OUTPUT_FILE_SUCCESS, index=False, encoding='utf-8-sig')

# 실패한 리뷰만 필터링
df_failed = final_df[final_df['matched_id'].isna()]
df_failed.to_csv(OUTPUT_FILE_FAILED, index=False, encoding='utf-8-sig')

# 전체 결과 저장
final_df.to_csv(OUTPUT_FILE_ALL, index=False, encoding='utf-8-sig')

# --- 9. 최종 통계 출력 ---
total_reviews = len(final_df)
success_count = len(df_success)
failed_count = len(df_failed)

print("\n--- [최종 결과 요약] ---")
print(f"총 리뷰 수: {total_reviews}건")
print(f"✅ 매핑 성공: {success_count}건 ({(success_count/total_reviews)*100:.2f}%) -> '{OUTPUT_FILE_SUCCESS}'")
print(f"❌ 매핑 실패: {failed_count}건 ({(failed_count/total_reviews)*100:.2f}%) -> '{OUTPUT_FILE_FAILED}'")
print(f"📄 전체 결과: '{OUTPUT_FILE_ALL}'")