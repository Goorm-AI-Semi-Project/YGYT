import json
import math
from typing import List, Dict, Any

# --------------------------------------------------------------------
# 1. 여기에 최적화된 '이동 마찰 점수' 계산 함수를 붙여넣습니다.
# --------------------------------------------------------------------
def calculate_travel_friction_score(path_data: dict) -> float:
    """
    GraphHopper의 단일 경로(path) 데이터를 기반으로
    '이동 마찰 점수'(0~1)를 계산합니다. (1점이 가장 좋음)
    
    [최적화 기준]
    - 관광객은 '총 시간'보다 '환승'과 '도보'에 더 민감합니다.
    - min/max 값은 서울시 대중교통 평균 데이터를 기반으로 설정합니다.
    """
    
    # 1. 핵심 지표 추출
    # ---------------------------------------------------
    # 총 소요 시간 (분)
    total_time_minutes = path_data.get('time', 0) / 1000 / 60
    # 총 환승 횟수
    num_transfers = path_data.get('transfers', 0)
    # 총 도보 거리 (미터)
    total_walk_meters = path_data.get('distance', 0)
    
    
    # 2. 각 지표를 0~1 사이 점수로 정규화 (Normalization)
    # ---------------------------------------------------
    
    # (A) 시간 점수: 20분 이하는 1점, 50분 이상은 0점
    max_time = 50  # 50분 이상 걸리면 점수 0점
    min_time = 20  # 20분 이내 도착은 점수 1점
    time_score = 1 - min(1, max(0, (total_time_minutes - min_time) / (max_time - min_time)))
    
    # (B) 도보 점수: 500m 이하는 1점, 1.2km 이상은 0점
    max_walk = 1200 # 1.2km
    min_walk = 500  # 500m
    walk_score = 1 - min(1, max(0, (total_walk_meters - min_walk) / (max_walk - min_walk)))
    
    # (C) 환승 점수: 0회 = 1점, 1회 = 0.4점, 2회 이상 = 0점
    if num_transfers == 0:
        transfer_score = 1.0
    elif num_transfers == 1:
        transfer_score = 0.4 # 환승 1회에 큰 페널티 적용
    else:
        transfer_score = 0.0 # 환승 2회 이상은 0점 처리
        
        
    # 3. 최종 점수 (가중 평균)
    # ---------------------------------------------------
    # '뚜벅이' 특성을 반영하여 '도보'와 '환승' 가중치를 높게 설정
    weights = {
        'walk': 0.4,       # (높음) 총 도보 거리
        'transfers': 0.4,  # (높음) 환승의 번거로움
        'time': 0.2        # (낮음) 총 소요 시간
    }
    
    final_score = (
        (time_score * weights['time']) +
        (walk_score * weights['walk']) +
        (transfer_score * weights['transfers'])
    )
    
    return final_score

# --------------------------------------------------------------------
# 2. JSON 파일을 읽고 함수를 테스트하는 메인 로직
# --------------------------------------------------------------------
if __name__ == "__main__":
    
    json_file_path = "response_1760792051980.json"
    all_scores = []
    
    try:
        # JSON 파일 열기
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 'route_plans' 키에서 경로 리스트 추출
        # (이 JSON 파일은 API의 최종 응답이므로 'route_plans' 키를 사용합니다)
        paths_list = data.get('route_plans')
        
        if not paths_list:
            print(f"❌ 오류: '{json_file_path}'에서 'route_plans' 키를 찾을 수 없습니다.")
        
        else:
            print(f"✅ '{json_file_path}' 로드 성공. 총 {len(paths_list)}개의 경로 테스트 시작...")
            
            # 각 경로를 순회하며 점수 계산
            for i, path in enumerate(paths_list):
                # 각 경로(path)를 함수에 전달하여 점수 계산
                score = calculate_travel_friction_score(path)
                all_scores.append(score)
                
                # 테스트 결과 출력
                print(f"\n--- 🗺️ 경로 {i+1} ---")
                print(f"  - 총 시간: {path.get('time', 0) / 1000 / 60:.1f} 분")
                print(f"  - 총 도보: {path.get('distance', 0):.1f} 미터")
                print(f"  - 환승 횟수: {path.get('transfers', 0)} 회")
                print(f"  🔥 계산된 '이동 마찰 점수': {score:.4f}")
            
            # 최종 요약
            if all_scores:
                best_score = max(all_scores)
                print("\n================================================")
                print(f"🏆 이 식당의 최종 '이동 마찰' 점수 (가장 좋은 경로): {best_score:.4f}")
                print("================================================")

    except FileNotFoundError:
        print(f"❌ 오류: '{json_file_path}' 파일을 찾을 수 없습니다.")
        print("스크립트와 같은 폴더에 JSON 파일이 있는지 확인하세요.")
    except json.JSONDecodeError:
        print(f"❌ 오류: '{json_file_path}' 파일이 올바른 JSON 형식이 아닙니다.")
    except Exception as e:
        print(f"❌ 알 수 없는 오류 발생: {e}")