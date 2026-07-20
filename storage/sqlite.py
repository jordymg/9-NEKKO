"""Storage SQLite — append-only (ARCHITECTURE.md §3 y §6).

El análisis nunca muta datos recolectados; solo INSERT y SELECT.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = "nekko.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS backtest_snapshots (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    question TEXT,
    asset TEXT,
    kind TEXT,
    strike REAL,
    ts INTEGER NOT NULL,
    tte_hours REAL,
    duration_hours REAL,
    implied_mid REAL,
    ref_spot REAL,
    ref_vol REAL,
    model_prob REAL,
    market_volume REAL,
    outcome INTEGER
);
CREATE INDEX IF NOT EXISTS idx_bt_market ON backtest_snapshots (market_id);
CREATE INDEX IF NOT EXISTS idx_bt_run ON backtest_snapshots (run_id);

CREATE TABLE IF NOT EXISTS resolutions (
    market_id TEXT PRIMARY KEY,
    outcome INTEGER,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    market_id TEXT NOT NULL,
    condition_id TEXT,
    token_id TEXT,
    ts INTEGER NOT NULL,
    implied_bid REAL,
    implied_ask REAL,
    implied_mid REAL,
    spread REAL,
    depth_bid REAL,
    depth_ask REAL,
    volume_24h REAL,
    tte_hours REAL,
    ref_spot REAL,
    ref_vol REAL,
    model_prob REAL,
    trigger TEXT NOT NULL DEFAULT 'grid'
);
CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshots (ts);
CREATE INDEX IF NOT EXISTS idx_snap_market ON snapshots (market_id);

-- Única excepción al append-only (ARCHITECTURE §6): ts_end de un gap se
-- completa vía UPDATE al recuperarse. Es metadata de operación del colector,
-- no dato de mercado recolectado; permite consultar "gaps abiertos".
CREATE TABLE IF NOT EXISTS gaps (
    id INTEGER PRIMARY KEY,
    ts_start INTEGER NOT NULL,
    ts_end INTEGER,
    reason TEXT
);
"""

_LIVE_COLS = (
    "market_id", "condition_id", "token_id", "ts", "implied_bid", "implied_ask",
    "implied_mid", "spread", "depth_bid", "depth_ask", "volume_24h", "tte_hours",
    "ref_spot", "ref_vol", "model_prob", "trigger",
)


def insert_live_snapshots(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        f"INSERT INTO snapshots ({', '.join(_LIVE_COLS)}) "
        f"VALUES ({', '.join('?' * len(_LIVE_COLS))})",
        [tuple(r.get(c) for c in _LIVE_COLS) for r in rows],
    )
    conn.commit()


def open_gap(conn: sqlite3.Connection, ts_start: int, reason: str) -> int:
    cur = conn.execute("INSERT INTO gaps (ts_start, reason) VALUES (?, ?)", (ts_start, reason))
    conn.commit()
    return cur.lastrowid


def close_gap(conn: sqlite3.Connection, gap_id: int, ts_end: int) -> None:
    conn.execute("UPDATE gaps SET ts_end = ? WHERE id = ?", (ts_end, gap_id))
    conn.commit()

_SNAPSHOT_COLS = (
    "run_id", "market_id", "question", "asset", "kind", "strike", "ts",
    "tte_hours", "duration_hours", "implied_mid", "ref_spot", "ref_vol",
    "model_prob", "market_volume", "outcome",
)


def connect(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    return conn


def insert_snapshots(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        f"INSERT INTO backtest_snapshots ({', '.join(_SNAPSHOT_COLS)}) "
        f"VALUES ({', '.join('?' * len(_SNAPSHOT_COLS))})",
        [tuple(r.get(c) for c in _SNAPSHOT_COLS) for r in rows],
    )
    conn.commit()


def upsert_resolution(conn: sqlite3.Connection, market_id: str, outcome: int | None,
                      resolved_at: str | None) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO resolutions (market_id, outcome, resolved_at) VALUES (?, ?, ?)",
        (market_id, outcome, resolved_at),
    )
    conn.commit()
