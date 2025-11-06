import pandas as pd
from rapidfuzz import process, fuzz
import sys
import re

# tqdm 라이브러리 설정
try:
    from tqdm import tqdm
    tqdm.pandas(desc="4단계 정밀 매핑 중")
    USE_TQDM = True
except ImportError:
    USE_TQDM = False

# --- 사용자 설정 ---
REVIEW_FILE = 'all_reviews_processed.csv'
BLUERIBBON_FILE = '20251016_서울시_음식점_목록_GPS.csv'
REVIEW_ID_COL = 'place_id'
REVIEW_NAME_COL = 'place_name'
BLUERIBBON_NAME_COL = '가게'
BLUERIBBON_ID_COL = 'id'

# 임계값 설정
SCORE_HIGH = 90  # 1,2,3단계 (엄격)
SCORE_LOW = 85   # 4단계 (유연)

OUTPUT_FILE_ALL = 'final_result_v15_all.csv'
OUTPUT_FILE_SUCCESS = 'final_result_v15_success.csv'
OUTPUT_FILE_FAILED = 'final_result_v15_failed.csv'
# -------------------

# 전처리 함수들
def clean_std(name): return re.sub(r'[^가-힣a-zA-Z0-9]', ' ', str(name)).strip().lower() if pd.notna(name) else ""
def clean_hangul(name): return re.sub(r'[^가-힣]', '', str(name)) if pd.notna(name) else ""
def clean_eng(name): return re.sub(r'[^a-zA-Z]', '', str(name)).lower() if pd.notna(name) else ""

print("최종 완결판(v15) 매핑을 시작합니다...")

# 1. 데이터 로드
try:
    df_reviews = pd.read_csv(REVIEW_FILE)
    df_blueribbon = pd.read_csv(BLUERIBBON_FILE)
except Exception as e:
    print(f"[오류] {e}")
    sys.exit()

# 2. 블루리본 참조 데이터 준비 (모든 버전 미리 생성)
df_blueribbon['c_std'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(clean_std)
df_blueribbon['c_hangul'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(clean_hangul)
df_blueribbon['c_eng'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(clean_eng)

# 참조 사전 생성 (검색 속도 최적화)
ref_std = df_blueribbon.set_index('c_std')[BLUERIBBON_NAME_COL].to_dict()
ref_hangul = df_blueribbon.set_index('c_hangul')[BLUERIBBON_NAME_COL].to_dict()
ref_eng = df_blueribbon.set_index('c_eng')[BLUERIBBON_NAME_COL].to_dict()

for ref in [ref_std, ref_hangul, ref_eng]: ref.pop('', None)

list_std = list(ref_std.keys())
list_hangul = list(ref_hangul.keys())
list_eng = list(ref_eng.keys())

# 3. 4단계 매핑 함수
def find_match_v15(original_name):
    # [1단계] 표준 전처리 + token_set_ratio (가장 강력)
    # "합 신사점" vs "합" -> 100점 나옴
    t_std = clean_std(original_name)
    if t_std:
        m = process.extractOne(t_std, list_std, scorer=fuzz.token_set_ratio, score_cutoff=SCORE_HIGH)
        if m: return ref_std[m[0]], m[1], "1차(표준+강력)"

    # [2단계] 한글 전용 (영어 폭탄 제거)
    # "다올 숯불구이...Reddit..." vs "다올숯불구이" -> 해결
    t_hangul = clean_hangul(original_name)
    if len(t_hangul) >= 2:
        m = process.extractOne(t_hangul, list_hangul, scorer=fuzz.WRatio, score_cutoff=SCORE_HIGH)
        if m: return ref_hangul[m[0]], m[1], "2차(한글전용)"

    # [3단계] 영어 전용
    t_eng = clean_eng(original_name)
    if len(t_eng) >= 3:
        m = process.extractOne(t_eng, list_eng, scorer=fuzz.WRatio, score_cutoff=SCORE_HIGH)
        if m: return ref_eng[m[0]], m[1], "3차(영어전용)"

    # [4단계] 최후의 보루 (표준 전처리 + 약간 낮은 임계값 85점)
    if t_std:
        m = process.extractOne(t_std, list_std, scorer=fuzz.token_set_ratio, score_cutoff=SCORE_LOW)
        if m: return ref_std[m[0]], m[1], "4차(유연매칭)"

    return None, 0, "실패"

# 4. 실행
unique_shops = df_reviews.groupby(REVIEW_ID_COL)[REVIEW_NAME_COL].first().reset_index()
print(f"총 {len(unique_shops)}개 고유 가게 매핑 시작...")

if USE_TQDM:
    results = unique_shops[REVIEW_NAME_COL].progress_apply(find_match_v15)
else:
    results = unique_shops[REVIEW_NAME_COL].apply(find_match_v15)

unique_shops[['matched_name', 'match_score', 'match_method']] = pd.DataFrame(results.tolist(), index=unique_shops.index)

# 5. ID 매핑 및 결과 병합
name_to_id = df_blueribbon.set_index(BLUERIBBON_NAME_COL)[BLUERIBBON_ID_COL].to_dict()
unique_shops['matched_id'] = unique_shops['matched_name'].map(name_to_id)

print("결과 파일 생성 중...")
df_merged = pd.merge(df_reviews, unique_shops, on=[REVIEW_ID_COL, REVIEW_NAME_COL], how='left')
final_df = pd.merge(df_merged, df_blueribbon[[BLUERIBBON_ID_COL, BLUERIBBON_NAME_COL, '주소', '카테고리', 'X좌표', 'Y좌표']], left_on='matched_id', right_on=BLUERIBBON_ID_COL, how='left', suffixes=('', '_br'))

# 6. 저장
final_df.to_csv(OUTPUT_FILE_ALL, index=False, encoding='utf-8-sig')
final_df[final_df['matched_id'].notna()].to_csv(OUTPUT_FILE_SUCCESS, index=False, encoding='utf-8-sig')
final_df[final_df['matched_id'].isna()].to_csv(OUTPUT_FILE_FAILED, index=False, encoding='utf-8-sig')

# 7. 최종 리포트
total = len(unique_shops)
success = unique_shops['matched_id'].notna().sum()
print(f"\n========== [최종 v15 결과 리포트] ==========")
print(f"고유 가게 매핑 성공: {success} / {total} ({(success/total)*100:.2f}%)")
print(f"실패 가게 수: {total - success}개")
print(f"--------------------------------------------")
print(f"단계별 성공 수:\n{unique_shops['match_method'].value_counts()}")
print(f"============================================")