"""game.py — core game logic: lazy regen, leveling, combat, classes, VIP,
skill bonuses, achievements, daily missions, notifications, event modifiers.
"""
import json
import math
import random
from datetime import datetime, timedelta

from db import guarded, TxFailed

FMT = "%Y-%m-%d %H:%M:%S"

ENERGY_TICK_SEC, ENERGY_PER_TICK = 300, 5
NERVE_TICK_SEC, NERVE_PER_TICK = 300, 1
HEALTH_TICK_SEC = 60  # +1% of max per minute


def now():
    return datetime.utcnow()


def ts(dt):
    return dt.strftime(FMT)


def parse(s):
    return datetime.strptime(s, FMT) if s else None


def xp_needed(level):
    return round(100 * level ** 1.5)


def skill_points_for_level(level):
    if level < 10:
        return 3
    if level < 20:
        return 6
    return 8


# ── Character classes ────────────────────────────────────────────────────────

CLASSES = {
    'enforcer': {
        'name': 'Enforcer', 'icon': '💪',
        'desc': 'Hard hitter. +20% fight damage, fast hospital recovery.',
        'stats': {'strength': 20, 'stamina': 10, 'intellect': 6, 'sexappeal': 4},
        'fight_dmg': 1.20, 'fight_def': 1.0, 'crime_mult': 0.90, 'crime_payout': 1.0,
        'casino_mult': 1.0, 'hospital_mult': 0.50, 'jail_mult': 1.0, 'regen_mult': 1.0,
    },
    'hacker': {
        'name': 'Hacker', 'icon': '💻',
        'desc': 'Crime specialist. +20% crime success, 50% shorter jail time.',
        'stats': {'strength': 5, 'stamina': 5, 'intellect': 20, 'sexappeal': 10},
        'fight_dmg': 0.85, 'fight_def': 0.90, 'crime_mult': 1.20, 'crime_payout': 1.10,
        'casino_mult': 1.0, 'hospital_mult': 1.0, 'jail_mult': 0.50, 'regen_mult': 1.0,
    },
    'conman': {
        'name': 'Conman', 'icon': '🎭',
        'desc': 'Silver tongue. +25% crime payout, +10% casino edge.',
        'stats': {'strength': 5, 'stamina': 5, 'intellect': 10, 'sexappeal': 20},
        'fight_dmg': 0.85, 'fight_def': 0.90, 'crime_mult': 1.0, 'crime_payout': 1.25,
        'casino_mult': 1.10, 'hospital_mult': 1.0, 'jail_mult': 1.0, 'regen_mult': 1.0,
    },
    'ghost': {
        'name': 'Ghost', 'icon': '👻',
        'desc': 'Shadow operative. +15% defence, +20% regen speed.',
        'stats': {'strength': 12, 'stamina': 18, 'intellect': 5, 'sexappeal': 5},
        'fight_dmg': 0.90, 'fight_def': 1.15, 'crime_mult': 1.0, 'crime_payout': 1.0,
        'casino_mult': 1.0, 'hospital_mult': 1.0, 'jail_mult': 0.75, 'regen_mult': 1.20,
    },
}


def get_class(player):
    code = (player['player_class'] if 'player_class' in player.keys() else None) or 'enforcer'
    return CLASSES.get(code, CLASSES['enforcer'])


# ── VIP system ───────────────────────────────────────────────────────────────

VIP_XP_MULT      = {0: 1.0, 1: 1.10, 2: 1.25, 3: 1.50}
VIP_CASH_MULT    = {0: 1.0, 1: 1.05, 2: 1.10, 3: 1.20}
VIP_REGEN_MULT   = {0: 1.0, 1: 1.0,  2: 1.05, 3: 1.10}
VIP_COMBAT_BONUS = {0: 0,   1: 0,    2: 0,    3: 10}


def get_vip_tier(player):
    tier = player['vip_tier'] if 'vip_tier' in player.keys() else 0
    until = player['vip_until'] if 'vip_until' in player.keys() else None
    if not tier:
        return 0
    if until and parse(until) > now():
        return tier
    return 0


def get_active_boost(con, user_id, boost_type):
    row = con.execute(
        "SELECT expires_at FROM player_boosts WHERE user_id=? AND boost_type=?",
        (user_id, boost_type)).fetchone()
    if row and row['expires_at'] and parse(row['expires_at']) > now():
        return True
    return False


# ── Passive skill tree bonuses ───────────────────────────────────────────────

SKILL_EFFECTS = {
    'street_brawler': {'fight_dmg': 0.10},
    'iron_skin':      {'fight_def': 0.10},
    'berserker':      {'fight_dmg': 0.20},
    'five_finger':    {'crime_success': 0.10},
    'fast_getaway':   {'crime_cd': 0.20},
    'crime_master':   {'crime_cash': 0.15},
    'adrenaline':     {'regen_mult': 0.15},
    'quick_healer':   {'hospital_mult': 0.30},
    'card_counter':   {'casino_mult': 0.10},
    'gang_connect':   {'territory_mult': 0.15},
    'kingpin':        {'crime_cash': 0.15, 'territory_mult': 0.10},
    'iron_will':      {'health_bonus': 25},
}


def get_skill_bonuses(con, user_id):
    bonuses = {
        'fight_dmg': 0.0, 'fight_def': 0.0, 'crime_success': 0.0, 'crime_cd': 0.0,
        'crime_cash': 0.0, 'regen_mult': 0.0, 'hospital_mult': 0.0, 'casino_mult': 0.0,
        'territory_mult': 0.0, 'health_bonus': 0,
    }
    rows = con.execute(
        "SELECT skill_code FROM player_skills WHERE user_id=?", (user_id,)).fetchall()
    for row in rows:
        for k, v in SKILL_EFFECTS.get(row['skill_code'], {}).items():
            bonuses[k] = bonuses.get(k, 0) + v
    return bonuses


# ── Regen ────────────────────────────────────────────────────────────────────

def lazy_regen(con, uid):
    p = con.execute(
        "SELECT energy,energy_max,energy_ts,nerve,nerve_max,nerve_ts,"
        "health,health_max,health_ts,hospital_until,player_class,vip_tier,vip_until "
        "FROM players WHERE user_id=?", (uid,)).fetchone()
    if not p:
        return
    t = now()
    cls = get_class(p)
    vip = get_vip_tier(p)
    skills = get_skill_bonuses(con, uid)
    regen_mult = cls['regen_mult'] * VIP_REGEN_MULT.get(vip, 1.0) * (1.0 + skills['regen_mult'])

    def bar(val, mx, last, tick, gain_per):
        last_dt = parse(last) or t
        ticks = int((t - last_dt).total_seconds() // tick)
        if ticks <= 0 or val >= mx:
            return (mx if val >= mx else val), ts(t) if val >= mx else last
        gained = int(ticks * gain_per * regen_mult)
        new_val = min(mx, val + gained)
        new_ts = ts(last_dt + timedelta(seconds=ticks * tick))
        return new_val, new_ts

    e, ets = bar(p["energy"], p["energy_max"], p["energy_ts"], ENERGY_TICK_SEC, ENERGY_PER_TICK)
    n, nts = bar(p["nerve"], p["nerve_max"], p["nerve_ts"], NERVE_TICK_SEC, NERVE_PER_TICK)

    # health: no regen while in hospital
    in_hospital = p["hospital_until"] and parse(p["hospital_until"]) > t
    if in_hospital:
        h, hts = p["health"], p["health_ts"]
    else:
        h, hts = bar(p["health"], p["health_max"], p["health_ts"], HEALTH_TICK_SEC,
                     max(1, p["health_max"] // 100))

    con.execute(
        "UPDATE players SET energy=?,energy_ts=?,nerve=?,nerve_ts=?,health=?,health_ts=? "
        "WHERE user_id=?",
        (e, ets or ts(t), n, nts or ts(t), h, hts or ts(t), uid),
    )


def get_player(con, uid):
    return con.execute(
        "SELECT p.*, u.username, u.is_admin, u.is_banned, u.created_at, u.last_active "
        "FROM players p JOIN users u ON u.id=p.user_id WHERE p.user_id=?", (uid,)).fetchone()


def status_locks(player):
    t, locks = now(), {}
    for key in ("jail_until", "hospital_until", "protection_until"):
        v = parse(player[key]) if player[key] else None
        if v and v > t:
            locks[key.replace("_until", "")] = int((v - t).total_seconds())
    return locks


# ── XP / leveling ────────────────────────────────────────────────────────────

def grant_xp(con, uid, xp, respect=0):
    p = con.execute("SELECT level,xp FROM players WHERE user_id=?", (uid,)).fetchone()
    level, total_xp = p["level"], p["xp"] + xp
    points = 0
    while total_xp >= xp_needed(level):
        level += 1
        points += skill_points_for_level(level)
    con.execute(
        "UPDATE players SET xp=?, level=?, respect=respect+?, skill_points=skill_points+? "
        "WHERE user_id=?", (total_xp, level, respect, points, uid))
    if level > p["level"]:
        notify(con, uid, f"Level up! You are now level {level}. +{points} skill points.")
        check_achievements(con, uid)
    return level


def notify(con, uid, body):
    con.execute("INSERT INTO notifications(user_id, body) VALUES (?,?)", (uid, body))


# ── Equipment bonus ──────────────────────────────────────────────────────────

def equipment_bonus(con, player):
    ids = [player["equipped_weapon"], player["equipped_car"],
           player["equipped_dog"], player["equipped_armor"]]
    weapon_atk = flat_atk = flat_def = 0
    for inv_id in ids:
        if not inv_id:
            continue
        row = con.execute(
            "SELECT i.type,i.atk,i.def FROM inventory v JOIN items i ON i.id=v.item_id "
            "WHERE v.id=? AND v.user_id=?", (inv_id, player["user_id"])).fetchone()
        if not row:
            continue
        if row["type"] == "weapon":
            weapon_atk += row["atk"]
        else:
            flat_atk += row["atk"]
            flat_def += row["def"]
    return weapon_atk, flat_atk, flat_def


# ── Combat ───────────────────────────────────────────────────────────────────

def resolve_fight(con, attacker, defender):
    def _stats(p):
        w, fa, fd = equipment_bonus(con, p)
        cls = get_class(p)
        vip = get_vip_tier(p)
        sk = get_skill_bonuses(con, p["user_id"])
        combat_bonus = VIP_COMBAT_BONUS.get(vip, 0)
        atk = (p["strength"] * (1 + w / 100.0) + fa) * cls['fight_dmg'] * (1 + sk['fight_dmg']) + combat_bonus
        dfn = (p["strength"] * 0.5 + p["stamina"] * 0.5 + fd) * cls['fight_def'] * (1 + sk['fight_def'])
        return atk, dfn

    a_atk, a_def = _stats(attacker)
    d_atk, d_def = _stats(defender)
    a_hp, d_hp = attacker["health"], defender["health"]
    log, turns = [], 0

    def hit_chance(atk, dfn):
        return max(0.05, min(0.95, 0.5 + (atk - dfn) / (atk + dfn + 1)))

    while turns < 25 and a_hp > 0 and d_hp > 0:
        turns += 1
        if random.random() < hit_chance(a_atk, d_def):
            dmg = max(1, int(a_atk * random.uniform(0.8, 1.2) * (1 - min(0.6, d_def / (d_def + a_atk + 1)))))
            d_hp -= dmg
            log.append(f"Turn {turns}: you hit {defender['username']} for {dmg}.")
        else:
            log.append(f"Turn {turns}: you miss.")
        if d_hp <= 0:
            break
        if random.random() < hit_chance(d_atk, a_def):
            dmg = max(1, int(d_atk * random.uniform(0.8, 1.2) * (1 - min(0.6, a_def / (a_def + d_atk + 1)))))
            a_hp -= dmg
            log.append(f"Turn {turns}: {defender['username']} hits you for {dmg}.")
        else:
            log.append(f"Turn {turns}: {defender['username']} misses.")

    if a_hp <= 0 and d_hp > 0:
        outcome = "loss"
    elif d_hp <= 0 and a_hp > 0:
        outcome = "win"
    else:
        outcome = "stalemate"
    return {"outcome": outcome, "turns": turns, "a_hp": max(0, a_hp),
            "d_hp": max(0, d_hp), "log": log}


# ── Missions ─────────────────────────────────────────────────────────────────

def bump_mission(con, uid, metric, amount=1):
    day = now().strftime("%Y-%m-%d")
    rows = con.execute("SELECT id,target FROM missions WHERE metric=? AND is_daily=1",
                       (metric,)).fetchall()
    for m in rows:
        con.execute(
            "INSERT INTO player_missions(user_id,mission_id,progress,day) VALUES (?,?,0,?) "
            "ON CONFLICT(user_id,mission_id,day) DO NOTHING", (uid, m["id"], day))
        con.execute(
            "UPDATE player_missions SET progress=progress+?, "
            "completed=CASE WHEN progress+?>=? THEN 1 ELSE completed END "
            "WHERE user_id=? AND mission_id=? AND day=? AND claimed=0",
            (amount, amount, m["target"], uid, m["id"], day))


# ── Achievements ──────────────────────────────────────────────────────────────

def award(con, uid, code):
    a = con.execute("SELECT id,name,gold_reward FROM achievements WHERE code=?", (code,)).fetchone()
    if not a:
        return
    cur = con.execute(
        "INSERT OR IGNORE INTO player_achievements(user_id, achievement_id) VALUES (?,?)",
        (uid, a["id"]))
    if cur.rowcount == 1:
        con.execute("UPDATE players SET gold=gold+? WHERE user_id=?", (a["gold_reward"], uid))
        notify(con, uid, f"Achievement unlocked: {a['name']} (+{a['gold_reward']} gold)")


def check_achievements(con, uid):
    p = con.execute(
        "SELECT level,bank,respect,crimes_done,fights_won FROM players WHERE user_id=?",
        (uid,)).fetchone()
    if not p:
        return
    if p["fights_won"] >= 1:  award(con, uid, "first_blood")
    if p["crimes_done"] >= 10: award(con, uid, "crime_10")
    if p["crimes_done"] >= 100: award(con, uid, "crime_100")
    if p["level"] >= 5:  award(con, uid, "level_5")
    if p["level"] >= 10: award(con, uid, "level_10")
    if p["level"] >= 20: award(con, uid, "level_20")
    if p["bank"] >= 100000: award(con, uid, "rich_100k")
    if p["respect"] >= 1000: award(con, uid, "respect_1000")


# ── Server-wide event modifiers ───────────────────────────────────────────────

def event_modifiers(con):
    t = ts(now())
    mods = {"payout": 1.0, "xp": 1.0, "success": 0.0, "regen": 1.0}
    for ev in con.execute(
            "SELECT modifier_json FROM events WHERE is_active=1 "
            "AND (starts_at IS NULL OR starts_at<=?) AND (ends_at IS NULL OR ends_at>=?)",
            (t, t)).fetchall():
        try:
            m = json.loads(ev["modifier_json"] or "{}")
        except ValueError:
            continue
        for k in ("payout", "xp", "regen"):
            if k in m:
                mods[k] *= float(m[k])
        if "success" in m:
            mods["success"] += float(m["success"])
    return mods
