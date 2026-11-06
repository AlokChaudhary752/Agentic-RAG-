# Enterprise Knowledge Agent: System Architecture

## 1. High-Level Architecture Overview

The **Enterprise Knowledge Agent** is a multi-tenant, permission-aware agentic RAG platform designed with hexagonal (ports and adapters) principles to ensure zero-leak document access control, autonomous self-correction, claim verification, and safe tool execution through Model Context Protocol (MCP).

```mermaid
flowchart TD
    subgraph ClientLayer["Client & Ingress Layer"]
        User["Employee / Client"] --> WebUI["Next.js Chat & Admin UI"]
        WebUI --> APIGateway["FastAPI Gateway / Router"]
    end

    subgraph AuthLayer["Governance & Security"]
        APIGateway --> JWT["JWT & Identity Resolver"]
        JWT --> ACLCompiler["ACL Filter Compiler"]
        ACLCompiler -.-> PreFilter["Vector-Level ACL Pre-Filter"]
    end

    subgraph AgentLayer["Agentic Orchestration (LangGraph)"]
        APIGateway --> Agent["LangGraph State Machine"]
        Agent --> Intent["Understand & Plan"]
        Intent --> RetrievalRouter["Retrieval Router"]
        RetrievalRouter --> HybridSearch["Hybrid Search (Dense + Sparse)"]
        HybridSearch --> Rerank["Cross-Encoder Reranker"]
        Rerank --> DefenseInDepth["Defense-in-Depth ACL Assertion"]
        DefenseInDepth --> Grader["Self-RAG Evidence Grader"]
        Grader --> ConflictResolver["Conflict Resolution Engine"]
        ConflictResolver --> Generator["Grounded Generator"]
        Generator --> ClaimVerifier["Claim-Level Faithfulness Verifier"]
        ClaimVerifier --> Decider{"Action Required?"}
        Decider -- Yes --> MCPClient["MCP Tool Client"]
        Decider -- No --> FinalResponse["Structured Response + Citations"]
        MCPClient --> HumanApproval{"Risk Level == High?"}
        HumanApproval -- Yes --> Interrupt["Interrupt & Await Human Approval"]
        HumanApproval -- No --> ExecuteTool["Execute Tool"]
        ExecuteTool --> FinalResponse
    end

    subgraph StorageLayer["Data & Persistence Layer"]
        PreFilter --> Qdrant["Qdrant Vector Database"]
        APIGateway --> Postgres["PostgreSQL (ACLs, Users, Audit)"]
        APIGateway --> Redis["Redis (Semantic Cache & Rate Limits)"]
    end
```

## 2. Ingestion Pipeline Architecture

```mermaid
flowchart LR
    Sources["Enterprise Sources\n(Google Drive, Notion, Confluence,\nSlack, Jira, Local PDFs)"] --> Connectors["BaseConnector Adapters"]
    Connectors --> Parsers["Layout-Aware Parsers\n(Tables, Markdown, OCR)"]
    Parsers --> Masker["PII Masker & Anonymizer"]
    Masker --> Chunking["Parent-Child & Section Chunking"]
    Chunking --> MetadataEnricher["Metadata & ACL Enrichment"]
    MetadataEnricher --> Embedder["Embedding & Sparse Generator"]
    Embedder --> VectorSink[("Qdrant Vector Store")]
    MetadataEnricher --> DBSink[("PostgreSQL Metadata & ACLs")]
```

## 3. Defense-in-Depth Permission Enforcement

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Gateway as API Gateway
    participant Auth as Identity & JWT
    participant Agent as Agent Graph
    participant Qdrant as Qdrant Vector Store
    participant Validator as Defense-in-Depth Validator
    participant LLM as Generator LLM

    User->>Gateway: Ask question with Bearer JWT
    Gateway->>Auth: Decode token & expand groups
    Auth-->>Gateway: Principal (User ID, Groups, Clearance)
    Gateway->>Agent: Run agent with Security Context
    Agent->>Qdrant: Hybrid Search with Native ACL Pre-Filter
    Note over Qdrant: HNSW graph search ONLY visits<br/>points matching user/group ACL
    Qdrant-->>Agent: Candidate chunks
    Agent->>Validator: Assert ACL compliance on all chunks
    alt Any chunk unauthorized
        Validator-->>Agent: Raise PermissionLeakError & trigger audit alert
        Agent-->>User: Fail closed (Security Exception)
    else All chunks authorized
        Validator-->>Agent: Validation passed
        Agent->>LLM: Synthesize answer with citations
        LLM-->>User: Grounded answer with verified citations
    end
```
