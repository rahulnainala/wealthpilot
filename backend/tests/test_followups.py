"""normalize_followups: coerce the fine-tuned model's messy FOLLOW-UPS trailer.

The wealthpilot LoRA emits the trailer inconsistently — literal placeholder,
mid-line marker, run-on questions, or placeholder-only. All must reduce to one
clean `FOLLOW-UPS: a | b | c` line (or none), with no scaffold leaking through.
"""

from app.services.ai.providers import normalize_followups

_LEAKS = ("q1 | q2", "three short question", "naturally ask", "ask next")


def _no_leak(text: str) -> bool:
    low = text.lower()
    return not any(p in low for p in _LEAKS) and "\n---" not in text


def test_placeholder_over_lines_under_dashes():
    raw = (
        "ONGC is 18.49% of the portfolio.\n\n"
        "FOLLOW-UPS: q1 | q2 | q3 — three short questions the owner would naturally ask next.\n"
        "---\n"
        "What specific risks does ONGC pose?\n"
        "How can I address the concentration issues?\n"
        "Should I revisit insurance coverage?"
    )
    out = normalize_followups(raw)
    assert _no_leak(out)
    assert out.count("FOLLOW-UPS:") == 1
    assert "What specific risks does ONGC pose?" in out
    assert out.startswith("ONGC is 18.49% of the portfolio.")


def test_marker_midline_with_runon_questions():
    raw = (
        "NMDC at Rs2,548 with P&L -Rs83. "
        "FOLLOW-UPS: q1 | q2 | q3 — three short questions the owner would naturally ask next.\n"
        "NMDC value and impact if it reaches +10%. "
        "What are the trends for NMDC? How does it affect overall risk?"
    )
    out = normalize_followups(raw)
    assert _no_leak(out)
    assert "What are the trends for NMDC?" in out
    assert "How does it affect overall risk?" in out
    # The statement fragment before the first '?' is dropped, not kept as a "question".
    assert "reaches +10%" not in out.split("FOLLOW-UPS:")[1]


def test_labelled_questions_over_lines():
    # The stored dataset shape: real questions each prefixed with a "q2:"/"q3:" label.
    raw = (
        "REIT distributions are part return-of-capital.\n\n"
        "FOLLOW-UPS:\n"
        "q1: How does return of capital affect long-term capital gains?\n"
        "q2 | Are there tax exemptions for senior citizens on REIT distributions?\n"
        "q3: Should I hold REITs in a taxable or tax-advantaged account?"
    )
    out = normalize_followups(raw)
    assert _no_leak(out)
    trailer = out.split("FOLLOW-UPS:")[1]
    assert "q1:" not in trailer and "q2 " not in trailer and "q3:" not in trailer
    assert "How does return of capital affect long-term capital gains?" in out


def test_quarter_reference_is_not_stripped():
    # A legit uppercase "Q4" quarter reference must survive (only lowercase q<n> labels go).
    raw = "Earnings look strong.\n\nFOLLOW-UPS: How did Q4 revenue compare to Q3?"
    out = normalize_followups(raw)
    assert "Q4 revenue" in out


def test_placeholder_only_drops_trailer_entirely():
    raw = (
        "NMDC's risk contribution is Rs-83. "
        "FOLLOW-UPS: q1 | q2 | q3 — three short questions the owner would naturally ask next."
    )
    out = normalize_followups(raw)
    assert _no_leak(out)
    assert "FOLLOW-UPS:" not in out
    assert out == "NMDC's risk contribution is Rs-83."


def test_already_clean_is_idempotent():
    raw = (
        "My VaR is 3.2%.\n\n"
        "FOLLOW-UPS: Why did it rise? | Which holding drives it? | Should I hedge?"
    )
    assert normalize_followups(raw) == raw


def test_no_trailer_unchanged():
    assert normalize_followups("Just a plain answer.") == "Just a plain answer."


def test_caps_at_three_followups():
    raw = (
        "Body.\n\nFOLLOW-UPS: A really? | B really? | C really? | D really? | E really?"
    )
    out = normalize_followups(raw)
    assert out.split("FOLLOW-UPS:")[1].count("|") == 2  # exactly three items
