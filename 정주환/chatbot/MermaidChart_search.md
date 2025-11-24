flowchart LR
    %% 전체 흐름: 왼쪽 -> 오른쪽
    linkStyle default interpolate basis

    %% 스타일 정의 (가독성 UP, 사이즈 최적화)
    classDef default font-size:12px,fill:#fff,stroke:#333,stroke-width:1px;
    classDef highlight fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef logic fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef decision fill:#fff9c4,stroke:#fbc02d,stroke-width:1px,shape:rhombus;

    %% === [왼쪽 기둥] 1. Input ===
    subgraph Left_Col [" "]
        direction TB
        style Left_Col fill:none,stroke:none

        subgraph S1 ["1. Input Processing"]
            direction TB
            User[("👤 User")]:::default
            Raw[Summary]:::default
            RAG[("📝 RAG Query")]:::highlight
            
            Filter[Filter Dict]:::default
            DBF[("🔍 DB Filter")]:::logic
            
            User --> Raw --> RAG
            User --> Filter --> DBF
        end
    end

    %% === [오른쪽 기둥] 2. Search + 3. Scoring ===
    subgraph Right_Col [" "]
        direction TB %% 이 안에서는 위에서 아래로 쌓임
        style Right_Col fill:none,stroke:none

        %% 2. Search
        subgraph S2 ["2. Hybrid Search"]
            direction TB
            Join[Combine]:::default
            Try1[Try 1: Hybrid]:::default
            Check{Result > 0?}:::decision
            Log[Log: Relax]:::default
            Try2[Try 2: RAG-Only]:::default
            Cands[Candidates]:::highlight
            
            Join --> Try1 --> Check
            Check -- No --> Log --> Try2 --> Cands
            Check -- Yes --> Cands
        end

        %% 3. Scoring
        subgraph S3 ["3. Python Scoring"]
            direction LR %% 내부는 가로로 배치하여 높이 절약
            
            Loop((Loop)):::default
            Img{Image?}:::decision
            Del["🚫 Del"]:::default
            Calc["Calc"]:::logic
            Add[Add]:::default
            Final[("✅ Final")]:::highlight

            Loop --> Img
            Img -- No --> Del --> Loop
            Img -- Yes --> Calc --> Add --> Loop
            Loop -- Done --> Final
        end
    end

    %% === [기둥 간 연결] ===
    RAG --> Join
    DBF --> Join
    Cands --> Loop