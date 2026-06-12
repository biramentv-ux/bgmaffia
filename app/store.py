from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .i18n import tf
from .auth import login_required
from .db import get_db

bp = Blueprint('store', __name__)

# ── Catalogue data (hardcoded; no DB lookup needed) ─────────────────────

GOLD_PACKAGES = [
    {'id': 1, 'name': 'Starter Pack',  'gold': 50,   'bonus': 0,   'price_usd': 1.99,  'tag': None},
    {'id': 2, 'name': 'Hustler Pack',  'gold': 150,  'bonus': 15,  'price_usd': 4.99,  'tag': 'POPULAR'},
    {'id': 3, 'name': 'Boss Pack',     'gold': 500,  'bonus': 75,  'price_usd': 14.99, 'tag': 'GREAT VALUE'},
    {'id': 4, 'name': 'Kingpin Pack',  'gold': 1200, 'bonus': 200, 'price_usd': 29.99, 'tag': None},
    {'id': 5, 'name': 'Cartel Pack',   'gold': 3000, 'bonus': 600, 'price_usd': 59.99, 'tag': 'BEST VALUE'},
]

BOOSTS = [
    {'type': 'energy_refill', 'name': 'Energy Refill',     'icon': '⚡', 'cost': 10, 'duration': None,
     'desc': 'Instantly fills your energy bar to maximum.'},
    {'type': 'nerve_refill',  'name': 'Nerve Refill',      'icon': '🔥', 'cost': 15, 'duration': None,
     'desc': 'Instantly fills your nerve bar to maximum.'},
    {'type': 'health_refill', 'name': 'Health Refill',     'icon': '❤️', 'cost': 10, 'duration': None,
     'desc': 'Instantly restores your health to maximum.'},
    {'type': 'xp_boost',      'name': '2× XP Boost',       'icon': '🌟', 'cost': 25, 'duration': 60,
     'desc': 'Double XP from all crimes and fights for 1 hour.'},
    {'type': 'crime_boost',   'name': '+25% Crime Cash',   'icon': '💰', 'cost': 30, 'duration': 60,
     'desc': '25% more cash from every crime for 1 hour.'},
    {'type': 'protection',    'name': 'Protection Bubble', 'icon': '🛡️', 'cost': 20, 'duration': 120,
     'desc': 'Immune to player attacks for 2 hours.'},
]

VIP_TIERS = [
    {'tier': 1, 'name': 'VIP Bronze', 'icon': '🥉', 'cost': 100, 'days': 7,
     'perks': ['+10% XP from all sources', '+5% crime cash', 'Bronze badge']},
    {'tier': 2, 'name': 'VIP Silver', 'icon': '🥈', 'cost': 250, 'days': 7,
     'perks': ['+25% XP from all sources', '+10% crime cash', '+5% regen speed', 'Silver badge']},
    {'tier': 3, 'name': 'VIP Gold',   'icon': '🥇', 'cost': 500, 'days': 7,
     'perks': ['+50% XP from all sources', '+20% crime cash', '+10% regen speed',
               '+10 ATK/DEF in combat', 'Gold badge & name color']},
]

_BOOST_MAP = {b['type']: b for b in BOOSTS}
_VIP_MAP   = {v['tier']: v for v in VIP_TIERS}
_PKG_MAP   = {p['id']:   p for p in GOLD_PACKAGES}


@bp.route('/store')
@login_required
def store_page():
    db  = get_db()
    uid = g.player['user_id']
    now_iso = datetime.utcnow().isoformat()
    active_rows = db.execute(
        "SELECT boost_type, expires_at FROM player_boosts WHERE user_id=? AND expires_at > ?",
        (uid, now_iso)
    ).fetchall()
    active_map = {r['boost_type']: r['expires_at'] for r in active_rows}
    txns = db.execute(
        "SELECT * FROM gold_transactions WHERE user_id=? ORDER BY ts DESC LIMIT 20",
        (uid,)
    ).fetchall()
    return render_template('store/store.html',
                           packages=GOLD_PACKAGES, boosts=BOOSTS, vip_tiers=VIP_TIERS,
                           active_map=active_map, txns=txns)


@bp.route('/store/buy_gold/<int:pkg_id>', methods=['POST'])
@login_required
def buy_gold(pkg_id):
    pkg = _PKG_MAP.get(pkg_id)
    if not pkg:
        flash(tf("Package not found."), 'error')
        return redirect(url_for('store.store_page'))

    db  = get_db()
    uid = g.player['user_id']
    total = pkg['gold'] + pkg['bonus']

    db.execute("BEGIN IMMEDIATE")
    db.execute("UPDATE players SET gold=gold+? WHERE user_id=?", (total, uid))
    db.execute(
        "INSERT INTO gold_transactions(user_id,amount,kind,ref_id) VALUES(?,?,?,?)",
        (uid, total, 'purchase', pkg_id)
    )
    db.commit()
    flash(f"✨ {pkg['name']} purchased! +{total} Gold added.", 'success')
    return redirect(url_for('store.store_page'))


@bp.route('/store/boost/<boost_type>', methods=['POST'])
@login_required
def activate_boost(boost_type):
    boost = _BOOST_MAP.get(boost_type)
    if not boost:
        flash(tf("Unknown boost."), 'error')
        return redirect(url_for('store.store_page'))

    db  = get_db()
    uid = g.player['user_id']
    cost = boost['cost']

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute(
        "SELECT gold, energy_max, nerve_max, health_max FROM players WHERE user_id=?", (uid,)
    ).fetchone())

    if player['gold'] < cost:
        db.execute("ROLLBACK")
        flash(f"Not enough Gold (need {cost}G, have {player['gold']}G).", 'error')
        return redirect(url_for('store.store_page'))

    now     = datetime.utcnow()
    now_iso = now.isoformat()
    db.execute("UPDATE players SET gold=gold-? WHERE user_id=?", (cost, uid))
    db.execute(
        "INSERT INTO gold_transactions(user_id,amount,kind,ref_id) VALUES(?,?,?,?)",
        (uid, -cost, 'boost', None)
    )

    if boost_type == 'energy_refill':
        db.execute("UPDATE players SET energy=energy_max, energy_ts=? WHERE user_id=?", (now_iso, uid))
        msg = "⚡ Energy fully restored!"
    elif boost_type == 'nerve_refill':
        db.execute("UPDATE players SET nerve=nerve_max, nerve_ts=? WHERE user_id=?", (now_iso, uid))
        msg = "🔥 Nerve fully restored!"
    elif boost_type == 'health_refill':
        db.execute("UPDATE players SET health=health_max, health_ts=? WHERE user_id=?", (now_iso, uid))
        msg = "❤️ Health fully restored!"
    elif boost_type == 'protection':
        expires = (now + timedelta(minutes=boost['duration'])).isoformat()
        db.execute("UPDATE players SET protection_until=? WHERE user_id=?", (expires, uid))
        db.execute(
            "INSERT OR REPLACE INTO player_boosts(user_id,boost_type,multiplier,expires_at) VALUES(?,?,?,?)",
            (uid, 'protection', 1.0, expires)
        )
        msg = f"🛡️ Protection active for {boost['duration']} min!"
    else:
        # Timed multiplier boosts
        expires    = (now + timedelta(minutes=boost['duration'])).isoformat()
        multiplier = 2.0 if boost_type == 'xp_boost' else 1.25
        db.execute(
            "INSERT OR REPLACE INTO player_boosts(user_id,boost_type,multiplier,expires_at) VALUES(?,?,?,?)",
            (uid, boost_type, multiplier, expires)
        )
        msg = f"{boost['icon']} {boost['name']} active for {boost['duration']} min!"

    db.commit()
    flash(msg, 'success')
    return redirect(url_for('store.store_page'))


@bp.route('/store/vip/<int:tier>', methods=['POST'])
@login_required
def buy_vip(tier):
    vip = _VIP_MAP.get(tier)
    if not vip:
        flash(tf("VIP tier not found."), 'error')
        return redirect(url_for('store.store_page'))

    db  = get_db()
    uid = g.player['user_id']
    cost = vip['cost']

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute(
        "SELECT gold, vip_tier, vip_until FROM players WHERE user_id=?", (uid,)
    ).fetchone())

    if player['gold'] < cost:
        db.execute("ROLLBACK")
        flash(f"Not enough Gold (need {cost}G, have {player['gold']}G).", 'error')
        return redirect(url_for('store.store_page'))

    now = datetime.utcnow()
    # Extend from current expiry if still active, else from now
    current_until = player.get('vip_until')
    if current_until:
        try:
            base = datetime.fromisoformat(current_until.replace(' ', 'T'))
            if base < now:
                base = now
        except Exception:
            base = now
    else:
        base = now
    new_until = (base + timedelta(days=vip['days'])).isoformat()
    # Keep the higher tier if stacking
    new_tier = max(player.get('vip_tier') or 0, tier)

    db.execute(
        "UPDATE players SET gold=gold-?, vip_tier=?, vip_until=? WHERE user_id=?",
        (cost, new_tier, new_until, uid)
    )
    db.execute(
        "INSERT INTO gold_transactions(user_id,amount,kind,ref_id) VALUES(?,?,?,?)",
        (uid, -cost, 'vip', tier)
    )
    db.commit()
    flash(f"{vip['icon']} {vip['name']} active for {vip['days']} days!", 'success')
    return redirect(url_for('store.store_page'))
