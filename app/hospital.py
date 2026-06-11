from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .auth import login_required
from .db import get_db

bp = Blueprint('hospital', __name__)

HEAL_COST_PER_MINUTE = 100  # $100 per minute off recovery


@bp.route('/hospital')
@login_required
def hospital_page():
    player = g.player
    now_iso = datetime.utcnow().isoformat()
    hosp_until = player.get('hospital_until') or ''
    in_hospital = hosp_until > now_iso if hosp_until else False
    minutes_left = 0
    heal_cost = 0
    if in_hospital:
        try:
            delta = (datetime.fromisoformat(hosp_until) - datetime.utcnow()).total_seconds()
            minutes_left = max(0, int(delta // 60))
            heal_cost = minutes_left * HEAL_COST_PER_MINUTE
        except Exception:
            pass
    return render_template('hospital/hospital.html',
                           in_hospital=in_hospital,
                           hosp_until=hosp_until,
                           minutes_left=minutes_left,
                           heal_cost=heal_cost)


@bp.route('/hospital/heal', methods=['POST'])
@login_required
def heal():
    db = get_db()
    uid = g.player['user_id']
    now_iso = datetime.utcnow().isoformat()

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())
    hosp_until = player.get('hospital_until') or ''
    if hosp_until <= now_iso:
        db.execute("ROLLBACK")
        flash("You're not in the hospital.", 'info')
        return redirect(url_for('hospital.hospital_page'))

    try:
        delta = (datetime.fromisoformat(hosp_until) - datetime.utcnow()).total_seconds()
        minutes_left = max(0, int(delta // 60))
    except Exception:
        minutes_left = 0

    heal_cost = minutes_left * HEAL_COST_PER_MINUTE
    if player['cash'] < heal_cost:
        db.execute("ROLLBACK")
        flash(f"Not enough cash. Need ${heal_cost:,} to leave hospital now.", 'error')
        return redirect(url_for('hospital.hospital_page'))

    db.execute(
        "UPDATE players SET hospital_until=NULL, health=health_max, cash=cash-? WHERE user_id=? AND cash>=?",
        (heal_cost, uid, heal_cost)
    )
    db.commit()
    flash(f"🏥 You paid ${heal_cost:,} and left the hospital at full health.", 'success')
    return redirect(url_for('home.dashboard'))
