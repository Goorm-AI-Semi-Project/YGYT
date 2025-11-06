import pandas as pd
import sys

# --- 사용자 설정 ---
MAPPED_REVIEWS_FILE = 'final_result_v19_safe.csv'
BLUERIBBON_FILE = '20251016_서울시_음식점_목록_GPS.csv'
OUTPUT_FILE = 'blueribbon_scores_only_reviewed.csv'

SCORE_COL_1 = 'quality_score'
SCORE_COL_2 = 'friendliness_score'
MATCHED_ID_COL = 'matched_id'
BLUERIBBON_ID_COL = 'id'
# -------------------

print("점수 집계 및 리뷰 없는 가게 제거를 시작합니다...")

# 1. 데이터 로드
try:
    df_mapped = pd.read_csv(MAPPED_REVIEWS_FILE)
    df_blueribbon = pd.read_csv(BLUERIBBON_FILE)
except Exception as e:
    print(f"[오류] {e}")
    sys.exit()

# 2. 매핑 성공 데이터 필터링
df_success = df_mapped[df_mapped[MATCHED_ID_COL].notna()].copy()

# 3. 평균 점수 계산
agg_df = df_success.groupby(MATCHED_ID_COL).agg({
    SCORE_COL_1: 'mean',
    SCORE_COL_2: 'mean',
    MATCHED_ID_COL: 'size'
}).rename(columns={
    SCORE_COL_1: 'avg_quality',
    SCORE_COL_2: 'avg_friendliness',
    MATCHED_ID_COL: 'review_count'
}).reset_index()

# inner join으로 변경
# (양쪽 모두에 데이터가 있는 경우만 남김 = 리뷰가 있는 가게만 남김)
df_final = pd.merge(
    df_blueribbon,
    agg_df,
    left_on=BLUERIBBON_ID_COL,
    right_on=MATCHED_ID_COL,
    how='inner'
)

if MATCHED_ID_COL in df_final.columns and MATCHED_ID_COL != BLUERIBBON_ID_COL:
    df_final.drop(columns=[MATCHED_ID_COL], inplace=True)

# 5. 저장 및 요약
df_final.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

print(f"\n========== [최종 결과 리포트] ==========")
print(f"원본 블루리본 가게 수: {len(df_blueribbon)}개")
print(f"리뷰가 있는 가게 수 (최종 저장됨): {len(df_final)}개")
print(f"삭제된 가게 수 (리뷰 없음): {len(df_blueribbon) - len(df_final)}개")
print(f"결과 파일: {OUTPUT_FILE}")
print("========================================")