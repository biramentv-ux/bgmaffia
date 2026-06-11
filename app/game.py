"""Core game logic: lazy regen, combat, levelling, checks."""
import random
import math
import json
from datetime import datetime, timedelta


# ── Regen constants ────────────────────────────────────────────────────
ENERGY_RATE = 5;  ENERGY_TICK = 300
NERVE_RATE  = 1;  NERVE_TICK  = 300
HEALTH_RATE = 1;  HEALTH_TICK = 60


def _now():
    return datetime.utcnow()


def lazy_regen(db, user_id):
    """Compute regen since last tick and persist. Returns fresh player dict."""
    row = db.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return None
    p = dict(row)
    now = _now()
    updates = {}

    def regen_bar(bar, mx, ts_col, rate, tick):
        cur = p[bar]
        cap = p[mx]
        if cur >= cap:
            # Advance the timestamp to now so we don't accumulate phantom ticks
            # while the bar was at cap, which would instantly refill on next spend.
            updates[ts_col] = now.isoformat()
            return
        ts_str = p[ts_col]
        if not ts_str:
            updates[ts_col] = now.isoformat()
            return
        try:
            ts = datetime.fromisoformat(ts_str)
        except Exception:
            updates[ts_col] = now.isoformat()
            return
        elapsed = (now - ts).total_seconds()
        ticks = int(elapsed // tick)
        if ticks <= 0:
            return
        gained = ticks * rate
        new_val = min(cur + gained, cap)
        updates[bar] = new_val
        updates[ts_col] = (ts + timedelta(seconds=ticks * tick)).isoformat()
        p[bar] = new_val

    regen_bar('energy', 'energy_max', 'energy_ts', ENERGY_RATE, ENERGY_TICK)
    regen_bar('nerve',  'nerve_max',  'nerve_ts',  NERVE_RATE,  NERVE_TICK)
    regen_bar('health', 'health_max', 'health_ts', HEALTH_RATE, HEALTH_TICK)

    if updates:
        cols = ', '.join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE players SET {cols} WHERE user_id=?",
                   list(updates.values()) + [user_id])
        db.commit()
        row = db.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()
        p = dict(row)
    return p


# ── Lock helpers ────────────────────────────────────────────────────────
def is_in_jail(player):
    j = player.get('jail_until')
    return bool(j and j > _now().isoformat())


def is_in_hospital(player):
    h = player.get('hospital_until')
    return bool(h and h > _now().isoformat())


def is_protected(player):
    prot = player.get('protection_until')
    return bool(prot and prot > _now().isoformat())


def is_online(user_row, timeout_minutes=5):
    la = user_row['last_active'] if hasattr(user_row, '__getitem__') else user_row.get('last_active')
    if not la:
        return False
    try:
        ts = datetime.fromisoformat(la)
    except Exception:
        return False
    return (_now() - ts).total_seconds() < timeout_minutes * 60


# ── Level / XP ──────────────────────────────────────────────────────────
def xp_for_level(level):
    return round(100 * (level ** 1.5))


def skill_points_per_level(level):
    if level <= 10:  return 3
    if level <= 20:  return 6
    return 8


def maybe_level_up(db, user_id, player):
    """Check if player has enough XP to level up. Returns new level."""
    level = player['level']
    xp    = player['xp']
    levelled = False
    while xp >= xp_for_level(level):
        level += 1
        sp = skill_points_per_level(level)
        db.execute(
            "UPDATE players SET level=?, skill_points=skill_points+?, nerve_max=nerve_max+1 WHERE user_id=?",
            (level, sp, user_id)
        )
        _notify(db, user_id, f"🎉 You reached level {level}! +{sp} skill points.")
        mission_progress(db, user_id, 'level', 1)
        levelled = True
    if levelled:
        db.commit()
    return level


# ── Crime success formula ───────────────────────────────────────────────
def crime_success_chance(crime, player):
    base = crime['base_success']
    skill = crime['skill_used']
    skill_val = player.get(skill, 10)
    bonus = (skill_val - 10) * 0.005   # +0.5% per stat point above 10
    return max(0.05, min(0.95, base + bonus))


# ── Combat ──────────────────────────────────────────────────────────────
def _effective_stats(player, db):
    """Return (atk, def) for a player including equipment."""
    w_atk = c_atk = d_atk = a_def = 0
    if player.get('equipped_weapon'):
        row = db.execute("SELECT atk FROM items WHERE id=?", (player['equipped_weapon'],)).fetchone()
        if row: w_atk = row['atk']
    if player.get('equipped_car'):
        row = db.execute("SELECT atk, def FROM items WHERE id=?", (player['equipped_car'],)).fetchone()
        if row: c_atk = row['atk']
    if player.get('equipped_dog'):
        row = db.execute("SELECT atk FROM items WHERE id=?", (player['equipped_dog'],)).fetchone()
        if row: d_atk = row['atk']
    if player.get('equipped_armor'):
        row = db.execute("SELECT def FROM items WHERE id=?", (player['equipped_armor'],)).fetchone()
        if row: a_def = row['def']

    eff_atk = player['strength'] * (1 + w_atk / 100.0) + (c_atk + d_atk) * 0.1
    eff_def = player['strength'] * 0.5 + player['stamina'] * 0.5 + a_def
    return eff_atk, eff_def


def resolve_fight(db, attacker_id, defender_id):
    """
    Simulate the fight. Returns dict with winner_id, turns, cash_stolen,
    respect_gain, outcome text.
    """
    atk_row = db.execute("SELECT * FROM players WHERE user_id=?", (attacker_id,)).fetchone()
    def_row = db.execute("SELECT * FROM players WHERE user_id=?", (defender_id,)).fetchone()
    atk_p = dict(atk_row); def_p = dict(def_row)

    atk_eff_atk, atk_eff_def = _effective_stats(atk_p, db)
    def_eff_atk, def_eff_def = _effective_stats(def_p, db)
    atk_eff = atk_eff_atk
    def_eff = def_eff_atk

    atk_hp = atk_p['health']
    def_hp = def_p['health']
    MAX_TURNS = 25
    turns = 0

    while atk_hp > 0 and def_hp > 0 and turns < MAX_TURNS:
        total = atk_eff + def_eff_def + 1
        hit_chance = max(0.05, min(0.95, 0.5 + (atk_eff - def_eff_def) / total))

        if random.random() < hit_chance:
            mitigation = def_eff_def / (def_eff_def + atk_eff + 1)
            dmg = atk_eff * random.uniform(0.8, 1.2) * (1 - mitigation)
            def_hp -= max(1, int(dmg))

        counter_chance = max(0.05, min(0.95, 0.5 + (def_eff - atk_eff_def) / (def_eff + atk_eff_def + 1)))
        if random.random() < counter_chance:
            mitigation = atk_eff_def / (atk_eff_def + def_eff + 1)
            dmg = def_eff * random.uniform(0.8, 1.2) * (1 - mitigation)
            atk_hp -= max(1, int(dmg))

        turns += 1

    if def_hp <= 0 and atk_hp > 0:
        winner_id = attacker_id
    elif atk_hp <= 0:
        winner_id = defender_id
    else:
        winner_id = None  # stalemate

    now = _now().isoformat()
    cash_stolen = 0
    respect_gain = 0

    if winner_id == attacker_id:
        pct = random.uniform(0.10, 0.20)
        cash_stolen = int(def_p['cash'] * pct)
        lvl_diff = atk_p['level'] - def_p['level']
        respect_gain = max(1, 10 - lvl_diff)   # punish punching down
        outcome = f"Victory! Stole ${cash_stolen:,}"
        hosp_mins = random.randint(15, 30)

        db.execute("BEGIN IMMEDIATE")
        # Transfer cash
        db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (cash_stolen, attacker_id))
        db.execute("UPDATE players SET cash=MAX(0,cash-?), health=1, hospital_until=datetime('now',?), protection_until=datetime('now','+15 minutes'), health_ts=? WHERE user_id=?",
                   (cash_stolen, f'+{hosp_mins} minutes', now, defender_id))
        db.execute("UPDATE players SET respect=respect+?, total_fights_won=total_fights_won+1 WHERE user_id=?",
                   (respect_gain, attacker_id))
        # Pay out any active bounties on the defender
        bounties = db.execute(
            "SELECT id, amount FROM bounties WHERE target_id=? AND status='active'", (defender_id,)
        ).fetchall()
        for b in bounties:
            prize = int(b['amount'] * 0.90)
            db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (prize, attacker_id))
            db.execute("UPDATE bounties SET status='collected', collected_by=? WHERE id=?",
                       (attacker_id, b['id']))
            _notify(db, attacker_id, f"💰 Bounty collected! +${prize:,}")
        db.commit()
        _notify(db, defender_id, f"😵 {_username(db,attacker_id)} beat you up and stole ${cash_stolen:,}!")
        _check_achievements(db, attacker_id)

    elif winner_id == defender_id:
        pct = random.uniform(0.05, 0.10)
        cash_stolen = int(atk_p['cash'] * pct)
        respect_gain = max(1, 5)
        outcome = f"Defeat! Lost ${cash_stolen:,}"
        hosp_mins = random.randint(10, 20)

        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (cash_stolen, defender_id))
        db.execute("UPDATE players SET cash=MAX(0,cash-?), health=1, hospital_until=datetime('now',?), health_ts=? WHERE user_id=?",
                   (cash_stolen, f'+{hosp_mins} minutes', now, attacker_id))
        db.execute("UPDATE players SET respect=respect+? WHERE user_id=?", (respect_gain, defender_id))
        db.commit()
        _notify(db, attacker_id, f"😵 {_username(db,defender_id)} beat you! Lost ${cash_stolen:,}.")

    else:
        outcome = "Stalemate – no respect awarded."
        db.execute("UPDATE players SET health=MAX(1,health-10) WHERE user_id=? OR user_id=?",
                   (attacker_id, defender_id))
        db.commit()

    db.execute(
        "INSERT INTO fights (attacker_id,defender_id,winner_id,cash_stolen,respect_gain,turns,outcome) VALUES (?,?,?,?,?,?,?)",
        (attacker_id, defender_id, winner_id, cash_stolen, respect_gain, turns, outcome)
    )
    db.commit()

    return {'winner_id': winner_id, 'turns': turns, 'cash_stolen': cash_stolen,
            'respect_gain': respect_gain, 'outcome': outcome}


# ── Notifications ───────────────────────────────────────────────────────
def _notify(db, user_id, body):
    db.execute("INSERT INTO notifications(user_id,body) VALUES(?,?)", (user_id, body))


def _username(db, user_id):
    row = db.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
    return row['username'] if row else '?'


# ── Achievement checks ──────────────────────────────────────────────────
def _check_achievements(db, user_id):
    p = dict(db.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone())
    earned = {r['achievement_id'] for r in db.execute(
        "SELECT achievement_id FROM player_achievements WHERE user_id=?", (user_id,))}

    checks = [
        (1, p['total_fights_won'] >= 1),
        (2, p['total_crimes'] >= 100),
        (3, p['total_fights_won'] >= 50),
        (4, p['bank'] >= 1_000_000),
        (5, p['gang_id'] is not None),
        (6, p['level'] >= 10),
        (7, p['level'] >= 25),
        (8, p['respect'] >= 1000),
    ]
    for aid, cond in checks:
        if cond and aid not in earned:
            db.execute("INSERT OR IGNORE INTO player_achievements(user_id,achievement_id) VALUES(?,?)",
                       (user_id, aid))
            row = db.execute("SELECT name FROM achievements WHERE id=?", (aid,)).fetchone()
            _notify(db, user_id, f"🏅 Achievement unlocked: {row['name']}")
    db.commit()


def check_achievements(db, user_id):
    _check_achievements(db, user_id)


# ── Daily mission progress helper ───────────────────────────────────────
def mission_progress(db, user_id, key, amount=1):
    """Increment a mission progress counter for missions that track the given key."""
    rows = db.execute(
        "SELECT m.id, m.req_json, pm.progress, pm.completed, pm.last_reset "
        "FROM missions m LEFT JOIN player_missions pm ON m.id=pm.mission_id AND pm.user_id=? "
        "WHERE m.req_json LIKE ?", (user_id, f'%"{key}"%')
    ).fetchall()

    today = _now().date().isoformat()
    for r in rows:
        m_id   = r['id']
        req    = json.loads(r['req_json'] or '{}')
        target = req.get(key, 0)
        if not target:
            continue
        prog      = r['progress'] or 0
        completed = r['completed'] or 0
        lr        = r['last_reset']

        # For daily missions, reset if last_reset is not today
        is_daily = db.execute("SELECT is_daily FROM missions WHERE id=?", (m_id,)).fetchone()['is_daily']
        if is_daily and lr != today:
            prog = 0; completed = 0

        if completed:
            continue

        new_prog = min(prog + amount, target)
        new_completed = 1 if new_prog >= target else 0

        db.execute(
            "INSERT INTO player_missions(user_id,mission_id,progress,completed,last_reset) VALUES(?,?,?,?,?) "
            "ON CONFLICT(user_id,mission_id) DO UPDATE SET progress=?,completed=?,last_reset=?",
            (user_id, m_id, new_prog, new_completed, today,
             new_prog, new_completed, today)
        )
        if new_completed and not completed:
            row = db.execute("SELECT descr,reward_json FROM missions WHERE id=?", (m_id,)).fetchone()
            _notify(db, user_id, f"✅ Mission complete: {row['descr']}")
            _apply_mission_reward(db, user_id, json.loads(row['reward_json']))
    db.commit()


def _apply_mission_reward(db, user_id, reward):
    cash    = reward.get('cash', 0)
    xp      = reward.get('xp', 0)
    gold    = reward.get('gold', 0)
    respect = reward.get('respect', 0)
    db.execute(
        "UPDATE players SET cash=cash+?, xp=xp+?, gold=gold+?, respect=respect+? WHERE user_id=?",
        (cash, xp, gold, respect, user_id)
    )


# ── Territory income ────────────────────────────────────────────────────
def accrue_territory(db):
    """Called by APScheduler every hour: credit territory income to owners."""
    now = _now().isoformat()
    territories = db.execute("SELECT * FROM territories WHERE owner_user IS NOT NULL OR owner_gang IS NOT NULL").fetchall()
    for t in territories:
        income = t['income_per_hour']
        if t['owner_user']:
            db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (income, t['owner_user']))
            _notify(db, t['owner_user'], f"💰 +${income} from {t['name']}")
        elif t['owner_gang']:
            db.execute("UPDATE gangs SET bank=bank+? WHERE id=?", (income, t['owner_gang']))
        db.execute("UPDATE territories SET last_collected=? WHERE id=?", (now, t['id']))
    db.commit()


# ── Bank interest ───────────────────────────────────────────────────────
def apply_bank_interest(db, rate=0.005):
    """Called by APScheduler every hour."""
    players = db.execute("SELECT user_id, bank FROM players WHERE bank > 0").fetchall()
    for p in players:
        interest = int(p['bank'] * rate)
        if interest > 0:
            db.execute("UPDATE players SET bank=bank+? WHERE user_id=?", (interest, p['user_id']))
            db.execute("INSERT INTO bank_log(user_id,kind,amount) VALUES(?,?,?)",
                       (p['user_id'], 'interest', interest))
    db.commit()


# ── Crypto market (2026 update) ─────────────────────────────────────────
CRYPTO_BASE = {'SHDW': 100.0, 'OMRT': 25.0, 'BLDD': 850.0}


def latest_crypto_prices(db):
    """Return {symbol: price} using the most recent row per symbol."""
    rows = db.execute(
        "SELECT symbol, price FROM crypto_prices p "
        "WHERE id = (SELECT MAX(id) FROM crypto_prices WHERE symbol = p.symbol)"
    ).fetchall()
    return {r['symbol']: r['price'] for r in rows}


def tick_crypto(db):
    """Random-walk each coin with mild mean reversion toward its base price."""
    prices = latest_crypto_prices(db)
    for sym, base in CRYPTO_BASE.items():
        cur = prices.get(sym, base)
        drift = (base - cur) / base * 0.01          # pull back toward base
        shock = random.gauss(0, 0.03)               # ±3% volatility per tick
        new = max(base * 0.05, cur * (1 + drift + shock))
        db.execute("INSERT INTO crypto_prices(symbol, price) VALUES(?,?)",
                   (sym, round(new, 2)))
    # keep one week of history
    db.execute("DELETE FROM crypto_prices WHERE ts < datetime('now', '-7 days')")
    db.commit()


# ── Lottery (2026 update) ────────────────────────────────────────────────
def get_open_draw(db):
    """Return the current open draw, creating one if needed."""
    row = db.execute("SELECT * FROM lottery_draws WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        return row
    db.execute("INSERT INTO lottery_draws(status) VALUES('open')")
    db.commit()
    return db.execute("SELECT * FROM lottery_draws WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()


def draw_lottery(db, house_cut=0.10):
    """Close the open draw: pick a ticket-weighted winner, pay out, open a new draw."""
    draw = db.execute("SELECT * FROM lottery_draws WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()
    if not draw:
        return
    tickets = db.execute(
        "SELECT user_id, qty FROM lottery_tickets WHERE draw_id=?", (draw['id'],)
    ).fetchall()
    if not tickets:
        # nothing sold yet — keep the draw open
        return
    pool = []
    for t in tickets:
        pool.extend([t['user_id']] * t['qty'])
    winner = random.choice(pool)
    prize = int(draw['pot'] * (1 - house_cut))
    db.execute("BEGIN IMMEDIATE")
    db.execute("UPDATE lottery_draws SET status='drawn', winner_id=?, drawn_at=datetime('now') WHERE id=? AND status='open'",
               (winner, draw['id']))
    db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (prize, winner))
    _notify(db, winner, f"🎟️ You WON the lottery! ${prize:,} in cash.")
    db.execute("INSERT INTO lottery_draws(status) VALUES('open')")
    db.commit()
