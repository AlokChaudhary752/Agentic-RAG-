"""Unit tests for RAGAS evaluation metrics and Golden Dataset models."""

import pytest

from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk, UserPrincipal
from evaluation.datasets.dataset_loader import DatasetCategory, load_golden_dataset
from evaluation.metrics.ragas_metrics import RagasMetricsEvaluator


@pytest.fixture
def evaluator() -> RagasMetricsEvaluator:
    return RagasMetricsEvaluator()


@pytest.fixture
def test_principal_alice() -> UserPrincipal:
    return UserPrincipal(
        user_id="emp_alice",
        email="alice@nimbus.com",
        full_name="Alice Smith",
        roles=["employee"],
        groups=["group_engineering"],
        clearance=ClassificationLevel.INTERNAL,
        tenant_id="tenant-nimbus-default",
    )


def test_faithfulness_calculation(evaluator: RagasMetricsEvaluator) -> None:
    # 1. Grounded answer
    context = [
        "Employees receive twenty-five days of paid annual vacation leave each calendar year.",
        "Up to 10 days of unused leave may be carried over.",
    ]
    grounded_answer = "Employees receive twenty-five days of paid annual vacation leave. Up to 10 days carry over."
    score = evaluator.calculate_faithfulness(grounded_answer, context)
    assert score >= 0.8

    # 2. Hallucinated answer (claims not in context)
    hallucinated = (
        "Employees receive 60 days of vacation and a company sports car for personal travel."
    )
    hallucinated_score = evaluator.calculate_faithfulness(hallucinated, context)
    assert hallucinated_score < 0.5

    # 3. Truthful refusal
    refusal = "I do not have sufficient information in the authorized enterprise documents to answer this question."
    assert evaluator.calculate_faithfulness(refusal, []) == 1.0


def test_answer_relevance_calculation(evaluator: RagasMetricsEvaluator) -> None:
    query = "What is the annual PTO allocation?"
    answer = "Nimbus employees receive 25 days of annual paid time off (PTO) leave."
    keywords = ["25", "days", "pto", "annual", "leave"]

    rel_score = evaluator.calculate_answer_relevance(query, answer, keywords)
    assert rel_score >= 0.8

    # Irrelevant evasive answer
    evasive = "The weather in San Francisco is currently sunny with a mild coastal breeze."
    evasive_score = evaluator.calculate_answer_relevance(query, evasive, keywords)
    assert evasive_score < 0.3

    # Truthful expected refusal
    refusal = "I do not have sufficient information in authorized documents."
    assert (
        evaluator.calculate_answer_relevance(query, refusal, keywords, expected_refusal=True) == 1.0
    )


def test_context_precision_calculation(evaluator: RagasMetricsEvaluator) -> None:
    # Relevant chunk at rank 1
    retrieved = ["hr-leave-policy-2026", "it-acceptable-use", "eng-python-standards"]
    expected = ["hr-leave-policy-2026"]
    prec = evaluator.calculate_context_precision(retrieved, expected)
    assert prec == 1.0

    # Relevant chunk at rank 3
    retrieved_late = ["it-acceptable-use", "eng-python-standards", "hr-leave-policy-2026"]
    prec_late = evaluator.calculate_context_precision(retrieved_late, expected)
    assert 0.0 < prec_late < 1.0

    # Zero relevant chunks
    assert (
        evaluator.calculate_context_precision(["it-acceptable-use"], ["hr-leave-policy-2026"])
        == 0.0
    )

    # Expected refusal: no docs retrieved -> perfect precision
    assert (
        evaluator.calculate_context_precision([], ["fin-salary-bands"], expected_refusal=True)
        == 1.0
    )


def test_context_recall_calculation(evaluator: RagasMetricsEvaluator) -> None:
    retrieved = ["hr-leave-policy-2026", "fin-travel-policy-2026"]
    expected = ["hr-leave-policy-2026", "fin-travel-policy-2026"]
    assert evaluator.calculate_context_recall(retrieved, expected) == 1.0

    # Partial recall (1 out of 2)
    assert evaluator.calculate_context_recall(["hr-leave-policy-2026"], expected) == 0.5


def test_permission_leak_detection(
    evaluator: RagasMetricsEvaluator, test_principal_alice: UserPrincipal
) -> None:
    # 1. Content leak (forbidden salary appears in answer)
    leaked_answer = "The base salary range for L5 is $175,000 to $225,000."
    has_leak = evaluator.calculate_permission_leak(
        answer=leaked_answer,
        forbidden_terms=["$175,000"],
        retrieved_chunks=[],
        principal=test_principal_alice,
    )
    assert has_leak is True

    # 2. Retrieval leak (CONFIDENTIAL chunk retrieved by INTERNAL user)
    confidential_chunk = DocumentChunk(
        id="chunk-conf-1",
        doc_id="fin-salary-bands",
        chunk_index=1,
        content="Confidential salary data",
        acl=DocumentACL(
            allowed_users=[],
            allowed_groups=["group_managers"],
            classification_level=ClassificationLevel.CONFIDENTIAL,
        ),
    )
    retrieval_leak = evaluator.calculate_permission_leak(
        answer="I do not have sufficient information.",
        forbidden_terms=[],
        retrieved_chunks=[confidential_chunk],
        principal=test_principal_alice,
    )
    assert retrieval_leak is True

    # 3. Clean compliant retrieval
    clean_chunk = DocumentChunk(
        id="chunk-pub-1",
        doc_id="hr-leave-policy-2026",
        chunk_index=1,
        content="25 days PTO",
        acl=DocumentACL(
            allowed_users=[],
            allowed_groups=["group_engineering"],
            classification_level=ClassificationLevel.INTERNAL,
        ),
    )
    clean = evaluator.calculate_permission_leak(
        answer="Employees receive 25 days PTO.",
        forbidden_terms=["$175,000"],
        retrieved_chunks=[clean_chunk],
        principal=test_principal_alice,
    )
    assert clean is False


def test_conflict_and_abstention_accuracy(evaluator: RagasMetricsEvaluator) -> None:
    # Conflict accuracy
    answer_with_notice = "**Notice on Document Versions**: Policy 2024 is deprecated. Meal per diem is $125 approved."
    assert (
        evaluator.calculate_conflict_accuracy(
            answer_with_notice, ["notice"], expected_conflict=True
        )
        == 1.0
    )

    # Abstention accuracy
    refusal_answer = "I do not have sufficient information in the authorized enterprise documents."
    assert evaluator.calculate_abstention_accuracy(refusal_answer, expected_refusal=True) == 1.0
    assert (
        evaluator.calculate_abstention_accuracy(
            "Here is the secret recipe: butter and sugar", expected_refusal=True
        )
        == 0.0
    )


def test_golden_dataset_loading() -> None:
    dataset = load_golden_dataset()
    assert len(dataset) >= 10

    # Verify categories exist
    factual_cases = dataset.by_category(DatasetCategory.FACTUAL)
    assert len(factual_cases) >= 1

    permission_cases = dataset.by_category(DatasetCategory.PERMISSION_ISOLATION)
    assert len(permission_cases) >= 1

    # Verify principal conversion
    first_tc = dataset.test_cases[0]
    principal = first_tc.to_user_principal()
    assert principal.user_id == first_tc.user_id
    assert principal.clearance == first_tc.user_clearance
