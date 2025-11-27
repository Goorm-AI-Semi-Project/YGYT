FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# GraphHopper JAR 파일 복사
COPY graphhopper-web-12.0-SNAPSHOT.jar .

# 설정 파일 및 데이터 디렉토리 복사
COPY config ./config
COPY custom_models ./custom_models
COPY data ./data

# 그래프 데이터 디렉토리 생성
RUN mkdir -p graphs

# 포트 노출
EXPOSE 8989 8990

# 환경변수 설정
ENV JAVA_OPTS="-Xmx24g -Xms4g"

# GraphHopper 서버 실행
CMD java $JAVA_OPTS -jar graphhopper-web-12.0-SNAPSHOT.jar server config/config-pt.yml
