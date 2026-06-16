-- BGMaffia on Concrete Empire base — full schema

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL COLLATE NOCASE,
  email TEXT,
  password_hash TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  last_active TEXT,
  is_admin INTEGER DEFAULT 0,
  is_banned INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS players (
  user_id INTEGER PRIMARY KEY REFERENCES users(id),
  level INTEGER DEFAULT 1,
  xp INTEGER DEFAULT 0,
  respect INTEGER DEFAULT 0,
  skill_points INTEGER DEFAULT 0,
  strength INTEGER DEFAULT 10,
  stamina INTEGER DEFAULT 10,
  intellect INTEGER DEFAULT 10,
  sexappeal INTEGER DEFAULT 10,
  energy INTEGER DEFAULT 100, energy_max INTEGER DEFAULT 100, energy_ts TEXT,
  nerve INTEGER DEFAULT 10,  nerve_max INTEGER DEFAULT 10,  nerve_ts TEXT,
  health INTEGER DEFAULT 100, health_max INTEGER DEFAULT 100, health_ts TEXT,
  cash INTEGER DEFAULT 0,
  bank INTEGER DEFAULT 1000,
  gold INTEGER DEFAULT 0,
  jail_until TEXT, hospital_until TEXT, protection_until TEXT,
  equipped_weapon INTEGER, equipped_car INTEGER, equipped_dog INTEGER, equipped_armor INTEGER,
  gang_id INTEGER REFERENCES gangs(id), gang_rank INTEGER,
  city_id INTEGER DEFAULT 1, job_id INTEGER, education_level INTEGER DEFAULT 0,
  fights_won INTEGER DEFAULT 0, fights_lost INTEGER DEFAULT 0,
  crimes_done INTEGER DEFAULT 0,
  last_daily TEXT,
  player_class TEXT DEFAULT 'enforcer',
  vip_tier INTEGER DEFAULT 0,
  vip_until TEXT,
  total_casino_wins INTEGER DEFAULT 0,
  total_earned INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS crimes (
  id INTEGER PRIMARY KEY, name TEXT, min_level INTEGER DEFAULT 1,
  energy_cost INTEGER, nerve_cost INTEGER DEFAULT 0,
  base_success REAL, payout_min INTEGER, payout_max INTEGER,
  xp_reward INTEGER, respect_reward INTEGER DEFAULT 1,
  cooldown_sec INTEGER, jail_sec INTEGER, skill_used TEXT
);

CREATE TABLE IF NOT EXISTS crime_log (
  id INTEGER PRIMARY KEY, user_id INTEGER, crime_id INTEGER,
  success INTEGER, payout INTEGER, ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS crime_cooldowns (
  user_id INTEGER, crime_id INTEGER, next_at TEXT,
  PRIMARY KEY (user_id, crime_id)
);

CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY, name TEXT, type TEXT,
  atk INTEGER DEFAULT 0, def INTEGER DEFAULT 0, price INTEGER,
  min_level INTEGER DEFAULT 1, stackable INTEGER DEFAULT 0, effect_json TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
  id INTEGER PRIMARY KEY, user_id INTEGER, item_id INTEGER, qty INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS fights (
  id INTEGER PRIMARY KEY, attacker_id INTEGER, defender_id INTEGER,
  winner_id INTEGER, cash_stolen INTEGER, respect_gain INTEGER,
  turns INTEGER, outcome TEXT, log_json TEXT, ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gangs (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE COLLATE NOCASE, tag TEXT, leader_id INTEGER,
  bank INTEGER DEFAULT 0, respect INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  hq_level INTEGER DEFAULT 1, max_members INTEGER DEFAULT 5
);

CREATE TABLE IF NOT EXISTS gang_members (
  gang_id INTEGER, user_id INTEGER, rank INTEGER, joined_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (gang_id, user_id)
);

CREATE TABLE IF NOT EXISTS gang_invites (
  gang_id INTEGER, user_id INTEGER, ts TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (gang_id, user_id)
);

CREATE TABLE IF NOT EXISTS gang_wars (
  id INTEGER PRIMARY KEY, attacker_gang INTEGER, defender_gang INTEGER,
  status TEXT DEFAULT 'active', winner_gang INTEGER,
  attacker_score INTEGER DEFAULT 0, defender_score INTEGER DEFAULT 0,
  started_at TEXT DEFAULT (datetime('now')), ended_at TEXT
);

CREATE TABLE IF NOT EXISTS territories (
  id INTEGER PRIMARY KEY, name TEXT, type TEXT, income_per_hour INTEGER,
  claim_cost INTEGER DEFAULT 0, min_respect INTEGER DEFAULT 0,
  owner_user INTEGER, owner_gang INTEGER, last_collected TEXT, city_id INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS bank_log (
  id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT, amount INTEGER,
  ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS marketplace (
  id INTEGER PRIMARY KEY, seller_id INTEGER, item_id INTEGER, qty INTEGER,
  price INTEGER, kind TEXT DEFAULT 'listing', top_bidder INTEGER,
  expires_at TEXT, status TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY, from_id INTEGER, to_id INTEGER, subject TEXT,
  body TEXT, is_read INTEGER DEFAULT 0, ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat (
  id INTEGER PRIMARY KEY, channel TEXT DEFAULT 'global', user_id INTEGER,
  body TEXT, ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS relations (
  user_id INTEGER, other_id INTEGER, kind TEXT,
  PRIMARY KEY (user_id, other_id)
);

CREATE TABLE IF NOT EXISTS achievements (
  id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, descr TEXT, gold_reward INTEGER DEFAULT 5
);

CREATE TABLE IF NOT EXISTS player_achievements (
  user_id INTEGER, achievement_id INTEGER, earned_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, achievement_id)
);

CREATE TABLE IF NOT EXISTS bounties (
  id INTEGER PRIMARY KEY, target_id INTEGER, placed_by INTEGER, amount INTEGER,
  status TEXT DEFAULT 'open', claimed_by INTEGER, ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS missions (
  id INTEGER PRIMARY KEY, code TEXT UNIQUE, descr TEXT,
  metric TEXT, target INTEGER, reward_json TEXT, is_daily INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS player_missions (
  user_id INTEGER, mission_id INTEGER, progress INTEGER DEFAULT 0,
  completed INTEGER DEFAULT 0, claimed INTEGER DEFAULT 0, day TEXT,
  PRIMARY KEY (user_id, mission_id, day)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, code TEXT, descr TEXT, modifier_json TEXT,
  starts_at TEXT, ends_at TEXT, is_active INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY, user_id INTEGER, body TEXT, is_read INTEGER DEFAULT 0,
  ts TEXT DEFAULT (datetime('now'))
);

-- Pay-to-win
CREATE TABLE IF NOT EXISTS player_boosts (
  user_id INTEGER, boost_type TEXT, expires_at TEXT,
  PRIMARY KEY (user_id, boost_type)
);
CREATE TABLE IF NOT EXISTS gold_transactions (
  id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT,
  gold_delta INTEGER, note TEXT, ts TEXT DEFAULT (datetime('now'))
);

-- PvE
CREATE TABLE IF NOT EXISTS npc_enemies (
  id INTEGER PRIMARY KEY, name TEXT, min_level INTEGER DEFAULT 1,
  health INTEGER, strength INTEGER, reward_min INTEGER, reward_max INTEGER,
  xp_reward INTEGER, loot_item_id INTEGER, loot_chance REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pve_log (
  id INTEGER PRIMARY KEY, user_id INTEGER, enemy_id INTEGER,
  outcome TEXT, payout INTEGER, xp INTEGER, ts TEXT DEFAULT (datetime('now'))
);

-- Skill tree
CREATE TABLE IF NOT EXISTS skills (
  id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, descr TEXT,
  category TEXT, sp_cost INTEGER DEFAULT 1, prereq_code TEXT,
  effect_json TEXT
);
CREATE TABLE IF NOT EXISTS player_skills (
  user_id INTEGER, skill_code TEXT,
  PRIMARY KEY (user_id, skill_code)
);

-- Crypto
CREATE TABLE IF NOT EXISTS crypto_coins (
  id INTEGER PRIMARY KEY, symbol TEXT UNIQUE, name TEXT,
  price REAL DEFAULT 1.0, prev_price REAL DEFAULT 1.0,
  last_updated TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS crypto_holdings (
  user_id INTEGER, coin_id INTEGER, amount REAL DEFAULT 0,
  PRIMARY KEY (user_id, coin_id)
);

-- Front businesses
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

-- Street lottery (hourly draw)
CREATE TABLE IF NOT EXISTS lottery_draws (
  id INTEGER PRIMARY KEY, winner_id INTEGER, prize INTEGER,
  ticket_count INTEGER, ts TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS lottery_tickets (
  id INTEGER PRIMARY KEY, user_id INTEGER, draw_id INTEGER,
  qty INTEGER DEFAULT 1, ts TEXT DEFAULT (datetime('now'))
);

-- Daily login rewards
CREATE TABLE IF NOT EXISTS daily_log (
  user_id INTEGER PRIMARY KEY, last_claim TEXT, streak INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chat_ts ON chat(id);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_inv_user ON inventory(user_id);
CREATE INDEX IF NOT EXISTS idx_market_status ON marketplace(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_fights_users ON fights(attacker_id, defender_id);
CREATE INDEX IF NOT EXISTS idx_msg_to ON messages(to_id, is_read);
CREATE INDEX IF NOT EXISTS idx_players_respect ON players(respect);
CREATE INDEX IF NOT EXISTS idx_lottery_draw ON lottery_tickets(draw_id);
