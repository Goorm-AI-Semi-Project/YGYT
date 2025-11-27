flowchart LR
    %% 전체 방향: 왼쪽 -> 오른쪽
    linkStyle default interpolate basis

    %% 스타일 정의
    classDef default font-size:12px,fill:#fff,stroke:#333,stroke-width:1px;
    classDef highlight fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef logic fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef db fill:#fff3e0,stroke:#ef6c00,stroke-width:2px;
    classDef decision fill:#fff9c4,stroke:#fbc02d,stroke-width:1px,shape:rhombus;

    %% === [왼쪽] 1. Input Processing ===
    subgraph Input_Block ["1. Input Processing"]
        direction TB
        User[("👤 User Profile")]:::default
        
        %% 텍스트 처리 경로
        User --> Raw[Summary]:::default
        Raw --> RAG[("📝 RAG Query")]:::highlight
        
        %% 필터 처리 경로
        User --> Filter[Filter Dict]:::default
        Filter --> DBF[("🔍 DB Filter")]:::logic
    end

    %% === [오른쪽] 2. Hybrid Search ===
    subgraph Search_Block ["2. Hybrid Search Logic"]
        direction TB
        Join[Combine Query & Filter]:::default
        
        Try1[Attempt 1: Hybrid]:::db
        Check{Hits > 0?}:::decision
        
        Log[Log: Relax Filter]:::default
        Try2[Attempt 2: RAG-Only]:::db
        
        Cands[Raw Candidates]:::highlight
        
        %% 내부 로직 연결
        Join --> Try1 --> Check
        Check -- No --> Log --> Try2 --> Cands
        Check -- Yes --> Cands
    end

    %% === [두 블록 연결] ===
    RAG --> Join
    DBF --> Join