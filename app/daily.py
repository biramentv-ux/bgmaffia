from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, g, current_app
from .i18n import tf
from .auth import login_required
from .db import get_db

bp = Blueprint('daily', __name__)


def _today():
    return datetime.utcnow().date()


def _get_streak(db, uid):
    row = db.execute("SELECT * FROM daily_rewards WHERE user_id=?", (uid,)).fetchone()
    return dict(row) if row else {'user_id': uid, 'streak': 0, 'last_claimed': None}


@bp.route('/daily')
@login_required
def daily_page():
    db = get_db()
    uid = g.player['user_id']
    streak = _get_streak(db, uid)
    claimed_today = streak['last_claimed'] == _today().isoformat()
    base = current_app.config['DAILY_REWARD_BASE']
    cap = current_app.config['DAILY_STREAK_CAP']
    next_day = streak['streak'] + 1 if streak['last_claimed'] == (_today() - timedelta(days=1)).isoformat() else 1
    next_reward = base * min(next_day, cap)
    return render_template('daily/daily.html',
                           streak=streak, claimed_today=claimed_today,
                           next_day=next_day, next_reward=next_reward,
                           gold_bonus=(next_day % 7 == 0))


@bp.route('/daily/claim', methods=['POST'])
@login_required
def claim():
    db = get_db()
    uid = g.player['user_id']
    today = _today()
    base = current_app.config['DAILY_REWARD_BASE']
    cap = current_app.config['DAILY_STREAK_CAP']

    db.execute("BEGIN IMMEDIATE")
    row = db.execute("SELECT * FROM daily_rewards WHERE user_id=?", (uid,)).fetchone()
    last = row['last_claimed'] if row else None
    if last == today.isoformat():
        db.execute("ROLLBACK")
        flash(tf("Already claimed today — come back tomorrow."), 'error')
        return redirect(url_for('daily.daily_page'))

    streak = (row['streak'] + 1) if (row and last == (today - timedelta(days=1)).isoformat()) else 1
    reward = base * min(streak, cap)
    gold = 1 if streak % 7 == 0 else 0

    if row:
        db.execute("UPDATE daily_rewards SET streak=?, last_claimed=? WHERE user_id=?",
                   (streak, today.isoformat(), uid))
    else:
        db.execute("INSERT INTO daily_rewards(user_id, streak, last_claimed) VALUES(?,?,?)",
                   (uid, streak, today.isoformat()))
    db.execute("UPDATE players SET cash=cash+?, gold=gold+? WHERE user_id=?", (reward, gold, uid))
    db.commit()

    msg = f"🎁 Day {streak} reward claimed: ${reward:,}"
    if gold:
        msg += " + 1 ✨ gold (weekly streak bonus)"
    flash(msg, 'success')
    return redirect(url_for('daily.daily_page'))
