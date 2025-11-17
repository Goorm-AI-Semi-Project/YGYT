ChatBot 구동시 참조사항

* GTFS Graphhopper 서버가 먼저 구동되야합니다
  * java -Xmx24g -jar web/target/graphhopper-web-12.0-SNAPSHOT.jar server reader-gtfs/config-example-pt.yml

* OPEN AI KEY 가 필요합니다
  * export OPENAI_API_KEY='sk-'

* ./data/에 ZIP 파일을 동일한 경로에 압축해제 해야합니다
  * https://github.com/Goorm-AI-Semi-Project/YGYT/blob/main/%EC%A0%95%EC%A3%BC%ED%99%98/chatbot/data/restaurant_summaries_output_en%2Ccn%2Cjp.zip

* Chatbot 실행
  * python app_main.py
  * http://localhost:8080/chatbot/
 
* ./restaurant_db/ 내의 파일이 변경되어야하는데 용량문제로 commit & push가 안됩니다 따라서 최초 실행 후
  * https://github.com/Goorm-AI-Semi-Project/YGYT/blob/main/%EC%A0%95%EC%A3%BC%ED%99%98/chatbot/config.py
  * 위 파일의 CLEAR_DB_AND_REBUILD = True 항목을 False 로 바꾸고 실행해야 속도가 빨라집니다
