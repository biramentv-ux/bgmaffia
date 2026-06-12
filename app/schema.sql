PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now')),
    last_active   TEXT,
    is_admin      INTEGER DEFAULT 0,
    is_banned     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL, -- weapon|car|dog|armor|consumable
    atk         INTEGER DEFAULT 0,
    def         INTEGER DEFAULT 0,
    price       INTEGER NOT NULL DEFAULT 0,
    min_level   INTEGER DEFAULT 1,
    stackable   INTEGER DEFAULT 0,
    effect_json TEXT
);

CREATE TABLE IF NOT EXISTS gangs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    tag         TEXT,
    leader_id   INTEGER NOT NULL,
    bank        INTEGER DEFAULT 0,
    respect     INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    hq_level    INTEGER DEFAULT 1,
    max_members INTEGER DEFAULT 5
);

CREATE TABLE IF NOT EXISTS players (
    user_id          INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    level            INTEGER DEFAULT 1,
    xp               INTEGER DEFAULT 0,
    respect          INTEGER DEFAULT 0,
    skill_points     INTEGER DEFAULT 0,
    strength         INTEGER DEFAULT 10,
    stamina          INTEGER DEFAULT 10,
    intellect        INTEGER DEFAULT 10,
    sexappeal        INTEGER DEFAULT 10,
    energy           INTEGER DEFAULT 100,
    energy_max       INTEGER DEFAULT 100,
    energy_ts        TEXT    DEFAULT (datetime('now')),
    nerve            INTEGER DEFAULT 10,
    nerve_max        INTEGER DEFAULT 10,
    nerve_ts         TEXT    DEFAULT (datetime('now')),
    health           INTEGER DEFAULT 100,
    health_max       INTEGER DEFAULT 100,
    health_ts        TEXT    DEFAULT (datetime('now')),
    cash             INTEGER DEFAULT 0,
    bank             INTEGER DEFAULT 1000,
    gold             INTEGER DEFAULT 0,
    jail_until       TEXT,
    hospital_until   TEXT,
    protection_until TEXT,
    equipped_weapon  INTEGER REFERENCES items(id),
    equipped_car     INTEGER REFERENCES items(id),
    equipped_dog     INTEGER REFERENCES items(id),
    equipped_armor   INTEGER REFERENCES items(id),
    gang_id          INTEGER REFERENCES gangs(id),
    gang_rank        INTEGER DEFAULT 0,
    city_id          INTEGER DEFAULT 1,
    job_id           INTEGER,
    education_level  INTEGER DEFAULT 0,
    total_crimes      INTEGER DEFAULT 0,
    total_fights_won  INTEGER DEFAULT 0,
    total_casino_wins INTEGER DEFAULT 0,
    total_earned     INTEGER DEFAULT 0,
    vip_tier         INTEGER DEFAULT 0,
    vip_until        TEXT
);

CREATE TABLE IF NOT EXISTS crimes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    min_level    INTEGER DEFAULT 1,
    energy_cost  INTEGER DEFAULT 5,
    nerve_cost   INTEGER DEFAULT 0,
    base_success REAL    DEFAULT 0.75,
    payout_min   INTEGER DEFAULT 50,
    payout_max   INTEGER DEFAULT 100,
    xp_reward    INTEGER DEFAULT 5,
    cooldown_sec INTEGER DEFAULT 60,
    jail_sec     INTEGER DEFAULT 300,
    skill_used   TEXT    DEFAULT 'strength'
);

CREATE TABLE IF NOT EXISTS crime_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    crime_id INTEGER NOT NULL,
    success  INTEGER NOT NULL,
    payout   INTEGER DEFAULT 0,
    ts       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS crime_cooldowns (
    user_id  INTEGER NOT NULL,
    crime_id INTEGER NOT NULL,
    next_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, crime_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL REFERENCES items(id),
    qty     INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS fights (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    attacker_id  INTEGER NOT NULL,
    defender_id  INTEGER NOT NULL,
    winner_id    INTEGER,
    cash_stolen  INTEGER DEFAULT 0,
    respect_gain INTEGER DEFAULT 0,
    turns        INTEGER DEFAULT 0,
    outcome      TEXT,
    ts           TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gang_members (
    gang_id   INTEGER NOT NULL REFERENCES gangs(id),
    user_id   INTEGER NOT NULL,
    rank      INTEGER DEFAULT 1,
    joined_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (gang_id, user_id)
);

CREATE TABLE IF NOT EXISTS gang_wars (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    attacker_gang  INTEGER NOT NULL,
    defender_gang  INTEGER NOT NULL,
    status         TEXT DEFAULT 'active',
    winner_gang    INTEGER,
    started_at     TEXT DEFAULT (datetime('now')),
    ended_at       TEXT
);

CREATE TABLE IF NOT EXISTS territories (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    type             TEXT NOT NULL,
    income_per_hour  INTEGER DEFAULT 200,
    owner_user       INTEGER,
    owner_gang       INTEGER,
    last_collected   TEXT,
    city_id          INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS bank_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind    TEXT NOT NULL, -- deposit|withdraw|interest|crime|fight|steal
    amount  INTEGER NOT NULL,
    ts      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS marketplace (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id  INTEGER NOT NULL,
    item_id    INTEGER NOT NULL REFERENCES items(id),
    qty        INTEGER DEFAULT 1,
    price      INTEGER NOT NULL,
    kind       TEXT DEFAULT 'listing',
    expires_at TEXT,
    status     TEXT DEFAULT 'active' -- active|sold|expired|cancelled
);

CREATE TABLE IF NOT EXISTS messages (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id  INTEGER NOT NULL,
    to_id    INTEGER NOT NULL,
    subject  TEXT DEFAULT '',
    body     TEXT NOT NULL,
    is_read  INTEGER DEFAULT 0,
    ts       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT DEFAULT 'global',
    user_id INTEGER NOT NULL,
    body    TEXT NOT NULL,
    ts      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS relations (
    user_id  INTEGER NOT NULL,
    other_id INTEGER NOT NULL,
    kind     TEXT NOT NULL, -- friend|enemy
    PRIMARY KEY (user_id, other_id)
);

CREATE TABLE IF NOT EXISTS achievements (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    code  TEXT UNIQUE NOT NULL,
    name  TEXT NOT NULL,
    descr TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_achievements (
    user_id        INTEGER NOT NULL,
    achievement_id INTEGER NOT NULL,
    earned_at      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, achievement_id)
);

CREATE TABLE IF NOT EXISTS bounties (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id    INTEGER NOT NULL,
    placed_by    INTEGER NOT NULL,
    amount       INTEGER NOT NULL,
    status       TEXT DEFAULT 'active', -- active|collected|expired
    placed_at    TEXT DEFAULT (datetime('now')),
    expires_at   TEXT,
    collected_by INTEGER
);

CREATE TABLE IF NOT EXISTS missions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE NOT NULL,
    descr       TEXT NOT NULL,
    reward_json TEXT NOT NULL,
    is_daily    INTEGER DEFAULT 0,
    req_json    TEXT
);

CREATE TABLE IF NOT EXISTS player_missions (
    user_id     INTEGER NOT NULL,
    mission_id  INTEGER NOT NULL,
    progress    INTEGER DEFAULT 0,
    completed   INTEGER DEFAULT 0,
    last_reset  TEXT,
    PRIMARY KEY (user_id, mission_id)
);

CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code          TEXT NOT NULL,
    descr         TEXT NOT NULL,
    modifier_json TEXT,
    starts_at     TEXT,
    ends_at       TEXT,
    active        INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notifications (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    body    TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    ts      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_rewards (
    user_id      INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    streak       INTEGER DEFAULT 0,
    last_claimed TEXT -- UTC date YYYY-MM-DD
);

CREATE TABLE IF NOT EXISTS crypto_prices (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    price  REAL NOT NULL,
    ts     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS crypto_holdings (
    user_id INTEGER NOT NULL,
    symbol  TEXT NOT NULL,
    amount  REAL DEFAULT 0,
    PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS businesses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    descr           TEXT,
    price           INTEGER NOT NULL,
    income_per_hour INTEGER NOT NULL,
    min_level       INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS player_businesses (
    user_id        INTEGER NOT NULL,
    business_id    INTEGER NOT NULL REFERENCES businesses(id),
    bought_at      TEXT DEFAULT (datetime('now')),
    last_collected TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, business_id)
);

CREATE TABLE IF NOT EXISTS lottery_draws (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    status    TEXT DEFAULT 'open', -- open|drawn
    pot       INTEGER DEFAULT 0,
    winner_id INTEGER,
    opened_at TEXT DEFAULT (datetime('now')),
    drawn_at  TEXT
);

CREATE TABLE IF NOT EXISTS lottery_tickets (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    draw_id INTEGER NOT NULL REFERENCES lottery_draws(id),
    user_id INTEGER NOT NULL,
    qty     INTEGER DEFAULT 1
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chat_ts       ON chat(channel, ts);
CREATE INDEX IF NOT EXISTS idx_notif_user    ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_inv_user      ON inventory(user_id);
CREATE INDEX IF NOT EXISTS idx_market_status ON marketplace(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_crime_log     ON crime_log(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_fights_users  ON fights(attacker_id, defender_id, ts);
CREATE INDEX IF NOT EXISTS idx_messages_to   ON messages(to_id, is_read);
CREATE INDEX IF NOT EXISTS idx_bounty_target ON bounties(target_id, status);
CREATE INDEX IF NOT EXISTS idx_crypto_sym    ON crypto_prices(symbol, ts);
CREATE INDEX IF NOT EXISTS idx_lotto_draw    ON lottery_tickets(draw_id);

-- Server-side blackjack state (prevents client from reading dealer/deck from cookie)
CREATE TABLE IF NOT EXISTS bj_sessions (
    user_id     INTEGER PRIMARY KEY,
    state_json  TEXT NOT NULL,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- Pay-to-win: gold transaction ledger
CREATE TABLE IF NOT EXISTS gold_transactions (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount  INTEGER NOT NULL,  -- positive=earn, negative=spend
    kind    TEXT NOT NULL,     -- purchase|boost|vip|admin
    ref_id  INTEGER,
    ts      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_gold_txn ON gold_transactions(user_id, ts);

-- Pay-to-win: active timed boosts per player
CREATE TABLE IF NOT EXISTS player_boosts (
    user_id    INTEGER NOT NULL,
    boost_type TEXT NOT NULL,
    multiplier REAL DEFAULT 1.0,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (user_id, boost_type)
);
CREATE INDEX IF NOT EXISTS idx_boosts_user ON player_boosts(user_id, expires_at);
