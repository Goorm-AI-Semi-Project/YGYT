import pandas as pd
import ast
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
import sys
from typing import List

# 설정 파일에서 전역 변수 임포트
from config import (
    RESTAURANT_DB_FILE, MENU_DB_FILE, DB_PERSISTENT_PATH,
    PROFILE_DB_FILE, MOCK_USER_RATINGS_FILE,
    RESTAURANT_COLLECTION_NAME, PROFILE_COLLECTION_NAME,
    CLEAR_DB_AND_REBUILD
)

# --- 전역 변수 선언 (app_main.py에서 사용) ---
df_restaurants = None
df_menus = None
collection = None
profile_collection = None
menu_groups = None
df_all_user_ratings = None 
df_restaurant_ratings_summary = None 
sentence_embedder = None
# (기존 main.py의 전역 변수)
all_restaurants_df_scoring = None
# -----------------------------------------------


def load_app_data(store_path, menu_path):
  """
  (함수 1/9)
  앱 실행에 필요한 모든 CSV 파일을 로드하여
  2개의 전역 DataFrame을 생성합니다.
  """
  global df_restaurants, df_menus, menu_groups
  
  try:
    # 1. 가게 DB (소개, 주소 등) 로드
    print(f"'{store_path}'에서 가게 DB 로드 중...")
    df_restaurants = pd.read_csv(store_path)
    df_restaurants['id'] = df_restaurants['id'].astype(str)
    df_restaurants = df_restaurants.set_index('id') # (id로 검색하기 쉽게 인덱스 설정)
    print(f"가게 DB {len(df_restaurants)}개 로드 완료.")
    
    # 2. 메뉴 DB (메뉴, 가격) 로드
    print(f"'{menu_path}'에서 메뉴 DB 로드 중...")
    df_menus = pd.read_csv(menu_path)
    df_menus['식당ID'] = df_menus['식당ID'].astype(str)
    menu_groups = df_menus.groupby('식당ID') # (전역 변수로 그룹화)
    print(f"메뉴 DB {len(df_menus)}개 로드 완료 (그룹화 완료).")
    
    return True

  except FileNotFoundError as e:
    print(f"[오류] 필수 파일 로드 실패: {e}")
    return False
  except Exception as e:
    print(f"[오류] 데이터 로드 실패: {e}")
    return False

def load_and_prepare_data(csv_path):
  """
  (함수 2/9)
  restaurant_summaries_output...csv 파일을 로드하고
  '메타데이터' 컬럼을 딕셔너리로 변환합니다.
  (DB 신규 구축 시에만 사용됨)
  """
  print(f"'{csv_path}' 파일 로드 중...")
  try:
    df = pd.read_csv(csv_path)
  except FileNotFoundError:
    print(f"[오류] 파일을 찾을 수 없습니다: {csv_path}")
    return None

  def safe_convert_to_dict(x):
    if pd.isna(x) or x == '{}' or x == '':
      return {}
    try:
      return ast.literal_eval(x)
    except Exception as e:
      print(f"메타데이터 파싱 오류: {e} \n데이터: {x}")
      return {"error": "parsing_failed"}

  print("메타데이터 컬럼을 딕셔너리로 변환 중...")
  df['메타데이터'] = df['메타데이터'].apply(safe_convert_to_dict)
  df['RAG텍스트'] = df['RAG텍스트'].fillna('')
  
  print(f"데이터 준비 완료: {len(df)}개")
  return df

def build_vector_db(store_csv_path, profile_csv_path, clear_db=False):
  """
  (함수 3/9 - 수정됨)
  레스토랑 DataFrame과 프로필 DataFrame을 받아
  ChromaDB를 구축하거나 로드합니다. (2개 컬렉션)
  """
  global collection, profile_collection, sentence_embedder # (전역 변수 3개 할당)
  
  print("\n--- 2단계: VectorDB 구축/로드 시작 ---")
  
  model_name = "distiluse-base-multilingual-cased-v1"
  sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=model_name
  )
  
  sentence_embedder = sentence_transformer_ef._model
  print(f"  > SentenceTransformer 모델 ('{model_name}')을 전역 'sentence_embedder'에 저장했습니다.")
  
  print(f"'{DB_PERSISTENT_PATH}' 경로에서 Persistent DB 클라이언트를 초기화합니다...")
  client = chromadb.PersistentClient(path=DB_PERSISTENT_PATH)

  if clear_db:
    print(f"[경고] CLEAR_DB_AND_REBUILD=True. 컬렉션 2개(restaurants, mock_profiles)를 삭제합니다.")
    try:
      client.delete_collection(name=RESTAURANT_COLLECTION_NAME)
      print(f"  > '{RESTAURANT_COLLECTION_NAME}' 삭제 완료.")
    except Exception as e:
      print(f"  > '{RESTAURANT_COLLECTION_NAME}' 삭제 실패 (무시): {e}")
    try:
      client.delete_collection(name=PROFILE_COLLECTION_NAME)
      print(f"  > '{PROFILE_COLLECTION_NAME}' 삭제 완료.")
    except Exception as e:
      print(f"  > '{PROFILE_COLLECTION_NAME}' 삭제 실패 (무시): {e}")

  # --- 1. 레스토랑 컬렉션 로드 ---
  try:
    print(f"\n[1/2] 기존 '{RESTAURANT_COLLECTION_NAME}' 컬렉션 로드를 시도합니다...")
    collection = client.get_collection(
      name=RESTAURANT_COLLECTION_NAME,
      embedding_function=sentence_transformer_ef
    )
    print(f"  > 'restaurants' 로드 완료: {collection.count()}개")
  except Exception as e:
    print(f"  > 'restaurants' 컬렉션을 찾을 수 없습니다. (이유: {e})")
    print("  > 새 'restaurants' 컬렉션을 생성하고 데이터 적재를 시작합니다.")
    
    df_for_embedding = load_and_prepare_data(store_csv_path)
    if df_for_embedding is None:
      print("[오류] 'restaurants' DB 적재를 위한 원본 CSV 로드에 실패했습니다.")
      return False

    try:
      collection = client.create_collection(
        name=RESTAURANT_COLLECTION_NAME,
        embedding_function=sentence_transformer_ef
      )
    except Exception as e:
      print(f"[오류] 'restaurants' 컬렉션 생성 실패: {e}")
      return False

    documents_list = df_for_embedding['RAG텍스트'].tolist()
    metadatas_list = df_for_embedding['메타데이터'].tolist() 
    ids_list = df_for_embedding['id'].astype(str).tolist()

    print("  > 'restaurants' 메타데이터 변환 중...")
    processed_metadatas = []
    for metadata_dict in metadatas_list:
      processed_meta_item = {}
      for key, value in metadata_dict.items():
        if value is None:
          processed_meta_item[key] = "" 
        elif isinstance(value, list):
          processed_meta_item[key] = ",".join(map(str, value))
        else:
          # (True -> "True", False -> "False", 123 -> "123")
          processed_meta_item[key] = str(value)
      processed_metadatas.append(processed_meta_item)

    print(f"  > 'restaurants' DB에 {len(ids_list)}개 적재 중 (배치)...")
    BATCH_SIZE = 5000
    for i in range(0, len(ids_list), BATCH_SIZE):
      end_i = min(i + BATCH_SIZE, len(ids_list))
      collection.add(
        documents=documents_list[i:end_i],
        metadatas=processed_metadatas[i:end_i],
        ids=ids_list[i:end_i]
      )
    print(f"  > 'restaurants' 신규 구축 완료: {collection.count()}개")

  # --- 2. 프로필 컬렉션 로드 ---
  try:
    print(f"\n[2/2] 기존 '{PROFILE_COLLECTION_NAME}' 컬렉션 로드를 시도합니다...")
    profile_collection = client.get_collection(
      name=PROFILE_COLLECTION_NAME,
      embedding_function=sentence_transformer_ef
    )
    print(f"  > 'mock_profiles' 로드 완료: {profile_collection.count()}개")
  except Exception as e:
    print(f"  > 'mock_profiles' 컬렉션을 찾을 수 없습니다. (이유: {e})")
    print("  > 새 'mock_profiles' 컬렉션을 생성하고 데이터 적재를 시작합니다.")
    
    try:
      # (프로필 DB 파일 로드)
      df_profiles = pd.read_csv(profile_csv_path)
      df_profiles = df_profiles.dropna(subset=['rag_query_text', 'user_id'])
      print(f"  > '{profile_csv_path}' 파일 로드 완료: {len(df_profiles)}개 프로필")
    except FileNotFoundError:
      print(f"[오류] '{profile_csv_path}' 파일을 찾을 수 없습니다.")
      return False
    except Exception as e:
      print(f"[오류] 프로필 파일 로드 실패: {e}")
      return False

    try:
      profile_collection = client.create_collection(
        name=PROFILE_COLLECTION_NAME,
        embedding_function=sentence_transformer_ef
      )
    except Exception as e:
      print(f"[오류] 'mock_profiles' 컬렉션 생성 실패: {e}")
      return False

    profile_docs = df_profiles['rag_query_text'].tolist()
    profile_ids = df_profiles['user_id'].astype(str).tolist()
    profile_metas = [{'user_id': uid} for uid in profile_ids]

    print(f"  > 'mock_profiles' DB에 {len(profile_ids)}개 적재 중...")
    profile_collection.add(
      documents=profile_docs,
      metadatas=profile_metas,
      ids=profile_ids
    )
    print(f"  > 'mock_profiles' 신규 구축 완료: {profile_collection.count()}개")

  print(f"--- 2단계: VectorDB 2개 컬렉션 로드/구축 완료 ---")
  return True

def load_user_ratings():
    """ 500명 평가 데이터를 로드하고 집계합니다. """
    global df_all_user_ratings, df_restaurant_ratings_summary
    try:
      print(f"'{MOCK_USER_RATINGS_FILE}'에서 500명 평가 데이터 로드 중...")
      df_all_user_ratings = pd.read_csv(MOCK_USER_RATINGS_FILE)
      
      if 'restaurant_id' in df_all_user_ratings.columns:
        df_all_user_ratings['restaurant_id'] = df_all_user_ratings['restaurant_id'].apply(str)
      else:
        print("[경고] 'restaurant_id' 컬럼이 500명 평가 파일에 없습니다.")
        raise KeyError("'restaurant_id' 컬럼 누락")
      
      if 'user_id' in df_all_user_ratings.columns:
        df_all_user_ratings['user_id'] = df_all_user_ratings['user_id'].apply(str)
      else:
        print("[경고] 'user_id' 컬럼이 500명 평가 파일에 없습니다.")
        raise KeyError("'user_id' 컬럼 누락")

      print("  > 식당(restaurant_id)별 '추천', '미추천' 카운트 집계 중...")
      
      valid_ratings = df_all_user_ratings[
        df_all_user_ratings['사용자평가'].isin(['추천', '미추천'])
      ]
      
      ratings_crosstab = pd.crosstab(
        valid_ratings['restaurant_id'], 
        valid_ratings['사용자평가']
      )
      
      if '추천' not in ratings_crosstab.columns:
        ratings_crosstab['추천'] = 0
      if '미추천' not in ratings_crosstab.columns:
        ratings_crosstab['미추천'] = 0
        
      df_restaurant_ratings_summary = ratings_crosstab[['추천', '미추천']].reset_index()
      
      print(f"  > 500명 평가 데이터 집계 완료: {len(df_restaurant_ratings_summary)}개 식당")
      return True
      
    except FileNotFoundError:
      print(f"[경고] {MOCK_USER_RATINGS_FILE} 파일을 찾을 수 없습니다. (평가 카운트 기능 비활성화)")
    except Exception as e:
      print(f"[경고] 500명 평가 데이터 로드/집계 중 오류: {e} (평가 카운트 기능 비활성화)")
    
    # (실패 또는 파일을 못찾아도 일단 True 반환하여 서버가 멈추지 않게 함)
    return True 

def load_scoring_data(file_path):
    """ (기존 main.py의 lifespan) 점수제용 식당 데이터를 로드합니다. """
    global all_restaurants_df_scoring
    try:
        all_restaurants_df_scoring = pd.read_csv(file_path)
        all_restaurants_df_scoring['id'] = all_restaurants_df_scoring['id'].astype(str)
        all_restaurants_df_scoring = all_restaurants_df_scoring.set_index('id')
        if 'price' not in all_restaurants_df_scoring.columns:
            print("Info: 'price' 컬럼이 없어 임의로 생성합니다. (테스트용)")
            all_restaurants_df_scoring['price'] = ['$'] * (len(all_restaurants_df_scoring) // 2) + ['$$'] * (len(all_restaurants_df_scoring) - len(all_restaurants_df_scoring) // 2)
        
        print(f"Success: {file_path} 로드 성공. (총 {len(all_restaurants_df_scoring)}개 식당)")
        return True
    except FileNotFoundError:
        print(f"Error: {file_path} 파일을 찾을 수 없습니다.", file=sys.stderr)
        all_restaurants_df_scoring = pd.DataFrame()
        return False
    
def get_restaurants_by_ids(ids: List[str]) -> pd.DataFrame:
    """
    식당 ID 리스트를 받아 DataFrame을 반환합니다.
    없는 ID는 건너뛰고 있는 것만 반환합니다.
    """
    global all_restaurants_df_scoring, df_restaurants

    # 1순위: all_restaurants_df_scoring, 2순위: df_restaurants
    source_df = all_restaurants_df_scoring if (all_restaurants_df_scoring is not None and not all_restaurants_df_scoring.empty) else df_restaurants

    if source_df is None or source_df.empty:
        print("[오류] 사용 가능한 DB가 없습니다.")
        return pd.DataFrame()

    try:
        unique_ids = list(dict.fromkeys(ids))

        # 존재하는 ID만 필터링
        valid_ids = [id for id in unique_ids if id in source_df.index]

        if not valid_ids:
            print(f"[경고] 요청된 {len(unique_ids)}개 ID 중 사용 가능한 ID가 없습니다.")
            return pd.DataFrame()

        if len(valid_ids) < len(unique_ids):
            missing_count = len(unique_ids) - len(valid_ids)
            print(f"[정보] {missing_count}개 ID를 찾을 수 없어 건너뜁니다. ({len(valid_ids)}개 반환)")

        result_df = source_df.loc[valid_ids].copy()

        # df_restaurants와 merge하여 image_url 등 추가 필드 보완
        if df_restaurants is not None and not df_restaurants.empty and source_df is not df_restaurants:
            result_df_reset = result_df.reset_index()
            df_restaurants_reset = df_restaurants.reset_index()

            # 한글 컬럼명을 영문으로 매핑
            column_mapping = {
                '가게': 'name',
                '주소': 'address',
                '카테고리': 'cuisine_type',
                '이미지URL': 'image_url',
                'LLM요약': 'summary',
                '평점': 'rating'
            }

            # df_restaurants에 영문 컬럼명 추가 (기존 한글명 유지하면서)
            for kor_col, eng_col in column_mapping.items():
                if kor_col in df_restaurants_reset.columns and eng_col not in df_restaurants_reset.columns:
                    df_restaurants_reset[eng_col] = df_restaurants_reset[kor_col]

            # 필요한 컬럼만 선택 (존재하는 컬럼만)
            merge_cols = ['id']
            for col in ['image_url', 'summary', 'rating', 'address', 'name', 'cuisine_type']:
                if col in df_restaurants_reset.columns:
                    merge_cols.append(col)

            merged = result_df_reset.merge(
                df_restaurants_reset[merge_cols],
                on='id',
                how='left',
                suffixes=('', '_orig')
            )

            # 중복 컬럼 처리
            for col in ['name', 'cuisine_type', 'address', 'rating', 'summary', 'image_url']:
                if f'{col}_orig' in merged.columns:
                    merged[col] = merged[col].fillna(merged[f'{col}_orig'])
                    merged = merged.drop(columns=[f'{col}_orig'])

            merged = merged.set_index('id')

            # 원래 순서 유지
            merged = merged.loc[valid_ids]
            return merged

        return result_df

    except Exception as e:
        print(f"[오류] get_restaurants_by_ids: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    
