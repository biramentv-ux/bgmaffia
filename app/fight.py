from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .i18n import tf
from .auth import login_required
from .db import get_db
from .game import resolve_fight, is_in_jail, is_in_hospital, is_protected, is_online, mission_progress, check_achievements

bp = Blueprint('fight', __name__)

ONLINE_MINUTES = 5


@bp.route('/attack')
@login_required
def attack_page():
    db = get_db()
    uid = g.player['user_id']
    level = g.player['level']
    now_iso = datetime.utcnow().isoformat()
    cutoff = f"datetime('now', '-{ONLINE_MINUTES} minutes')"

    targets = db.execute(
        f"""SELECT u.id, u.username, u.last_active, p.level, p.respect, p.health,
               p.jail_until, p.hospital_until, p.protection_until,
               p.equipped_weapon, p.equipped_car, p.equipped_dog
            FROM users u JOIN players p ON u.id=p.user_id
            WHERE u.id != ?
              AND u.last_active >= {cutoff}
              AND (p.jail_until IS NULL OR p.jail_until <= ?)
              AND (p.hospital_until IS NULL OR p.hospital_until <= ?)
              AND (p.protection_until IS NULL OR p.protection_until <= ?)
              AND u.is_banned = 0
            ORDER BY p.level DESC""",
        (uid, now_iso, now_iso, now_iso)
    ).fetchall()

    return render_template('fight/attack.html', targets=targets, now_iso=now_iso)


@bp.route('/attack/<int:target_id>', methods=['POST'])
@login_required
def attack(target_id):
    db = get_db()
    uid = g.player['user_id']
    now_iso = datetime.utcnow().isoformat()

    if target_id == uid:
        flash("You can't attack yourself.", 'error')
        return redirect(url_for('fight.attack_page'))

    # Validate attacker
    db.execute("BEGIN IMMEDIATE")
    attacker = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())
    if attacker['health'] < 10:
        db.execute("ROLLBACK")
        flash("You're too injured to fight (need at least 10 HP).", 'error')
        return redirect(url_for('fight.attack_page'))

    # Validate target
    target_p = db.execute("SELECT * FROM players WHERE user_id=?", (target_id,)).fetchone()
    target_u = db.execute("SELECT * FROM users WHERE id=?", (target_id,)).fetchone()
    if not target_p or not target_u:
        db.execute("ROLLBACK")
        flash(tf("Target not found."), 'error')
        return redirect(url_for('fight.attack_page'))
    target_p = dict(target_p)

    if not is_online(target_u):
        db.execute("ROLLBACK")
        flash(tf("That player is no longer online."), 'error')
        return redirect(url_for('fight.attack_page'))
    if is_in_jail(target_p) or is_in_hospital(target_p) or is_protected(target_p):
        db.execute("ROLLBACK")
        flash(tf("That player cannot be attacked right now."), 'error')
        return redirect(url_for('fight.attack_page'))
    db.execute("ROLLBACK")

    result = resolve_fight(db, uid, target_id)
    mission_progress(db, uid, 'wins')
    check_achievements(db, uid)

    flash(f"⚔️ {result['outcome']} ({result['turns']} turns)", 'success' if result['winner_id'] == uid else 'error')
    return redirect(url_for('fight.fight_log_page', fight_id=db.execute("SELECT MAX(id) FROM fights WHERE attacker_id=?", (uid,)).fetchone()[0]))


@bp.route('/fight/<int:fight_id>')
@login_required
def fight_log_page(fight_id):
    db = get_db()
    fight = db.execute(
        "SELECT f.*, ua.username as atk_name, ud.username as def_name "
        "FROM fights f JOIN users ua ON f.attacker_id=ua.id JOIN users ud ON f.defender_id=ud.id "
        "WHERE f.id=?", (fight_id,)
    ).fetchone()
    if not fight:
        return "Fight not found", 404
    return render_template('fight/fight_log.html', fight=fight)
