"""Self-checks for the deterministic conversation-driving logic (Part 1) and
the downturn presence protocol (Part 2). None of this hits the LLM — these
are exactly the pieces that must work even if Groq/Ollama is unreachable.
"""
import os
from pathlib import Path

os.environ["DB_PATH_OVERRIDE"] = str(Path(__file__).parent / "test_chat.db")

from datetime import date, timedelta

from db import get_conn, init_db
from rules import (
    compute_allocation,
    trigger_downturn,
    get_pending_downturn,
    NIFTY50_2020_DRAWDOWN_PERCENT,
    get_matured_fds,
    create_goal,
)
from chat import build_greeting, _call_tool, GATED_TOOLS, enforce_brevity, _SENTENCE_SPLIT


def _seed_user_with_equity(conn, risk_appetite="growth", horizon_years=15, gold_purchases=3):
    cur = conn.execute(
        "INSERT INTO users (name, tax_slab_percent, age, risk_appetite, goal, horizon_years) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Test", 20, 35, risk_appetite, "retirement", horizon_years),
    )
    uid = cur.lastrowid
    conn.execute("INSERT INTO savings_accounts (user_id, balance) VALUES (?, ?)", (uid, 100000))
    today = date.today()
    conn.execute(
        "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, 200000, 7.0, (today - timedelta(days=180)).isoformat(), (today + timedelta(days=365)).isoformat()),
    )
    conn.commit()
    for _ in range(gold_purchases):
        conn.execute(
            "INSERT INTO gold_etf_purchases (user_id, amount_inr, price_per_gram_inr, units_grams, purchased_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, 100, 8200, 100 / 8200, date.today().isoformat()),
        )
    conn.commit()
    return uid


def test_build_greeting_fd_first_sequence():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM chat_progress")
    conn.execute("DELETE FROM downturn_events")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _seed_user_with_equity(conn, gold_purchases=0)
    conn.close()

    g1 = build_greeting(uid)
    assert g1["stage"] == "fd_intro"
    assert g1["tool_calls"][0]["name"] == "get_fd_snapshot"

    g2 = build_greeting(uid)
    assert g2["stage"] == "post_tax_intro"

    g3 = build_greeting(uid)
    assert g3["stage"] == "gold_intro"

    g4 = build_greeting(uid)
    assert g4["stage"] == "ready"
    print("ok")
    return uid


def test_gated_tools_blocked_until_sequence_complete():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM chat_progress")
    conn.execute("DELETE FROM downturn_events")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _seed_user_with_equity(conn, gold_purchases=3)
    conn.close()

    # Sequence not shown yet -> gated tools must refuse, not return real data.
    for tool_name in GATED_TOOLS:
        args = {"equity_amount_inr": 1000} if tool_name == "get_risk_scenario" else {}
        result = _call_tool(tool_name, args, uid)
        assert result.get("blocked") is True

    # Walk the sequence to completion.
    build_greeting(uid)  # fd_intro
    build_greeting(uid)  # post_tax_intro
    build_greeting(uid)  # gold_intro

    result = _call_tool("get_allocation", {}, uid)
    assert "blocked" not in result
    assert "allocation" in result
    print("ok")


def test_downturn_takes_priority_and_numbers_match_compute_allocation():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM chat_progress")
    conn.execute("DELETE FROM downturn_events")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _seed_user_with_equity(conn, gold_purchases=3)
    conn.close()

    allocation = compute_allocation(uid)
    equity_before = next(a for a in allocation["allocation"] if a["asset_class"] == "equity")["amount_inr"]
    expected_after = round(equity_before * (1 + NIFTY50_2020_DRAWDOWN_PERCENT / 100), 2)

    event = trigger_downturn(uid)
    assert event["equity_amount_before"] == equity_before
    assert event["equity_amount_after"] == expected_after
    assert event["drawdown_percent"] == NIFTY50_2020_DRAWDOWN_PERCENT

    # Downturn must win even though the FD-first sequence hasn't been shown yet.
    greeting = build_greeting(uid)
    assert greeting["stage"] == "downturn"
    assert isinstance(greeting["reply"], list)
    joined = " ".join(greeting["reply"])
    assert f"{equity_before:,.0f}" in joined
    assert f"{expected_after:,.0f}" in joined

    # Event is consumed — asking again must not repeat the downturn message.
    assert get_pending_downturn(uid) is None
    next_greeting = build_greeting(uid)
    assert next_greeting["stage"] != "downturn"
    print("ok")


def _sentence_count(text: str) -> int:
    return len([s for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()])


def test_enforce_brevity_truncates_long_paragraph():
    # A dense, comma-stacked explainer paragraph — the exact "what is a fixed
    # deposit" failure mode described in the report.
    wall_of_text = (
        "A fixed deposit, or FD, is a financial instrument offered by banks where you "
        "deposit a lump sum of money for a fixed period of time, ranging from a few days "
        "to several years, and in return, the bank pays you a fixed rate of interest, "
        "which is generally higher than a regular savings account, and this interest can "
        "be paid out periodically or at maturity, depending on the type of FD you choose."
    )
    result = enforce_brevity(wall_of_text)
    assert len(result) <= 3  # 2 content sentences + 1 "want more?" offer
    assert result[-1] == "Want me to say more?"
    for sentence in result[:-1]:
        assert sentence.count(",") <= 2, f"sentence still comma-heavy: {sentence}"


def test_enforce_brevity_leaves_short_replies_alone():
    short = "Your FD is worth ₹4,50,000 today. That's up from ₹4,00,000."
    result = enforce_brevity(short)
    assert result == ["Your FD is worth ₹4,50,000 today.", "That's up from ₹4,00,000."]
    assert "Want me to say more?" not in result


def test_deterministic_greetings_are_short():
    """Every proactive (non-LLM) message must itself obey the 2-sentence-per-
    bubble rule — the hard constraint applies to Aadhya's own scripted copy,
    not just LLM output."""
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM chat_progress")
    conn.execute("DELETE FROM downturn_events")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _seed_user_with_equity(conn, gold_purchases=3)
    conn.close()

    trigger_downturn(uid)
    for _ in range(5):  # downturn, fd_intro, post_tax_intro, gold_intro, ready
        greeting = build_greeting(uid)
        for bubble in greeting["reply"]:
            assert _sentence_count(bubble) <= 2, f"bubble too long: {bubble}"
    print("ok")


def test_ladder_proposal_priority_and_shape():
    """Matured-FD ladder proposal must outrank the FD-first onboarding
    sequence (it's an urgent, time-bound event like the downturn alert) but
    must not outrank an active downturn."""
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM chat_progress")
    conn.execute("DELETE FROM downturn_events")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _seed_user_with_equity(conn, gold_purchases=0)
    today = date.today()
    conn.execute(
        "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, 100000, 7.0, (today - timedelta(days=365)).isoformat(), today.isoformat()),
    )
    conn.commit()
    conn.close()

    # Fresh user, nothing shown yet, but a matured FD is waiting -> ladder
    # proposal must come before fd_intro.
    greeting = build_greeting(uid)
    assert greeting["stage"] == "ladder_proposal"
    for bubble in greeting["reply"]:
        assert _sentence_count(bubble) <= 2

    # Not shown again on the next call.
    greeting2 = build_greeting(uid)
    assert greeting2["stage"] != "ladder_proposal"
    print("ok")


def test_downturn_still_beats_ladder_proposal():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM chat_progress")
    conn.execute("DELETE FROM downturn_events")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _seed_user_with_equity(conn, gold_purchases=3)
    today = date.today()
    conn.execute(
        "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, 100000, 7.0, (today - timedelta(days=365)).isoformat(), today.isoformat()),
    )
    conn.commit()
    conn.close()

    trigger_downturn(uid)
    greeting = build_greeting(uid)
    assert greeting["stage"] == "downturn"

    greeting2 = build_greeting(uid)
    assert greeting2["stage"] == "ladder_proposal"
    print("ok")


def test_approve_ladder_via_call_tool_stops_reproposing():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM chat_progress")
    conn.execute("DELETE FROM downturn_events")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _seed_user_with_equity(conn, gold_purchases=0)
    today = date.today()
    cur = conn.execute(
        "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, 100000, 7.0, (today - timedelta(days=365)).isoformat(), today.isoformat()),
    )
    fd_id = cur.lastrowid
    conn.commit()
    conn.close()

    result = _call_tool("approve_ladder", {"fixed_deposit_id": fd_id}, uid)
    assert "blocked" not in result
    assert result["new_fixed_deposit_id"] is not None
    assert get_matured_fds(uid) == []
    print("ok")


def test_get_goals_tool_not_gated_before_sequence_complete():
    """Goals aren't market-linked content — unlike get_allocation/
    get_risk_scenario, get_goals must work even before the FD-first
    sequence finishes."""
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM chat_progress")
    conn.execute("DELETE FROM downturn_events")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _seed_user_with_equity(conn, gold_purchases=0)
    conn.commit()
    conn.close()

    create_goal(uid, "Emergency cushion")
    result = _call_tool("get_goals", {}, uid)
    assert "blocked" not in result
    assert result["goals"][0]["name"] == "Emergency cushion"
    print("ok")


if __name__ == "__main__":
    test_build_greeting_fd_first_sequence()
    test_gated_tools_blocked_until_sequence_complete()
    test_downturn_takes_priority_and_numbers_match_compute_allocation()
    test_enforce_brevity_truncates_long_paragraph()
    test_enforce_brevity_leaves_short_replies_alone()
    test_deterministic_greetings_are_short()
    test_ladder_proposal_priority_and_shape()
    test_downturn_still_beats_ladder_proposal()
    test_approve_ladder_via_call_tool_stops_reproposing()
    test_get_goals_tool_not_gated_before_sequence_complete()
