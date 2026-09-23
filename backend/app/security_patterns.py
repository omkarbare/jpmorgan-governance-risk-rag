from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SecurityFinding:
    category: str
    message: str
    start: int | None = None
    end: int | None = None


# Do not make these patterns overly broad: false positives are especially
# frustrating for a policy/governance research tool.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "groq_api_key",
        re.compile(r"\bgsk_[A-Za-z0-9_\-]{16,}\b"),
    ),
    (
        "openai_api_key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{16,}\b"),
    ),
    (
        "generic_api_token",
        re.compile(
            r"(?i)\b(?:api[_ -]?key|access[_ -]?token|secret[_ -]?key|password)"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9_\-/.+=]{12,}"
        ),
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-/.+=]{16,}\b"),
    ),
]

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "social_security_number",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
    (
        "email_address",
        re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
        ),
    ),
    (
        "phone_number",
        re.compile(
            r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?"
            r"(?:\(?\d{2,4}\)?[\s.-]?)\d{3,4}[\s.-]?\d{4}(?!\d)"
        ),
    ),
    (
        "payment_card",
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    ),
    (
        "bank_account_like_number",
        re.compile(r"(?i)\b(?:account(?:\s+number)?|routing(?:\s+number)?)\s*[:#-]?\s*\d{6,17}\b"),
    ),
]

INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "instruction_override",
        re.compile(
            r"(?i)\b(?:ignore|disregard|override|forget|bypass)\b"
            r".{0,100}\b(?:previous|prior|above|system|developer|instructions?|rules?|policy)\b"
        ),
    ),
    (
        "prompt_extraction",
        re.compile(
            r"(?i)\b(?:reveal|show|print|dump|extract|repeat|display)\b"
            r".{0,90}\b(?:system\s+prompt|developer\s+prompt|hidden\s+prompt|instructions?)\b"
        ),
    ),
    (
        "role_hijack",
        re.compile(
            r"(?i)\b(?:act\s+as|pretend\s+to\s+be|you\s+are\s+now|jailbreak|dan\s+mode)\b"
        ),
    ),
    (
        "tool_or_data_exfiltration",
        re.compile(
            r"(?i)\b(?:read|open|print|return|exfiltrate|upload)\b"
            r".{0,100}\b(?:\.env|environment\s+variables?|api\s*keys?|secrets?|passwords?|tokens?)\b"
        ),
    ),
    (
        "retrieval_instruction_attack",
        re.compile(
            r"(?i)\b(?:treat|follow|execute)\b.{0,100}"
            r"\b(?:retrieved|source|document|pdf|chunk).{0,100}\b(?:instructions?|commands?)\b"
        ),
    ),
]

MISUSE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "control_evasion",
        re.compile(
            r"(?i)\b(?:evade|bypass|circumvent|defeat|avoid)\b"
            r".{0,100}\b(?:control|compliance|audit|monitoring|sanctions|kyc|aml|policy)\b"
        ),
    ),
    (
        "fraud_or_deception",
        re.compile(
            r"(?i)\b(?:commit|hide|facilitate|plan)\b.{0,100}"
            r"\b(?:fraud|bribery|money\s+laundering|insider\s+trading)\b"
        ),
    ),
    (
        "sanctions_evasion",
        re.compile(r"(?i)\b(?:evade|bypass|circumvent)\b.{0,80}\bsanctions?\b"),
    ),
]

OFF_TOPIC_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)^\s*(?:write|generate|create)\s+(?:a\s+)?(?:poem|song|story|joke)\b"),
    re.compile(r"(?i)^\s*(?:solve|calculate)\s+.*(?:homework|math\s+problem)\b"),
    re.compile(r"(?i)^\s*(?:who\s+won|sports|recipe|movie|celebrity)\b"),
]

REPEATED_CHARACTER_PATTERN = re.compile(r"(.)\1{24,}")


def _find(
    text: str,
    patterns: Iterable[tuple[str, re.Pattern[str]]],
    *,
    label: str,
) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for category, pattern in patterns:
        for match in pattern.finditer(text):
            findings.append(
                SecurityFinding(
                    category=category,
                    message=f"{label}: {category.replace('_', ' ')}",
                    start=match.start(),
                    end=match.end(),
                )
            )
    return findings


def detect_secrets(text: str) -> list[SecurityFinding]:
    return _find(text, SECRET_PATTERNS, label="Sensitive credential detected")


def detect_pii(text: str) -> list[SecurityFinding]:
    return _find(text, PII_PATTERNS, label="Sensitive personal data detected")


def detect_prompt_injection(text: str) -> list[SecurityFinding]:
    return _find(text, INJECTION_PATTERNS, label="Prompt-injection pattern detected")


def detect_misuse(text: str) -> list[SecurityFinding]:
    return _find(text, MISUSE_PATTERNS, label="Potentially harmful request detected")


def is_off_topic(text: str) -> bool:
    return any(pattern.search(text) for pattern in OFF_TOPIC_PATTERNS)


def has_excessive_repetition(text: str) -> bool:
    return bool(REPEATED_CHARACTER_PATTERN.search(text))


def redact_sensitive_text(text: str) -> str:
    redacted = text

    for _, pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)

    for category, pattern in PII_PATTERNS:
        redacted = pattern.sub(f"[REDACTED_{category.upper()}]", redacted)

    return redacted
