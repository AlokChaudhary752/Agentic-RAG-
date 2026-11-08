"""Unit tests for Admin & Evaluation results API endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.unit
async def test_admin_evaluation_results_endpoint(async_client: AsyncClient) -> None:
    """Verify /api/v1/admin/eval/results returns evaluation benchmark metrics."""
    response = await async_client.get("/api/v1/admin/eval/results")
    assert response.status_code == 200
    data = response.json()
    assert "agent_summary" in data or "summary" in data
    assert data.get("hypothesis_proven") is True or data.get("summary", {}).get("hypothesis_proven") is True
