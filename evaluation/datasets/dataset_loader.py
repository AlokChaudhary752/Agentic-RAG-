"""Golden Dataset loader and validation models for Enterprise Knowledge Agent evaluation."""

import json
import sys
from enum import StrEnum
from pathlib import Path

# Ensure root and backend directories are in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pydantic import BaseModel, Field

from app.domain.models import ClassificationLevel, UserPrincipal


class DatasetCategory(StrEnum):
    """Categorical classification of evaluation test cases."""

    FACTUAL = "factual"
    MULTI_HOP = "multi_hop"
    CONFLICT_RESOLUTION = "conflict_resolution"
    PERMISSION_ISOLATION = "permission_isolation"
    UNANSWERABLE = "unanswerable"
    PROMPT_INJECTION = "prompt_injection"
    MULTILINGUAL = "multilingual"


class GoldenTestCase(BaseModel):
    """Single verified test case within the golden evaluation suite."""

    id: str = Field(..., description="Unique test case identifier")
    query: str = Field(..., description="Natural language user question or prompt")
    category: DatasetCategory = Field(..., description="Category for segmented analysis")
    user_id: str = Field(..., description="Caller identity persona (e.g. emp_alice, mgr_bob)")
    user_clearance: ClassificationLevel = Field(
        default=ClassificationLevel.INTERNAL, description="Clearance level of caller"
    )
    user_groups: list[str] = Field(
        default_factory=list, description="Department and functional groups of caller"
    )
    user_email: str = Field(default="", description="Email address of the caller")
    expected_answer_keywords: list[str] = Field(
        default_factory=list, description="Keywords expected in grounded answer"
    )
    forbidden_terms: list[str] = Field(
        default_factory=list, description="Sensitive terms that MUST NOT appear (leak test)"
    )
    expected_doc_ids: list[str] = Field(
        default_factory=list, description="Authoritative document IDs required in context"
    )
    expected_conflict: bool = Field(
        default=False, description="Whether conflict resolution notice is expected"
    )
    expected_refusal: bool = Field(
        default=False, description="Whether the agent must refuse/abstain from answering"
    )

    def to_user_principal(self) -> UserPrincipal:
        """Convert test case user attributes into a runtime UserPrincipal."""
        return UserPrincipal(
            user_id=self.user_id,
            email=self.user_email or f"{self.user_id}@nimbus.com",
            full_name=self.user_id.replace("_", " ").title(),
            roles=["employee"],
            groups=self.user_groups,
            clearance=self.user_clearance,
            tenant_id="tenant-nimbus-default",
        )


class GoldenDataset(BaseModel):
    """Collection of verified golden test cases."""

    test_cases: list[GoldenTestCase] = Field(default_factory=list)

    def by_category(self, category: DatasetCategory) -> list[GoldenTestCase]:
        """Filter test cases by category."""
        return [tc for tc in self.test_cases if tc.category == category]

    def __len__(self) -> int:
        return len(self.test_cases)


def load_golden_dataset(path: str | Path | None = None) -> GoldenDataset:
    """Load and validate the golden test dataset from JSONL or JSON file."""
    dataset_path = Path(__file__).parent / "golden_qa.jsonl" if path is None else Path(path)

    if not dataset_path.exists():
        raise FileNotFoundError(f"Golden dataset file not found at: {dataset_path}")

    test_cases: list[GoldenTestCase] = []

    if dataset_path.suffix == ".jsonl":
        with open(dataset_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    test_cases.append(GoldenTestCase.model_validate(data))
    else:
        with open(dataset_path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                test_cases = [GoldenTestCase.model_validate(item) for item in data]
            elif isinstance(data, dict) and "test_cases" in data:
                test_cases = [GoldenTestCase.model_validate(item) for item in data["test_cases"]]

    return GoldenDataset(test_cases=test_cases)
