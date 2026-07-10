"""Synthetic demo data only, per PRD Section 5 (no real customer data).
ponytail: single hardcoded demo user (id=1), stub-auth means no multi-user login yet.
"""
import random
from datetime import date, timedelta

from faker import Faker

from db import get_conn, init_db

fake = Faker("en_IN")


def seed():
    init_db()
    conn = get_conn()
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] > 0:
        conn.close()
        return

    cur = conn.execute(
        "INSERT INTO users (name, tax_slab_percent, age, risk_appetite, goal, horizon_years) VALUES (?, ?, ?, ?, ?, ?)",
        (
            fake.name(),
            random.choice([0, 5, 20, 30]),
            random.randint(25, 60),
            random.choice(["conservative", "moderate", "growth"]),
            random.choice(["emergency fund", "child's education", "retirement", "home purchase"]),
            random.randint(1, 20),
        ),
    )
    user_id = cur.lastrowid

    conn.execute(
        "INSERT INTO savings_accounts (user_id, balance) VALUES (?, ?)",
        (user_id, round(random.uniform(20000, 150000), 2)),
    )

    today = date.today()
    for _ in range(random.randint(2, 3)):
        tenure_days = random.choice([365, 730, 1095, 1825])
        start = today - timedelta(days=random.randint(30, 400))
        conn.execute(
            "INSERT INTO fixed_deposits (user_id, principal, interest_rate_percent, start_date, maturity_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                round(random.uniform(50000, 500000), 2),
                round(random.uniform(6.5, 7.5), 2),
                start.isoformat(),
                (start + timedelta(days=tenure_days)).isoformat(),
            ),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed()
