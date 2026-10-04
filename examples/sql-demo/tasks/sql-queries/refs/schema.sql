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
