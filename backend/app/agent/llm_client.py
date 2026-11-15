"""LLM client abstraction with LiteLLM integration and deterministic offline fallbacks."""

import os
import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.models import DocumentChunk

# Prevent LiteLLM from attempting network requests for remote model price lists
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

logger = get_logger(__name__)


class VerificationResult(BaseModel):
    """Result of claim-level faithfulness verification."""

    faithfulness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    unsupported_claims: list[str] = Field(default_factory=list)
    is_faithful: bool = Field(default=True)


class LLMService:
    """Provides provider-agnostic model routing (LiteLLM) and reliable offline synthesis fallbacks."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.fast_model = getattr(self.settings, "llm_fast_model", "gemini/gemini-1.5-flash")
        self.strong_model = getattr(
            self.settings,
            "llm_strong_model",
            getattr(self.settings, "llm_primary_model", "gemini/gemini-1.5-pro"),
        )
        self.provider = getattr(self.settings, "llm_provider", "litellm")

    def _get_active_model_and_key(self) -> tuple[str | None, str | None, str | None]:
        """Detect configured LLM provider, active model identifier, API key, and api_base."""
        # 1. Gemini
        gemini_key = getattr(self.settings, "gemini_api_key", None) or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            model = (
                self.strong_model if "gemini" in self.strong_model else "gemini/gemini-1.5-flash"
            )
            return model, gemini_key, None

        # 2. OpenAI
        openai_key = getattr(self.settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY")
        if openai_key:
            return "gpt-4o-mini", openai_key, None

        # 3. Anthropic
        anthropic_key = getattr(self.settings, "anthropic_api_key", None) or os.getenv(
            "ANTHROPIC_API_KEY"
        )
        if anthropic_key:
            return "claude-3-5-haiku-20241022", anthropic_key, None

        # 4. Ollama Local Endpoint
        ollama_url = getattr(self.settings, "llm_local_ollama_url", "http://localhost:11434")
        if self.provider == "ollama" or os.getenv("USE_OLLAMA") == "true":
            ollama_model = os.getenv("OLLAMA_MODEL", "ollama/llama3.2:1b")
            return ollama_model, None, ollama_url

        return None, None, None

    def _call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> str | None:
        """Invoke live LLM via LiteLLM if an active provider is configured."""
        model, api_key, api_base = self._get_active_model_and_key()
        if not model:
            return None

        try:
            import litellm

            litellm.telemetry = False

            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": 15.0,
            }
            if api_key:
                kwargs["api_key"] = api_key
            if api_base:
                kwargs["api_base"] = api_base

            response = litellm.completion(**kwargs)
            if response and response.choices:
                content = response.choices[0].message.content
                if content:
                    logger.info("Successfully synthesized response via LiteLLM", model=model)
                    return str(content).strip()
        except Exception as exc:
            logger.warning("LiteLLM invocation failed, using offline fallback", error=str(exc))

        return None

    def classify_intent(self, query: str) -> str:
        """Classify user intent into factual_lookup, multi_hop, action_request, chit_chat, or out_of_scope."""
        q = query.lower().strip()
        # Chit-chat
        words = re.findall(r"\w+", q)
        if words and words[0] in {"hi", "hello", "hey", "howdy", "greetings"}:
            return "chit_chat"
        if q in {
            "thanks",
            "thank you",
            "good morning",
            "good evening",
            "good afternoon",
            "bye",
            "goodbye",
        }:
            return "chit_chat"

        # Action requests
        action_pattern = re.compile(
            r"\b(create|open|file|log|submit|send|update|check|get|show|track|view)\s+(?:the\s+)?(?:status\s+of\s+)?(?:a\s+|an\s+)?(jira|ticket|bug|issue|email)\b",
            re.IGNORECASE,
        )
        if action_pattern.search(q):
            return "action_request"

        if re.search(r"\b(?:status\s+of\s+ticket|ticket\s+status)\b", q, re.IGNORECASE):
            return "action_request"

        if re.search(r"\b[A-Z]{2,10}-\d+\b", query) and any(
            w in q for w in ["status", "check", "progress"]
        ):
            return "action_request"

        # Multi-hop queries
        comparison_keywords = [
            "compare",
            "difference between",
            "versus",
            " vs ",
            "how does x relate to y",
        ]
        if any(kw in q for kw in comparison_keywords):
            return "multi_hop"

        return "factual_lookup"

    def grade_evidence(self, query: str, chunks: list[DocumentChunk]) -> tuple[str, float]:
        """Evaluate whether candidate chunks contain sufficient factual evidence to answer query."""
        if not chunks:
            return "irrelevant", 0.0

        query_terms = set(re.findall(r"\w+", query.lower()))
        stop_words = {
            "what",
            "is",
            "the",
            "for",
            "and",
            "in",
            "of",
            "to",
            "how",
            "a",
            "an",
            "does",
            "do",
            "are",
            "at",
        }
        meaningful_terms = query_terms - stop_words

        if not meaningful_terms:
            return "relevant", 0.8

        total_matches = 0
        for chunk in chunks:
            content_words = set(re.findall(r"\w+", chunk.content.lower()))
            matches = meaningful_terms.intersection(content_words)
            if matches:
                total_matches += len(matches)

        overlap_ratio = min(1.0, total_matches / (len(meaningful_terms) * len(chunks)))

        if overlap_ratio >= 0.25:
            return "relevant", overlap_ratio
        elif overlap_ratio >= 0.1:
            return "ambiguous", overlap_ratio
        else:
            return "irrelevant", overlap_ratio

    def _extract_meaningful_terms(self, text: str) -> set[str]:
        """Extract searchable keywords excluding standard punctuation and common stop words."""
        stop_words = {
            "what",
            "is",
            "the",
            "for",
            "and",
            "in",
            "of",
            "to",
            "how",
            "a",
            "an",
            "does",
            "do",
            "are",
            "at",
            "our",
            "we",
            "can",
            "all",
            "be",
            "on",
            "by",
            "with",
            "about",
            "this",
            "that",
            "who",
            "where",
            "when",
            "why",
            "from",
            "have",
            "has",
            "had",
        }
        words = set(re.findall(r"\w+", text.lower()))
        return words - stop_words

    def _synthesize_deterministic(
        self,
        query: str,
        chunks: list[DocumentChunk],
        conflict_notices: list[str] | None,
        citations: list[dict[str, Any]],
    ) -> str:
        """High-precision, deterministic synthesis engine for reliable offline enterprise responses."""
        paragraphs: list[str] = []

        # 1. Front-load conflict notices if present
        if conflict_notices:
            for notice in conflict_notices:
                paragraphs.append(f"> ⚠️ **Notice on Document Versions**: {notice}")

        # 2. Synthesize key authoritative facts from top chunks
        for idx, chunk in enumerate(chunks[:3], start=1):
            header = f"Section: {chunk.title}"
            if chunk.section_path:
                header += f" > {chunk.section_path}"

            lines = [line.strip() for line in chunk.content.split("\n") if line.strip()]
            substantive = [line for line in lines if not line.startswith("#")]
            snippet = " ".join(substantive[:4]) if substantive else (lines[0] if lines else "")

            if snippet:
                citation_marker = f"[^{idx}] [{chunk.title}, {chunk.section_path or 'General'}]"
                paragraphs.append(f"{header} > {snippet} {citation_marker}")

        return "\n\n".join(paragraphs)

    def generate_grounded_answer(
        self,
        query: str,
        chunks: list[DocumentChunk],
        conflict_notices: list[str] | None = None,
    ) -> tuple[str, list[dict[str, Any]], float]:
        """Synthesize factual answer strictly grounded in retrieved chunks with citations."""
        query_terms = self._extract_meaningful_terms(query)

        # Filter candidate chunks to only those that contain at least one meaningful query term
        relevant_chunks: list[DocumentChunk] = []
        if query_terms and chunks:
            for c in chunks:
                chunk_words = set(re.findall(r"\w+", c.content.lower()))
                title_words = set(re.findall(r"\w+", c.title.lower()))
                if query_terms.intersection(chunk_words | title_words):
                    relevant_chunks.append(c)
        else:
            relevant_chunks = chunks

        # Honest refusal if no evidence matches query intent
        if not relevant_chunks:
            return (
                "I do not have sufficient information in the authorized enterprise documents "
                "to answer this question.",
                [],
                0.0,
            )

        # Prepare verified citation objects
        citations: list[dict[str, Any]] = []
        for c in relevant_chunks[:3]:
            citations.append(
                {
                    "doc_id": c.doc_id,
                    "title": c.title,
                    "section_path": c.section_path,
                    "source": c.source,
                    "source_url": c.source_url,
                }
            )

        # 1. Attempt live LLM synthesis via LiteLLM
        context_blocks: list[str] = []
        for idx, c in enumerate(relevant_chunks[:3], start=1):
            context_blocks.append(
                f"[Document {idx}]: {c.title} (Section: {c.section_path or 'General'})\n{c.content}"
            )
        context_str = "\n\n".join(context_blocks)

        notices_str = ""
        if conflict_notices:
            notices_str = (
                "Conflict Notices:\n" + "\n".join(f"- {n}" for n in conflict_notices) + "\n\n"
            )

        system_prompt = (
            "You are the Nimbus Enterprise Knowledge Agent. Answer the user query strictly and solely "
            "using the authorized enterprise documents provided in <context>. Follow these rules strictly:\n"
            "1. Grounding: Every single claim must be directly supported by <context>. Do not fabricate or assume.\n"
            "2. Inline Citations: Reference the source document using standard footnote markers [^1], [^2] corresponding "
            "to [Document 1], [Document 2], etc.\n"
            "3. Conflict Notices: If conflict notices are present, mention them clearly at the beginning.\n"
            "4. Refusal: If <context> does not contain sufficient facts to answer the question, respond strictly with: "
            "'I do not have sufficient information in the authorized enterprise documents to answer this question.'\n"
            "5. Tone: Concise, professional, executive-ready markdown with bullet points where appropriate."
        )

        user_prompt = (
            f"{notices_str}<context>\n{context_str}\n</context>\n\nQuestion: {query}\n\nAnswer:"
        )

        llm_response = self._call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=800,
        )

        if llm_response:
            confidence = 0.95 if relevant_chunks[0].authority_score >= 0.8 else 0.80
            return llm_response, citations, confidence

        # 2. Enhanced Deterministic Offline Fallback
        deterministic_answer = self._synthesize_deterministic(
            query=query,
            chunks=relevant_chunks,
            conflict_notices=conflict_notices,
            citations=citations,
        )
        confidence = 0.95 if relevant_chunks[0].authority_score >= 0.8 else 0.75
        return deterministic_answer, citations, confidence

    def verify_faithfulness(
        self,
        answer: str,
        chunks: list[DocumentChunk],
    ) -> VerificationResult:
        """Perform claim-level verification asserting answer claims are supported by context."""
        if not chunks:
            return VerificationResult(
                faithfulness_score=1.0, unsupported_claims=[], is_faithful=True
            )

        combined_context = " ".join(c.content.lower() for c in chunks)
        sentences = [s.strip() for s in re.split(r"[.!?\n]", answer) if len(s.strip()) > 15]

        unsupported: list[str] = []
        supported_count = 0

        for sentence in sentences:
            # Skip conflict notices, citations, and standard refusals
            sentence_clean = re.sub(r"\[\^?\d+\]", "", sentence).strip()
            if (
                "notice on document" in sentence_clean.lower()
                or "sufficient information" in sentence_clean.lower()
                or "enterprise knowledge agent" in sentence_clean.lower()
            ):
                supported_count += 1
                continue

            words = set(re.findall(r"\w+", sentence_clean.lower()))
            stop_words = {
                "the",
                "and",
                "is",
                "in",
                "to",
                "of",
                "a",
                "an",
                "that",
                "it",
                "for",
                "on",
                "with",
            }
            meaningful_words = words - stop_words

            if not meaningful_words:
                supported_count += 1
                continue

            overlap = meaningful_words.intersection(set(re.findall(r"\w+", combined_context)))
            if len(overlap) / len(meaningful_words) >= 0.50:
                supported_count += 1
            else:
                unsupported.append(sentence)

        score = supported_count / max(1, len(sentences))
        return VerificationResult(
            faithfulness_score=round(score, 2),
            unsupported_claims=unsupported,
            is_faithful=len(unsupported) == 0,
        )
