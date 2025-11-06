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
          processed_meta_item[key] = value
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
    식당 ID 리스트를 받아, final_scorer가 사용할
    'all_restaurants_df_scoring'에서 DataFrame을 반환합니다.
    """
    global all_restaurants_df_scoring # (load_scoring_data에서 로드된 전역 변수)
    
    if all_restaurants_df_scoring is None:
        print("[오류] 스코어링 DB(all_restaurants_df_scoring)가 로드되지 않았습니다.")
        return pd.DataFrame()
        
    try:
        # loc를 사용하여 ID 리스트 순서대로 DataFrame을 반환
        # (중복 ID가 있을 경우를 대비해 unique 처리)
        unique_ids = list(dict.fromkeys(ids))
        return all_restaurants_df_scoring.loc[unique_ids].copy()
    except KeyError as e:
        print(f"[오류] get_restaurants_by_ids: 일부 ID를 찾을 수 없음: {e}")
        # 찾을 수 있는 ID만 필터링
        valid_ids = [id for id in unique_ids if id in all_restaurants_df_scoring.index]
        if valid_ids:
            return all_restaurants_df_scoring.loc[valid_ids].copy()
        return pd.DataFrame()
    except Exception as e:
        print(f"[오류] get_restaurants_by_ids: {e}")
        return pd.DataFrame()
    
