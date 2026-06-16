"""store.py — pay-to-win: gold packages, VIP tiers, instant boosts.
Purchases are simulated (no real payment). Extend with Stripe in production.
"""
from datetime import timedelta

from flask import Blueprint, g, render_template, request, redirect, url_for, flash

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf
from game import notify, now, ts, parse, get_vip_tier

bp = Blueprint("store", __name__)

GOLD_PACKAGES = [
    {"id": "g50",   "gold": 50,   "price": 1.99,  "label": "Starter"},
    {"id": "g200",  "gold": 200,  "price": 4.99,  "label": "Hustler"},
    {"id": "g600",  "gold": 600,  "price": 9.99,  "label": "Operator", "bonus": "🔥 Best value"},
    {"id": "g1500", "gold": 1500, "price": 19.99, "label": "Kingpin"},
    {"id": "g3600", "gold": 3600, "price": 59.99, "label": "Cartel", "bonus": "⭐ Best deal"},
]

BOOSTS = [
    {"type": "xp_boost",       "name": "XP Boost",        "desc": "2× XP for 1 hour",          "gold": 20, "duration_min": 60},
    {"type": "cash_boost",     "name": "Cash Boost",       "desc": "2× crime payouts for 1 hour","gold": 25, "duration_min": 60},
    {"type": "energy_refill",  "name": "Energy Refill",    "desc": "Instantly fill energy to max","gold": 15},
    {"type": "nerve_refill",   "name": "Nerve Refill",     "desc": "Instantly fill nerve to max", "gold": 10},
    {"type": "health_refill",  "name": "Health Refill",    "desc": "Instantly restore full health","gold": 15},
    {"type": "protection",     "name": "Shield",           "desc": "1 hour PvP protection",       "gold": 30, "duration_min": 60},
]

VIP_TIERS = [
    {"tier": 1, "name": "Bronze VIP", "gold": 100, "days": 30,
     "perks": ["+10% XP", "+5% cash", "Priority support"]},
    {"tier": 2, "name": "Silver VIP", "gold": 250, "days": 30,
     "perks": ["+25% XP", "+10% cash", "+5% regen", "Silver badge"]},
    {"tier": 3, "name": "Gold VIP",   "gold": 600, "days": 30,
     "perks": ["+50% XP", "+20% cash", "+10% regen", "+10 combat", "Gold badge"]},
]


@bp.route("/store")
@login_required
def store():
    con = get_db()
    uid = g.user["user_id"]
    # get current boost expiry for each type
    boost_status = {}
    for b in BOOSTS:
        row = con.execute(
            "SELECT expires_at FROM player_boosts WHERE user_id=? AND boost_type=?",
            (uid, b["type"])).fetchone()
        if row and row["expires_at"] and parse(row["expires_at"]) > now():
            boost_status[b["type"]] = row["expires_at"]
    history = con.execute(
        "SELECT * FROM gold_transactions WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (uid,)).fetchall()
    vip = get_vip_tier(g.user)
    return render_template("store.html",
                           packages=GOLD_PACKAGES, boosts=BOOSTS, vip_tiers=VIP_TIERS,
                           boost_status=boost_status, history=history, current_vip=vip)


@bp.route("/store/buy_gold/<pkg_id>", methods=("POST",))
@login_required
def buy_gold(pkg_id):
    check_csrf()
    pkg = next((p for p in GOLD_PACKAGES if p["id"] == pkg_id), None)
    if not pkg:
        flash("Package not found.")
        return redirect(url_for("store.store"))
    con = get_db()
    uid = g.user["user_id"]
    con.execute("UPDATE players SET gold=gold+? WHERE user_id=?", (pkg["gold"], uid))
    con.execute(
        "INSERT INTO gold_transactions(user_id,kind,gold_delta,note) VALUES (?,?,?,?)",
        (uid, "purchase", pkg["gold"], f"{pkg['label']} pack (simulated)"))
    con.commit()
    flash(f"Purchased {pkg['gold']} Gold ({pkg['label']} pack). Demo mode — no charge.")
    return redirect(url_for("store.store"))


@bp.route("/store/boost/<boost_type>", methods=("POST",))
@login_required
def activate_boost(boost_type):
    check_csrf()
    boost = next((b for b in BOOSTS if b["type"] == boost_type), None)
    if not boost:
        flash("Unknown boost.")
        return redirect(url_for("store.store"))
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        guarded(c, "UPDATE players SET gold=gold-? WHERE user_id=? AND gold>=?",
                (boost["gold"], uid, boost["gold"]))
        c.execute(
            "INSERT INTO gold_transactions(user_id,kind,gold_delta,note) VALUES (?,?,?,?)",
            (uid, "boost", -boost["gold"], boost["name"]))
        if boost_type == "energy_refill":
            c.execute("UPDATE players SET energy=energy_max WHERE user_id=?", (uid,))
        elif boost_type == "nerve_refill":
            c.execute("UPDATE players SET nerve=nerve_max WHERE user_id=?", (uid,))
        elif boost_type == "health_refill":
            c.execute("UPDATE players SET health=health_max WHERE user_id=?", (uid,))
        elif boost_type == "protection":
            expires = ts(now() + timedelta(minutes=boost["duration_min"]))
            c.execute("UPDATE players SET protection_until=? WHERE user_id=?", (expires, uid))
        elif "duration_min" in boost:
            expires = ts(now() + timedelta(minutes=boost["duration_min"]))
            c.execute(
                "INSERT INTO player_boosts(user_id,boost_type,expires_at) VALUES (?,?,?) "
                "ON CONFLICT(user_id,boost_type) DO UPDATE SET expires_at=?",
                (uid, boost_type, expires, expires))
    try:
        transact(con, work)
        flash(f"{boost['name']} activated!")
    except TxFailed:
        flash("Not enough Gold.")
    return redirect(url_for("store.store"))


@bp.route("/store/vip/<int:tier>", methods=("POST",))
@login_required
def buy_vip(tier):
    check_csrf()
    vip = next((v for v in VIP_TIERS if v["tier"] == tier), None)
    if not vip:
        flash("VIP tier not found.")
        return redirect(url_for("store.store"))
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        p = c.execute("SELECT vip_until, vip_tier FROM players WHERE user_id=?", (uid,)).fetchone()
        current_tier = p["vip_tier"] or 0
        is_active = p["vip_until"] and parse(p["vip_until"]) > now()
        # Prevent lower-tier purchase from extending a higher-tier subscription
        if is_active and current_tier > tier:
            raise TxFailed("higher_tier")
        guarded(c, "UPDATE players SET gold=gold-? WHERE user_id=? AND gold>=?",
                (vip["gold"], uid, vip["gold"]))
        base = now()
        # Only extend from current expiry when upgrading or renewing the same tier
        if is_active and current_tier == tier:
            base = parse(p["vip_until"])
        new_until = ts(base + timedelta(days=vip["days"]))
        c.execute("UPDATE players SET vip_tier=?, vip_until=? WHERE user_id=?",
                  (tier, new_until, uid))
        c.execute(
            "INSERT INTO gold_transactions(user_id,kind,gold_delta,note) VALUES (?,?,?,?)",
            (uid, "vip", -vip["gold"], f"{vip['name']} x{vip['days']}d"))
        notify(c, uid, f"VIP activated: {vip['name']} for {vip['days']} days!")
    try:
        transact(con, work)
        flash(f"{vip['name']} activated for {vip['days']} days!")
    except TxFailed as e:
        if str(e) == "higher_tier":
            flash("You already have a higher-tier VIP active. Renew or upgrade instead.")
        else:
            flash("Not enough Gold.")
    return redirect(url_for("store.store"))
