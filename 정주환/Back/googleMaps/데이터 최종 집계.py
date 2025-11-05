"""
[최종 집계 스크립트 V2: aggregate_final_data_v2.py]
-------------------------------------------------
목적: 'all_reviews_processed.csv' (모든 리뷰에 점수/정보가 포함된 파일)을
     'place_id' 기준으로 '집계(Aggregate)'하여
     가게별 최종 마스터 파일을 생성합니다.

필요 파일:
1. all_reviews_processed.csv (정주환님이 주신 8개 컬럼을 가진 파일)

생성 파일:
1. ENRICHED_RESTAURANTS_FINAL.csv (휴리스틱 모델용 최종 DB)
"""

import pandas as pd
import json
import re
from collections import Counter
from tqdm import tqdm
tqdm.pandas(desc="Aggregating Tags")

# --- 0. 설정: 파일 이름 및 컬럼명 ---

# [입력 파일] (정주환님의 처리 완료된 파일)
INPUT_PROCESSED_FILE = 'all_reviews_processed.csv'

# [출력 파일] (최종 마스터 DB)
OUTPUT_FINAL_FILE = 'ENRICHED_RESTAURANTS_FINAL.csv'

# (중요!) 정주환님이 주신 컬럼 리스트 기반
COLUMN_NAMES = {
    # --- 식별자 ---
    "place_id": "place_id",

    # --- 집계할 점수 ---
    "q_score": "quality_score",       # (신규) 품질 점수
    "f_score": "friendliness_score",    # (신규) 친화도 점수
    
    # --- 집계할 태그 ---
    "tags": "experience_details",     # (다이닝마 파일의 그 컬럼)
    
    # --- 카운트용 ---
    "text": "review_text",

    # --- 고유 정보 (가게당 1개) ---
    "unique_info": [
        "place_id", 
        "place_name", 
        "price_range", 
        "is_vegetarian"
    ] 
}

# --- 1. 집계용 커스텀 함수 정의 (태그 합산) ---

def aggregate_tags_from_json_list(experience_details_series):
    """
    한 가게의 모든 'experience_details' (JSON 리스트 문자열)를 받아
    모든 태그의 카운트를 합산하여 최종 JSON 문자열 1개로 반환합니다.
    
     형식 예: "[{""name"":""음식"",""value"":5}, {""name"":""서비스"",""value"":""매장 내 식사""}]"
    """
    total_counter = Counter()
    
    for json_list_str in experience_details_series.dropna():
        try:
            # JSON 리스트 문자열을 파이썬 리스트 객체로 변환
            tags_list = json.loads(json_list_str)
            
            if isinstance(tags_list, list):
                for tag_dict in tags_list:
                    if isinstance(tag_dict, dict) and 'name' in tag_dict and tag_dict['name'] is not None:
                        # "name"을 태그 키로 사용
                        tag_name = tag_dict['name']
                        total_counter.update([tag_name])
                        
        except (json.JSONDecodeError, TypeError):
            pass # 파싱 오류 무시
            
    # 최종 합산된 Counter를 다시 JSON 문자열로 변환
    return json.dumps(dict(total_counter), ensure_ascii=False)

# --- 2. 메인 집계 파이프라인 ---
def main():
    print(f"--- 최종 집계 파이프라인 (V2) 시작 ---")
    
    # 1. '처리 완료된' 리뷰 파일 로드
    print(f"1/3. '{INPUT_PROCESSED_FILE}' 로드 중...")
    try:
        # (중요) 스크립트에 필요한 모든 컬럼명을 usecols에 명시
        use_cols = [
            COLUMN_NAMES["place_id"],
            COLUMN_NAMES["q_score"],
            COLUMN_NAMES["f_score"],
            COLUMN_NAMES["tags"],
            COLUMN_NAMES["text"]
        ] + [col for col in COLUMN_NAMES["unique_info"] if col != COLUMN_NAMES["place_id"]]
        
        # 중복된 컬럼명 제거
        use_cols = sorted(list(set(use_cols))) 
        
        df = pd.read_csv(INPUT_PROCESSED_FILE, usecols=use_cols, encoding='utf-8')
    except FileNotFoundError:
        print(f"❌ 오류: '{INPUT_PROCESSED_FILE}' 파일을 찾을 수 없습니다.")
        return
    except ValueError as e:
        print(f"❌ 오류: 파일에 필요한 컬럼이 없습니다: {e}")
        print(f"필요한 컬럼: {use_cols}")
        print("COLUMN_NAMES 변수의 컬럼명이 실제 파일과 일치하는지 확인하세요.")
        return
    except Exception as e:
        print(f"❌ 오류: 파일 로드 중 문제 발생: {e}")
        return

    print(f"✅ 총 {len(df)}개의 '처리된 리뷰' 로드 완료.")

    # 2. '가게 고유 정보' 추출 (master_df 생성)
    print("2/3. '가게 고유 정보' 추출 중 (drop_duplicates)...")
    master_df = df[COLUMN_NAMES["unique_info"]].drop_duplicates(subset=[COLUMN_NAMES["place_id"]]).reset_index(drop=True)
    print(f"✅ {len(master_df)}개의 고유한 가게 마스터 생성.")

    # 3. '집계 피처' 생성 (features_df 생성)
    print("3/3. 'place_id' 기준으로 점수 및 태그 집계 중...")
    
    # (핵심) NLP 계산 없이, 단순 평균/사이즈/커스텀 함수 집계
    features_df = df.groupby(COLUMN_NAMES["place_id"]).agg(
        # 1. (신규) 품질 점수 평균
        avg_quality_score = (COLUMN_NAMES["q_score"], 'mean'),
        # 2. (신규) 친화도 점수 평균
        avg_friendliness_score = (COLUMN_NAMES["f_score"], 'mean'),
        # 3. 태그 합산 (다이닝마 파일의 'experience_details' 컬럼 기준)
        tag_counts_json = (COLUMN_NAMES["tags"], aggregate_tags_from_json_list),
        # 4. 리뷰 개수 (review_text 기준)
        review_count = (COLUMN_NAMES["text"], 'size')
    ).reset_index()
    
    print("✅ 피처 집계 완료.")

    # 4. (병합) 고유 정보 + 집계 피처
    final_df = pd.merge(
        master_df,
        features_df,
        on=COLUMN_NAMES["place_id"],
        how='inner'
    )

    # 5. 최종 파일 저장
    final_df.to_csv(OUTPUT_FINAL_FILE, index=False, encoding='utf-8-sig')
    
    print(f"\n🎉 모든 작업 완료! 최종 파일 '{OUTPUT_FINAL_FILE}' 저장 성공!")
    print(f"최종 {len(final_df)}개 맛집 데이터 생성 완료.")
    print("\n--- 최종 데이터 샘플 ---")
    print(final_df.head())

if __name__ == "__main__":
    main()