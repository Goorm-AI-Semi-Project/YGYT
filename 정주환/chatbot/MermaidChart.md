flowchart LR
    %% 스타일 정의
    linkStyle default interpolate basis
    
    classDef main fill:#f9f,stroke:#333,stroke-width:2px,color:black;
    classDef logic fill:#ccf,stroke:#333,stroke-width:1px,color:black;
    classDef data fill:#dfd,stroke:#333,stroke-width:1px,color:black;
    classDef view fill:#ffd,stroke:#333,stroke-width:1px,color:black;
    classDef ext fill:#fff,stroke:#f00,stroke-width:2px,stroke-dasharray: 5 5,color:black;

    %% 1. 메인 실행 및 초기화
    subgraph Main_Entry ["🚀 app_main.py (Server & UI)"]
        direction TB
        App[FastAPI Server]:::main
        Lifespan[Lifespan: Data Load]:::main
        UI[Gradio UI]:::main
    end

    %% 2. 컨트롤러
    subgraph Control_Layer ["🎮 gradio_callbacks.py"]
        direction TB
        Init[start_chat / reset]:::logic
        Chat[chat_survey]:::logic
        RecoFlow[_run_recommendation]:::logic
    end

    %% 3. 핵심 로직
    subgraph Logic_Layer ["⚙️ Core Logic"]
        direction TB
        LLM_U[llm_utils.py]:::logic
        GPT((OpenAI\nGPT-4o)):::logic
        Search[search_logic.py]:::logic
        Filter[RAG & Filter]:::logic
        Scorer[API.final_scorer]:::logic
    end

    %% 4. 뷰 및 리소스 (상단 배치 유도)
    subgraph View_Resource ["🎨 View & Resources"]
        direction TB
        PV[profile_view.py]:::view
        I18N[i18n_texts.py]:::view
    end

    %% 5. 데이터 계층 (하단 배치)
    subgraph Data_Layer ["💾 Data Persistence"]
        direction TB
        DL[data_loader.py]:::data
        CSV[(CSV Files)]:::data
        Chroma[(ChromaDB)]:::data
    end

    %% 6. 외부 서비스 (위치 강제 조정을 위해 맨 뒤에 정의)
    subgraph External_Services ["🌐 External API"]
        direction TB
        %% ★ 수정됨: \n 대신 <br/> 사용하고 따옴표로 감쌈
        GH(("GraphHopper<br/>Localhost:8989")):::ext
    end

    %% --- 연결 정의 ---

    %% 메인 -> 데이터
    Lifespan --> DL
    DL --> CSV & Chroma

    %% UI 상호작용
    UI -- "User Input" --> Chat
    UI -- "Load/Lang" --> Init
    Init --> LLM_U
    
    %% 채팅 및 LLM
    Chat -- "Profile Complete" --> RecoFlow
    Chat --> LLM_U
    LLM_U <--> GPT

    %% 추천 로직
    RecoFlow --> Search
    Search --> Filter
    Filter -- "Query" --> Chroma
    
    RecoFlow -- "Candidates" --> Scorer
    Scorer <--"Route Calc"--> GH
    Scorer -- "Scored Results" --> RecoFlow

    %% 뷰 렌더링
    RecoFlow -- "Format HTML" --> Search
    RecoFlow -- "Render Card" --> PV
    Search & UI --> I18N
    RecoFlow -- "Update UI" --> UI

    %% ★ [Layout Hack] 그래프호퍼를 데이터 레이어 옆(아래쪽)으로 강제 이동시키는 투명 링크
    Chroma ~~~ GH
