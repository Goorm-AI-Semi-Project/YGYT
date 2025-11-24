flowchart LR
    %% 스타일 정의 (곡선 및 색상)
    linkStyle default interpolate basis
    
    classDef main fill:#f9f,stroke:#333,stroke-width:2px,color:black;
    classDef logic fill:#ccf,stroke:#333,stroke-width:1px,color:black;
    classDef data fill:#dfd,stroke:#333,stroke-width:1px,color:black;
    classDef view fill:#ffd,stroke:#333,stroke-width:1px,color:black;

    %% 1. 메인 실행 및 초기화 (가장 왼쪽)
    subgraph Main_Entry ["🚀 app_main.py (Server & UI)"]
        direction TB
        App[FastAPI Server]:::main
        Lifespan[Lifespan: Data Load]:::main
        UI[Gradio UI]:::main
    end

    %% 2. 컨트롤러 (중간)
    subgraph Control_Layer ["🎮 gradio_callbacks.py"]
        direction TB
        Init[start_chat / reset]:::logic
        Chat[chat_survey]:::logic
        RecoFlow[_run_recommendation]:::logic
    end

    %% 3. 핵심 로직 (중간-오른쪽)
    subgraph Logic_Layer ["⚙️ Core Logic"]
        direction TB
        LLM_U[llm_utils.py]:::logic
        GPT((GPT-4.1-mini)):::logic
        Search[search_logic.py]:::logic
        Filter[RAG & Filter]:::logic
        Scorer[API.final_scorer]:::logic
    end

    %% 4. 데이터 (하단/오른쪽)
    subgraph Data_Layer ["💾 Data Persistence"]
        direction TB
        DL[data_loader.py]:::data
        CSV[(CSV Files)]:::data
        Chroma[(ChromaDB)]:::data
    end

    %% 5. 뷰/리소스 (상단/오른쪽)
    subgraph View_Resource ["🎨 View & Resources"]
        direction TB
        PV[profile_view.py]:::view
        I18N[i18n_texts.py]:::view
    end

    %% --- 연결 정의 ---

    %% 메인 -> 데이터 로드
    Lifespan --> DL
    DL --> CSV & Chroma

    %% UI 상호작용
    UI -- "User Input" --> Chat
    UI -- "Load/Lang" --> Init
    Init --> LLM_U
    
    %% 채팅 및 추천 흐름
    Chat -- "Profile Complete" --> RecoFlow
    Chat --> LLM_U
    LLM_U <--> GPT

    %% 추천 로직 흐름
    RecoFlow --> Search
    Search --> Filter
    Filter -- "Query" --> Chroma
    RecoFlow -- "Candidates" --> Scorer
    Scorer -- "Scored Results" --> RecoFlow

    %% 뷰 렌더링 및 응답
    RecoFlow -- "Format HTML" --> Search
    RecoFlow -- "Render Card" --> PV
    Search & UI --> I18N
    RecoFlow -- "Update UI" --> UI