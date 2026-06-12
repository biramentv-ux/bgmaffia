import random
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .i18n import tf
from .auth import login_required
from .db import get_db
from .game import (crime_success_chance, maybe_level_up, mission_progress,
                   check_achievements, _notify,
                   get_active_boost, get_vip_tier, VIP_CASH_MULT, VIP_XP_MULT)

bp = Blueprint('crimes', __name__)


@bp.route('/crimes')
@login_required
def crimes_page():
    db = get_db()
    player = g.player
    crimes = db.execute("SELECT * FROM crimes WHERE min_level <= ? ORDER BY min_level", (player['level'],)).fetchall()
    now_iso = datetime.utcnow().isoformat()
    cooldowns = {
        r['crime_id']: r['next_at']
        for r in db.execute("SELECT crime_id, next_at FROM crime_cooldowns WHERE user_id=?", (player['user_id'],)).fetchall()
    }
    return render_template('crimes/crimes.html', crimes=crimes, cooldowns=cooldowns, now_iso=now_iso)


@bp.route('/crimes/<int:crime_id>/commit', methods=['POST'])
@login_required
def commit(crime_id):
    db = get_db()
    uid = g.player['user_id']
    now = datetime.utcnow()
    now_iso = now.isoformat()

    crime = db.execute("SELECT * FROM crimes WHERE id=?", (crime_id,)).fetchone()
    if not crime:
        flash(tf("Crime not found."), 'error')
        return redirect(url_for('crimes.crimes_page'))

    # All validation inside a transaction
    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())

    # Level check
    if player['level'] < crime['min_level']:
        db.execute("ROLLBACK")
        flash("You're not high enough level for that crime.", 'error')
        return redirect(url_for('crimes.crimes_page'))

    # Energy check
    if player['energy'] < crime['energy_cost']:
        db.execute("ROLLBACK")
        flash(f"Not enough energy (need {crime['energy_cost']}, have {player['energy']}).", 'error')
        return redirect(url_for('crimes.crimes_page'))

    # Cooldown check
    cd = db.execute("SELECT next_at FROM crime_cooldowns WHERE user_id=? AND crime_id=?", (uid, crime_id)).fetchone()
    if cd and cd['next_at'] > now_iso:
        db.execute("ROLLBACK")
        flash(tf("This crime is still on cooldown."), 'error')
        return redirect(url_for('crimes.crimes_page'))

    # Compute success
    success_chance = crime_success_chance(crime, player)
    succeeded = random.random() < success_chance
    payout = 0

    if succeeded:
        payout = random.randint(crime['payout_min'], crime['payout_max'])
        xp_gain = crime['xp_reward']
        # Apply active boosts and VIP multipliers
        vip = get_vip_tier(player)
        crime_mult = (get_active_boost(db, uid, 'crime_boost') or 1.0) * VIP_CASH_MULT.get(vip, 1.0)
        xp_mult    = (get_active_boost(db, uid, 'xp_boost')   or 1.0) * VIP_XP_MULT.get(vip, 1.0)
        payout  = int(payout  * crime_mult)
        xp_gain = int(xp_gain * xp_mult)
        db.execute(
            "UPDATE players SET energy=energy-?, cash=cash+?, xp=xp+?, respect=respect+?, "
            "total_crimes=total_crimes+?, total_earned=total_earned+? WHERE user_id=? AND energy>=?",
            (crime['energy_cost'], payout, xp_gain, max(1, xp_gain // 10),
             1, payout, uid, crime['energy_cost'])
        )
    else:
        # Failed – possible jail
        jailed = random.random() < 0.35  # 35% chance of jail on failure
        db.execute(
            "UPDATE players SET energy=energy-?, total_crimes=total_crimes+? WHERE user_id=? AND energy>=?",
            (crime['energy_cost'], 1, uid, crime['energy_cost'])
        )
        if jailed:
            db.execute(
                "UPDATE players SET jail_until=datetime('now',?), cash=0 WHERE user_id=?",
                (f'+{crime["jail_sec"]} seconds', uid)
            )
            db.execute("UPDATE players SET total_crimes=total_crimes-1 WHERE user_id=?", (uid,))  # undo double-count

    # Set cooldown
    next_at = (now.timestamp() + crime['cooldown_sec'])
    next_at_iso = datetime.utcfromtimestamp(next_at).isoformat()
    db.execute(
        "INSERT INTO crime_cooldowns(user_id,crime_id,next_at) VALUES(?,?,?) "
        "ON CONFLICT(user_id,crime_id) DO UPDATE SET next_at=?",
        (uid, crime_id, next_at_iso, next_at_iso)
    )

    db.execute("INSERT INTO crime_log(user_id,crime_id,success,payout) VALUES(?,?,?,?)",
               (uid, crime_id, int(succeeded), payout))
    db.commit()

    # Post-commit: level-up check, mission progress
    player = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())
    maybe_level_up(db, uid, player)
    mission_progress(db, uid, 'crimes')
    if succeeded:
        mission_progress(db, uid, 'earned', payout)
    check_achievements(db, uid)

    if succeeded:
        flash(f"✅ {crime['name']} succeeded! +${payout:,}", 'success')
    else:
        msg = "❌ You got caught and thrown in jail!" if player.get('jail_until') else "❌ The crime failed."
        flash(msg, 'error')
        if player.get('jail_until'):
            return redirect(url_for('jail.jail_page'))

    return redirect(url_for('crimes.crimes_page'))
