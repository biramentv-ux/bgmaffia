from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .i18n import tf
from .auth import login_required
from .db import get_db
from .game import is_in_jail

bp = Blueprint('jail', __name__)

BAIL_COST_PER_MINUTE = 200
BUST_NERVE_COST = 2
BUST_SELF_NERVE_COST = 3


@bp.route('/jail')
@login_required
def jail_page():
    db = get_db()
    uid = g.player['user_id']
    now_iso = datetime.utcnow().isoformat()
    player = g.player
    jail_until = player.get('jail_until') or ''
    in_jail = jail_until > now_iso if jail_until else False
    minutes_left = 0
    bail_cost = 0
    if in_jail:
        try:
            delta = (datetime.fromisoformat(jail_until) - datetime.utcnow()).total_seconds()
            minutes_left = max(0, int(delta // 60) + 1)
            bail_cost = minutes_left * BAIL_COST_PER_MINUTE
        except Exception:
            pass

    # Inmates list (other jailed players that can be busted)
    inmates = db.execute(
        "SELECT u.id, u.username, p.level, p.respect, p.jail_until "
        "FROM players p JOIN users u ON p.user_id=u.id "
        "WHERE p.jail_until > ? AND u.id != ? ORDER BY p.jail_until",
        (now_iso, uid)
    ).fetchall()

    return render_template('jail/jail.html',
                           in_jail=in_jail,
                           jail_until=jail_until,
                           minutes_left=minutes_left,
                           bail_cost=bail_cost,
                           inmates=inmates)


@bp.route('/jail/bail', methods=['POST'])
@login_required
def bail():
    db = get_db()
    uid = g.player['user_id']
    now_iso = datetime.utcnow().isoformat()

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())
    jail_until = player.get('jail_until') or ''
    if jail_until <= now_iso:
        db.execute("ROLLBACK")
        flash("You're not in jail.", 'info')
        return redirect(url_for('home.dashboard'))

    try:
        delta = (datetime.fromisoformat(jail_until) - datetime.utcnow()).total_seconds()
        minutes_left = max(0, int(delta // 60) + 1)
    except Exception:
        minutes_left = 0

    bail_cost = minutes_left * BAIL_COST_PER_MINUTE
    if player['cash'] < bail_cost:
        db.execute("ROLLBACK")
        flash(f"Not enough cash. Bail is ${bail_cost:,}.", 'error')
        return redirect(url_for('jail.jail_page'))

    db.execute(
        "UPDATE players SET jail_until=NULL, cash=cash-? WHERE user_id=? AND cash>=?",
        (bail_cost, uid, bail_cost)
    )
    db.commit()
    flash(f"🔓 You paid ${bail_cost:,} bail and are free!", 'success')
    return redirect(url_for('home.dashboard'))


@bp.route('/jail/bust/<int:target_id>', methods=['POST'])
@login_required
def bust(target_id):
    """Bust another player out of jail (costs nerve)."""
    db = get_db()
    uid = g.player['user_id']
    now_iso = datetime.utcnow().isoformat()

    db.execute("BEGIN IMMEDIATE")
    buster = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())
    if is_in_jail(buster):
        db.execute("ROLLBACK")
        flash("You're in jail – you can't bust others.", 'error')
        return redirect(url_for('jail.jail_page'))
    if buster['nerve'] < BUST_NERVE_COST:
        db.execute("ROLLBACK")
        flash(f"Not enough nerve (need {BUST_NERVE_COST}).", 'error')
        return redirect(url_for('jail.jail_page'))

    inmate_p = db.execute("SELECT * FROM players WHERE user_id=?", (target_id,)).fetchone()
    if not inmate_p or not (inmate_p['jail_until'] or '') > now_iso:
        db.execute("ROLLBACK")
        flash("That player isn't in jail.", 'error')
        return redirect(url_for('jail.jail_page'))

    db.execute("UPDATE players SET nerve=nerve-? WHERE user_id=? AND nerve>=?",
               (BUST_NERVE_COST, uid, BUST_NERVE_COST))
    db.execute("UPDATE players SET jail_until=NULL WHERE user_id=?", (target_id,))
    db.commit()

    target_name = db.execute("SELECT username FROM users WHERE id=?", (target_id,)).fetchone()['username']
    from .game import _notify
    _notify(db, target_id, f"🔓 {buster['user_id']} busted you out of jail!")
    db.commit()
    flash(f"✅ You busted {target_name} out of jail! (-{BUST_NERVE_COST} nerve)", 'success')
    return redirect(url_for('jail.jail_page'))
