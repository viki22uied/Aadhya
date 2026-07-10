import os
import sqlite3
from pathlib import Path

# Tests set DB_PATH_OVERRIDE so they never touch the live demo database —
# running the test suite against the shared aadhya.db previously corrupted
# the demo user by bumping SQLite's autoincrement past id 1.
DB_PATH = Path(os.environ.get("DB_PATH_OVERRIDE", Path(__file__).parent / "aadhya.db"))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        -- age, risk_appetite, goal, horizon_years are C1's PRD-named direct
        -- inputs (self-declared), not demographic/income proxies — P3 only
        -- bars using income/occupation as a segmentation proxy, not these.
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tax_slab_percent REAL NOT NULL,
            age INTEGER NOT NULL,
            risk_appetite TEXT NOT NULL,
            goal TEXT NOT NULL,
            horizon_years INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS savings_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            balance REAL NOT NULL
        );

        -- D2: goal-based framing. A user-named goal (e.g. "child's
        -- education") that FDs and gold purchases can be tagged with, so
        -- Aadhya can talk about holdings by goal name instead of only by
        -- instrument.
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        -- ladder_proposed/matured_handled support B2 (FD Ladder Autopilot):
        -- proposed = Aadhya has surfaced the re-ladder/sweep proposal for
        -- this matured FD; handled = the user approved it and this FD's
        -- proceeds have been split into a new FD + a debt sweep.
        CREATE TABLE IF NOT EXISTS fixed_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            principal REAL NOT NULL,
            interest_rate_percent REAL NOT NULL,
            start_date TEXT NOT NULL,
            maturity_date TEXT NOT NULL,
            ladder_proposed INTEGER NOT NULL DEFAULT 0,
            matured_handled INTEGER NOT NULL DEFAULT 0,
            goal_id INTEGER REFERENCES goals(id)
        );

        -- A3: Gold ETF micro-SIP, not "digital gold" — see rules.py comment
        -- above GOLD_ETF_PRICE_PER_GRAM_INR for why.
        CREATE TABLE IF NOT EXISTS gold_etf_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            amount_inr REAL NOT NULL,
            price_per_gram_inr REAL NOT NULL,
            units_grams REAL NOT NULL,
            purchased_at TEXT NOT NULL,
            goal_id INTEGER REFERENCES goals(id)
        );

        -- B1: one-tap loan/overdraft against an FD. FD continues untouched;
        -- interest accrues only on the drawn amount.
        CREATE TABLE IF NOT EXISTS fd_loan_draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fixed_deposit_id INTEGER NOT NULL REFERENCES fixed_deposits(id),
            amount_inr REAL NOT NULL,
            interest_rate_min_percent REAL NOT NULL,
            interest_rate_max_percent REAL NOT NULL,
            drawn_at TEXT NOT NULL
        );

        -- Chat sequencing: tracks which steps of the PRD's FD-first trust
        -- sequence (A1 -> A2 -> A3) Aadhya has already proactively shown this
        -- user, so the conversation can enforce the order deterministically
        -- instead of hoping the LLM remembers or chooses to follow it.
        CREATE TABLE IF NOT EXISTS chat_progress (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            fd_shown INTEGER NOT NULL DEFAULT 0,
            post_tax_shown INTEGER NOT NULL DEFAULT 0,
            gold_shown INTEGER NOT NULL DEFAULT 0
        );

        -- C3: downturn presence protocol. A demo-triggered event carrying the
        -- real equity amount before/after a simulated drawdown, so Aadhya's
        -- proactive downturn message always uses rule-computed numbers.
        CREATE TABLE IF NOT EXISTS downturn_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            equity_amount_before REAL NOT NULL,
            equity_amount_after REAL NOT NULL,
            drawdown_percent REAL NOT NULL,
            triggered_at TEXT NOT NULL,
            shown INTEGER NOT NULL DEFAULT 0
        );

        -- B2: the debt/hybrid-fund leg of an approved ladder split. The
        -- other leg is just a new row in fixed_deposits.
        CREATE TABLE IF NOT EXISTS debt_sweeps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            source_fixed_deposit_id INTEGER NOT NULL REFERENCES fixed_deposits(id),
            amount_inr REAL NOT NULL,
            yield_percent REAL NOT NULL,
            swept_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()
