"""Connector for local file system directory scanning and ingestion."""

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.domain.models import ClassificationLevel, DocStatus, DocumentACL, RawDocument
from app.ingestion.connectors.base import BaseConnector


class LocalFolderConnector(BaseConnector):
    """Scans and extracts documents from a local directory supporting Markdown and Text files."""

    def __init__(self, folder_path: str, tenant_id: str = "tenant-nimbus-default") -> None:
        self.folder_path = Path(folder_path)
        self.tenant_id = tenant_id

    @property
    def name(self) -> str:
        return "local_folder"

    async def test_connection(self) -> bool:
        """Check if folder exists and is readable."""
        return self.folder_path.exists() and self.folder_path.is_dir()

    def _parse_frontmatter(self, raw_text: str) -> tuple[dict[str, Any], str]:
        """Extract YAML frontmatter if present, returning metadata and body."""
        frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
        match = frontmatter_pattern.match(raw_text)
        if match:
            yaml_str = match.group(1)
            body = raw_text[match.end() :]
            try:
                meta = yaml.safe_load(yaml_str) or {}
                return meta, body
            except Exception:
                return {}, raw_text
        return {}, raw_text

    def _build_raw_document(self, file_path: Path) -> RawDocument:
        raw_text = file_path.read_text(encoding="utf-8")
        meta, body = self._parse_frontmatter(raw_text)

        stat = file_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        ctime = datetime.fromtimestamp(stat.st_ctime, tz=UTC)

        doc_id = meta.get("id") or f"doc-{file_path.stem}"
        title = meta.get("title") or file_path.stem.replace("_", " ").title()
        author = meta.get("author") or "Nimbus System"
        version = str(meta.get("version", "1.0"))
        language = meta.get("language") or ("hi" if "_hindi" in file_path.stem.lower() else "en")
        owner_group = meta.get("owner_group") or "group_general"

        raw_status = meta.get("doc_status", "approved").lower()
        if raw_status == "deprecated":
            doc_status = DocStatus.DEPRECATED
        elif raw_status == "draft":
            doc_status = DocStatus.DRAFT
        else:
            doc_status = DocStatus.APPROVED

        authority_score = float(meta.get("authority_score", 0.8))
        if doc_status == DocStatus.DEPRECATED:
            authority_score = min(authority_score, 0.3)

        # Build ACL
        acl_data = meta.get("acl", {})
        allowed_users = acl_data.get("allowed_users", [])
        allowed_groups = acl_data.get("allowed_groups", [])
        raw_classification = acl_data.get("classification_level", "INTERNAL")
        classification = ClassificationLevel.from_str(raw_classification)

        acl = DocumentACL(
            allowed_users=allowed_users,
            allowed_groups=allowed_groups,
            classification_level=classification,
        )

        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        return RawDocument(
            id=doc_id,
            source=self.name,
            source_url=f"file://{file_path.resolve()}",
            title=title,
            content=body.strip(),
            author=author,
            created_at=ctime,
            updated_at=mtime,
            version=version,
            doc_status=doc_status,
            authority_score=authority_score,
            language=language,
            owner_group=owner_group,
            acl=acl,
            content_hash=content_hash,
            metadata={"tenant_id": self.tenant_id, "file_path": str(file_path)},
        )

    async def fetch_documents(self) -> list[RawDocument]:
        """Traverse directory and return all parsed documents."""
        if not await self.test_connection():
            return []

        docs: list[RawDocument] = []
        for file_path in self.folder_path.glob("**/*"):
            if file_path.is_file() and file_path.suffix.lower() in (".md", ".txt", ".json"):
                try:
                    docs.append(self._build_raw_document(file_path))
                except Exception:
                    continue
        return docs

    async def get_changes_since(self, checkpoint: datetime | None) -> list[RawDocument]:
        """Return only files updated after checkpoint."""
        all_docs = await self.fetch_documents()
        if not checkpoint:
            return all_docs
        return [d for d in all_docs if d.updated_at > checkpoint]
