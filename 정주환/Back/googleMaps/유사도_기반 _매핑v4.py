import pandas as pd
from rapidfuzz import process, fuzz
import sys
import re

# tqdm 라이브러리 설정
try:
    from tqdm import tqdm
    tqdm.pandas(desc="[최종 완성] 매핑 진행 중")
    USE_TQDM = True
except ImportError:
    USE_TQDM = False

# --- 1. 사용자 설정 ---
REVIEW_FILE = 'review_data.csv'
BLUERIBBON_FILE = 'blueribbon_data.csv'
REVIEW_ID_COL = 'place_id'
REVIEW_NAME_COL = 'place_name'
BLUERIBBON_NAME_COL = '가게'
BLUERIBBON_ID_COL = 'id'
# 임계값을 85점으로 조정하여 '미스터리' 실패 케이스를 구제합니다.
SCORE_CUTOFF = 85

# 결과 파일명
OUTPUT_FILE_ALL = 'final_result_all.csv'
OUTPUT_FILE_SUCCESS = 'final_result_success.csv'
OUTPUT_FILE_FAILED = 'final_result_failed.csv'

# -----------------------

def aggressive_clean(name):
    """
    초강력 전처리: 한글, 영문, 숫자만 남기고 싹 다 제거
    (띄어쓰기, 괄호, 특수문자 등으로 인한 불일치를 원천 봉쇄)
    """
    if pd.isna(name): return None
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', str(name)).lower()

print("최종 매핑 작업을 시작합니다...")

# 1. 데이터 로드
try:
    df_reviews = pd.read_csv(REVIEW_FILE)
    df_blueribbon = pd.read_csv(BLUERIBBON_FILE)
except Exception as e:
    print(f"[오류] 파일 로드 실패: {e}")
    sys.exit()

# 2. 블루리본 참조 데이터 준비 (초강력 전처리)
df_blueribbon['clean_name'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(aggressive_clean)
# 참조용 사전 (중복 제거)
blueribbon_names = list(df_blueribbon['clean_name'].dropna().unique())
print(f"참조 데이터 준비 완료: {len(blueribbon_names)}개 블루리본 가게")

# 3. 고유 place_id 추출 및 전처리
unique_shops = df_reviews.groupby(REVIEW_ID_COL)[REVIEW_NAME_COL].first().reset_index()
unique_shops['clean_name'] = unique_shops[REVIEW_NAME_COL].apply(aggressive_clean)
print(f"총 {len(unique_shops)}개의 고유한 리뷰 가게에 대해 매핑을 시작합니다...")

# 4. 매핑 함수 (WRatio 사용 - 전처리된 문자열 비교에 효과적)
def find_match(target_clean):
    if not target_clean: return None, 0, None
    match = process.extractOne(
        target_clean, 
        blueribbon_names, 
        scorer=fuzz.WRatio, 
        score_cutoff=SCORE_CUTOFF
    )
    if match:
        matched_clean, score, _ = match
        info = df_blueribbon[df_blueribbon['clean_name'] == matched_clean].iloc[0]
        return info[BLUERIBBON_NAME_COL], score, info[BLUERIBBON_ID_COL]
    return None, 0, None

# 5. 실행
if USE_TQDM:
    results = unique_shops['clean_name'].progress_apply(find_match)
else:
    results = unique_shops['clean_name'].apply(find_match)

unique_shops[['matched_name', 'match_score', 'matched_id']] = pd.DataFrame(results.tolist(), index=unique_shops.index)

# 6. 결과 병합
print("결과 병합 및 파일 저장 중...")
df_merged = pd.merge(df_reviews, unique_shops[[REVIEW_ID_COL, 'matched_name', 'match_score', 'matched_id']], on=REVIEW_ID_COL, how='left')
final_df = pd.merge(df_merged, df_blueribbon.drop(columns=['clean_name']), left_on='matched_id', right_on=BLUERIBBON_ID_COL, how='left', suffixes=('', '_br'))

# 7. 성공/실패 분리 저장
df_success = final_df[final_df['matched_id'].notna()]
df_failed = final_df[final_df['matched_id'].isna()]

final_df.to_csv(OUTPUT_FILE_ALL, index=False, encoding='utf-8-sig')
df_success.to_csv(OUTPUT_FILE_SUCCESS, index=False, encoding='utf-8-sig')
df_failed.to_csv(OUTPUT_FILE_FAILED, index=False, encoding='utf-8-sig')

# 8. 최종 통계
print(f"\n========== [최종 결과 리포트] ==========")
print(f"총 리뷰 수: {len(final_df)}건")
print(f"✅ 매핑 성공: {len(df_success)}건 ({len(df_success)/len(final_df)*100:.2f}%)")
print(f"❌ 매핑 실패: {len(df_failed)}건")
print(f"----------------------------------------")
print(f"고유 가게 매핑 성공: {unique_shops['matched_id'].notna().sum()} / {len(unique_shops)}개")
print(f"========================================")