# Enterprise Knowledge Agent: Technical Architecture & System Design

> A production-grade, permission-aware, agentic RAG platform designed with hexagonal (ports and adapters) principles to guarantee **zero permission leaks**, autonomous self-correction, claim verification, and safe tool execution through Model Context Protocol (MCP).

---

## 1. System Topology & Architectural Overview

The **Enterprise Knowledge Agent** is structured into five cohesive subsystems: Ingress & Client, Security & Governance, Stateful Agent Orchestration (LangGraph), Tool Execution (MCP), and Storage & Persistence.

```mermaid
flowchart TD
    subgraph ClientLayer["1. Client & Ingress Layer"]
        User["Employee / Client"] --> NextUI["Next.js 14 Web UI\n(Chat, Citations Drawer, Admin Console)"]
        CLI["scripts/demo.py CLI"] --> APIGateway["FastAPI Gateway / Router\n(:8000/api/v1)"]
        NextUI --> APIGateway
    end

    subgraph GovernanceLayer["2. Security & Governance Subsystem"]
        APIGateway --> Auth["JWT & Principal Extractor\n(Salted PBKDF2 / Bearer Tokens)"]
        Auth --> RateLimiter["Sliding Window Rate Limiter\n(Per-Tenant & Per-User)"]
        RateLimiter --> InjectionFilter["Prompt Injection Defense\n(Regex + Heuristic Risk Scoring)"]
        InjectionFilter --> Cache["ACL-Scoped Semantic Cache\n(MD5(Query + Tenant + Clearance + Groups))"]
        APIGateway --> AuditTrail[("PostgreSQL Immutable Audit Trail\n(Hash, User ID, Tool Calls, No PII)")]
    end

    subgraph AgentLayer["3. Stateful Agent Orchestration (LangGraph)"]
        Cache -.->|Cache Miss| StateMachine["LangGraph Agent Workflow"]
        StateMachine --> Understand["Intent Classifier\n(Factual, Multi-hop, Action, Chit-chat)"]
        Understand --> RewritePlan["Query Transformer\n(Acronym Expansion, Multi-hop Decomposition)"]
        RewritePlan --> Retrieve["Hybrid Retrieval Coordinator"]
        Retrieve --> GradeEvidence["Self-RAG Evidence Grader"]
        GradeEvidence -->|Weak Evidence & Budget > 0| RewritePlan
        GradeEvidence -->|Sufficient Evidence| ResolveConflicts["Cross-Document Conflict Resolver"]
        ResolveConflicts --> Generate["Grounded Answer Synthesis"]
        Generate --> VerifyClaims["Claim-Level Faithfulness Verifier"]
        VerifyClaims --> DecideAction{"Action Request?"}
        DecideAction -->|Yes| MCPClient["MCP Tool Client"]
        DecideAction -->|No| Respond["Respond Node + Citations"]
    end

    subgraph ToolLayer["4. Tool Governance & Model Context Protocol (MCP)"]
        MCPClient --> ToolRisk{"Tool Risk Level"}
        ToolRisk -->|write_high| ApprovalGate["Human-in-the-Loop Approval Gate\n(State Paused, Awaiting Admin Decision)"]
        ToolRisk -->|read / write_low| AutoExec["Autonomous Execution"]
        ApprovalGate -->|Approved| AutoExec
        AutoExec --> MCPServers["In-Memory MCP Server Hub\n(Jira Store, Email Store, Document Index)"]
        MCPServers --> Respond
    end

    subgraph StorageLayer["5. Storage & Persistence"]
        Retrieve --> DenseSearch["Qdrant Vector Database\n(HNSW with Vector-Level ACL Pre-Filter)"]
        Retrieve --> SparseSearch["BM25 Index\n(Document-Level In-Memory / Filtered)"]
        AuditTrail --> PostgresDB[("PostgreSQL Database\n(Users, Roles, Groups, Audit Logs)")]
        RateLimiter --> RedisCache[("Redis / Local Cache\n(Semantic Cache & Rate Limits)")]
    end
```

---

## 2. Ingestion Pipeline & Layout Parsing

The ingestion pipeline ingests enterprise documents from heterogeneous connectors (Local Folders, Google Drive, Notion, Confluence, Slack, Jira), extracts structured tables and text, redacts sensitive PII, chunks documents hierarchically, and synchronizes vector payloads with relational access control lists.

```mermaid
flowchart LR
    Sources["Enterprise Sources\n(Drive, Notion, Confluence,\nSlack, Jira, PDFs, Markdown)"] --> Connectors["BaseConnector Adapters"]
    Connectors --> Parsers["Layout-Aware Parsers\n(Markdown, HTML, PDF Tables, Metadata)"]
    Parsers --> Masker["Presidio PII Masker\n(SSN, Credit Cards, API Keys, Emails)"]
    Masker --> Chunker["Structure Chunker\n(Parent-Child & Section Hierarchy)"]
    Chunker --> Enricher["Metadata & ACL Compiler\n(User Allowlist, Group Allowlist, Clearance Level)"]
    Enricher --> QdrantSync["Qdrant Vector Indexing\n(Payload: doc_id, chunk_id, ACL, Status, Year)"]
    Enricher --> PostgresSync["PostgreSQL Persistence\n(Documents, ACLs, Versions, Chunks)"]
```

### Ingestion Components
1. **Layout-Aware Parsing (`backend/app/ingestion/parsers/`)**: Preserves Markdown tables, section header breadcrumbs (`HR > Benefits > Travel`), author metadata, and publication dates.
2. **PII Masking (`backend/app/ingestion/masking/`)**: Scans content using Microsoft Presidio and regex heuristics, redacting sensitive credentials and employee identification numbers.
3. **Structure Chunking (`backend/app/ingestion/chunkers/`)**: Splits documents into parent-child chunks (300-800 tokens) with 50-token overlaps, maintaining explicit section references for exact inline citations.
4. **ACL Compiler (`backend/app/ingestion/pipeline.py`)**: Attaches cryptographic hashes and explicit security metadata to every chunk: `allowed_users`, `allowed_groups`, and `classification_level` (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`).

---

## 3. Dual-Layer Zero-Leak Permission Enforcement

To mathematically guarantee **Zero Permission Leaks**, security enforcement is applied at two independent defense boundaries:

```mermaid
sequenceDiagram
    autonumber
    actor User as Employee / Client
    participant GW as API Gateway & Auth
    participant Agent as LangGraph Orchestrator
    participant Qdrant as Qdrant Vector DB
    participant Assertion as Defense-in-Depth Validator
    participant LLM as Grounded LLM

    User->>GW: POST /api/v1/chat/completions (Bearer JWT)
    GW->>GW: Verify HMAC-SHA256 signature & decode claims
    Note over GW: UserPrincipal: user_id, clearance, groups
    GW->>Agent: Invoke graph with UserPrincipal context
    Agent->>Qdrant: Hybrid Search with Native ACL Pre-Filter
    Note over Qdrant: HNSW graph search ONLY visits nodes matching:<br/>(allowed_users CONTAINS user_id OR<br/>allowed_groups OVERLAPS user_groups) AND<br/>(chunk_clearance <= user_clearance)
    Qdrant-->>Agent: Candidate chunks (Dense results)
    Agent->>Assertion: Secondary In-Memory Assertion
    alt Any chunk violates user permissions
        Assertion-->>Agent: Raise PermissionLeakError & log SECURITY_ALERT
        Agent-->>User: Fail Closed (HTTP 403 / Sanitized refusal)
    else All chunks authorized
        Assertion-->>Agent: Compliance Verified (0 leaks)
        Agent->>LLM: Synthesize answer with citations
        LLM-->>User: Grounded response + Inline section citations
    end
```

### Defense Boundaries:
1. **Primary Defense (Vector Index Traversal)**: Qdrant query filters ensure unauthorized vectors are never visited during HNSW graph traversal.
2. **Secondary Defense (In-Memory Assertion)**: Every candidate chunk is re-validated against the caller's active `UserPrincipal` before being passed to LLM synthesis. If an unauthorized chunk is detected, execution fails closed and raises a high-severity security audit event.
3. **Tertiary Defense (ACL-Scoped Semantic Cache)**: Cache keys hash query text together with `tenant_id`, `clearance`, and sorted `groups`. A cached response generated for Bob (manager) can never be returned to Alice (employee).
4. **Tool Permission Checks**: MCP tools verify caller group membership and clearance before executing actions.

---

## 4. LangGraph Multi-Step Stateful Agent Architecture

The agent workflow is modeled as a compiled state graph with conditional cyclic branching for Self-RAG reflection:

```mermaid
stateDiagram-v2
    [*] --> understand: Query Received
    understand --> rewrite_and_plan: Intent Classified

    state rewrite_and_plan {
        [*] --> check_intent
        check_intent --> chit_chat: Intent in [chit_chat, out_of_scope]
        check_intent --> transform_query: Intent in [factual_lookup, multi_hop, action_request]
    }

    rewrite_and_plan --> respond: Chit-Chat Fast Path
    rewrite_and_plan --> retrieve: Knowledge Retrieval

    retrieve --> grade_evidence: Chunks Retrieved
    
    state grade_evidence {
        [*] --> evaluate_relevance
        evaluate_relevance --> weak_evidence: Overlap < 0.25
        evaluate_relevance --> good_evidence: Overlap >= 0.25
    }

    grade_evidence --> retrieve: Self-RAG Loop (if iteration < 2)
    grade_evidence --> resolve_conflicts: Evidence Ready

    resolve_conflicts --> generate: Chunks Re-ranked & Notices Formulated
    generate --> verify: Draft Answer & Citations Synthesized

    state verify {
        [*] --> claim_extraction
        claim_extraction --> assert_grounding: Context Overlap Check
    }

    verify --> decide_action: Faithfulness Score Computed

    decide_action --> human_approval: Action Requires Approval (write_high)
    decide_action --> respond: No Action or Low-Risk Action Executed

    human_approval --> respond: Approval Decision Processed
    respond --> [*]: Final Response + Citations Delivered
```

---

## 5. Model Context Protocol (MCP) & Human-In-The-Loop Governance

Enterprise actions (Jira ticket creation, summary email dispatch, document metadata inspection) are exposed through Model Context Protocol (MCP) servers with strict risk classification:

| Tool Name | Server | Risk Level | Description | Requires Approval |
|---|---|---|---|---|
| `get_document_metadata` | `enterprise_docs` | `read` | Retrieve document metadata and ACLs | No |
| `list_recent_changes` | `enterprise_docs` | `read` | List recent knowledge modifications | No |
| `get_ticket_status` | `jira_server` | `read` | Inspect Jira ticket status and priority | No |
| `send_summary_email` | `email_server` | `write_low` | Dispatch knowledge summary to user | No |
| `create_jira_ticket` | `jira_server` | `write_high` | Create engineering or security tickets | **Yes** (Human-in-the-Loop) |

### Action Lifecycle:
1. **Planning**: Agent detects intent `action_request` and maps request to `create_jira_ticket`.
2. **Risk Intercept**: MCP Client checks tool risk tier. Because `create_jira_ticket` is `write_high`, execution is paused, state is committed to memory checkpointer, and `approval_required: true` is returned to the user.
3. **Human Review**: User/Admin reviews target action details in UI modal or CLI.
4. **Resumption**: Client sends resumption payload (`approval_granted: true` or `approval_granted: false`) with matching `thread_id`.
5. **Execution & Audit**: MCP client validates caller role, checks client-side idempotency cache, calls tool server, records execution in PostgreSQL audit trail, and returns ticket URL.

---

## 6. Observability, Telemetry & Reliability

```mermaid
flowchart LR
    API["FastAPI App (:8000)"] --> PrometheusExposition["/api/v1/metrics"]
    PrometheusExposition --> Prometheus["Prometheus Server (:9090)"]
    Prometheus --> Grafana["Grafana Dashboards (:3002)\n- Zero Permission Leak Alert Panel\n- QPS & P50/P95 Latency\n- Cost (USD) & Token Burn\n- Cache Hit Ratio\n- Rate Limit Throttling"]
    
    API --> CostTracker["Cost Tracker & Model Router\n(Gemini Flash for Routing/Grading,\nGemini Pro for Synthesis/Verification)"]
    API --> RateLimiter["Sliding Window Limiter\n(X-RateLimit-* Headers)"]
```

- **Prometheus Metrics**: `agent_query_total`, `agent_reasoning_latency_seconds`, `rag_cache_hits_total`, `rag_cache_misses_total`, `rag_permission_leaks_total`, `mcp_tool_execution_total`, `rate_limit_exceeded_total`, `llm_token_usage_total`, `llm_estimated_cost_usd_total`.
- **Zero Permission Leak Alert**: Grafana alert triggers immediately if `rag_permission_leaks_total > 0`.
- **Dynamic Model Routing**: Routes lightweight intent classification and evidence grading to Gemini Flash (\$0.075 / 1M prompt tokens) and complex synthesis to Gemini Pro (\$1.25 / 1M prompt tokens), reducing total query cost by up to 65%.
