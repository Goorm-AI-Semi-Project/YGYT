from pydantic import BaseModel, Field
from typing import List, Dict, Any

# (기존 main.py의 모델)
class RecommendationRequest(BaseModel):
    user_start_location: str = Field(..., 
                                     description="사용자 출발 좌표 (예: 37.5665,126.9780)", 
                                     json_schema_extra={'example': "37.5665,126.9780"})
    user_price_prefs: List[str] = Field(default_factory=list, 
                                        description="사용자 선호 가격대 (예: ['$$', '$$$'])", 
                                        json_schema_extra={'example': ['$$', '$$$']})
    candidate_count: int = Field(default=150, 
                                 description="1단계 후보군 수", 
                                 json_schema_extra={'example': 150})

class RecommendationResponse(BaseModel):
    recommendations: List[Dict[str, Any]] = Field(..., description="최종 점수로 정렬된 추천 식당 목록")
    log_info: Dict[str, Any] = Field(..., description="로그 기록용 메타데이터")