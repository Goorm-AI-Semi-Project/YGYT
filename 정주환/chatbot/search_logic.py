import pandas as pd
import json
import os
import ast
from urllib.parse import quote 
from typing import List
from urllib.parse import urlparse, quote
import textwrap

# (data_loader에서 로드된 전역 변수를 사용)
import data_loader as db
from llm_utils import generate_rag_query

import data_loader as db
from llm_utils import generate_rag_query
from typing import List, Set # ⬅️ Set 추가

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
  Gradio에 표시할 단일 식당의 *HTML* 문자열을 반환합니다. (CSS 클래스 사용)
  """
  
  # (전역 변수 참조)
  if db.df_restaurants is None or db.menu_groups is None:
       # (오류 메시지도 HTML 형식으로 반환)
       return """
       <div class="border-item">
         <h4>[{rank_prefix} {rank_index}] ID: {store_id_str} (DB 미로드)</h4>
       </div>
       """

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

    # 2. (다른 사용자 평가 카운트 조회) - (간략하게 수정)
    social_proof_html = "" 
    if db.df_restaurant_ratings_summary is not None and not db.df_restaurant_ratings_summary.empty:
      try:
        rating_info = db.df_restaurant_ratings_summary[
          db.df_restaurant_ratings_summary['restaurant_id'] == store_id_str
        ]
        if not rating_info.empty:
          recommend_count = rating_info['추천'].iloc[0]
          non_recommend_count = rating_info['미추천'].iloc[0]
          # (HTML에 바로 삽입할 수 있도록 ' | ' 포함)
          social_proof_html = f" | 👍 {recommend_count} / 👎 {non_recommend_count}"
      except Exception as e:
        print(f"[서식 오류] ID {store_id_str} 평가 카운트 조회: {e}")

    # 3. (이미지 HTML 생성)
    image_html_string = ""
    no_image_filename = "img_restaruant_no_image.png"
    if pd.notna(store_image_url) and store_image_url:
      path = urlparse(store_image_url).path
      filename = os.path.basename(path)
      if filename != no_image_filename:
        # (Markdown 대신 HTML <img> 태그 사용)
        image_html_string = f'<img src="{store_image_url}" alt="{store_name} 이미지" style="width:100%; max-height:200px; object-fit:cover; border-radius: 8px; margin-bottom: 12px;">'
        
    # 4. (링크 2종 HTML 생성) ⬇️⬇️⬇️ 여기를 수정합니다 ⬇️⬇️⬇️
    
    detail_link_md = ""
    if pd.notna(detail_url) and detail_url:
      # (app_main.py에 추가한 'html-button-primary' 클래스 사용)
      detail_link_md = f'<a href="{detail_url}" target="_blank" class="html-button html-button-primary">가게 상세정보</a>'

    map_link_md = ""
    if pd.notna(store_y) and pd.notna(store_x) and store_y and store_x:
      store_name_encoded = quote(store_name)
      kakao_map_url = f"https://map.kakao.com/?q={store_name_encoded}&map_type=TYPE_MAP&rq={store_y},{store_x}"
      # (app_main.py에 추가한 'html-button-secondary' 클래스 사용)
      map_link_md = f'<a href="{kakao_map_url}" target="_blank" class="html-button html-button-secondary">카카오맵 길찾기</a>'
    # ⬆️⬆️⬆️ 수정 완료 ⬆️⬆️⬆️

    links_md = ""
    if detail_link_md and map_link_md:
      links_md = f"{detail_link_md} | {map_link_md}"
    elif detail_link_md:
      links_md = f"{detail_link_md}"
    elif map_link_md:
      links_md = f"{map_link_md}"

    # 5. (메뉴 정보 HTML 생성)
    menu_html = ""
    menu_items_html = "" # (<li> 태그만 담을 변수)
    try:
      menus_df = db.menu_groups.get_group(store_id_str)
      rep_menus = menus_df[menus_df['대표여부'] == 'Y'].head(3)
      if rep_menus.empty:
        rep_menus = menus_df.head(3)
      for _, menu_row in rep_menus.iterrows():
        # (Markdown '*' 대신 <li> 태그 사용)
        menu_items_html += f"<li>{menu_row['메뉴']} ({menu_row['가격원문']})</li>"
      
      if not menu_items_html:
        menu_items_html = "<li>(메뉴 정보 없음)</li>"
      
      # (HTML 문자열 생성 시 f-string의 들여쓰기를 피합니다)
      menu_html = textwrap.dedent(f"""
        <details open style="margin-bottom: 12px;">
          <summary style="cursor: pointer; font-weight: bold;">주요 메뉴 보기</summary>
          <ul style="margin-top: 8px;">{menu_items_html}</ul>
        </details>
      """)
        
    except KeyError:
      menu_html = "" # (메뉴 정보 없으면 아예 표시 안함)

    # 6. (카테고리 태그 생성)
    category_tag_html = ""
    if store_category and store_category != 'N/A':
        # (app_main.py의 'text-xs-bg' CSS 클래스 사용)
        category_tag_html = f'<span class="text-xs-bg">{store_category}</span>'

    # 7. (최종 HTML 조합)
    # (기존 Markdown 대신, 요청하신 UI 구조와 CSS 클래스를 사용)
    output_html = f"""
    <div class="border-item">
      {image_html_string}
      <h4 style="margin-bottom: 8px;">[{rank_prefix} {rank_index}] {store_name}</h4>
      <div style="margin-bottom: 8px;">📍 {store_address}{social_proof_html}</div>
      <p style="margin-bottom: 12px;">{store_intro}</p>
      
      <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 12px;">
        {category_tag_html}
      </div>
      
      {menu_html}
      
      <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px;">
        {detail_link_md}
        {map_link_md}
      </div>
    </div>
    """
    
    # ⬅️ 2. 최종 반환값에서 textwrap.dedent()를 호출합니다.
    #    (f-string의 들여쓰기를 모두 제거하여 순수 HTML로 만듭니다)
    return textwrap.dedent(output_html).strip()
    
  except KeyError as ke:
     print(f"[서식 오류] ID {store_id_str} (KeyError): {ke}")
     return f'<div class="border-item"><h4>[{rank_prefix} {rank_index}] ID: {store_id_str} (상세 정보 조회 실패)</h4></div>'
  except Exception as inner_e:
     print(f"[서식 오류] ID {store_id_str} (Exception): {inner_e}")
     return f'<div class="border-item"><h4>[{rank_prefix} {rank_index}] ID: {store_id_str} (상세 정보 조회 실패)</h4></div>'
      
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
    python_post_filter = {}
    post_filter_keys = ['main_ingredients_list', 'suitable_for']

    for key, val in user_filter_dict.items():
      if key in post_filter_keys and val != 'N/A' and val:
        if isinstance(val, str):
          # [기존 로직] 값이 문자열이면(예: "닭고기,해산물") 쉼표로 분리
          python_post_filter[key] = [v.strip() for v in val.split(',') if v.strip()]
        elif isinstance(val, list):
          # [수정] 값이 이미 리스트이면(예: ["닭고기", "해산물"]) 그대로 사용
          python_post_filter[key] = val
        else:
          # (기타 예외 처리)
          try:
            python_post_filter[key] = [str(val)]
          except:
            pass # 변환 실패 시 무시
    
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
        
        # [!!! 수정 !!!]
        # 6. (ID 리스트 대신) 점수가 포함된 딕셔너리 리스트 반환
        print(f"--- 1단계: RAG + 점수제 완료. 후보 {len(final_results)}개 반환 ---")
        
        return final_results # ⬅️ [수정] 점수 정보가 담긴 'final_results'를 반환   

    except Exception as e:
        print(f"\n[오류] 1단계 후보군 생성 중 오류: {e}")
        return []
      
    
def get_ground_truth_for_user(
    live_rag_query_text: str,
    max_similar_users: int = 5
) -> Set[str]:
  """
  현재 사용자의 RAG 쿼리를 기반으로,
  유사 사용자들이 '추천'한 식당 ID의 *집합(Set)*을 반환합니다. (Ground Truth)
  """
  
  # (data_loader.py에서 로드된 전역 DB 참조)
  if db.profile_collection is None or db.df_all_user_ratings is None:
    print("[Ground Truth] DB가 로드되지 않았습니다.")
    return set()

  try:
    # 1. 유사 사용자 쿼리 (기존 로직과 동일)
    results = db.profile_collection.query(
      query_texts=[live_rag_query_text],
      n_results=max_similar_users
    )
    
    if not results.get('ids', [[]])[0]:
      print("[Ground Truth] 유사 사용자를 찾지 못했습니다.")
      return set()
      
    # 2. 유사 사용자의 user_id 추출
    similar_user_ids = [meta['user_id'] for meta in results['metadatas'][0]]

    # 3. 유사 사용자가 '추천'한 식당 ID 목록 조회
    ground_truth_df = db.df_all_user_ratings[
      (db.df_all_user_ratings['user_id'].isin(similar_user_ids)) &
      (db.df_all_user_ratings['사용자평가'] == '추천')
    ]
    
    if ground_truth_df.empty:
      print("[Ground Truth] 유사 사용자가 '추천'한 식당이 없습니다.")
      return set()

    # 4. ID를 집합(Set)으로 반환
    ground_truth_set = set(ground_truth_df['restaurant_id'].astype(str))
    print(f"[Ground Truth] 유사 사용자 {len(similar_user_ids)}명으로부터 정답 {len(ground_truth_set)}개 발견")
    return ground_truth_set

  except Exception as e:
    print(f"[오류] Ground Truth 생성 중 오류: {e}")
    return set()
