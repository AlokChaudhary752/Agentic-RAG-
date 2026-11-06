# Evaluation Framework & Benchmark Plan

## 1. Overview
The evaluation harness validates that the Enterprise Knowledge Agent delivers high accuracy, strict permission isolation, and verified grounding over company knowledge.

## 2. Evaluation Datasets (`evaluation/datasets/`)
- `golden_qa.jsonl`: 150+ verified enterprise questions, expected answers, and source citations covering:
  - Single-hop factual lookup
  - Multi-hop across multiple departments
  - Table and matrix queries (e.g. salary bands, SLA tiers)
  - Conflicting version resolutions (e.g. 2024 vs 2026 policies)
  - Unanswerable / out-of-scope questions (abstention verification)
  - Hindi language queries
- `permission_matrix.jsonl`: Comprehensive cartesian matrix: `(User Role x Document x Clearance)`.
- `conflict_cases.jsonl`: Paired conflicting documents with expected authoritative output.
- `injection_attacks.jsonl`: Prompt injection adversarial jailbreak attempts.

## 3. Core Metrics
- **Faithfulness**: Percentage of claims in generated answers supported by retrieved context.
- **Answer Relevance**: Semantic similarity to ground truth without hallucination.
- **Context Precision**: Ratio of relevant chunks retrieved in top ranks.
- **Context Recall**: Coverage of required ground truth chunks in retrieved set.
- **Permission Leak Rate**: MUST BE 0.00% across all user roles and test vectors.
- **Abstention Accuracy**: Correctly responding "I don't know" when evidence is insufficient.
- **Latency (p50 / p95)**: Round-trip response time.

