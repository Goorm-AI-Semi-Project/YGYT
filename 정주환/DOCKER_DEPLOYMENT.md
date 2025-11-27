# Docker Compose 배포 가이드

## 서비스 구성

- **GraphHopper** (8989) - 라우팅 엔진
- **Backend** (8000) - 식당 추천 API
- **APIserver** (8001) - 챗봇 API
- **Frontend** (3000) - React 개발 서버

## 사전 준비

### 1. 환경 변수 설정

`APIserver/.env` 파일 생성:
```bash
OPENAI_API_KEY=your_key_here
```

### 2. 필수 데이터 파일 확인

각 디렉토리에 데이터 파일이 있는지 확인:

```
deploy/data/south-korea-251014.osm.pbf
deploy/data/202303_GTFS_DataSet.zip
back/RecommendationAlgorithm/blueribbon_scores_only_reviewed.csv
APIserver/data/*.csv
APIserver/restaurant_db/chroma.sqlite3
```

## 실행

```bash
# 빌드 및 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

## 접속

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- APIserver API: http://localhost:8001/docs
- GraphHopper: http://localhost:8989/info

## 문제 해결

### GraphHopper 시작 느림
첫 실행 시 그래프 생성으로 수분~수십분 소요됩니다.

### 메모리 부족
`docker-compose.yml`에서 `-Xmx24g`를 `-Xmx16g`로 변경하세요.

### 포트 충돌
`docker-compose.yml`에서 포트 번호 변경하세요.
