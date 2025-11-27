import pandas as pd
import json
import os
import ast
from urllib.parse import quote 
from typing import List
from urllib.parse import urlparse, quote

# (data_loader에서 로드된 전역 변수를 사용)
import data_loader as db
from llm_utils import generate_rag_query

# --- (함수 7/9) ---
def create_filter_metadata(profile_data):
  """
  13개 항목의 전체 프로필을 받아,
  하이브리드 검색에 필요한 6개 항목의 필터 딕셔너리를 생성합니다.
  """
  filter_dict = {
    "budget_range": profile_data.get('budget', 'N/A'),
    "spicy_available": profile_data.get('spicy_ok', 'N/A'),
    "vegetarian_options": profile_data.get('is_vegetarian', 'N/A'),
    "main_ingredients_list": profile_data.get('like_ingredients', 'N/A'),
    "suitable_for": profile_data.get('travel_type', 'N/A'),
    "food_category": profile_data.get('food_category', 'N/A')
  }
  return filter_dict

# --- (함수 8/9 중 하나) ---
def build_filters_from_profile(user_filter_dict):
  """
  사용자 프로필 딕셔너리를 받아 ChromaDB 1차 필터(DB)를 생성합니다.
  """
  db_pre_filter_list = [] 
  
  DB_FILTER_KEYS = ['budget_range', 'spicy_available', 'vegetarian_options']

  for key, value in user_filter_dict.items():
    if value == 'N/A' or not value: 
      continue
      
    if key == 'food_category':
      # 사용자의 'food_category'는 가게 DB의 'high_level_category'와 매칭
      db_pre_filter_list.append({"high_level_category": value})
      
    elif key in DB_FILTER_KEYS:
      # 'O' -> "True" (문자열)
      # 'X' -> "False" (문자열)
      # 'budget_range' ('중' 등)은 그대로 사용
      if value == 'O':
        filter_value = "True"
      elif value == 'X':
        filter_value = "False"
      else:
        filter_value = value # ('중', '고' 등)
      
      db_pre_filter_list.append({key: filter_value})
      
  db_pre_filter = {"$and": db_pre_filter_list} if db_pre_filter_list else {}
  
  return db_pre_filter

# --- (함수 8/9 중 하나 - 14번 셀) ---
def format_restaurant_markdown(store_id_str, rank_prefix="추천", rank_index=1):
  """
  store_id_str(가게ID)을(를) 받아, 전역 변수(df_restaurants 등)를 참조하여
  Gradio에 표시할 단일 식당의 Markdown 문자열을 반환합니다.
  """
  
  # (전역 변수 참조)
  if db.df_restaurants is None or db.menu_groups is None:
       return f"**[{rank_prefix} {rank_index}] ID: {store_id_str}** (DB 미로드)\n\n---\n\n"

  try:
    # 1. (가게 정보 조회)
    store_info = db.df_restaurants.loc[store_id_str]
    store_name = store_info['가게']
    store_address = store_info['주소']
    store_intro = store_info['소개']
    store_image_url = store_info.get('이미지URL', '') 
    
    detail_url = store_info.get('상세URL', '')
    store_y = store_info.get('Y좌표', '')
    store_x = store_info.get('X좌표', '')
    
    try:
      store_category = store_info.get('high_level_category', 'N/A')
    except KeyError:
      store_category = 'N/A' 

    # 2. (다른 사용자 평가 카운트 조회)
    social_proof_string = "" 
    if db.df_restaurant_ratings_summary is not None and not db.df_restaurant_ratings_summary.empty:
      try:
        rating_info = db.df_restaurant_ratings_summary[
          db.df_restaurant_ratings_summary['restaurant_id'] == store_id_str
        ]
        if not rating_info.empty:
          recommend_count = rating_info['추천'].iloc[0]
          non_recommend_count = rating_info['미추천'].iloc[0]
          social_proof_string = (
            f"**다른 사용자 평가:** 👍 {recommend_count}명 / 👎 {non_recommend_count}명\n\n"
          )
      except Exception as e:
        print(f"[서식 오류] ID {store_id_str} 평가 카운트 조회: {e}")

    # 3. (이미지 마크다운 생성)
    image_md_string = ""
    no_image_filename = "img_restaruant_no_image.png"
    if pd.notna(store_image_url) and store_image_url:
      path = urlparse(store_image_url).path
      filename = os.path.basename(path)
      if filename != no_image_filename:
        image_md_string = f"![{store_name} 이미지]({store_image_url})\n\n"
        
    # 4. (신규 링크 2종 생성 (HTML 사용))
    detail_link_md = ""
    if pd.notna(detail_url) and detail_url:
      detail_link_md = f'<a href="{detail_url}" target="_blank">가게 상세정보</a>'

    map_link_md = ""
    if pd.notna(store_y) and pd.notna(store_x) and store_y and store_x:
      store_name_encoded = quote(store_name)
      kakao_map_url = f"https://map.kakao.com/?q={store_name_encoded}&map_type=TYPE_MAP&rq={store_y},{store_x}"
      map_link_md = f'<a href="{kakao_map_url}" target="_blank">카카오맵 길찾기</a>'

    links_md = ""
    if detail_link_md and map_link_md:
      links_md = f"{detail_link_md} | {map_link_md}\n\n"
    elif detail_link_md:
      links_md = f"{detail_link_md}\n\n"
    elif map_link_md:
      links_md = f"{map_link_md}\n\n"

    # 5. (메뉴 정보 조회)
    menu_str = ""
    try:
      menus_df = db.menu_groups.get_group(store_id_str)
      rep_menus = menus_df[menus_df['대표여부'] == 'Y'].head(3)
      if rep_menus.empty:
        rep_menus = menus_df.head(3)
      for _, menu_row in rep_menus.iterrows():
        menu_str += f"* {menu_row['메뉴']} ({menu_row['가격원문']})\n"
      if not menu_str:
        menu_str = "* (메뉴 정보 없음)\n"
    except KeyError:
      menu_str = "* (메뉴 정보 없음)\n"

    # 6. (최종 Markdown 조합)
    output_md = (
      f"**[{rank_prefix} {rank_index}] {store_name}**\n\n"
      f"{image_md_string}"
      f"{social_proof_string}"
      f"{links_md}"
      f"**위치:** {store_address}\n\n"
      f"**소개:** {store_intro}\n\n"
      f"**음식종류:** {store_category}\n\n"
      f"**주요메뉴:**\n{menu_str}\n"
      f"\n---\n\n"
    )
    return output_md
    
  except KeyError as ke:
     print(f"[서식 오류] ID {store_id_str} (KeyError): {ke}")
     return f"**[{rank_prefix} {rank_index}] ID: {store_id_str}** (상세 정보 조회 실패)\\n\\n---\n\n"
  except Exception as inner_e:
     print(f"[서식 오류] ID {store_id_str} (Exception): {inner_e}")
     return f"**[{rank_prefix} {rank_index}] ID: {store_id_str}** (상세 정보 조회 실패)\\n\\n---\n\n"

# --- (함수 8/9 중 하나 - 15번 셀) ---
def get_similar_user_recommendations(
    live_rag_query_text, 
    primary_reco_ids, 
    max_similar_users=1, 
    max_new_recos=2
  ):
  """
  현재 사용자의 RAG 쿼리와 기본 추천 ID 목록을 받아,
  유사 사용자가 '추천'한 식당 중 겹치지 않는 식당의
  Markdown 문자열을 반환합니다.
  """
  
  if db.profile_collection is None:
    print("[유사 추천] 'profile_collection'이 로드되지 않았습니다.")
    return ""
    
  if db.df_all_user_ratings is None:
    print("[유사 추천] 'df_all_user_ratings'가 로드되지 않았습니다.")
    return ""

  try:
    # 1. 'mock_profiles' DB에서 유사 사용자 쿼리
    results = db.profile_collection.query(
      query_texts=[live_rag_query_text],
      n_results=max_similar_users
    )
    
    if not results.get('ids', [[]])[0]:
      print("[유사 추천] 유사한 사용자를 찾지 못했습니다.")
      return ""
      
    # 2. 유사 사용자의 user_id 추출
    similar_user_ids = [meta['user_id'] for meta in results['metadatas'][0]]
    print(f"[유사 추천] 찾은 유사 사용자: {similar_user_ids}")

    # 3. 유사 사용자가 '추천'한 식당 ID 목록 조회
    similar_user_likes = db.df_all_user_ratings[
      (db.df_all_user_ratings['user_id'].isin(similar_user_ids)) &
      (db.df_all_user_ratings['사용자평가'] == '추천')
    ]
    
    if similar_user_likes.empty:
      print("[유사 추천] 유사 사용자가 '추천'한 식당이 없습니다.")
      return ""

    # 4. 기본 추천과 겹치지 않는 식당 ID 필터링
    new_recommendations = []
    for store_id in similar_user_likes['restaurant_id'].astype(str):
      if store_id not in primary_reco_ids and store_id not in new_recommendations:
        new_recommendations.append(store_id)
        
    if not new_recommendations:
      print("[유사 추천] 겹치지 않는 추가 추천 식당이 없습니다.")
      return ""
      
    # 5. 최종 Markdown 문자열 생성 (구분자 포함)
    output_secondary_string = (
      f"\n\n---\n\n"
      f"### 🤖 Charlie님과 비슷한 사용자가 추천한 식당\n\n"
    )
    
    recos_to_show = new_recommendations[:max_new_recos]
    print(f"[유사 추천] 추가할 식당: {recos_to_show}")
    
    for i, store_id in enumerate(recos_to_show):
      output_secondary_string += format_restaurant_markdown(
        store_id, 
        rank_prefix="유사 추천", 
        rank_index=i+1
      )
      
    return output_secondary_string
    
  except Exception as e:
    print(f"[오류] 유사 사용자 추천 생성 중 오류: {e}")
    return "" # (오류 시 빈 문자열 반환)

# --- (함수 8/9 - 16번 셀) ---
# 1단계 후보군 ID만 반환하는 아래 함수로 대체합니다.

def get_rag_candidate_ids(
    user_profile_row: dict,
    n_results: int = 50
) -> List[str]:
    """
    (1단계) RAG + 점수제(Scoring)를 실행하여,
    최종 후보군 식당 ID 리스트를 반환합니다. (기존 로직 재사용)
    """
    print("\n--- 1단계: RAG + 점수제 후보군 생성 시작 ---")
    
    # 1. 사용자 프로필(dict)에서 데이터 추출
    try:
        user_original_summary = user_profile_row['rag_query_text']
        user_filter_dict = json.loads(user_profile_row['filter_metadata_json'])
    except Exception as e:
        print(f"[오류] 사용자 프로필 파싱 실패: {e}")
        return []

    # 2. 쿼리 및 필터 생성
    user_rag_query = generate_rag_query(user_original_summary)
    db_pre_filter = build_filters_from_profile(user_filter_dict)
    python_post_filter = {key: val.split(',') for key, val in user_filter_dict.items() 
                          if key in ['main_ingredients_list', 'suitable_for'] and val != 'N/A' and val}
    
    print(f"  > RAG 쿼리: '{user_rag_query}'")
    print(f"  > DB 1차 필터: {db_pre_filter}")

    # 3. ChromaDB에 RAG 검색 실행
    try:
        print(f"  > RAG + 1차 필터 검색 (Top {n_results}개)...")
        
        if db_pre_filter: 
            results = db.collection.query(
                query_texts=[user_rag_query],
                n_results=n_results,
                where=db_pre_filter
            )
        else: 
            results = db.collection.query(
                query_texts=[user_rag_query],
                n_results=n_results
            )
        
        print(f"  > 1차 검색 완료: {len(results['ids'][0])}개 후보 반환")
        
        if not results.get('ids', [[]])[0]:
            print("  > [필터 완화] 1차 필터 결과 0건. RAG-Only(필터 없음)로 재시도...")
            results = db.collection.query(
                query_texts=[user_rag_query],
                n_results=n_results
            )
            print(f"  > RAG-Only 검색 완료: {len(results['ids'][0])}개 후보 반환")
            if not results.get('ids', [[]])[0]:
                print("  > RAG-Only 검색 결과도 없습니다.")
                return []
        
        # 4. Python으로 *점수(Scoring)* 계산 (기존 로직)
        final_results_with_score = []
        
        for i in range(len(results['ids'][0])):
            store_id = results['ids'][0][i]
            rag_distance = results['distances'][0][i] 
            metadata = results['metadatas'][0][i]
            
            filter_score = 0
            
            if user_filter_dict.get('food_category') == metadata.get('high_level_category'):
                filter_score += 3
            if user_filter_dict.get('budget_range') == metadata.get('budget_range'):
                filter_score += 2
            if user_filter_dict.get('spicy_available') == metadata.get('spicy_available'):
                filter_score += 2
            if user_filter_dict.get('vegetarian_options') == metadata.get('vegetarian_options'):
                filter_score += 2

            if 'suitable_for' in python_post_filter:
                if all(req in metadata.get('suitable_for', '') for req in python_post_filter['suitable_for']): 
                    filter_score += 1
            if 'main_ingredients_list' in python_post_filter:
                if any(req in metadata.get('main_ingredients_list', '') for req in python_post_filter['main_ingredients_list']): 
                    filter_score += 1

            final_results_with_score.append({
                "id": store_id,
                "rag_distance": rag_distance, 
                "filter_score": filter_score,
            })
        
        # 5. 최종 랭킹
        final_results = sorted(
            final_results_with_score, 
            key=lambda x: (-x['filter_score'], x['rag_distance']), 
        )
        
        # 6. ID 리스트 반환
        final_candidate_ids = [item['id'] for item in final_results]
        print(f"--- 1단계: RAG + 점수제 완료. 후보 ID {len(final_candidate_ids)}개 반환 ---")
        
        return final_candidate_ids

    except Exception as e:
        print(f"\n[오류] 1단계 후보군 생성 중 오류: {e}")
        return []
    
