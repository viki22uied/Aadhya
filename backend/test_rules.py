import os
from pathlib import Path

os.environ["DB_PATH_OVERRIDE"] = str(Path(__file__).parent / "test_rules.db")

from datetime import date, timedelta

from db import get_conn, init_db
from rules import (
    fd_snapshot,
    post_tax_real_yield,
    CPI_YOY_MAY_2026,
    buy_gold_etf_round_up,
    GOLD_ETF_PRICE_PER_GRAM_INR,
    loan_against_fd_offer,
    draw_loan_against_fd,
    LTV_PERCENT,
    compute_allocation,
    GOLD_ENGAGEMENT_NONE,
    GOLD_ENGAGEMENT_ESTABLISHED,
    rupee_risk_scenario,
    NIFTY50_2020_DRAWDOWN_PERCENT,
    NIFTY50_POST_CRASH_REBOUND_PERCENT_APPROX,
    get_matured_fds,
    propose_fd_ladder,
    approve_fd_ladder,
    LADDER_PERCENT,
    SWEEP_PERCENT,
    DEBT_INSTRUMENT_YIELD_PERCENT,
    build_allocation_share_text,
    build_loan_offer_share_text,
    build_gold_share_text,
    gold_snapshot,
    get_gold_milestones,
    GOLD_MILESTONE_THRESHOLDS_INR,
    create_goal,
    list_goals,
    assign_fd_to_goal,
    assign_gold_to_goal,
    get_goal_progress,
)


def _insert_test_user(conn, risk_appetite="moderate", horizon_years=10):
    cur = conn.execute(
        "INSERT INTO users (name, tax_slab_percent, age, risk_appetite, goal, horizon_years) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Test", 20, 35, risk_appetite, "retirement", horizon_years),
    )
    return cur.lastrowid


def test_fd_snapshot():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn)
    conn.execute("INSERT INTO savings_accounts (user_id, balance) VALUES (?, ?)", (uid, 10000))
    today = date.today()
    start = today - timedelta(days=365)
    maturity = today + timedelta(days=365)
    conn.execute(
        "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, 100000, 7.0, start.isoformat(), maturity.isoformat()),
    )
    conn.commit()
    conn.close()

    snap = fd_snapshot(uid)
    assert snap["savings_balance"] == 10000.0
    assert len(snap["fixed_deposits"]) == 1
    fd = snap["fixed_deposits"][0]
    # 1 year elapsed of 2-year tenure at 7% simple interest
    assert fd["current_value"] == 107000.0
    assert fd["maturity_value"] == 114000.0
    assert snap["total_fd_principal"] == 100000.0
    reality = fd["post_tax_reality"]
    # 100000 @ 7% for 2 years = 14000 nominal interest, 20% tax = 2800 tax
    assert reality["nominal_interest"] == 14000.0
    assert reality["tax_deducted"] == 2800.0
    assert reality["post_tax_value"] == 111200.0
    assert reality["cpi_yoy_assumption_percent"] == round(CPI_YOY_MAY_2026 * 100, 2)
    loan_offer = fd["loan_offer"]
    assert loan_offer["max_loan_amount"] == round(107000.0 * LTV_PERCENT, 2)
    assert loan_offer["interest_rate_min_percent"] == 8.0
    assert loan_offer["interest_rate_max_percent"] == 9.0
    print("ok")
    return uid, fd["id"]


def test_post_tax_real_yield_zero_days():
    result = post_tax_real_yield(100000, 7.0, 20, 0)
    assert result["nominal_interest"] == 0.0
    assert result["real_annual_yield_percent"] == 0.0
    print("ok")


def test_gold_etf_round_up():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn)
    conn.commit()
    conn.close()

    snap = buy_gold_etf_round_up(uid, 100)
    assert snap["total_invested"] == 100.0
    assert snap["total_units_grams"] == round(100 / GOLD_ETF_PRICE_PER_GRAM_INR, 4)
    assert len(snap["purchases"]) == 1

    snap = buy_gold_etf_round_up(uid, 50)
    assert snap["total_invested"] == 150.0
    assert len(snap["purchases"]) == 2
    print("ok")


def test_loan_against_fd():
    _uid, fd_id = test_fd_snapshot()

    result = draw_loan_against_fd(fd_id, 10000)
    assert result["amount_drawn"] == 10000.0
    assert result["fixed_deposit_id"] == fd_id

    try:
        draw_loan_against_fd(fd_id, 10_000_000)
        assert False, "should have rejected a draw above the max loan amount"
    except ValueError:
        pass
    print("ok")


def test_compute_allocation_no_gold_engagement():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn, risk_appetite="growth", horizon_years=15)
    conn.execute("INSERT INTO savings_accounts (user_id, balance) VALUES (?, ?)", (uid, 100000))
    conn.commit()
    conn.close()

    result = compute_allocation(uid)
    assert result["gold_engagement_stage"] == GOLD_ENGAGEMENT_NONE
    pct_total = sum(a["percent"] for a in result["allocation"])
    assert pct_total == 100
    equity = next(a for a in result["allocation"] if a["asset_class"] == "equity")
    assert equity["percent"] == 0  # no market-linked allocation before gold ramp starts (principle 2)
    for a in result["allocation"]:
        assert isinstance(a["reasoning"], str) and len(a["reasoning"]) > 0
    print("ok")


def test_compute_allocation_established_gold_engagement():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn, risk_appetite="growth", horizon_years=15)
    conn.commit()
    conn.close()

    for _ in range(3):
        buy_gold_etf_round_up(uid, 100)

    result = compute_allocation(uid)
    assert result["gold_engagement_stage"] == GOLD_ENGAGEMENT_ESTABLISHED
    pct_total = sum(a["percent"] for a in result["allocation"])
    assert pct_total == 100
    equity = next(a for a in result["allocation"] if a["asset_class"] == "equity")
    assert equity["percent"] == 35  # growth + long horizon + established gold engagement
    print("ok")


def test_rupee_risk_scenario():
    result = rupee_risk_scenario(10000)
    # -39.24% drawdown on 10,000 -> known trough value
    expected_worst = round(10000 * (1 + NIFTY50_2020_DRAWDOWN_PERCENT / 100), 2)
    assert result["worst_case"]["value_at_trough"] == expected_worst
    assert result["worst_case"]["drawdown_percent"] == NIFTY50_2020_DRAWDOWN_PERCENT
    expected_best = round(10000 * (1 + NIFTY50_POST_CRASH_REBOUND_PERCENT_APPROX / 100), 2)
    assert result["best_case"]["value_after_rebound_approx"] == expected_best
    assert result["worst_case"]["value_at_trough"] < 10000
    assert result["best_case"]["value_after_rebound_approx"] > 10000
    print("ok")


def test_compute_allocation_attaches_risk_scenario_only_for_equity():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn, risk_appetite="growth", horizon_years=15)
    conn.commit()
    conn.close()

    # stage=none: no equity, no risk_scenario
    result = compute_allocation(uid)
    equity = next(a for a in result["allocation"] if a["asset_class"] == "equity")
    assert equity["percent"] == 0
    assert equity["risk_scenario"] is None

    # established gold engagement -> equity kicks in -> risk_scenario present
    for _ in range(3):
        buy_gold_etf_round_up(uid, 100)
    result = compute_allocation(uid)
    equity = next(a for a in result["allocation"] if a["asset_class"] == "equity")
    assert equity["percent"] > 0
    assert equity["risk_scenario"] is not None
    assert equity["risk_scenario"]["worst_case"]["value_at_trough"] < equity["amount_inr"]
    print("ok")


def _insert_matured_fd(conn, uid, principal=100000, rate=7.0, tenure_days=365):
    today = date.today()
    start = today - timedelta(days=tenure_days)
    cur = conn.execute(
        "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, principal, rate, start.isoformat(), today.isoformat()),
    )
    return cur.lastrowid


def test_get_matured_fds_and_propose_ladder():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM debt_sweeps")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn)
    fd_id = _insert_matured_fd(conn, uid, principal=100000, rate=7.0, tenure_days=365)
    conn.commit()
    conn.close()

    matured = get_matured_fds(uid)
    assert len(matured) == 1
    assert matured[0]["id"] == fd_id

    proposal = propose_fd_ladder(fd_id)
    # 100000 @ 7% for 365 days = 107000 matured amount
    assert proposal["matured_amount"] == 107000.0
    assert proposal["ladder_amount"] == round(107000.0 * LADDER_PERCENT / 100, 2)
    assert proposal["sweep_amount"] == round(107000.0 * SWEEP_PERCENT / 100, 2)
    assert proposal["sweep_yield_percent"] == DEBT_INSTRUMENT_YIELD_PERCENT
    assert proposal["ladder_amount"] + proposal["sweep_amount"] == proposal["matured_amount"]
    print("ok")
    return uid, fd_id


def test_approve_fd_ladder_creates_new_fd_and_sweep_and_stops_reproposing():
    uid, fd_id = test_get_matured_fds_and_propose_ladder()

    result = approve_fd_ladder(uid, fd_id)
    assert result["new_fixed_deposit_id"] is not None

    conn = get_conn()
    new_fd = conn.execute(
        "SELECT principal, interest_rate_percent FROM fixed_deposits WHERE id = ?", (result["new_fixed_deposit_id"],)
    ).fetchone()
    assert new_fd["principal"] == result["ladder_amount"]
    sweep = conn.execute(
        "SELECT amount_inr, yield_percent FROM debt_sweeps WHERE source_fixed_deposit_id = ?", (fd_id,)
    ).fetchone()
    assert sweep["amount_inr"] == result["sweep_amount"]
    assert sweep["yield_percent"] == DEBT_INSTRUMENT_YIELD_PERCENT
    conn.close()

    # Matured FD is now handled — must not show up again.
    assert get_matured_fds(uid) == []
    print("ok")


def test_share_text_contains_real_numbers():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM savings_accounts")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn, risk_appetite="growth", horizon_years=15)
    conn.execute("INSERT INTO savings_accounts (user_id, balance) VALUES (?, ?)", (uid, 50000))
    today = date.today()
    cur = conn.execute(
        "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, 100000, 7.0, (today - timedelta(days=100)).isoformat(), (today + timedelta(days=365)).isoformat()),
    )
    fd_id = cur.lastrowid
    conn.commit()
    conn.close()

    for _ in range(3):
        buy_gold_etf_round_up(uid, 100)

    allocation = compute_allocation(uid)
    alloc_text = build_allocation_share_text(uid)
    for a in allocation["allocation"]:
        assert f"{a['percent']}%" in alloc_text
        assert f"{a['amount_inr']:,.0f}" in alloc_text

    loan_text = build_loan_offer_share_text(fd_id)
    assert "borrow against" in loan_text
    assert "%" in loan_text

    gold = gold_snapshot(uid)
    gold_text = build_gold_share_text(uid)
    assert f"{gold['total_invested']:,.0f}" in gold_text
    assert f"{gold['current_value']:,.0f}" in gold_text
    print("ok")


def _insert_gold_purchase_on(conn, uid, day, amount=50):
    conn.execute(
        "INSERT INTO gold_etf_purchases (user_id, amount_inr, price_per_gram_inr, units_grams, purchased_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, amount, 8200, amount / 8200, day.isoformat()),
    )


def test_gold_milestones_active_streak():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn)
    today = date.today()
    _insert_gold_purchase_on(conn, uid, today, amount=50)
    _insert_gold_purchase_on(conn, uid, today - timedelta(days=1), amount=50)
    _insert_gold_purchase_on(conn, uid, today - timedelta(days=2), amount=50)
    conn.commit()
    conn.close()

    result = get_gold_milestones(uid)
    assert result["current_streak_days"] == 3
    assert result["longest_streak_days"] == 3
    assert result["total_purchases"] == 3
    assert result["total_invested"] == 150.0
    assert result["how_this_works"]  # non-empty disclosure present
    print("ok")


def test_gold_milestones_broken_streak():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn)
    today = date.today()
    _insert_gold_purchase_on(conn, uid, today - timedelta(days=5), amount=50)
    conn.commit()
    conn.close()

    result = get_gold_milestones(uid)
    assert result["current_streak_days"] == 0  # last purchase wasn't today/yesterday
    assert result["longest_streak_days"] == 1
    print("ok")


def test_gold_milestones_thresholds():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn)
    today = date.today()
    _insert_gold_purchase_on(conn, uid, today, amount=150)
    conn.commit()
    conn.close()

    result = get_gold_milestones(uid)
    reached = {m["amount_inr"]: m["reached"] for m in result["milestones"]}
    assert reached[100] is True
    assert reached[500] is False
    assert set(reached.keys()) == set(GOLD_MILESTONE_THRESHOLDS_INR)
    print("ok")


def test_goal_progress_tracks_tagged_fd_and_gold():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM goals")
    conn.execute("DELETE FROM gold_etf_purchases")
    conn.execute("DELETE FROM fixed_deposits")
    conn.execute("DELETE FROM users")
    uid = _insert_test_user(conn)
    today = date.today()
    cur = conn.execute(
        "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, 100000, 7.0, (today - timedelta(days=365)).isoformat(), (today + timedelta(days=365)).isoformat()),
    )
    fd_id = cur.lastrowid
    conn.commit()
    conn.close()

    goal = create_goal(uid, "Emergency cushion")
    assert goal["name"] == "Emergency cushion"
    assert list_goals(uid)[0]["id"] == goal["id"]

    assign_fd_to_goal(fd_id, goal["id"])
    buy_gold_etf_round_up(uid, 100)
    assign_gold_to_goal(uid, goal["id"])

    progress = get_goal_progress(uid)
    assert len(progress) == 1
    g = progress[0]
    # 100000 @ 7% for 1 year = 107000
    assert g["fd_value"] == 107000.0
    assert g["gold_value"] == round((100 / GOLD_ETF_PRICE_PER_GRAM_INR) * GOLD_ETF_PRICE_PER_GRAM_INR, 2)
    assert g["total_value"] == round(g["fd_value"] + g["gold_value"], 2)

    snapshot = fd_snapshot(uid)
    tagged_fd = next(f for f in snapshot["fixed_deposits"] if f["id"] == fd_id)
    assert tagged_fd["goal_name"] == "Emergency cushion"
    print("ok")


def test_assign_fd_to_goal_rejects_unknown_fd():
    try:
        assign_fd_to_goal(999999, 1)
        assert False, "should have rejected an unknown FD id"
    except ValueError:
        pass
    print("ok")


if __name__ == "__main__":
    test_fd_snapshot()
    test_post_tax_real_yield_zero_days()
    test_gold_etf_round_up()
    test_loan_against_fd()
    test_compute_allocation_no_gold_engagement()
    test_compute_allocation_established_gold_engagement()
    test_rupee_risk_scenario()
    test_compute_allocation_attaches_risk_scenario_only_for_equity()
    test_get_matured_fds_and_propose_ladder()
    test_approve_fd_ladder_creates_new_fd_and_sweep_and_stops_reproposing()
    test_share_text_contains_real_numbers()
    test_gold_milestones_active_streak()
    test_gold_milestones_broken_streak()
    test_gold_milestones_thresholds()
    test_goal_progress_tracks_tagged_fd_and_gold()
    test_assign_fd_to_goal_rejects_unknown_fd()
