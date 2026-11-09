"""Integration test asserting that Enterprise Agentic RAG outperforms Naive RAG baseline."""

import json
from pathlib import Path

import pytest

from evaluation.benchmark_runner import BenchmarkRunner
from evaluation.datasets.dataset_loader import load_golden_dataset


@pytest.mark.integration
def test_benchmark_runner_proves_agentic_hypothesis(tmp_path: Path) -> None:
    """Validate empirical benchmark comparison and assert agent superiority over baseline."""
    dataset = load_golden_dataset()
    runner = BenchmarkRunner(dataset=dataset)

    report = runner.run_benchmark()

    # 1. Core Hypothesis Verification: Agent strictly beats Naive baseline
    assert report.hypothesis_proven is True, (
        "Agent must outperform Naive Baseline across core metrics"
    )

    # 2. Strict Security Zero Leak Gate
    assert report.agent_summary.permission_leak_rate_percent == 0.0, (
        "Enterprise Agent must have 0.00% permission leak rate"
    )
    assert report.baseline_summary.permission_leak_rate_percent > 0.0, (
        "Naive baseline should fail permission isolation on restricted queries"
    )

    # 3. Grounding & Precision Metrics
    assert report.agent_summary.mean_faithfulness >= 0.85
    assert report.agent_summary.mean_context_precision >= 0.70
    assert report.agent_summary.mean_context_recall >= 0.75
    assert report.agent_summary.mean_answer_relevance >= 0.65

    # 4. Artifact generation validation
    json_path = tmp_path / "test_results.json"
    md_path = tmp_path / "test_report.md"

    runner.write_report_artifacts(
        report=report,
        output_json_path=json_path,
        report_md_path=md_path,
    )

    assert json_path.exists()
    assert md_path.exists()

    with open(json_path, encoding="utf-8") as f:
        saved_data = json.load(f)
        assert saved_data["hypothesis_proven"] is True
        assert saved_data["agent_summary"]["permission_leak_rate_percent"] == 0.0

    report_text = md_path.read_text(encoding="utf-8")
    assert "Benchmark Report" in report_text
    assert "0.00% (Guaranteed)" in report_text
