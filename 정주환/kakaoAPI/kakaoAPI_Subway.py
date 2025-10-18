import pandas as pd
import requests
import time
import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# 1. 지하철 CSV 파일 불러오기
try:
    df_subway = pd.read_csv('tnHseStatnOrd2.csv', encoding='cp949')
except FileNotFoundError:
    print("Error: 'tnHseStatnOrd2.csv' 파일을 찾을 수 없습니다. 스크립트와 같은 폴더에 있는지 확인하세요.")
    exit()
except UnicodeDecodeError:
    try:
        df_subway = pd.read_csv('tnHseStatnOrd2.csv', encoding='utf-8')
    except Exception as e:
        print(f"Error: CSV 파일을 읽는 중 에러 발생: {e}")
        exit()

# 2. API 호출을 위한 정보 설정
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")
if not KAKAO_API_KEY:
    print("Error: .env 파일에서 KAKAO_API_KEY를 찾을 수 없습니다. .env 파일을 올바르게 설정했는지 확인하세요.")
    exit()
    
url = "https://apis-navi.kakaomobility.com/v1/directions"
headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}

results = []

# 3. 지하철 호선 및 방면별로 그룹화
for (line_id, direction), group in df_subway.groupby(['지하철호선ID', '방면구분']):
    # 순번이 존재하고 숫자인 경우에만 정렬 시도
    if '하행순번' in group.columns and pd.api.types.is_numeric_dtype(group['하행순번']):
        group = group.sort_values(by='하행순번').reset_index(drop=True)
    else:
        # 순번이 없으면 순서 보장 불가, 원본 순서대로 진행
        group = group.reset_index(drop=True)

    if not group.empty and '지하철역명' in group.columns:
        print(f"--- 지하철 호선: {line_id} ({group.iloc[0]['지하철역명']} 방면) 처리 중 ---")

    for i in range(len(group) - 1):
        current_station = group.iloc[i]
        next_station = group.iloc[i+1]

        params = {
            "origin": f"{current_station['지하철역X좌표']},{current_station['지하철역Y좌표']}",
            "destination": f"{next_station['지하철역X좌표']},{next_station['지하철역Y좌표']}"
        }

        try:
            response = requests.get(url, params=params, headers=headers).json()
            
            # [수정된 부분] API 응답에 'routes' 키가 있는지 먼저 확인
            if 'routes' in response and response['routes']:
                summary = response['routes'][0]['summary']
                duration_sec = summary['duration']
                distance_m = summary['distance']
            else:
                # 'routes' 키가 없다면, API가 보낸 에러 메시지를 출력
                error_msg = response.get('error_message', '알 수 없는 오류')
                print(f"  -> API 응답 에러: {current_station['지하철역명']} -> {next_station['지하철역명']} 구간 / 원인: {error_msg}")
                duration_sec = -1
                distance_m = -1

        except Exception as e:
            print(f"  -> 스크립트 에러: {current_station['지하철역명']} -> {next_station['지하철역명']} 구간 / {e}")
            duration_sec = -1
            distance_m = -1

        station_data = current_station.to_dict()
        station_data['duration_to_next'] = duration_sec
        station_data['distance_to_next'] = distance_m
        results.append(station_data)
        
        time.sleep(0.05)

    if not group.empty:
        last_station_data = group.iloc[-1].to_dict()
        last_station_data['duration_to_next'] = 0
        last_station_data['distance_to_next'] = 0
        results.append(last_station_data)

# 6. 새로운 CSV 파일로 저장
new_df_subway = pd.DataFrame(results)
new_df_subway.to_csv('subway_routes_enriched.csv', index=False, encoding='utf-8-sig')

print("\n--- 모든 작업 완료! 'subway_routes_enriched.csv' 파일이 생성되었습니다. ---")