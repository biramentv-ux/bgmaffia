import sqlite3
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA synchronous=NORMAL")
        g.db.execute("PRAGMA busy_timeout=5000")
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA temp_store=MEMORY")
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))
    with current_app.open_resource('seed.sql') as f:
        db.executescript(f.read().decode('utf8'))
    db.commit()


def migrate_db():
    """Apply forward-only schema migrations. Safe to run on every startup."""
    db = get_db()
    # New tables (CREATE TABLE IF NOT EXISTS — idempotent)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS gold_transactions (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount  INTEGER NOT NULL,
            kind    TEXT NOT NULL,
            ref_id  INTEGER,
            ts      TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_gold_txn ON gold_transactions(user_id, ts);

        CREATE TABLE IF NOT EXISTS player_boosts (
            user_id    INTEGER NOT NULL,
            boost_type TEXT NOT NULL,
            multiplier REAL DEFAULT 1.0,
            expires_at TEXT NOT NULL,
            PRIMARY KEY (user_id, boost_type)
        );
        CREATE INDEX IF NOT EXISTS idx_boosts_user ON player_boosts(user_id, expires_at);
    """)
    # New columns on existing tables (ignore "duplicate column" error)
    for sql in [
        "ALTER TABLE players ADD COLUMN vip_tier INTEGER DEFAULT 0",
        "ALTER TABLE players ADD COLUMN vip_until TEXT",
    ]:
        try:
            db.execute(sql)
        except Exception:
            pass
    db.commit()


def query(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur
