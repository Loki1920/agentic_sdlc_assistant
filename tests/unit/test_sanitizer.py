"""Unit tests for utils/sanitizer.py — PII redaction."""
from __future__ import annotations

import pytest

from utils.sanitizer import redact_pii


# ── Email ──────────────────────────────────────────────────────────────────────

def test_redact_email_basic():
    result = redact_pii("Contact john.doe@example.com for help.")
    assert "[EMAIL REDACTED]" in result
    assert "john.doe@example.com" not in result


def test_redact_email_multiple():
    result = redact_pii("From: a@x.com, cc: b@y.org")
    assert result.count("[EMAIL REDACTED]") == 2


def test_redact_email_preserves_surrounding_text():
    result = redact_pii("Call support at admin@corp.io today.")
    assert "Call support at" in result
    assert "today." in result


# ── Phone ──────────────────────────────────────────────────────────────────────

def test_redact_phone_international():
    result = redact_pii("Reach us at +1-800-555-1234.")
    assert "[PHONE REDACTED]" in result
    assert "+1-800-555-1234" not in result


def test_redact_phone_domestic():
    result = redact_pii("Call (800) 555-1234 now.")
    assert "[PHONE REDACTED]" in result


# ── Token ──────────────────────────────────────────────────────────────────────

def test_redact_token_long_alphanumeric():
    token = "A" * 40
    result = redact_pii(f"Token: {token}")
    assert "[TOKEN REDACTED]" in result
    assert token not in result


def test_no_redact_short_string():
    """Short strings < 32 chars should NOT be redacted."""
    result = redact_pii("abc123def456")
    assert "[TOKEN REDACTED]" not in result


# ── Edge cases ─────────────────────────────────────────────────────────────────

def test_empty_string_unchanged():
    assert redact_pii("") == ""


def test_none_unchanged():
    assert redact_pii(None) is None


def test_plain_text_unchanged():
    text = "Add rate limiting to the API endpoint."
    assert redact_pii(text) == text


def test_redact_multiple_patterns_in_one_string():
    text = "Contact user@test.com or call +44-20-7946-0958 using token " + "X" * 35
    result = redact_pii(text)
    assert "[EMAIL REDACTED]" in result
    assert "[PHONE REDACTED]" in result
    assert "[TOKEN REDACTED]" in result
    assert "user@test.com" not in result
