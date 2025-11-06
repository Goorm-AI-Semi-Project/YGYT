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

SCORE_HIGH = 90  # 안전 구간
SCORE_LOW = 75   # 확인필요 구간

OUTPUT_FILE_ALL = 'final_result_v17_all.csv'
OUTPUT_FILE_VERIFY = 'matches_needing_verification.csv' # 확인필요 목록 별도 저장
# -------------------

def clean_std(name): return re.sub(r'[^가-힣a-zA-Z0-9]', ' ', str(name)).strip().lower() if pd.notna(name) else ""
def clean_hangul(name): return re.sub(r'[^가-힣]', '', str(name)) if pd.notna(name) else ""
def clean_eng(name): return re.sub(r'[^a-zA-Z]', '', str(name)).lower() if pd.notna(name) else ""

print("75점 로그 기능이 포함된 매핑을 시작합니다...")

# 1. 데이터 로드
try:
    df_reviews = pd.read_csv(REVIEW_FILE)
    df_blueribbon = pd.read_csv(BLUERIBBON_FILE)
except Exception as e:
    print(f"[오류] {e}")
    sys.exit()

# 2. 참조 데이터 준비
df_blueribbon['c_std'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(clean_std)
df_blueribbon['c_hangul'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(clean_hangul)
df_blueribbon['c_eng'] = df_blueribbon[BLUERIBBON_NAME_COL].apply(clean_eng)

ref_std = df_blueribbon.set_index('c_std')[BLUERIBBON_NAME_COL].to_dict()
ref_hangul = df_blueribbon.set_index('c_hangul')[BLUERIBBON_NAME_COL].to_dict()
ref_eng = df_blueribbon.set_index('c_eng')[BLUERIBBON_NAME_COL].to_dict()
for ref in [ref_std, ref_hangul, ref_eng]: ref.pop('', None)

list_std = list(ref_std.keys())
list_hangul = list(ref_hangul.keys())
list_eng = list(ref_eng.keys())

# 3. 4단계 매핑 함수
def find_match_v17(original_name):
    # [1단계] 표준 (90점)
    t_std = clean_std(original_name)
    if t_std:
        m = process.extractOne(t_std, list_std, scorer=fuzz.token_set_ratio, score_cutoff=SCORE_HIGH)
        if m: return ref_std[m[0]], m[1], "1차(안전)"

    # [2단계] 한글 (90점)
    t_hangul = clean_hangul(original_name)
    if len(t_hangul) >= 2:
        m = process.extractOne(t_hangul, list_hangul, scorer=fuzz.WRatio, score_cutoff=SCORE_HIGH)
        if m: return ref_hangul[m[0]], m[1], "2차(한글안전)"

    # [3단계] 영어 (90점)
    t_eng = clean_eng(original_name)
    if len(t_eng) >= 3:
        m = process.extractOne(t_eng, list_eng, scorer=fuzz.WRatio, score_cutoff=SCORE_HIGH)
        if m: return ref_eng[m[0]], m[1], "3차(영어안전)"

    # [4단계] ★ 최후통첩 (75점) - 로그 대상 ★
    if t_std:
        m = process.extractOne(t_std, list_std, scorer=fuzz.WRatio, score_cutoff=SCORE_LOW)
        if m: return ref_std[m[0]], m[1], "4차(확인필요)"

    return None, 0, "실패"

# 4. 실행
unique_shops = df_reviews.groupby(REVIEW_ID_COL)[REVIEW_NAME_COL].first().reset_index()
if USE_TQDM:
    results = unique_shops[REVIEW_NAME_COL].progress_apply(find_match_v17)
else:
    results = unique_shops[REVIEW_NAME_COL].apply(find_match_v17)

unique_shops[['matched_name', 'match_score', 'match_method']] = pd.DataFrame(results.tolist(), index=unique_shops.index)

# 5. ID 매핑 및 저장
name_to_id = df_blueribbon.set_index(BLUERIBBON_NAME_COL)[BLUERIBBON_ID_COL].to_dict()
unique_shops['matched_id'] = unique_shops['matched_name'].map(name_to_id)

df_merged = pd.merge(df_reviews, unique_shops, on=[REVIEW_ID_COL, REVIEW_NAME_COL], how='left')
final_df = pd.merge(df_merged, df_blueribbon.drop(columns=['c_std', 'c_hangul', 'c_eng']), left_on='matched_id', right_on=BLUERIBBON_ID_COL, how='left', suffixes=('', '_br'))

final_df.to_csv(OUTPUT_FILE_ALL, index=False, encoding='utf-8-sig')

# 6. ★ 확인필요 로그 출력 및 별도 저장 ★
verify_list = unique_shops[unique_shops['match_method'] == "4차(확인필요)"]
verify_list.to_csv(OUTPUT_FILE_VERIFY, index=False, encoding='utf-8-sig')

print(f"\n========== [v17 매핑 결과 리포트] ==========")
print(f"전체 성공: {unique_shops['matched_id'].notna().sum()} / {len(unique_shops)} ({(unique_shops['matched_id'].notna().sum()/len(unique_shops))*100:.2f}%)")
print(f"단계별 성공 수:\n{unique_shops['match_method'].value_counts()}")
print(f"--------------------------------------------")
print(f"⚠️ [확인필요] 75~89점 구간 매핑: {len(verify_list)}건")
print(f"목록이 '{OUTPUT_FILE_VERIFY}'에 저장되었습니다.")
print(f"--------------------------------------------")
print("🔍 [확인필요] 샘플 로그 (상위 20개):")
for _, row in verify_list.head(20).iterrows():
    print(f" - [리뷰] {row[REVIEW_NAME_COL]}  <--({row['match_score']:.1f}점)-->  [블루리본] {row['matched_name']}")
print("============================================")