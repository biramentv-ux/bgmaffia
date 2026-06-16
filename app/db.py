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
    # New tables
    db.executescript("""
        CREATE TABLE IF NOT EXISTS npc_enemies (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, icon TEXT NOT NULL,
            min_level INTEGER DEFAULT 1, energy_cost INTEGER DEFAULT 5,
            atk INTEGER DEFAULT 10, def INTEGER DEFAULT 5, hp INTEGER DEFAULT 50,
            payout_min INTEGER DEFAULT 30, payout_max INTEGER DEFAULT 80,
            xp_reward INTEGER DEFAULT 5, drop_item_id INTEGER, drop_chance REAL DEFAULT 0.10
        );
        CREATE TABLE IF NOT EXISTS pve_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            enemy_id INTEGER NOT NULL, won INTEGER NOT NULL,
            payout INTEGER DEFAULT 0, xp_gain INTEGER DEFAULT 0,
            ts TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_pve_log ON pve_log(user_id, ts);
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL, icon TEXT NOT NULL, category TEXT NOT NULL,
            cost INTEGER DEFAULT 1, effect_json TEXT NOT NULL,
            requires TEXT, descr TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS player_skills (
            user_id INTEGER NOT NULL, skill_code TEXT NOT NULL,
            unlocked_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, skill_code)
        );
    """)
    # New columns on existing tables (ignore "duplicate column" error)
    for sql in [
        "ALTER TABLE players ADD COLUMN vip_tier INTEGER DEFAULT 0",
        "ALTER TABLE players ADD COLUMN vip_until TEXT",
        "ALTER TABLE players ADD COLUMN player_class TEXT DEFAULT 'enforcer'",
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
