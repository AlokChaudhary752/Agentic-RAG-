"""PII detection and masking engine with classification-aware policies."""

import re

from app.domain.models import ClassificationLevel


class PIIMasker:
    """Detects and redacts Personally Identifiable Information (PII) based on security classification."""

    def __init__(self) -> None:
        self.email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
        self.phone_pattern = re.compile(
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        )
        self.ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        self.credit_card_pattern = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
        self.salary_pattern = re.compile(
            r"(?:salary|compensation|base pay|ctc)[\s:]+\$?\s*([0-9]{2,3}(?:,[0-9]{3})+|\d{5,7})\b",
            re.IGNORECASE,
        )

    def detect_pii(self, text: str) -> list[str]:
        """Identify which PII categories are present in the provided text."""
        flags: list[str] = []
        if self.email_pattern.search(text):
            flags.append("EMAIL")
        if self.phone_pattern.search(text):
            flags.append("PHONE")
        if self.ssn_pattern.search(text):
            flags.append("SSN")
        if self.credit_card_pattern.search(text):
            flags.append("CREDIT_CARD")
        if self.salary_pattern.search(text):
            flags.append("SALARY")
        return flags

    def mask(self, text: str, classification: ClassificationLevel) -> tuple[str, list[str]]:
        """Apply classification-specific masking rules, returning masked text and detected flags."""
        flags = self.detect_pii(text)
        if not flags:
            return text, []

        masked = text

        # Mandatory redaction across all classification levels
        masked = self.ssn_pattern.sub("[SSN_REDACTED]", masked)
        masked = self.credit_card_pattern.sub("[CARD_REDACTED]", masked)

        if classification == ClassificationLevel.PUBLIC:
            # Public documents must redact all personal emails, phone numbers, and salaries
            masked = self.email_pattern.sub("[EMAIL_REDACTED]", masked)
            masked = self.phone_pattern.sub("[PHONE_REDACTED]", masked)
            masked = self.salary_pattern.sub("Salary: [REDACTED_PUBLIC_VIEW]", masked)

        elif classification == ClassificationLevel.INTERNAL:
            # Internal documents redact personal email domains (e.g. gmail, yahoo) but retain nimbus.com
            def email_repl(match: re.Match[str]) -> str:
                addr = match.group(0)
                if addr.endswith("@nimbus.com") or addr.endswith("@nimbus.internal"):
                    return addr
                return "[EXTERNAL_EMAIL_REDACTED]"

            masked = self.email_pattern.sub(email_repl, masked)
            masked = self.phone_pattern.sub("[PHONE_REDACTED]", masked)

        # CONFIDENTIAL and RESTRICTED retain authorized departmental context while flagging presence
        return masked, flags
