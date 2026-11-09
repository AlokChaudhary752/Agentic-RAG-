"""Seed database with users, groups, and run initial corpus ingestion."""

import asyncio
import sys
from pathlib import Path

# Ensure root and backend directories are in sys.path for direct invocation
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.repositories.user_repo import UserRepository
from app.db.session import get_session_context, init_db
from app.ingestion.connectors.local_folder import LocalFolderConnector
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.qdrant_client import QdrantService
from scripts.generate_corpus import generate_corpus

SEEDED_GROUPS = [
    ("group_engineering", "Engineering", "Software, Systems, and Data Engineering"),
    ("group_managers", "People Managers", "Team leads and engineering managers"),
    ("group_hr", "Human Resources", "People operations, talent, and benefits"),
    ("group_finance", "Finance & Accounting", "FP&A, payroll, treasury, and procurement"),
    ("group_legal", "Legal & Compliance", "Corporate legal, IP, contracts, and privacy"),
    ("group_sales", "Sales & Marketing", "Revenue generation and account executives"),
    ("group_it", "Information Technology", "IT infrastructure, support, and endpoint security"),
    ("group_security", "Security & Red Team", "Information security and threat intelligence"),
    ("group_executives", "Executive Committee", "C-Suite officers and board members"),
]

SEEDED_USERS = [
    {
        "id": "emp_alice",
        "email": "alice@nimbus.com",
        "full_name": "Alice Smith",
        "hashed_password": "pbkdf2:sha256:fakehash_alice",
        "role": "employee",
        "clearance": "INTERNAL",
        "groups": ["group_engineering"],
    },
    {
        "id": "mgr_bob",
        "email": "bob@nimbus.com",
        "full_name": "Bob Jones",
        "hashed_password": "pbkdf2:sha256:fakehash_bob",
        "role": "manager",
        "clearance": "CONFIDENTIAL",
        "groups": ["group_engineering", "group_managers"],
    },
    {
        "id": "hr_carol",
        "email": "carol@nimbus.com",
        "full_name": "Carol White",
        "hashed_password": "pbkdf2:sha256:fakehash_carol",
        "role": "hr_admin",
        "clearance": "CONFIDENTIAL",
        "groups": ["group_hr"],
    },
    {
        "id": "fin_david",
        "email": "david@nimbus.com",
        "full_name": "David Brown",
        "hashed_password": "pbkdf2:sha256:fakehash_david",
        "role": "finance",
        "clearance": "CONFIDENTIAL",
        "groups": ["group_finance"],
    },
    {
        "id": "eng_elena",
        "email": "elena@nimbus.com",
        "full_name": "Elena Rostova",
        "hashed_password": "pbkdf2:sha256:fakehash_elena",
        "role": "staff_engineer",
        "clearance": "CONFIDENTIAL",
        "groups": ["group_engineering", "group_security"],
    },
    {
        "id": "exec_frank",
        "email": "frank@nimbus.com",
        "full_name": "Frank Vance",
        "hashed_password": "pbkdf2:sha256:fakehash_frank",
        "role": "executive",
        "clearance": "RESTRICTED",
        "groups": ["group_executives", "group_managers", "group_engineering"],
    },
]


async def seed() -> None:
    print("1. Generating synthetic corpus...")
    total_docs = generate_corpus()

    print("2. Initializing database schema...")
    await init_db()

    print("3. Seeding groups and users...")
    async with get_session_context() as session:
        user_repo = UserRepository(session)
        for gid, name, desc in SEEDED_GROUPS:
            await user_repo.upsert_group(gid, name, desc)

        for u in SEEDED_USERS:
            await user_repo.upsert_user(
                user_id=u["id"],
                email=u["email"],
                full_name=u["full_name"],
                hashed_password=u["hashed_password"],
                role=u["role"],
                clearance=u["clearance"],
                group_ids=u["groups"],
            )

    print("4. Indexing corpus into Qdrant & PostgreSQL via IngestionPipeline...")
    qdrant = QdrantService()
    qdrant.init_collection()

    async with get_session_context() as session:
        pipeline = IngestionPipeline(session, qdrant_service=qdrant)
        connector = LocalFolderConnector("data/sample_corpus")
        sync_result = await pipeline.run_sync(connector)
        print(f"Ingestion Sync Result: {sync_result}")

    print(f"Successfully seeded {len(SEEDED_USERS)} users and indexed {total_docs} documents.")


if __name__ == "__main__":
    asyncio.run(seed())

