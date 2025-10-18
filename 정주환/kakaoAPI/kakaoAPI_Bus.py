import pandas as pd
import requests
import time
import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# 1. CSV 파일 불러오기
try:
    df = pd.read_csv('seoul_bus_routes.csv')
except FileNotFoundError:
    print("Error: 'seoul_bus_routes.csv' 파일을 찾을 수 없습니다. 스크립트와 같은 폴더에 있는지 확인하세요.")
    exit()

# 2. API 호출을 위한 정보 설정
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")
if not KAKAO_API_KEY:
    print("Error: .env 파일에서 KAKAO_API_KEY를 찾을 수 없습니다. .env 파일을 올바르게 설정했는지 확인하세요.")
    exit()

url = "https://apis-navi.kakaomobility.com/v1/directions"
headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}

# 결과를 저장할 리스트
results = []

# 3. 노선(ROUTE_ID)별로 그룹화하여 처리
for route_id, group in df.groupby('ROUTE_ID'):
    group = group.sort_values(by='순번').reset_index(drop=True)
    
    # 노선명이 비어있지 않은 경우에만 로그 출력
    if not group.empty and '노선명' in group.columns:
        print(f"--- 버스 노선: {group.iloc[0]['노선명']} ({route_id}) 처리 중 ---")

    for i in range(len(group) - 1):
        current_stop = group.iloc[i]
        next_stop = group.iloc[i+1]

        params = {
            "origin": f"{current_stop['X좌표']},{current_stop['Y좌표']}",
            "destination": f"{next_stop['X좌표']},{next_stop['Y좌표']}"
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
                print(f"  -> API 응답 에러: {current_stop['정류소명']} -> {next_stop['정류소명']} 구간 / 원인: {error_msg}")
                duration_sec = -1
                distance_m = -1
            
        except Exception as e:
            # 그 외 예상치 못한 에러 (예: 인터넷 연결 문제 등)
            print(f"  -> 스크립트 에러: {current_stop['정류소명']} -> {next_stop['정류소명']} 구간 / {e}")
            duration_sec = -1
            distance_m = -1

        stop_data = current_stop.to_dict()
        stop_data['duration_to_next'] = duration_sec
        stop_data['distance_to_next'] = distance_m
        results.append(stop_data)
        
        time.sleep(0.05) # API 호출 제한을 피하기 위한 최소한의 딜레이

    # 각 노선의 마지막 정류장 추가
    if not group.empty:
        last_stop_data = group.iloc[-1].to_dict()
        last_stop_data['duration_to_next'] = 0
        last_stop_data['distance_to_next'] = 0
        results.append(last_stop_data)

# 6. 새로운 CSV 파일로 저장
new_df = pd.DataFrame(results)
new_df.to_csv('seoul_bus_routes_enriched.csv', index=False, encoding='utf-8-sig')

print("\n--- 모든 작업 완료! 'seoul_bus_routes_enriched.csv' 파일이 생성되었습니다. ---")