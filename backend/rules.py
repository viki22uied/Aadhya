"""Deterministic, auditable rule functions. The LLM calls these as tools —
it never computes a financial number inline (PRD hard constraint).
"""
from datetime import date, datetime, timedelta

from db import get_conn

# All-India CPI YoY inflation, May 2026 (Provisional), released 2026-06-12 by
# MoSPI (Ministry of Statistics and Programme Implementation, Govt. of India).
# Source: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2272112
# ponytail: monthly figure, not a live feed — refresh manually against the
# latest MoSPI release before any future demo.
CPI_YOY_MAY_2026 = 0.0393


def _simple_interest_value(principal: float, rate_percent: float, days: float) -> float:
    return principal * (1 + (rate_percent / 100) * (days / 365))


def post_tax_real_yield(principal: float, rate_percent: float, tax_slab_percent: float, days: float) -> dict:
    """A2: post-tax, inflation-adjusted reality for a deposit. FD interest is
    fully taxable at the depositor's own slab rate (TDS is just withholding,
    not the final liability) — R5. Uses CPI_YOY_MAY_2026 as the single
    inflation assumption shared across every "real, inflation-adjusted"
    figure in the app (also used by C2's risk explainer)."""
    years = days / 365
    nominal_interest = principal * (rate_percent / 100) * years
    tax_deducted = nominal_interest * (tax_slab_percent / 100)
    post_tax_interest = nominal_interest - tax_deducted
    post_tax_value = principal + post_tax_interest

    inflation_adjusted_value = post_tax_value / ((1 + CPI_YOY_MAY_2026) ** years) if years > 0 else post_tax_value
    real_gain = inflation_adjusted_value - principal
    real_annual_yield_percent = ((real_gain / principal) / years * 100) if years > 0 else 0.0

    return {
        "nominal_interest": round(nominal_interest, 2),
        "tax_deducted": round(tax_deducted, 2),
        "post_tax_value": round(post_tax_value, 2),
        "inflation_adjusted_value": round(inflation_adjusted_value, 2),
        "real_gain": round(real_gain, 2),
        "real_annual_yield_percent": round(real_annual_yield_percent, 2),
        "cpi_yoy_assumption_percent": round(CPI_YOY_MAY_2026 * 100, 2),
    }


def add_to_savings(user_id: int, amount_inr: float) -> float:
    """Demo control: tops up the savings balance so judges can simulate a
    deposit at any point rather than being stuck with whatever seed.py
    randomly generated. Returns the new balance."""
    conn = get_conn()
    row = conn.execute("SELECT id, balance FROM savings_accounts WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO savings_accounts (user_id, balance) VALUES (?, ?)", (user_id, amount_inr))
        new_balance = amount_inr
    else:
        new_balance = row["balance"] + amount_inr
        conn.execute("UPDATE savings_accounts SET balance = ? WHERE id = ?", (new_balance, row["id"]))
    conn.commit()
    conn.close()
    return round(new_balance, 2)


def fd_snapshot(user_id: int) -> dict:
    """A1: FD-first snapshot. Plain accrual math only — no tax/real-yield
    framing here, that belongs to A2's post-tax reality panel."""
    conn = get_conn()
    user = conn.execute("SELECT tax_slab_percent FROM users WHERE id = ?", (user_id,)).fetchone()
    tax_slab_percent = user["tax_slab_percent"] if user else 0.0
    savings = conn.execute(
        "SELECT balance FROM savings_accounts WHERE user_id = ?", (user_id,)
    ).fetchone()
    fds = conn.execute(
        "SELECT fd.id, fd.principal, fd.interest_rate_percent, fd.start_date, fd.maturity_date, "
        "fd.goal_id, g.name AS goal_name FROM fixed_deposits fd "
        "LEFT JOIN goals g ON g.id = fd.goal_id WHERE fd.user_id = ?",
        (user_id,),
    ).fetchall()
    conn.close()

    today = date.today()
    fd_list = []
    total_principal = 0.0
    total_current_value = 0.0
    total_maturity_value = 0.0

    for fd in fds:
        start = date.fromisoformat(fd["start_date"])
        maturity = date.fromisoformat(fd["maturity_date"])
        days_elapsed = max((today - start).days, 0)
        total_tenure_days = (maturity - start).days

        current_value = _simple_interest_value(fd["principal"], fd["interest_rate_percent"], days_elapsed)
        maturity_value = _simple_interest_value(fd["principal"], fd["interest_rate_percent"], total_tenure_days)
        reality = post_tax_real_yield(
            fd["principal"], fd["interest_rate_percent"], tax_slab_percent, total_tenure_days
        )
        loan_offer = loan_against_fd_offer(current_value, fd["interest_rate_percent"])

        fd_list.append(
            {
                "id": fd["id"],
                "principal": round(fd["principal"], 2),
                "interest_rate_percent": fd["interest_rate_percent"],
                "start_date": fd["start_date"],
                "maturity_date": fd["maturity_date"],
                "current_value": round(current_value, 2),
                "maturity_value": round(maturity_value, 2),
                "post_tax_reality": reality,
                "loan_offer": loan_offer,
                "goal_id": fd["goal_id"],
                "goal_name": fd["goal_name"],
            }
        )
        total_principal += fd["principal"]
        total_current_value += current_value
        total_maturity_value += maturity_value

    return {
        "tax_slab_percent": tax_slab_percent,
        "savings_balance": round(savings["balance"], 2) if savings else 0.0,
        "fixed_deposits": fd_list,
        "total_fd_principal": round(total_principal, 2),
        "total_fd_current_value": round(total_current_value, 2),
        "total_fd_maturity_value": round(total_maturity_value, 2),
    }


# --- A3: Gold micro-SIP ---
#
# PRD originally specified "digital gold" as the entry-ramp product (R6).
# SEBI's public caution of 2025-11-08 states digital gold/e-gold products are
# NOT regulated by SEBI or RBI, fall outside both regulators' jurisdiction,
# and have no formal grievance/redressal mechanism — SEBI explicitly steers
# investors to SEBI-regulated alternatives instead.
# Source: https://www.sebi.gov.in/media-and-notifications/press-releases/nov-2025/caution-to-public-regarding-dealing-in-digital-gold-_97676.html
#
# Re-scoped (user-approved) to Gold ETFs: SEBI-regulated, exchange-traded,
# fractional, continuously purchasable — the only one of the PRD's three
# listed gold wrappers (digital gold / SGB / gold ETF) that keeps the
# ₹10–100/day micro-SIP UX intact. SGBs were considered but rejected for the
# micro-SIP flow specifically because of their 1-gram minimum unit and
# tranche-window (not continuous) purchase — that breaks the "invested every
# day" feedback loop R6's micro-SIP framing depends on.

# Placeholder demo price — no live market-data feed wired up yet, and no
# brokerage/distribution partner has been named (PRD Open Question #3 is
# still open: "SGB/Gold ETF distribution partner — pending IDBI's actual
# brokerage tie-up"). Replace with a real quote from that partner's feed
# before this leaves demo status.
GOLD_ETF_PRICE_PER_GRAM_INR = 8200.0


def buy_gold_etf_round_up(user_id: int, amount_inr: float) -> dict:
    """Records a micro-SIP purchase at the current (placeholder) Gold ETF
    price and returns the updated holding snapshot."""
    units_grams = amount_inr / GOLD_ETF_PRICE_PER_GRAM_INR
    conn = get_conn()
    conn.execute(
        "INSERT INTO gold_etf_purchases (user_id, amount_inr, price_per_gram_inr, units_grams, purchased_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount_inr, GOLD_ETF_PRICE_PER_GRAM_INR, units_grams, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return gold_snapshot(user_id)


def gold_snapshot(user_id: int) -> dict:
    conn = get_conn()
    purchases = conn.execute(
        "SELECT amount_inr, price_per_gram_inr, units_grams, purchased_at "
        "FROM gold_etf_purchases WHERE user_id = ? ORDER BY purchased_at",
        (user_id,),
    ).fetchall()
    conn.close()

    total_invested = sum(p["amount_inr"] for p in purchases)
    total_units_grams = sum(p["units_grams"] for p in purchases)
    current_value = total_units_grams * GOLD_ETF_PRICE_PER_GRAM_INR

    return {
        "product": "Gold ETF (SEBI-regulated) — not digital gold, see SEBI caution 2025-11-08",
        "current_price_per_gram_inr": GOLD_ETF_PRICE_PER_GRAM_INR,
        "total_invested": round(total_invested, 2),
        "total_units_grams": round(total_units_grams, 4),
        "current_value": round(current_value, 2),
        "purchases": [
            {
                "amount_inr": round(p["amount_inr"], 2),
                "price_per_gram_inr": p["price_per_gram_inr"],
                "units_grams": round(p["units_grams"], 4),
                "purchased_at": p["purchased_at"],
            }
            for p in purchases
        ],
    }


# --- B1: Loan/overdraft against FD ---
#
# LTV: 90% — per Policybazaar/BankBazaar aggregator data on IDBI's FDOD
# (overdraft-against-FD) product, not independently confirmed on
# idbi.bank.in; treat as best-available secondary-sourced figure pending
# IDBI's internal rate card.
LTV_PERCENT = 0.90

# Interest spread over the FD's own rate: general market range (RBI FAQ,
# Paisabazaar, BankBazaar — PRD R9), NOT IDBI-specific. IDBI's own FDOD
# schedule of charges lists account fees but not the interest spread — no
# primary or secondary source for IDBI's actual number was found. Illustrative
# only, pending IDBI's confirmed rate card.
SPREAD_OVER_FD_RATE_MIN = 0.01
SPREAD_OVER_FD_RATE_MAX = 0.02


def loan_against_fd_offer(fd_current_value: float, fd_interest_rate_percent: float) -> dict:
    """Max draw-down amount and illustrative interest-rate range for an
    overdraft against this FD. The FD itself is untouched and keeps earning
    interest; the borrower pays interest only on the amount actually drawn."""
    max_loan_amount = fd_current_value * LTV_PERCENT
    return {
        "ltv_percent": round(LTV_PERCENT * 100, 2),
        "max_loan_amount": round(max_loan_amount, 2),
        "interest_rate_min_percent": round(fd_interest_rate_percent + SPREAD_OVER_FD_RATE_MIN * 100, 2),
        "interest_rate_max_percent": round(fd_interest_rate_percent + SPREAD_OVER_FD_RATE_MAX * 100, 2),
        "rate_is_illustrative": True,
    }


def get_loan_offer_for_fd(fixed_deposit_id: int) -> dict:
    """Read-only: fetches a specific FD and computes its loan offer. Used by
    both the draw endpoint and the chat tool-calling layer so there's one
    code path for "what can I borrow against FD X" — never re-derived by an
    LLM."""
    conn = get_conn()
    fd = conn.execute(
        "SELECT principal, interest_rate_percent, start_date FROM fixed_deposits WHERE id = ?",
        (fixed_deposit_id,),
    ).fetchone()
    conn.close()
    if fd is None:
        raise ValueError(f"no fixed deposit with id {fixed_deposit_id}")

    days_elapsed = max((date.today() - date.fromisoformat(fd["start_date"])).days, 0)
    current_value = _simple_interest_value(fd["principal"], fd["interest_rate_percent"], days_elapsed)
    return {
        "fixed_deposit_id": fixed_deposit_id,
        "fd_current_value": round(current_value, 2),
        **loan_against_fd_offer(current_value, fd["interest_rate_percent"]),
    }


def draw_loan_against_fd(fixed_deposit_id: int, amount_inr: float) -> dict:
    """Records a mock loan draw (no real disbursement rails in the demo)."""
    offer = get_loan_offer_for_fd(fixed_deposit_id)

    if amount_inr > offer["max_loan_amount"]:
        raise ValueError(f"amount {amount_inr} exceeds max loan amount {offer['max_loan_amount']}")

    conn = get_conn()

    conn.execute(
        "INSERT INTO fd_loan_draws (fixed_deposit_id, amount_inr, interest_rate_min_percent, "
        "interest_rate_max_percent, drawn_at) VALUES (?, ?, ?, ?, ?)",
        (
            fixed_deposit_id,
            amount_inr,
            offer["interest_rate_min_percent"],
            offer["interest_rate_max_percent"],
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"fixed_deposit_id": fixed_deposit_id, "amount_drawn": round(amount_inr, 2), **offer}


# --- C1: Rule-based allocation engine ---
#
# No return/volatility assumption constants here (deliberate, user-confirmed
# scope decision): C1 allocates the user's *current* rupees across asset
# classes with plain reasoning — it does not project future returns. Return
# assumptions (equity/debt/gold CAGR) belong to C2's rupee-framed risk
# explainer, not here, so this engine never needed a citable return figure.
#
# The percentages below are the engine's own rule-design parameters (a
# product decision), not a claim about market fact — unlike LTV_PERCENT or
# CPI_YOY_MAY_2026 above, they don't need a citation, only user-testing to
# tune. ponytail: hand-picked rule table, revisit once real usage data exists.
#
# Segmentation basis (P3): stage is derived only from the user's own
# behavioral data already in this app (how many gold ETF purchases they've
# made) — never from income or occupation.
GOLD_ENGAGEMENT_NONE = "none"
GOLD_ENGAGEMENT_EARLY = "early"
GOLD_ENGAGEMENT_ESTABLISHED = "established"


def _gold_engagement_stage(purchase_count: int) -> str:
    if purchase_count == 0:
        return GOLD_ENGAGEMENT_NONE
    if purchase_count < 3:
        return GOLD_ENGAGEMENT_EARLY
    return GOLD_ENGAGEMENT_ESTABLISHED


def compute_allocation(user_id: int) -> dict:
    """C1: deterministic allocation across fd_debt / gold / equity, grounded
    in the user's actual existing FDs (A1) and gold ETF holdings (A3) as
    first-class inputs (PRD F-a) — not a generic questionnaire-only split."""
    conn = get_conn()
    user = conn.execute(
        "SELECT age, risk_appetite, goal, horizon_years FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    gold_purchase_count = conn.execute(
        "SELECT COUNT(*) c FROM gold_etf_purchases WHERE user_id = ?", (user_id,)
    ).fetchone()["c"]
    conn.close()

    fd_snap = fd_snapshot(user_id)
    gold_snap = gold_snapshot(user_id)

    total_holdings = fd_snap["savings_balance"] + fd_snap["total_fd_current_value"] + gold_snap["current_value"]
    stage = _gold_engagement_stage(gold_purchase_count)

    # Principle 2 (Section 3): never open a new user with a market-linked
    # (equity) allocation. Equity only enters once gold engagement (the
    # trust-building entry ramp, R6) is established.
    if stage == GOLD_ENGAGEMENT_NONE:
        pct = {"fd_debt": 90, "gold": 10, "equity": 0}
        equity_reason = (
            "I'm keeping equity at 0% for now — you haven't started your gold ETF yet, "
            "and I only suggest equity after some gold activity."
        )
    elif stage == GOLD_ENGAGEMENT_EARLY:
        pct = {"fd_debt": 85, "gold": 15, "equity": 0}
        equity_reason = (
            "I'm keeping equity at 0% — you're still early in gold ETF investing, "
            "so I'm not introducing market-linked equity yet."
        )
    else:
        long_horizon = user["horizon_years"] >= 5
        if user["risk_appetite"] == "conservative":
            pct = {"fd_debt": 70, "gold": 20, "equity": 10}
        elif user["risk_appetite"] == "moderate":
            pct = {"fd_debt": 55, "gold": 20, "equity": 25} if long_horizon else {"fd_debt": 65, "gold": 20, "equity": 15}
        else:  # growth
            pct = {"fd_debt": 45, "gold": 20, "equity": 35} if long_horizon else {"fd_debt": 55, "gold": 20, "equity": 25}
        equity_reason = (
            f"I'm putting {pct['equity']}% into equity because you've built up steady gold ETF "
            f"activity, your risk appetite is '{user['risk_appetite']}', and your goal "
            f"('{user['goal']}') has a {user['horizon_years']}-year horizon."
        )

    amounts = {k: round(total_holdings * v / 100, 2) for k, v in pct.items()}

    return {
        "gold_engagement_stage": stage,
        "total_holdings": round(total_holdings, 2),
        "allocation": [
            {
                "asset_class": "fd_debt",
                "percent": pct["fd_debt"],
                "amount_inr": amounts["fd_debt"],
                "reasoning": (
                    f"I'm keeping {pct['fd_debt']}% ({round(amounts['fd_debt'])} INR) in your existing "
                    "FDs and savings because that's the stable base you already trust."
                ),
            },
            {
                "asset_class": "gold",
                "percent": pct["gold"],
                "amount_inr": amounts["gold"],
                "reasoning": (
                    f"I'm putting {pct['gold']}% ({round(amounts['gold'])} INR) into Gold ETF, building "
                    f"on the {gold_purchase_count} gold purchase(s) you've already made."
                ),
            },
            {
                "asset_class": "equity",
                "percent": pct["equity"],
                "amount_inr": amounts["equity"],
                "reasoning": equity_reason,
                # C2: only shown for nonzero equity exposure — see rupee_risk_scenario().
                "risk_scenario": rupee_risk_scenario(amounts["equity"]) if amounts["equity"] > 0 else None,
            },
        ],
    }


# --- C2: Rupee-framed risk explainer ---
#
# Worst case: Nifty 50 2020 COVID drawdown. Peak 12,362 (14 Jan 2020) to
# trough 7,511 (23 Mar 2020), a -39.2% drawdown, recovering to the pre-COVID
# peak by ~Nov 2020 (~10 months). Cross-corroborated by three independent
# secondary sources (no single NSE-primary page surfaced the exact daily
# close in research, but all three converge tightly):
# https://upstox.com/news/market-news/stocks/markets-in-a-bear-grip-sensex-nifty-50-log-worst-monthly-fall-since-covid-19/article-191090/
# https://moneyvesta.com/nifty-50-drawdowns-and-recoveries/
# https://en.wikipedia.org/wiki/2020_stock_market_crash
NIFTY50_2020_PEAK = 12362
NIFTY50_2020_PEAK_DATE = "2020-01-14"
NIFTY50_2020_TROUGH = 7511
NIFTY50_2020_TROUGH_DATE = "2020-03-23"
NIFTY50_2020_DRAWDOWN_PERCENT = round((NIFTY50_2020_TROUGH - NIFTY50_2020_PEAK) / NIFTY50_2020_PEAK * 100, 2)
NIFTY50_2020_RECOVERY_DATE_APPROX = "2020-11-23"  # ~10 months after the trough

# Best case: post-crash rebound. User-confirmed to use this figure despite
# lower precision than the drawdown above — it is a rounded, qualitative
# "nearly doubled" claim from ONE secondary source, not two dated index
# closes I could subtract. No primary-source (NSE/Yahoo/Investing.com) exact
# closing value for ~23 Mar 2021 surfaced in research. Treat as approximate.
# Source: https://moneyvesta.com/nifty-50-drawdowns-and-recoveries/
NIFTY50_POST_CRASH_REBOUND_PERCENT_APPROX = 100.0
NIFTY50_POST_CRASH_REBOUND_WINDOW = "23 Mar 2020 to ~23 Mar 2021 (approx. 1 year)"


def rupee_risk_scenario(equity_amount_inr: float) -> dict:
    """Shows a specific rupee amount going into equity under the real 2020
    Nifty 50 worst-case drawdown and an approximate post-crash best-case
    rebound — never abstract risk labels."""
    worst_case_value = equity_amount_inr * (1 + NIFTY50_2020_DRAWDOWN_PERCENT / 100)
    best_case_value = equity_amount_inr * (1 + NIFTY50_POST_CRASH_REBOUND_PERCENT_APPROX / 100)

    return {
        "worst_case": {
            "period_label": "2020 COVID drawdown",
            "from_date": NIFTY50_2020_PEAK_DATE,
            "to_date": NIFTY50_2020_TROUGH_DATE,
            "index": "Nifty 50",
            "drawdown_percent": NIFTY50_2020_DRAWDOWN_PERCENT,
            "value_at_trough": round(worst_case_value, 2),
            "recovered_by_date_approx": NIFTY50_2020_RECOVERY_DATE_APPROX,
            "precision": "corroborated by 3 independent secondary sources",
        },
        "best_case": {
            "period_label": "Post-crash rebound",
            "window": NIFTY50_POST_CRASH_REBOUND_WINDOW,
            "index": "Nifty 50",
            "return_percent_approx": NIFTY50_POST_CRASH_REBOUND_PERCENT_APPROX,
            "value_after_rebound_approx": round(best_case_value, 2),
            "precision": "approximate — rounded secondary-source claim, not exact index-to-index calculation",
        },
    }


# --- Chat sequencing state (Part 1: Aadhya drives the conversation) ---
#
# Tracked in the DB, not in conversation history, so the FD-first ordering
# (PRD principle 1) survives across page loads/sessions and doesn't depend on
# the LLM remembering or choosing to follow it.

CHAT_STEPS = ("fd_shown", "post_tax_shown", "gold_shown")


def get_chat_progress(user_id: int) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM chat_progress WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO chat_progress (user_id) VALUES (?)", (user_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM chat_progress WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return {step: bool(row[step]) for step in CHAT_STEPS}


def mark_chat_step_shown(user_id: int, step: str) -> None:
    if step not in CHAT_STEPS:
        raise ValueError(f"unknown chat step {step}")
    get_chat_progress(user_id)  # ensures a row exists
    conn = get_conn()
    conn.execute(f"UPDATE chat_progress SET {step} = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def sequence_complete(user_id: int) -> bool:
    progress = get_chat_progress(user_id)
    return all(progress.values())


def reset_chat_progress(user_id: int) -> None:
    """Demo helper — lets the same seeded user be replayed from a fresh
    conversation state without re-seeding the whole database."""
    conn = get_conn()
    conn.execute("DELETE FROM chat_progress WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM downturn_events WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# --- C3: Downturn presence protocol ---
#
# Reuses the exact same 2020 Nifty 50 drawdown figure already cited in C2
# (NIFTY50_2020_DRAWDOWN_PERCENT, -39.24%) so the numbers stay consistent
# everywhere they appear, per the user's requirement.


def trigger_downturn(user_id: int) -> dict:
    """Demo control: simulates the user's current equity allocation dropping
    by the real 2020 Nifty 50 drawdown. Records an unshown event so the next
    chat interaction leads with it, unprompted."""
    allocation = compute_allocation(user_id)
    equity = next(a for a in allocation["allocation"] if a["asset_class"] == "equity")
    equity_before = equity["amount_inr"]
    equity_after = round(equity_before * (1 + NIFTY50_2020_DRAWDOWN_PERCENT / 100), 2)

    conn = get_conn()
    conn.execute(
        "INSERT INTO downturn_events (user_id, equity_amount_before, equity_amount_after, "
        "drawdown_percent, triggered_at, shown) VALUES (?, ?, ?, ?, ?, 0)",
        (user_id, equity_before, equity_after, NIFTY50_2020_DRAWDOWN_PERCENT, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {
        "equity_amount_before": equity_before,
        "equity_amount_after": equity_after,
        "drawdown_percent": NIFTY50_2020_DRAWDOWN_PERCENT,
    }


def get_pending_downturn(user_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM downturn_events WHERE user_id = ? AND shown = 0 ORDER BY triggered_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "equity_amount_before": row["equity_amount_before"],
        "equity_amount_after": row["equity_amount_after"],
        "drawdown_percent": row["drawdown_percent"],
    }


def mark_downturn_shown(event_id: int) -> None:
    conn = get_conn()
    conn.execute("UPDATE downturn_events SET shown = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()


# --- B2: FD Ladder Autopilot ---
#
# Debt/hybrid-instrument yield: India's 10-Year G-Sec yield, ~6.76-6.84% as
# of 9-23 Jul 2026, tracked via RBI/CCIL benchmark data — the standard proxy
# for debt-fund expected returns, and a current yield (not a long-run CAGR),
# which fits a short-tenure sweep. User-confirmed to use this figure.
# Source: https://rbi.org.in/Scripts/bs_viewcontent.aspx?Id=1956
# ponytail: point-in-time yield, not a live feed — refresh manually, same as
# CPI_YOY_MAY_2026 above.
DEBT_INSTRUMENT_YIELD_PERCENT = 6.8

# Split between "re-ladder into a new FD" and "sweep into debt/hybrid" — this
# is the engine's own rule-design choice (like C1's allocation percentages),
# not a market fact, so it doesn't need a citation, only user-testing to
# tune later. ponytail: hand-picked 60/40 split, revisit with real usage data.
LADDER_PERCENT = 60
SWEEP_PERCENT = 40


def get_matured_fds(user_id: int) -> list[dict]:
    """FDs at/past maturity that haven't had a ladder proposal shown yet."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, principal, interest_rate_percent, start_date, maturity_date, ladder_proposed "
        "FROM fixed_deposits WHERE user_id = ? AND matured_handled = 0",
        (user_id,),
    ).fetchall()
    conn.close()
    today = date.today()
    return [dict(r) for r in rows if date.fromisoformat(r["maturity_date"]) <= today]


def propose_fd_ladder(fixed_deposit_id: int) -> dict:
    """Read-only: computes the re-ladder/sweep split for one matured FD."""
    conn = get_conn()
    fd = conn.execute(
        "SELECT principal, interest_rate_percent, start_date, maturity_date FROM fixed_deposits WHERE id = ?",
        (fixed_deposit_id,),
    ).fetchone()
    conn.close()
    if fd is None:
        raise ValueError(f"no fixed deposit with id {fixed_deposit_id}")

    start = date.fromisoformat(fd["start_date"])
    maturity = date.fromisoformat(fd["maturity_date"])
    tenure_days = (maturity - start).days
    matured_amount = _simple_interest_value(fd["principal"], fd["interest_rate_percent"], tenure_days)

    ladder_amount = round(matured_amount * LADDER_PERCENT / 100, 2)
    sweep_amount = round(matured_amount * SWEEP_PERCENT / 100, 2)

    return {
        "fixed_deposit_id": fixed_deposit_id,
        "matured_amount": round(matured_amount, 2),
        "ladder_percent": LADDER_PERCENT,
        "ladder_amount": ladder_amount,
        "ladder_rate_percent": fd["interest_rate_percent"],
        "ladder_projected_1yr_value": round(_simple_interest_value(ladder_amount, fd["interest_rate_percent"], 365), 2),
        "sweep_percent": SWEEP_PERCENT,
        "sweep_amount": sweep_amount,
        "sweep_yield_percent": DEBT_INSTRUMENT_YIELD_PERCENT,
        "sweep_projected_1yr_value": round(sweep_amount * (1 + DEBT_INSTRUMENT_YIELD_PERCENT / 100), 2),
    }


def mark_ladder_proposed(fixed_deposit_id: int) -> None:
    conn = get_conn()
    conn.execute("UPDATE fixed_deposits SET ladder_proposed = 1 WHERE id = ?", (fixed_deposit_id,))
    conn.commit()
    conn.close()


def approve_fd_ladder(user_id: int, fixed_deposit_id: int) -> dict:
    """Executes the proposal: creates a new FD for the laddered portion,
    records a debt sweep for the rest, and marks the matured FD handled so
    it's never proposed again."""
    proposal = propose_fd_ladder(fixed_deposit_id)
    today = date.today()

    conn = get_conn()
    fd = conn.execute("SELECT interest_rate_percent FROM fixed_deposits WHERE id = ?", (fixed_deposit_id,)).fetchone()
    conn.execute(
        "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            user_id,
            proposal["ladder_amount"],
            fd["interest_rate_percent"],
            today.isoformat(),
            date(today.year + 1, today.month, today.day).isoformat(),
        ),
    )
    new_fd_id = conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]

    conn.execute(
        "INSERT INTO debt_sweeps (user_id, source_fixed_deposit_id, amount_inr, yield_percent, swept_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, fixed_deposit_id, proposal["sweep_amount"], DEBT_INSTRUMENT_YIELD_PERCENT, today.isoformat()),
    )
    conn.execute("UPDATE fixed_deposits SET matured_handled = 1 WHERE id = ?", (fixed_deposit_id,))
    conn.commit()
    conn.close()

    return {"new_fixed_deposit_id": new_fd_id, **proposal}


# --- C4: Joint/Family View ---
#
# Plain-text summaries (WhatsApp-friendly), built from the exact same rule
# functions used everywhere else — no new numbers computed here, just
# formatting for a third party (spouse/parent) reading it secondhand.
# Written in third person about "your family member" since it's meant to be
# forwarded, not read by the account holder themselves.


def build_allocation_share_text(user_id: int) -> str:
    allocation = compute_allocation(user_id)
    lines = [
        "Aadhya (bank advisor) suggested this split for our savings:",
        "",
    ]
    for a in allocation["allocation"]:
        label = {"fd_debt": "FDs & Savings", "gold": "Gold ETF", "equity": "Equity"}[a["asset_class"]]
        lines.append(f"- {label}: {a['percent']}% (₹{a['amount_inr']:,.0f})")
    lines.append("")
    lines.append(f"Total: ₹{allocation['total_holdings']:,.0f}")
    return "\n".join(lines)


def build_loan_offer_share_text(fixed_deposit_id: int) -> str:
    offer = get_loan_offer_for_fd(fixed_deposit_id)
    return (
        "Aadhya (bank advisor) says we can borrow against one of our FDs:\n\n"
        f"- Up to ₹{offer['max_loan_amount']:,.0f}\n"
        f"- Est. rate: {offer['interest_rate_min_percent']}%-{offer['interest_rate_max_percent']}%\n"
        "- The FD keeps earning interest the whole time"
    )


def build_gold_share_text(user_id: int) -> str:
    gold = gold_snapshot(user_id)
    return (
        "Our Gold ETF savings so far:\n\n"
        f"- Invested: ₹{gold['total_invested']:,.0f}\n"
        f"- Current value: ₹{gold['current_value']:,.0f} ({gold['total_units_grams']}g)"
    )


# --- D1: Transparent Milestones ---
#
# Thresholds are the engine's own rule-design choice (like C1's allocation
# percentages, B2's ladder split) — not a market fact, so no citation needed.
# Tracks gold ETF activity specifically since that's the recurring habit this
# product is trying to build (R6) — not FDs/loans, which are one-off actions.
GOLD_MILESTONE_THRESHOLDS_INR = [100, 500, 1000, 5000, 10000]


def get_gold_milestones(user_id: int) -> dict:
    """Honest, visible tracker — no fake urgency, no dark patterns. Streak is
    literally 'consecutive calendar days with a gold purchase', nothing more;
    the disclosure text in the API response states exactly what is and isn't
    being measured, per the PRD's R10 transparency requirement."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT purchased_at FROM gold_etf_purchases WHERE user_id = ? ORDER BY purchased_at", (user_id,)
    ).fetchall()
    conn.close()

    purchase_dates = sorted({date.fromisoformat(r["purchased_at"][:10]) for r in rows})

    longest_streak = 0
    current_run = 0
    previous_day = None
    for day in purchase_dates:
        if previous_day is not None and (day - previous_day).days == 1:
            current_run += 1
        else:
            current_run = 1
        longest_streak = max(longest_streak, current_run)
        previous_day = day

    today = date.today()
    if purchase_dates and purchase_dates[-1] in (today, today - timedelta(days=1)):
        current_streak = current_run
    else:
        current_streak = 0

    total_invested = gold_snapshot(user_id)["total_invested"]
    milestones = [
        {"amount_inr": t, "reached": total_invested >= t} for t in GOLD_MILESTONE_THRESHOLDS_INR
    ]

    return {
        "current_streak_days": current_streak,
        "longest_streak_days": longest_streak,
        "total_purchases": len(purchase_dates),
        "total_invested": round(total_invested, 2),
        "milestones": milestones,
        "how_this_works": (
            "The streak counts consecutive calendar days you've added to your gold savings. "
            "Milestones are just invested-amount thresholds you've crossed. Neither is linked "
            "to any bank offer, deadline, or reward — it's only tracking what you've actually done."
        ),
    }


# --- D2: Goal-based framing ---
#
# Goals are just user-named labels that existing FDs/gold purchases can be
# tagged with — no new financial figures, just a different lens on numbers
# already computed elsewhere (fd_snapshot, gold_snapshot).


def create_goal(user_id: int, name: str) -> dict:
    conn = get_conn()
    created_at = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO goals (user_id, name, created_at) VALUES (?, ?, ?)", (user_id, name, created_at)
    )
    goal_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": goal_id, "name": name, "created_at": created_at}


def list_goals(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, created_at FROM goals WHERE user_id = ? ORDER BY created_at", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def assign_fd_to_goal(fixed_deposit_id: int, goal_id: int) -> None:
    conn = get_conn()
    fd = conn.execute("SELECT id FROM fixed_deposits WHERE id = ?", (fixed_deposit_id,)).fetchone()
    if fd is None:
        conn.close()
        raise ValueError(f"no fixed deposit with id {fixed_deposit_id}")
    conn.execute("UPDATE fixed_deposits SET goal_id = ? WHERE id = ?", (goal_id, fixed_deposit_id))
    conn.commit()
    conn.close()


def assign_gold_to_goal(user_id: int, goal_id: int) -> None:
    """Tags the user's whole gold holding to one goal — gold is an
    aggregate of many small purchases, so per-purchase tagging isn't a
    meaningful unit here; the goal follows the holding, not each ₹10 top-up."""
    conn = get_conn()
    conn.execute("UPDATE gold_etf_purchases SET goal_id = ? WHERE user_id = ?", (goal_id, user_id))
    conn.commit()
    conn.close()


def get_goal_progress(user_id: int) -> list[dict]:
    """Real current-value progress per goal, reusing the exact same accrual
    math as fd_snapshot/gold_snapshot — not a separate calculation."""
    goals = list_goals(user_id)
    conn = get_conn()
    today = date.today()
    result = []
    for goal in goals:
        fds = conn.execute(
            "SELECT principal, interest_rate_percent, start_date FROM fixed_deposits WHERE goal_id = ?",
            (goal["id"],),
        ).fetchall()
        fd_value = sum(
            _simple_interest_value(fd["principal"], fd["interest_rate_percent"], max((today - date.fromisoformat(fd["start_date"])).days, 0))
            for fd in fds
        )
        gold_grams = conn.execute(
            "SELECT COALESCE(SUM(units_grams), 0) g FROM gold_etf_purchases WHERE goal_id = ?", (goal["id"],)
        ).fetchone()["g"]
        gold_value = gold_grams * GOLD_ETF_PRICE_PER_GRAM_INR
        result.append(
            {
                "id": goal["id"],
                "name": goal["name"],
                "fd_value": round(fd_value, 2),
                "gold_value": round(gold_value, 2),
                "total_value": round(fd_value + gold_value, 2),
            }
        )
    conn.close()
    return result
