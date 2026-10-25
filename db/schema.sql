CREATE TABLE shops (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE products (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);

CREATE TABLE daily_sales (
  shop_id INT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  day DATE NOT NULL,
  units INT NOT NULL CHECK (units >= 0),
  PRIMARY KEY (shop_id, product_id, day)
);

CREATE TABLE stock_levels (
  shop_id INT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  on_hand INT NOT NULL CHECK (on_hand >= 0),
  lead_time_days INT NOT NULL DEFAULT 5 CHECK (lead_time_days BETWEEN 1 AND 21),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (shop_id, product_id)
);

CREATE TABLE model_runs (
  id SERIAL PRIMARY KEY,
  trained_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  method TEXT NOT NULL,
  series INT NOT NULL,
  mae DOUBLE PRECISION
);

CREATE TABLE forecasts (
  shop_id INT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  day DATE NOT NULL,
  yhat DOUBLE PRECISION NOT NULL,
  sd DOUBLE PRECISION NOT NULL,
  PRIMARY KEY (shop_id, product_id, day)
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  shop_id INT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  qty INT NOT NULL CHECK (qty > 0),
  status TEXT NOT NULL DEFAULT 'approved' CHECK (status IN ('approved', 'cancelled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX orders_lookup ON orders (shop_id, product_id, created_at DESC);
