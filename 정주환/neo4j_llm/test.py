import os
import dotenv
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

# .env 파일에서 환경 변수 불러오기
dotenv.load_dotenv()

# 1. Neo4j 그래프 연결 
graph = Neo4jGraph(
    url=os.environ.get("NEO4J_URI"),
    username=os.environ.get("NEO4J_USERNAME"),
    password=os.environ.get("NEO4J_PASSWORD")
)

# 스키마 새로고침 
graph.refresh_schema()

# 2. OpenAI LLM 초기화 
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# 3. LLM에게 더 강력한 규칙을 지시하는 프롬프트로 수정
CYPHER_GENERATION_TEMPLATE = """
Task:Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.

**VERY IMPORTANT RULE:**
To access properties on a relationship, you **MUST** assign a variable to it in the MATCH clause.
- **CORRECT Example:** `MATCH (a)-[r:RELATIONSHIP]->(b) RETURN r.property`
- **INCORRECT Example:** `MATCH (a)-[:RELATIONSHIP]->(b) RETURN RELATIONSHIP.property`
You must follow this rule precisely.

Schema:
{schema}

Question: {question}
Cypher Query:
"""
CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
)

# 4. Cypher QA 체인 생성 
cypher_chain = GraphCypherQAChain.from_llm(
    llm=llm,
    graph=graph,
    verbose=True,
    validate_cypher=True,
    allow_dangerous_requests=True,
    cypher_prompt=CYPHER_GENERATION_PROMPT 
)

# 5. 자연어 질의 실행 
print("--- 예시 질문 1: 간단한 경로 탐색 ---")
question1 = "경복궁에서 가장 가까운 버스 정류장은 어디이고, 걸어서 몇 분 걸리나요?"
result1 = cypher_chain.invoke({"query": question1})
print(f"답변: {result1['result']}\n")

print("--- 예시 질문 2: 여러 단계를 거치는 복합 질문 ---")
question2 = "'역사 탐방' 테마가 추천하는 곳 근처에 있는 식당은 어디인가요?"
result2 = cypher_chain.invoke({"query": question2})
print(f"답변: {result2['result']}\n")

print("--- 예시 질문 3: 속성 필터링 질문 ---")
question3 = "맵기 레벨이 3 이상인 국물 요리를 추천해주세요."
result3 = cypher_chain.invoke({"query": question3})
print(f"답변: {result3['result']}\n")

print("--- 예시 질문 4: 관계 필터링 (부정) 질문 ---")
question4 = "갑각류 알레르기가 있는 사람이 피해야 할 음식은 무엇인가요?"
result4 = cypher_chain.invoke({"query": question4})
print(f"답변: {result4['result']}\n")