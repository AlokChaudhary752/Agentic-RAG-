"""Evaluation and Regression Gate runner for CI/CD and local verification."""

import argparse
import sys
from pathlib import Path

# Add project root to path for direct invocation
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.benchmark_runner import BenchmarkRunner  # noqa: E402
from evaluation.datasets.dataset_loader import load_golden_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run RAGAS evaluation harness and CI regression gates."
    )
    parser.add_argument(
        "--gate-check",
        action="store_true",
        help="Enforce regression gates and exit with non-zero status if thresholds are breached",
    )
    parser.add_argument(
        "--min-faithfulness",
        type=float,
        default=0.85,
        help="Minimum required mean faithfulness score (default: 0.85)",
    )
    parser.add_argument(
        "--min-context-precision",
        type=float,
        default=0.70,
        help="Minimum required mean context precision score (default: 0.70)",
    )
    parser.add_argument(
        "--min-answer-relevance",
        type=float,
        default=0.65,
        help="Minimum required mean answer relevance score (default: 0.65)",
    )
    parser.add_argument(
        "--max-permission-leak-rate",
        type=float,
        default=0.0,
        help="Maximum permitted permission leak rate in percent (default: 0.0)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to evaluation dataset JSONL/JSON (default: evaluation/datasets/golden_qa.jsonl)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="evaluation/benchmark_results.json",
        help="Destination path for benchmark output JSON",
    )
    parser.add_argument(
        "--report-md",
        type=str,
        default="docs/benchmark_report.md",
        help="Destination path for benchmark report Markdown",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("🚀 Running Enterprise Knowledge Agent Benchmarking & Evaluation Suite")
    print("=" * 70)

    dataset = load_golden_dataset(args.dataset)
    print(f"Loaded {len(dataset)} verified test cases from golden evaluation dataset.\n")

    runner = BenchmarkRunner(dataset=dataset)
    report = runner.run_benchmark()

    # Persist artifacts
    runner.write_report_artifacts(
        report=report,
        output_json_path=args.output_json,
        report_md_path=args.report_md,
    )

    ag = report.agent_summary
    bl = report.baseline_summary

    print("=" * 70)
    print("📊 BENCHMARK COMPARISON SUMMARY")
    print("=" * 70)
    print(f"{'Metric':<32} | {'Naive Baseline':<16} | {'Enterprise Agent':<16} | {'Advantage'}")
    print("-" * 75)
    print(
        f"{'Faithfulness':<32} | {bl.mean_faithfulness:<16.4f} | {ag.mean_faithfulness:<16.4f} | +{(ag.mean_faithfulness - bl.mean_faithfulness) * 100:.1f}%"
    )
    print(
        f"{'Answer Relevance':<32} | {bl.mean_answer_relevance:<16.4f} | {ag.mean_answer_relevance:<16.4f} | +{(ag.mean_answer_relevance - bl.mean_answer_relevance) * 100:.1f}%"
    )
    print(
        f"{'Context Precision':<32} | {bl.mean_context_precision:<16.4f} | {ag.mean_context_precision:<16.4f} | +{(ag.mean_context_precision - bl.mean_context_precision) * 100:.1f}%"
    )
    print(
        f"{'Context Recall':<32} | {bl.mean_context_recall:<16.4f} | {ag.mean_context_recall:<16.4f} | +{(ag.mean_context_recall - bl.mean_context_recall) * 100:.1f}%"
    )
    print(
        f"{'Permission Leak Rate':<32} | {bl.permission_leak_rate_percent:<15.1f}% | {ag.permission_leak_rate_percent:<15.1f}% | Zero Leak"
    )
    print(
        f"{'Conflict Resolution Accuracy':<32} | {bl.conflict_resolution_accuracy_percent:<15.1f}% | {ag.conflict_resolution_accuracy_percent:<15.1f}% | +{(ag.conflict_resolution_accuracy_percent - bl.conflict_resolution_accuracy_percent):.1f}%"
    )
    print(
        f"{'Abstention Accuracy':<32} | {bl.abstention_accuracy_percent:<15.1f}% | {ag.abstention_accuracy_percent:<15.1f}% | +{(ag.abstention_accuracy_percent - bl.abstention_accuracy_percent):.1f}%"
    )
    print("-" * 75)
    print(f"Hypothesis Proven: {'✅ YES' if report.hypothesis_proven else '❌ NO'}")
    print(f"Artifacts saved to: {args.output_json} and {args.report_md}\n")

    if args.gate_check:
        print("=" * 70)
        print("🛡️ REGRESSION GATE VERIFICATION")
        print("=" * 70)
        failed_gates: list[str] = []

        if ag.mean_faithfulness < args.min_faithfulness:
            failed_gates.append(
                f"Faithfulness {ag.mean_faithfulness:.4f} < threshold {args.min_faithfulness}"
            )
        else:
            print(f"✅ Faithfulness Gate PASSED ({ag.mean_faithfulness:.4f} >= {args.min_faithfulness})")

        if ag.mean_context_precision < args.min_context_precision:
            failed_gates.append(
                f"Context Precision {ag.mean_context_precision:.4f} < threshold {args.min_context_precision}"
            )
        else:
            print(
                f"✅ Context Precision Gate PASSED ({ag.mean_context_precision:.4f} >= {args.min_context_precision})"
            )

        if ag.mean_answer_relevance < args.min_answer_relevance:
            failed_gates.append(
                f"Answer Relevance {ag.mean_answer_relevance:.4f} < threshold {args.min_answer_relevance}"
            )
        else:
            print(
                f"✅ Answer Relevance Gate PASSED ({ag.mean_answer_relevance:.4f} >= {args.min_answer_relevance})"
            )

        if ag.permission_leak_rate_percent > args.max_permission_leak_rate:
            failed_gates.append(
                f"Permission Leak Rate {ag.permission_leak_rate_percent}% > allowed {args.max_permission_leak_rate}%"
            )
        else:
            print(
                f"✅ Zero Permission Leak Gate PASSED ({ag.permission_leak_rate_percent}% <= {args.max_permission_leak_rate}%)"
            )

        if failed_gates:
            print("\n❌ REGRESSION GATE FAILURE DETECTED:")
            for g in failed_gates:
                print(f"   - {g}")
            return 1
        else:
            print("\n🎉 ALL CI REGRESSION GATES PASSED SUCCESSFULLY!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
