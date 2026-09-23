from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.security_patterns import (
    SecurityFinding,
    detect_misuse,
    detect_pii,
    detect_prompt_injection,
    detect_secrets,
    has_excessive_repetition,
    is_off_topic,
    redact_sensitive_text,
)


MAX_QUERY_LENGTH = 4_000
MIN_QUERY_LENGTH = 3

CITATION_PATTERN = re.compile(r"\[(\d+)\]")

FINANCIAL_ADVICE_PATTERN = re.compile(
    r"(?i)\b(?:should i buy|should i sell|invest in|investment advice|"
    r"price target|portfolio allocation|trade this stock|buy shares)\b"
)

LEGAL_OR_COMPLIANCE_ADVICE_PATTERN = re.compile(
    r"(?i)\b(?:legal advice|am i compliant|are we compliant|"
    r"does this comply|guarantee compliance|tell me what to do legally)\b"
)

UNSUPPORTED_CERTAINTY_PATTERN = re.compile(
    r"(?i)\b(?:guaranteed|certainly|definitely|will always|zero risk)\b"
)


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    reason: str | None = None
    user_message: str | None = None
    sanitized_text: str | None = None
    findings: tuple[SecurityFinding, ...] = ()


@dataclass(frozen=True)
class OutputDecision:
    answer: str
    cited_indices: tuple[int, ...]
    blocked: bool = False
    reason: str | None = None


def validate_input(query: str) -> GuardrailDecision:
    normalized = " ".join(query.split())

    if len(normalized) < MIN_QUERY_LENGTH:
        return GuardrailDecision(
            allowed=False,
            reason="query_too_short",
            user_message="Please enter a more specific governance, risk, policy, or compliance question.",
        )

    if len(normalized) > MAX_QUERY_LENGTH:
        return GuardrailDecision(
            allowed=False,
            reason="query_too_long",
            user_message=f"Please keep the question under {MAX_QUERY_LENGTH:,} characters.",
        )

    if has_excessive_repetition(normalized):
        return GuardrailDecision(
            allowed=False,
            reason="repeated_characters",
            user_message="Please rephrase the question without repeated or malformed text.",
        )

    secret_findings = detect_secrets(normalized)
    if secret_findings:
        return GuardrailDecision(
            allowed=False,
            reason="credential_submission",
            user_message=(
                "For your security, do not submit API keys, passwords, access tokens, "
                "or other credentials in a question."
            ),
            findings=tuple(secret_findings),
        )

    pii_findings = detect_pii(normalized)
    if pii_findings:
        return GuardrailDecision(
            allowed=False,
            reason="pii_submission",
            user_message=(
                "For privacy, do not submit personal, account, payment-card, "
                "phone, email, or identity information. Please remove it and try again."
            ),
            findings=tuple(pii_findings),
        )

    injection_findings = detect_prompt_injection(normalized)
    if injection_findings:
        return GuardrailDecision(
            allowed=False,
            reason="prompt_injection",
            user_message=(
                "I can help with questions about the indexed governance and risk "
                "documents, but I cannot reveal system instructions, credentials, "
                "or follow attempts to override safeguards."
            ),
            findings=tuple(injection_findings),
        )

    misuse_findings = detect_misuse(normalized)
    if misuse_findings:
        return GuardrailDecision(
            allowed=False,
            reason="harmful_misuse",
            user_message=(
                "I cannot assist with evading controls, sanctions, compliance "
                "requirements, audits, monitoring, or other safeguards."
            ),
            findings=tuple(misuse_findings),
        )

    if is_off_topic(normalized):
        return GuardrailDecision(
            allowed=False,
            reason="off_topic",
            user_message=(
                "This assistant is limited to questions about the indexed JPMorgan "
                "corporate governance, risk, conduct, and policy documents."
            ),
        )

    return GuardrailDecision(
        allowed=True,
        sanitized_text=normalized,
    )


def validate_output(
    *,
    answer: str,
    max_citation_index: int,
    query: str,
) -> OutputDecision:
    sanitized = redact_sensitive_text(answer).strip()

    secrets = detect_secrets(answer)
    pii = detect_pii(answer)
    if secrets or pii:
        return OutputDecision(
            answer=(
                "I cannot provide that response because it appears to contain "
                "sensitive credentials or personal information."
            ),
            cited_indices=(),
            blocked=True,
            reason="sensitive_output",
        )

    valid_indices: list[int] = []
    for raw_index in CITATION_PATTERN.findall(sanitized):
        index = int(raw_index)
        if 1 <= index <= max_citation_index and index not in valid_indices:
            valid_indices.append(index)

    # Remove invalid citation markers. They are never mapped to a source.
    sanitized = re.sub(
        r"\[(\d+)\]",
        lambda match: match.group(0)
        if 1 <= int(match.group(1)) <= max_citation_index
        else "",
        sanitized,
    )
    sanitized = re.sub(r"\s{2,}", " ", sanitized).strip()

    if max_citation_index > 0 and not valid_indices:
        return OutputDecision(
            answer=(
                "I could not produce a properly cited answer from the retrieved "
                "documents. Please rephrase the question or try a more specific "
                "document-focused request."
            ),
            cited_indices=(),
            blocked=True,
            reason="missing_citations",
        )

    if FINANCIAL_ADVICE_PATTERN.search(query):
        sanitized += (
            "\\n\\nThis is a document-based summary, not personalized investment "
            "advice. Consider a qualified financial professional for advice tailored "
            "to your circumstances."
        )

    if LEGAL_OR_COMPLIANCE_ADVICE_PATTERN.search(query):
        sanitized += (
            "\\n\\nThis is a document-based summary, not legal or compliance advice. "
            "Consult qualified legal, compliance, or risk professionals for a "
            "determination in your specific context."
        )

    if UNSUPPORTED_CERTAINTY_PATTERN.search(sanitized):
        sanitized += (
            "\\n\\nNote: the answer is limited to the retrieved document evidence "
            "and should not be treated as a guarantee or certainty."
        )

    return OutputDecision(
        answer=sanitized,
        cited_indices=tuple(valid_indices),
    )


def safe_insufficient_evidence_answer() -> str:
    return (
        "I could not find sufficient evidence in the indexed documents to answer "
        "that question reliably. Please ask a more specific question or add an "
        "appropriate source document."
    )
