#!/usr/bin/env python3
"""Build refs/shop.db and refs/schema.sql for the sql-queries suite.

Deterministic: the same seed produces the same rows, so every reference
query in the task files has a fixed answer. Re-run after editing the data
generator; commit both outputs. Stdlib only.

The data carries the suite's house conventions on purpose: two test
accounts with real-looking orders, product categories in mixed case, an
order status ladder where only some statuses count as revenue, and
customers who never ordered.
"""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

REFS = Path(__file__).resolve().parent / "refs"
SEED = 11

SCHEMA = """\
CREATE TABLE customers (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  email      TEXT NOT NULL,
  country    TEXT NOT NULL,
  signed_up  TEXT NOT NULL          -- ISO date, YYYY-MM-DD
);

CREATE TABLE products (
  id               INTEGER PRIMARY KEY,
  name             TEXT NOT NULL,
  category         TEXT NOT NULL,
  unit_price_cents INTEGER NOT NULL
);

CREATE TABLE orders (
  id           INTEGER PRIMARY KEY,
  customer_id  INTEGER NOT NULL REFERENCES customers(id),
  placed_at    TEXT NOT NULL,        -- ISO timestamp, YYYY-MM-DD HH:MM:SS
  status       TEXT NOT NULL         -- placed | paid | shipped | delivered | cancelled | refunded
);

CREATE TABLE order_items (
  order_id    INTEGER NOT NULL REFERENCES orders(id),
  product_id  INTEGER NOT NULL REFERENCES products(id),
  quantity    INTEGER NOT NULL,
  PRIMARY KEY (order_id, product_id)
);
"""

CUSTOMERS = [
    ("Alice Martin", "alice@martin.example", "DE", "2024-11-03"),
    ("Bruno Costa", "bruno.costa@mail.example", "BR", "2024-12-15"),
    ("Chen Wei", "chen.wei@mail.example", "SG", "2025-01-08"),
    ("Dana Levi", "dana@levi.example", "DE", "2025-01-21"),
    ("Emeka Obi", "emeka.obi@mail.example", "NG", "2025-02-02"),
    ("Farah Haddad", "farah@haddad.example", "SG", "2025-02-19"),
    ("Grace Park", "grace.park@mail.example", "BR", "2025-03-05"),
    ("Hugo Silva", "hugo@silva.example", "BR", "2025-03-27"),
    ("Ines Weber", "ines.weber@mail.example", "DE", "2025-04-10"),
    ("Jonas Berg", "jonas@berg.example", "DE", "2025-05-14"),
    ("Kavya Rao", "kavya.rao@mail.example", "SG", "2025-05-30"),
    ("Liam Doyle", "liam@doyle.example", "NG", "2025-06-11"),
    # Test accounts: real-looking rows that every report must exclude.
    ("Test Buyer", "test.buyer@example.com", "SG", "2025-01-02"),
    ("QA Bot", "qa.bot@example.com", "DE", "2025-02-10"),
]
NEVER_ORDER = {"Dana Levi", "Jonas Berg", "Liam Doyle", "QA Bot"}

PRODUCTS = [
    ("Notebook A5", "Stationery", 799), ("Fountain Pen", "stationery", 4500),
    ("Desk Lamp", "Office", 3999), ("Monitor Arm", "office", 12900),
    ("Ceramic Mug", "kitchen", 1250), ("Pour-over Kettle", "Kitchen", 6800),
    ("Sticky Notes", "stationery", 349), ("Cable Tray", "office", 2499),
    ("Desk Pad", "Office", 1899),
]
# Cable Tray only ever sits in orders that do not count as revenue; Desk
# Pad only in a test account's orders. Both are "never sold".
ONLY_UNPAID = "Cable Tray"
ONLY_TEST = "Desk Pad"

N_ORDERS = 60
STATUSES = (["placed"] * 2 + ["paid"] * 3 + ["shipped"] * 2 + ["delivered"] * 3
            + ["cancelled"] * 2 + ["refunded"] * 1)
REVENUE_STATUSES = {"paid", "shipped", "delivered"}

# Fixed orders that make the date-window and test-account probes bite:
# (customer, placed_at, status, [(product, quantity), ...])
PLANTED = [
    ("Alice Martin", "2025-03-31 18:30:00", "delivered", [("Notebook A5", 2)]),
    ("Bruno Costa", "2025-01-31 21:15:00", "paid", [("Ceramic Mug", 1)]),
    ("Test Buyer", "2025-01-12 09:00:00", "delivered", [("Desk Pad", 1), ("Desk Lamp", 1)]),
]


def build(refs: Path = REFS) -> Path:
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "schema.sql").write_text(SCHEMA, encoding="utf-8")
    db_path = refs / "shop.db"
    if db_path.exists():
        db_path.unlink()

    rng = random.Random(SEED)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO customers(name, email, country, signed_up) VALUES (?, ?, ?, ?)",
                    CUSTOMERS)
    con.executemany("INSERT INTO products(name, category, unit_price_cents) VALUES (?, ?, ?)",
                    PRODUCTS)

    customer_ids = {name: i + 1 for i, (name, *_) in enumerate(CUSTOMERS)}
    product_ids = {name: i + 1 for i, (name, *_) in enumerate(PRODUCTS)}
    ordering = [customer_ids[c[0]] for c in CUSTOMERS if c[0] not in NEVER_ORDER]
    test_ids = {customer_ids[c[0]] for c in CUSTOMERS if c[1].endswith("@example.com")}
    start = datetime(2025, 1, 1)
    orders, items = [], []
    for order_id in range(1, N_ORDERS + 1):
        placed = start + timedelta(minutes=rng.randrange(0, 181 * 24 * 60))
        status = rng.choice(STATUSES)
        customer = rng.choice(ordering)
        orders.append((order_id, customer, placed.strftime("%Y-%m-%d %H:%M:%S"), status))
        allowed = [pid for name, pid in product_ids.items()
                   if not (name == ONLY_UNPAID and status in REVENUE_STATUSES)
                   and not (name == ONLY_TEST and customer not in test_ids)]
        for product_id in rng.sample(allowed, rng.randint(1, 3)):
            items.append((order_id, product_id, rng.randint(1, 4)))
    for offset, (customer, placed_at, status, lines) in enumerate(PLANTED, start=1):
        order_id = N_ORDERS + offset
        orders.append((order_id, customer_ids[customer], placed_at, status))
        items.extend((order_id, product_ids[name], qty) for name, qty in lines)
    con.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", orders)
    con.executemany("INSERT INTO order_items VALUES (?, ?, ?)", items)
    con.commit()
    con.close()
    return db_path


if __name__ == "__main__":
    print(build())
