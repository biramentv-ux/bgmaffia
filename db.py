"""db.py — SQLite access layer with forward-only schema migration.

Every connection gets the WAL pragmas. All read-then-write game mutations go
through transact(), which opens BEGIN IMMEDIATE so the write lock is taken
up front and retries on transient busy errors.
"""
import os
import sqlite3
import time
from flask import g

DB_PATH = os.environ.get("GAME_DB", os.path.join(os.path.dirname(__file__), "game.db"))

PRAGMAS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA busy_timeout=5000;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA temp_store=MEMORY;",
)


def _connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    for p in PRAGMAS:
        con.execute(p)
    return con


def get_db():
    if "db" not in g:
        g.db = _connect()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def raw_connection():
    return _connect()


class TxFailed(Exception):
    pass


def transact(con, fn, retries=3):
    for attempt in range(retries):
        try:
            con.execute("BEGIN IMMEDIATE")
            result = fn(con)
            con.commit()
            return result
        except TxFailed:
            con.rollback()
            raise
        except sqlite3.OperationalError as e:
            con.rollback()
            if "locked" in str(e) or "busy" in str(e):
                time.sleep(0.05 * (attempt + 1))
                continue
            raise
    raise sqlite3.OperationalError("database busy after retries")


def guarded(con, sql, params):
    cur = con.execute(sql, params)
    if cur.rowcount != 1:
        raise TxFailed(sql)
    return cur


def init_db(seed=True):
    here = os.path.dirname(__file__)
    con = _connect()
    with open(os.path.join(here, "schema.sql")) as f:
        con.executescript(f.read())
    if seed:
        with open(os.path.join(here, "seed.sql")) as f:
            con.executescript(f.read())
    con.commit()
    con.close()


def migrate_db():
    """Forward-only idempotent migrations. Safe to call on every startup."""
    con = raw_connection()

    def add_col(table, col, typedef):
        try:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError:
            pass

    # New player columns
    add_col("players", "player_class", "TEXT DEFAULT 'enforcer'")
    add_col("players", "vip_tier", "INTEGER DEFAULT 0")
    add_col("players", "vip_until", "TEXT")
    add_col("players", "total_casino_wins", "INTEGER DEFAULT 0")
    add_col("players", "total_earned", "INTEGER DEFAULT 0")

    # New tables
    con.executescript("""
    CREATE TABLE IF NOT EXISTS player_boosts (
      user_id INTEGER, boost_type TEXT, expires_at TEXT,
      PRIMARY KEY (user_id, boost_type)
    );
    CREATE TABLE IF NOT EXISTS gold_transactions (
      id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT,
      gold_delta INTEGER, note TEXT, ts TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS npc_enemies (
      id INTEGER PRIMARY KEY, name TEXT, min_level INTEGER DEFAULT 1,
      health INTEGER, strength INTEGER, reward_min INTEGER, reward_max INTEGER,
      xp_reward INTEGER, loot_item_id INTEGER, loot_chance REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS pve_log (
      id INTEGER PRIMARY KEY, user_id INTEGER, enemy_id INTEGER,
      outcome TEXT, payout INTEGER, xp INTEGER, ts TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS skills (
      id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, descr TEXT,
      category TEXT, sp_cost INTEGER DEFAULT 1, prereq_code TEXT,
      effect_json TEXT
    );
    CREATE TABLE IF NOT EXISTS player_skills (
      user_id INTEGER, skill_code TEXT,
      PRIMARY KEY (user_id, skill_code)
    );
    CREATE TABLE IF NOT EXISTS crypto_coins (
      id INTEGER PRIMARY KEY, symbol TEXT UNIQUE, name TEXT,
      price REAL DEFAULT 1.0, prev_price REAL DEFAULT 1.0,
      last_updated TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS crypto_holdings (
      user_id INTEGER, coin_id INTEGER, amount REAL DEFAULT 0,
      PRIMARY KEY (user_id, coin_id)
    );
    CREATE TABLE IF NOT EXISTS businesses (
      id INTEGER PRIMARY KEY, name TEXT, descr TEXT,
      price INTEGER, income_per_hour INTEGER, max_accrual_hours INTEGER DEFAULT 24,
      min_level INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS player_businesses (
      user_id INTEGER, business_id INTEGER, purchased_at TEXT DEFAULT (datetime('now')),
      last_collected TEXT DEFAULT (datetime('now')),
      PRIMARY KEY (user_id, business_id)
    );
    CREATE TABLE IF NOT EXISTS lottery_draws (
      id INTEGER PRIMARY KEY, winner_id INTEGER, prize INTEGER,
      ticket_count INTEGER, ts TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS lottery_tickets (
      id INTEGER PRIMARY KEY, user_id INTEGER, draw_id INTEGER,
      qty INTEGER DEFAULT 1, ts TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS daily_log (
      user_id INTEGER PRIMARY KEY, last_claim TEXT, streak INTEGER DEFAULT 0
    );
    """)

    con.commit()
    con.close()
