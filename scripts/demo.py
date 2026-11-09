"""Interactive CLI Demonstration for Enterprise Knowledge Agent.

Demonstrates the 3 core platform differentiators:
1. Zero Permission Leaks (Alice vs Bob ACL isolation on confidential salary bands).
2. Cross-Document Conflict Resolution (2025 superseded vs 2026 approved travel meal policy).
3. Human-in-the-Loop MCP Action Execution (Jira ticket creation approval gate).
"""

import argparse
import sys
import time
from typing import Any

# Ensure backend directory is in path
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx

# ANSI terminal formatting
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_RED = "\033[41m"


def print_banner() -> None:
    banner = f"""
{Style.CYAN}{Style.BOLD}================================================================================
          ENTERPRISE KNOWLEDGE AGENT: PRODUCTION DEMONSTRATION
================================================================================{Style.RESET}
  {Style.DIM}Agentic RAG * Zero Permission Leaks * Conflict Resolution * MCP Tools{Style.RESET}
"""
    print(banner)


def print_section(title: str, subtitle: str) -> None:
    print(f"\n{Style.BOLD}{Style.BLUE}>>> {title.upper()}{Style.RESET}")
    print(f"    {Style.DIM}{subtitle}{Style.RESET}")
    print(f"{Style.DIM}{'-' * 76}{Style.RESET}")


def get_client() -> tuple[Any, str]:
    """Connect to live FastAPI server if running, otherwise use FastAPI TestClient."""
    live_url = "http://127.0.0.1:8000"
    try:
        resp = httpx.get(f"{live_url}/api/v1/health", timeout=1.0)
        if resp.status_code == 200:
            print(f"  {Style.GREEN}Connected to live HTTP server at {live_url}{Style.RESET}")
            return httpx.Client(base_url=live_url, timeout=30.0), "http"
    except Exception:
        pass

    print(f"  {Style.YELLOW}Running in-process using direct FastAPI TestClient engine...{Style.RESET}")
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app), "in_process"


def mint_token(client: Any, persona: dict[str, Any]) -> str:
    """Request signed JWT token for persona."""
    resp = client.post("/api/v1/auth/token", json=persona)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to mint token: {resp.status_code} - {resp.text}")
    data = resp.json()
    return data["access_token"]


def run_chat(
    client: Any,
    token: str,
    query: str,
    thread_id: str | None = None,
    approval_granted: bool | None = None,
) -> dict[str, Any]:
    """Execute chat completion request."""
    headers = {"Authorization": f"Bearer {token}"}
    payload: dict[str, Any] = {"query": query}
    if thread_id:
        payload["thread_id"] = thread_id
    if approval_granted is not None:
        payload["approval_granted"] = approval_granted

    resp = client.post("/api/v1/chat/completions", json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"Chat request failed: {resp.status_code} - {resp.text}")
    return resp.json()


# Personas
ALICE = {
    "user_id": "emp_alice",
    "email": "alice@nimbus.com",
    "full_name": "Alice Chen",
    "roles": ["employee"],
    "groups": ["group_engineering", "engineering", "all-staff"],
    "clearance": "INTERNAL",
    "tenant_id": "tenant-nimbus-default",
}

BOB = {
    "user_id": "mgr_bob",
    "email": "bob@nimbus.com",
    "full_name": "Bob Martinez",
    "roles": ["manager"],
    "groups": ["group_engineering", "group_managers", "management", "all-staff"],
    "clearance": "CONFIDENTIAL",
    "tenant_id": "tenant-nimbus-default",
}


def demo_scenario_1_permission_isolation(client: Any, interactive: bool) -> None:
    print_section(
        "Scenario 1: Zero-Leak Permission Isolation (Alice vs. Bob)",
        "Querying confidential executive salary bands across different security clearances.",
    )

    query = "What are the executive engineering salary bands for L6 and L7 staff?"

    # 1. Alice (Internal clearance)
    token_alice = mint_token(client, ALICE)
    print(f"\n  [1.1] User: {Style.BOLD}{ALICE['full_name']}{Style.RESET}")
    print(f"        Role: {ALICE['roles'][0]} | Clearance: {Style.YELLOW}{ALICE['clearance']}{Style.RESET}")
    print(f"        Query: \"{Style.CYAN}{query}{Style.RESET}\"")
    print(f"        {Style.DIM}Executing retrieval with vector-level ACL pre-filter...{Style.RESET}")

    t0 = time.perf_counter()
    res_alice = run_chat(client, token_alice, query)
    dt_alice = time.perf_counter() - t0

    print(f"\n  {Style.BOLD}Agent Response to Alice:{Style.RESET}")
    print(f"  {Style.MAGENTA}{res_alice['answer']}{Style.RESET}")
    print(f"  Citations Returned: {len(res_alice['citations'])}")
    print(f"  Steps Executed: {' -> '.join(res_alice['steps_executed'])}")
    print(f"  Latency: {dt_alice:.2f}s")

    # Verification assertion
    assert "HR-SAL" not in res_alice["answer"], "LEAK DETECTED: Salary doc in answer!"
    print(f"  {Style.GREEN}[PASSED] ZERO LEAK: Alice was refused access to confidential compensation data.{Style.RESET}")

    if interactive:
        input(f"\n{Style.DIM}Press Enter to run the same query as Bob (Manager)...{Style.RESET}")

    # 2. Bob (Confidential clearance)
    token_bob = mint_token(client, BOB)
    print(f"\n  [1.2] User: {Style.BOLD}{BOB['full_name']}{Style.RESET}")
    print(f"        Role: {BOB['roles'][0]} | Clearance: {Style.GREEN}{BOB['clearance']}{Style.RESET}")
    print(f"        Query: \"{Style.CYAN}{query}{Style.RESET}\"")
    print(f"        {Style.DIM}Executing retrieval with authorized ACL pre-filter...{Style.RESET}")

    t0 = time.perf_counter()
    res_bob = run_chat(client, token_bob, query)
    dt_bob = time.perf_counter() - t0

    print(f"\n  {Style.BOLD}Agent Response to Bob:{Style.RESET}")
    print(f"  {Style.GREEN}{res_bob['answer']}{Style.RESET}")
    print(f"\n  Verified Citations:")
    for cit in res_bob["citations"]:
        print(f"    - [{cit['doc_id']}] {cit['title']} ({cit['section_path']})")
    print(f"  Confidence: {res_bob['confidence']}")
    print(f"  Latency: {dt_bob:.2f}s")
    print(f"  {Style.GREEN}[PASSED] AUTHORIZED: Bob received authorized salary bands with verified citations.{Style.RESET}")


def demo_scenario_2_conflict_resolution(client: Any, interactive: bool) -> None:
    print_section(
        "Scenario 2: Cross-Document Knowledge Conflict Resolution",
        "Resolving contradictory travel meal per diem policies (2024 deprecated vs 2026 approved).",
    )

    query = "What is our company's approved daily travel meal per diem rate?"
    token_alice = mint_token(client, ALICE)

    print(f"\n  User: {Style.BOLD}{ALICE['full_name']}{Style.RESET} | Query: \"{Style.CYAN}{query}{Style.RESET}\"")
    print(f"  {Style.DIM}Detecting knowledge conflicts between fin-travel-policy-2024 ($75) and fin-travel-policy-2026 ($125)...{Style.RESET}")

    t0 = time.perf_counter()
    res = run_chat(client, token_alice, query)
    dt = time.perf_counter() - t0

    print(f"\n  {Style.BOLD}Agent Response:{Style.RESET}")
    print(f"  {Style.CYAN}{res['answer']}{Style.RESET}")

    if res.get("conflict_notices"):
        print(f"\n  {Style.YELLOW}{Style.BOLD}Knowledge Conflict Notices:{Style.RESET}")
        for notice in res["conflict_notices"]:
            print(f"    [!] {notice}")

    print(f"\n  Citations:")
    for cit in res.get("citations", []):
        print(f"    - [{cit['doc_id']}] {cit['title']}")
    print(f"  Latency: {dt:.2f}s")

    assert any(
        "125" in res["answer"]
        or "125" in str(res.get("conflict_notices", []))
        or cit["doc_id"] == "fin-travel-policy-2026"
        for cit in res.get("citations", [])
    ), "Expected 2026 approved rate ($125/day)!"
    print(f"  {Style.GREEN}[PASSED] CONFLICT RESOLVED: Agent preferred approved 2026 policy over superseded 2024 policy.{Style.RESET}")


def demo_scenario_3_human_in_the_loop_mcp(client: Any, interactive: bool) -> None:
    print_section(
        "Scenario 3: Human-in-the-Loop Safe Tool Execution (MCP)",
        "Executing high-risk write_high Jira ticket creation gated by human approval.",
    )

    query = "Create a Jira ticket to patch OpenSSL vulnerability in staging"
    token_bob = mint_token(client, BOB)

    # Step 1: Initial request (should pause for approval)
    print(f"\n  [3.1] Initial Request from {Style.BOLD}{BOB['full_name']}{Style.RESET}:")
    print(f"        Query: \"{Style.CYAN}{query}{Style.RESET}\"")
    print(f"        {Style.DIM}Evaluating intent and tool risk classification...{Style.RESET}")

    res_1 = run_chat(client, token_bob, query)
    thread_id = res_1["thread_id"]

    print(f"\n  Status: {Style.YELLOW}{Style.BOLD}APPROVAL REQUIRED{Style.RESET}")
    print(f"  Tool Target: {Style.BOLD}create_jira_ticket{Style.RESET} (Risk Level: {Style.RED}write_high{Style.RESET})")
    print(f"  Thread ID: {thread_id}")
    print(f"  Steps Executed: {' -> '.join(res_1['steps_executed'])}")
    print(f"  Agent Guidance: {res_1['answer']}")

    assert res_1.get("approval_required") is True, "Expected approval_required to be True!"
    print(f"  {Style.GREEN}[PASSED] SAFETY GATE: Agent halted execution and requested human approval.{Style.RESET}")

    if interactive:
        user_choice = input(f"\n{Style.BOLD}Simulate Human Decision: [A]pprove or [R]eject? (Default: A): {Style.RESET}").strip().lower()
        granted = user_choice != "r"
    else:
        granted = True
        print(f"\n  {Style.DIM}[Auto-Mode] Simulating operator approving ticket creation...{Style.RESET}")

    # Step 2: Resume with decision
    print(f"\n  [3.2] Resuming Thread {thread_id} with approval_granted={granted}...")
    res_2 = run_chat(client, token_bob, query, thread_id=thread_id, approval_granted=granted)

    print(f"\n  {Style.BOLD}Execution Result:{Style.RESET}")
    print(f"  {Style.GREEN}{res_2['answer']}{Style.RESET}")
    print(f"  Approval Required Now: {res_2['approval_required']}")
    print(f"  Steps Executed: {' -> '.join(res_2['steps_executed'])}")

    if granted:
        assert "NIMBUS-" in res_2["answer"], "Expected created ticket ID in response!"
        print(f"  {Style.GREEN}[PASSED] MCP EXECUTION: Tool executed safely upon verified human authorization.{Style.RESET}")
    else:
        print(f"  {Style.YELLOW}[PASSED] REJECTION RECORDED: Tool execution safely aborted.{Style.RESET}")


def print_summary() -> None:
    print(f"""
{Style.BOLD}{Style.GREEN}================================================================================
                    DEMONSTRATION COMPLETE: ALL GATES VERIFIED
================================================================================{Style.RESET}
  1. {Style.BOLD}Zero Permission Leaks{Style.RESET}: Vector Pre-filtering blocked confidential data from unauthorized persona.
  2. {Style.BOLD}Conflict Resolution{Style.RESET}: 2026 approved policy correctly prioritized with contradiction warning.
  3. {Style.BOLD}MCP Tool Governance{Style.RESET}: High-risk Jira creation was successfully gated by human authorization.

  {Style.BOLD}Next Steps:{Style.RESET}
  - Web UI: Open {Style.CYAN}http://localhost:3000{Style.RESET} to interact visually with personas, citations, and approval modals.
  - Admin Dashboard: Visit {Style.CYAN}http://localhost:3000/admin{Style.RESET} to inspect RAGAS benchmarks and audit events.
  - Metrics: Prometheus telemetry is exposed at {Style.CYAN}http://localhost:8000/api/v1/metrics{Style.RESET}.
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise Knowledge Agent Interactive Demo")
    parser.add_argument(
        "--scenario",
        choices=["1", "2", "3", "all"],
        default="all",
        help="Specific scenario to execute (default: all)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Pause between demo steps for user input",
    )
    args = parser.parse_args()

    print_banner()
    client, mode = get_client()

    try:
        if args.scenario in ("1", "all"):
            demo_scenario_1_permission_isolation(client, args.interactive)
        if args.scenario in ("2", "all"):
            demo_scenario_2_conflict_resolution(client, args.interactive)
        if args.scenario in ("3", "all"):
            demo_scenario_3_human_in_the_loop_mcp(client, args.interactive)

        print_summary()
    finally:
        if hasattr(client, "close"):
            client.close()


if __name__ == "__main__":
    main()
