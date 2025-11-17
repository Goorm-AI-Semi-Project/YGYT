# search_logic.py (수정 완료 - 'no_image' 필터링)

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

from i18n_texts import get_text
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
      db_pre_filter_list.append({"high_level_category": value})
      
    elif key in DB_FILTER_KEYS:
      if value == 'O':
        filter_value = "True"
      elif value == 'X':
        filter_value = "False"
      else:
        filter_value = value 
      
      db_pre_filter_list.append({key: filter_value})
      
  db_pre_filter = {"$and": db_pre_filter_list} if db_pre_filter_list else {}
  
  return db_pre_filter

# --- (함수 8/9 중 하나 - 14번 셀) ---
def format_restaurant_markdown(store_id_str, rank_prefix="추천", rank_index=1, lang_code="KR"):
  """
  store_id_str(가게ID)을(를) 받아, 전역 변수(df_restaurants 등)를 참조하여
  Gradio에 표시할 단일 식당의 *HTML* 문자열을 반환합니다. (CSS 클래스 사용)
  """
  
  if db.df_restaurants is None or db.menu_groups is None:
       db_not_loaded_text = get_text("store_not_loaded", lang_code, store_id_str=store_id_str)
       return f"""
       <div class="border-item">
         <h4>[{rank_prefix} {rank_index}] ID: {store_id_str} {db_not_loaded_text}</h4>
       </div>
       """

  try:
    # 1. (가게 정보 조회)
    store_info = db.df_restaurants.loc[store_id_str]
    
    suffix_map = {'US': '_en', 'JP': '_jp', 'CN': '_cn'}
    suffix = suffix_map.get(lang_code.upper(), '') 

    store_name = store_info.get(f'가게{suffix}')
    if pd.isna(store_name) or not store_name:
      store_name = store_info['가게']
      
    store_address = store_info.get(f'주소{suffix}')
    if pd.isna(store_address) or not store_address:
      store_address = store_info['주소']
      
    store_intro = store_info.get(f'소개{suffix}')
    if pd.isna(store_intro) or not store_intro:
      store_intro = store_info['소개']

    store_image_url = store_info.get('이미지URL', '') 
    detail_url = store_info.get('상세URL', '')
    store_y = store_info.get('Y좌표', '')
    store_x = store_info.get('X좌표', '')
    
    try:
      store_category = store_info.get('high_level_category', 'N/A')
    except KeyError:
      store_category = 'N/A' 

    # ⬇️ [신규] 뱃지/로고 데이터 조회
    is_red_ribbon = store_info.get('레드리본 선정', 'N') == 'Y'
    is_seoul_2025 = store_info.get('서울 2025 선정', 'N') == 'Y'

    # ⬇️ [신규] 뱃지/로고 HTML 생성 (i18n 텍스트 사용)
    red_ribbon_html = ""
    seoul_2025_html = ""
    if is_red_ribbon:
      # (i18n_texts.py에 정의된 키 사용)
      title_text = get_text("pc_red_ribbon_title", lang_code)
      red_ribbon_html = f' <span class="badge-ribbon" title="{title_text}">🎀</span>'
    if is_seoul_2025:
      # (i18n_texts.py에 정의된 키 사용)
      title_text = get_text("pc_seoul_2025_title", lang_code)
      seoul_2025_html = f' <span class="badge-seoul2025" title="{title_text}">서울2025</span>'
    # ⬆️ [신규 수정 완료]

    # 2. (다른 사용자 평가 카운트 조회)
    social_proof_html = "" 
    if db.df_restaurant_ratings_summary is not None and not db.df_restaurant_ratings_summary.empty:
      try:
        rating_info = db.df_restaurant_ratings_summary[
          db.df_restaurant_ratings_summary['restaurant_id'] == store_id_str
        ]
        if not rating_info.empty:
          recommend_count = rating_info['추천'].iloc[0]
          non_recommend_count = rating_info['미추천'].iloc[0]
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
        image_html_string = f'<img src="{store_image_url}" alt="{store_name} 이미지" style="width:100%; max-height:200px; object-fit:cover; border-radius: 8px; margin-bottom: 12px;">'
    
    # 4. (링크 2종 HTML 생성)
    detail_link_md = ""
    if pd.notna(detail_url) and detail_url:
      detail_link_text = get_text("detail_link_text", lang_code)
      detail_link_md = f'<a href="{detail_url}" target="_blank" class="html-button html-button-primary">{detail_link_text}</a>'

    map_link_md = ""
    if pd.notna(store_y) and pd.notna(store_x) and store_y and store_x:
      store_name_encoded = quote(store_name) 
      kakao_map_url = f"https://map.kakao.com/?q={store_name_encoded}&map_type=TYPE_MAP&rq={store_y},{store_x}"
      map_link_text = get_text("map_link_text", lang_code)
      map_link_md = f'<a href="{kakao_map_url}" target="_blank" class="html-button html-button-secondary">{map_link_text}</a>'

    links_md = ""
    if detail_link_md and map_link_md:
      links_md = f"{detail_link_md} | {map_link_md}"
    elif detail_link_md:
      links_md = f"{detail_link_md}"
    elif map_link_md:
      links_md = f"{map_link_md}"

    # 5. (메뉴 정보 HTML 생성)
    menu_html = ""
    menu_items_html = "" 
    try:
      menus_df = db.menu_groups.get_group(store_id_str)
      rep_menus = menus_df[menus_df['대표여부'] == 'Y'].head(3)
      if rep_menus.empty:
        rep_menus = menus_df.head(3)
      for _, menu_row in rep_menus.iterrows():
        menu_items_html += f"<li>{menu_row['메뉴']} ({menu_row['가격원문']})</li>"
      
      if not menu_items_html:
        menu_items_html = f"<li>{get_text('menu_not_found', lang_code)}</li>"
      
      menu_summary_text = get_text("menu_summary", lang_code)
      menu_html = textwrap.dedent(f"""
        <details open style="margin-bottom: 12px;">
          <summary style="cursor: pointer; font-weight: bold;">{menu_summary_text}</summary>
          <ul style="margin-top: 8px;">{menu_items_html}</ul>
        </details>
      """)
        
    except KeyError:
      menu_html = "" 

    # 6. (카테고리 태그 생성)
    # 6.1. (기존) high_level_category 태그
    category_tag_html = ""
    if store_category and store_category != 'N/A':
        category_tag_html = f'<span class="text-xs-bg">{store_category}</span>'
        
    # ⬇️ [신규] 6.2. '카테고리' 컬럼 상세 태그
    specific_tags_html = ""
    # (data_loader.py에서 병합한 번역 컬럼을 사용)
    category_string_raw = store_info.get(f'카테고리{suffix}')
    if pd.isna(category_string_raw) or not category_string_raw:
      # (번역본이 없으면 한글 원본 '카테고리' 컬럼 사용)
      category_string_raw = store_info.get('카테고리', '') 

    if pd.notna(category_string_raw) and category_string_raw:
      # (쉼표로 분리하고, strip()으로 공백 제거)
      tags_list = [tag.strip() for tag in category_string_raw.split(',') if tag.strip()]
      for tag in tags_list:
        # (CSS 클래스를 재사용하고, 요청대로 '#' 추가)
        specific_tags_html += f'<span class="text-xs-bg"># {tag}</span>'
    # ⬆️ [신규 수정 완료]

    # 7. (최종 HTML 조합)
    address_html = get_text("info_address", lang_code, store_address=store_address, social_proof_html="") 
    output_html = f"""
    <div class="border-item">
      {image_html_string}
      <h4 style="margin-bottom: 8px;">[{rank_prefix} {rank_index}] {store_name}{red_ribbon_html}{seoul_2025_html}</h4>
      <div style="margin-bottom: 8px;">{address_html}{social_proof_html}</div>
      <p style="margin-bottom: 12px;">{store_intro}</p>
      
      <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 12px;">
        {category_tag_html}
        {specific_tags_html}
      </div>
      
      {menu_html}
      
      <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px;">
        {detail_link_md}
        {map_link_md}
      </div>
    </div>
    """
    
    return textwrap.dedent(output_html).strip()
    
  except KeyError as ke:
     print(f"[서식 오류] ID {store_id_str} (KeyError): {ke}")
     not_found_text = get_text("store_not_found", lang_code, store_id_str=store_id_str)
     return f'<div class="border-item"><h4>[{rank_prefix} {rank_index}] {not_found_text}</h4></div>'
  except Exception as inner_e:
     print(f"[서식 오류] ID {store_id_str} (Exception): {inner_e}")
     not_found_text = get_text("store_not_found", lang_code, store_id_str=store_id_str)
     return f'<div class="border-item"><h4>[{rank_prefix} {rank_index}] {not_found_text}</h4></div>'
      
# --- (함수 8/9 중 하나 - 15번 셀) ---
def get_similar_user_recommendations(
    live_rag_query_text, 
    primary_reco_ids, 
    max_similar_users=1, 
    max_new_recos=2,
    lang_code="KR"
  ):
  """
  (변경 없음)
  """
  
  if db.profile_collection is None:
    print("[유사 추천] 'profile_collection'이 로드되지 않았습니다.")
    return ""
    
  if db.df_all_user_ratings is None:
    print("[유사 추천] 'df_all_user_ratings'가 로드되지 않았습니다.")
    return ""

  try:
    results = db.profile_collection.query(
      query_texts=[live_rag_query_text],
      n_results=max_similar_users
    )
    
    if not results.get('ids', [[]])[0]:
      print("[유사 추천] 유사한 사용자를 찾지 못했습니다.")
      return ""
      
    similar_user_ids = [meta['user_id'] for meta in results['metadatas'][0]]
    print(f"[유사 추천] 찾은 유사 사용자: {similar_user_ids}")

    similar_user_likes = db.df_all_user_ratings[
      (db.df_all_user_ratings['user_id'].isin(similar_user_ids)) &
      (db.df_all_user_ratings['사용자평가'] == '추천')
    ]
    
    if similar_user_likes.empty:
      print("[유사 추천] 유사 사용자가 '추천'한 식당이 없습니다.")
      return ""

    new_recommendations = []
    for store_id in similar_user_likes['restaurant_id'].astype(str):
      if store_id not in primary_reco_ids and store_id not in new_recommendations:
        new_recommendations.append(store_id)
        
    if not new_recommendations:
      print("[유사 추천] 겹치지 않는 추가 추천 식당이 없습니다.")
      return ""
      
    header_text = get_text("similar_user_reco_header", lang_code)
    output_secondary_string = (
      f"\n\n---\n\n"
      f"{header_text}\n\n"
    )
    
    recos_to_show = new_recommendations[:max_new_recos]
    print(f"[유사 추천] 추가할 식당: {recos_to_show}")
    
    rank_prefix_similar = get_text("rank_prefix_similar", lang_code)
    
    for i, store_id in enumerate(recos_to_show):
      output_secondary_string += format_restaurant_markdown(
        store_id, 
        rank_prefix=rank_prefix_similar,
        rank_index=i+1,
        lang_code=lang_code,
      )
      
    return output_secondary_string
    
  except Exception as e:
    print(f"[오류] 유사 사용자 추천 생성 중 오류: {e}")
    return "" 

# --- (함수 8/9 - 16번 셀) ---
def get_rag_candidate_ids(
    user_profile_row: dict,
    n_results: int = 50
) -> List[dict]: 
    """
    (1단계) RAG + 점수제(Scoring)를 실행하여,
    최종 후보군 식당 ID 리스트를 반환합니다.
    """
    print("\n--- 1단계: RAG + 점수제 후보군 생성 시작 ---")
    
    try:
        user_original_summary = user_profile_row['rag_query_text']
        user_filter_dict = json.loads(user_profile_row['filter_metadata_json'])
    except Exception as e:
        print(f"[오류] 사용자 프로필 파싱 실패: {e}")
        return []

    user_rag_query = generate_rag_query(user_original_summary)
    db_pre_filter = build_filters_from_profile(user_filter_dict)
    python_post_filter = {}
    post_filter_keys = ['main_ingredients_list', 'suitable_for']

    for key, val in user_filter_dict.items():
      if key in post_filter_keys and val != 'N/A' and val:
        if isinstance(val, str):
          python_post_filter[key] = [v.strip() for v in val.split(',') if v.strip()]
        elif isinstance(val, list):
          python_post_filter[key] = val
        else:
          try:
            python_post_filter[key] = [str(val)]
          except:
            pass 
    
    print(f"  > RAG 쿼리: '{user_rag_query}'")
    print(f"  > DB 1차 필터: {db_pre_filter}")

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
            
            # ⬇️ [핵심 수정] 이미지 필터링 (Boosting -> Filtering으로 변경)
            image_url_metadata = metadata.get('이미지URL', '')
            if 'no_image' in image_url_metadata:
              continue # 'no_image'가 포함된 항목은 리스트에 추가하지 않고 건너뜀
            
            filter_score = 0
            
            # (기존 필터 점수)
            if user_filter_dict.get('food_category') == metadata.get('high_level_category'):
                filter_score += 3
            if user_filter_dict.get('budget_range') == metadata.get('budget_range'):
                filter_score += 2
            if user_filter_dict.get('spicy_available') == metadata.get('spicy_available'):
                filter_score += 2
            if user_filter_dict.get('vegetarian_options') == metadata.get('vegetarian_options'):
                filter_score += 2
            
            # ⬇️ [삭제] 기존 이미지 가중치 로직은 위 'continue'로 대체됨
            # if 'no_image' not in image_url_metadata:
            #   filter_score += 2 

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
        
        print(f"--- 1단계: RAG + 점수제 완료. (no_image 필터링 후) 후보 {len(final_results)}개 반환 ---")
        
        return final_results 

    except Exception as e:
        print(f"\n[오류] 1단계 후보군 생성 중 오류: {e}")
        return []
      
    
def get_ground_truth_for_user(
    live_rag_query_text: str,
    max_similar_users: int = 5
) -> Set[str]:
  """
  (변경 없음)
  """
  
  if db.profile_collection is None or db.df_all_user_ratings is None:
    print("[Ground Truth] DB가 로드되지 않았습니다.")
    return set()

  try:
    results = db.profile_collection.query(
      query_texts=[live_rag_query_text],
      n_results=max_similar_users
    )
    
    if not results.get('ids', [[]])[0]:
      print("[Ground Truth] 유사 사용자를 찾지 못했습니다.")
      return set()
      
    similar_user_ids = [meta['user_id'] for meta in results['metadatas'][0]]

    ground_truth_df = db.df_all_user_ratings[
      (db.df_all_user_ratings['user_id'].isin(similar_user_ids)) &
      (db.df_all_user_ratings['사용자평가'] == '추천')
    ]
    
    if ground_truth_df.empty:
      print("[Ground Truth] 유사 사용자가 '추천'한 식당이 없습니다.")
      return set()

    ground_truth_set = set(ground_truth_df['restaurant_id'].astype(str))
    print(f"[Ground Truth] 유사 사용자 {len(similar_user_ids)}명으로부터 정답 {len(ground_truth_set)}개 발견")
    return ground_truth_set

  except Exception as e:
    print(f"[오류] Ground Truth 생성 중 오류: {e}")
    return set()
