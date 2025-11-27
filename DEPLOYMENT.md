# 배포 가이드

## 로컬 개발 환경

로컬에서 개발할 때는 기본 `docker-compose.yml` 사용:

```bash
# 컨테이너 빌드 및 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

**접속 주소:**
- 프론트엔드: http://localhost:3000
- API 서버: http://localhost:8000
- GraphHopper: http://localhost:8989

---

## AWS 프로덕션 배포

AWS EC2 (탄력적 IP: `43.200.106.102`)에 배포할 때는 **프로덕션용 설정** 사용:

```bash
# 프로덕션 설정으로 빌드 및 실행
docker-compose -f docker-compose.prod.yml up -d --build

# 로그 확인
docker-compose -f docker-compose.prod.yml logs -f

# 중지
docker-compose -f docker-compose.prod.yml down
```

**접속 주소:**
- 프론트엔드: http://43.200.106.102:3000
- API 서버: http://43.200.106.102:8000

---

## 주요 차이점

### 로컬 (`docker-compose.yml`)
- API URL: `http://localhost:8000`
- CORS: `localhost:3000` 허용

### AWS (`docker-compose.prod.yml`)
- API URL: `http://43.200.106.102:8000`
- CORS: AWS IP 주소 허용

---

## AWS 보안 그룹 설정

다음 포트들을 인바운드 규칙에 추가하세요:

| 포트 | 프로토콜 | 용도 |
|------|----------|------|
| 3000 | TCP | 프론트엔드 |
| 8000 | TCP | API 서버 |
| 8989 | TCP | GraphHopper (선택) |
| 22   | TCP | SSH |

---

## 트러블슈팅

### 1. API 연결 실패 (`ERR_CONNECTION_REFUSED`)
- AWS 보안 그룹에서 8000 포트 확인
- `docker-compose.prod.yml` 사용했는지 확인
- 컨테이너 실행 상태: `docker ps`

### 2. CORS 오류
- `app.py`의 CORS 설정에 IP 추가되었는지 확인
- 브라우저 캐시 삭제 (Ctrl+Shift+Delete)

### 3. 용량 부족
- `requirements.txt`에 PyTorch CPU 버전 명시됨
- 불필요한 Docker 이미지 삭제: `docker system prune -a`

---

## 환경 변수

### 필수 환경 변수 (`.env` 파일)
`APIserver/.env` 파일에 다음 키들을 설정하세요:

```bash
OPENAI_API_KEY=your_key_here
HUGGINGFACEHUB_API_TOKEN=your_key_here
LANGCHAIN_API_KEY=your_key_here
# ... 기타 필요한 API 키
```
