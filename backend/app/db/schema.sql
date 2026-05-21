-- Predictions cache (avoids re-running inference on every request)
CREATE TABLE IF NOT EXISTS predictions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    p10         REAL NOT NULL,
    p50         REAL NOT NULL,
    p90         REAL NOT NULL,
    signal      TEXT NOT NULL,
    model_ver   TEXT NOT NULL DEFAULT 'tft_v1',
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(date, ticker)
);

-- Paper trading portfolio history (90+ days, one row per date)
CREATE TABLE IF NOT EXISTS portfolio_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,
    value       REAL NOT NULL
);

-- Current open positions
CREATE TABLE IF NOT EXISTS positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL UNIQUE,
    shares          REAL NOT NULL,
    avg_buy_price   REAL NOT NULL,
    opened_date     TEXT NOT NULL
);

-- Trade log
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    action      TEXT NOT NULL,   -- 'BUY' or 'SELL'
    quantity    REAL NOT NULL,
    price       REAL NOT NULL,
    reason      TEXT NOT NULL
);
