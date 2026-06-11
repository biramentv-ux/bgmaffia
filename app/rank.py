from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .i18n import tf
from .auth import login_required
from .db import get_db

bp = Blueprint('rank', __name__)


@bp.route('/leaderboard')
@login_required
def leaderboard_page():
    db = get_db()
    by_respect = db.execute(
        "SELECT u.username, p.level, p.respect, p.total_fights_won "
        "FROM players p JOIN users u ON p.user_id=u.id ORDER BY p.respect DESC LIMIT 20"
    ).fetchall()
    by_level = db.execute(
        "SELECT u.username, p.level, p.xp, p.respect "
        "FROM players p JOIN users u ON p.user_id=u.id ORDER BY p.level DESC, p.xp DESC LIMIT 20"
    ).fetchall()
    by_wealth = db.execute(
        "SELECT u.username, p.level, p.bank+p.cash as wealth "
        "FROM players p JOIN users u ON p.user_id=u.id ORDER BY wealth DESC LIMIT 20"
    ).fetchall()
    return render_template('rank/leaderboard.html',
                           by_respect=by_respect, by_level=by_level, by_wealth=by_wealth)


@bp.route('/achievements')
@login_required
def achievements_page():
    db = get_db()
    uid = g.player['user_id']
    all_ach = db.execute("SELECT * FROM achievements").fetchall()
    earned  = {r['achievement_id'] for r in db.execute(
        "SELECT achievement_id FROM player_achievements WHERE user_id=?", (uid,)
    ).fetchall()}
    return render_template('rank/achievements.html', all_ach=all_ach, earned=earned)


@bp.route('/hitlist')
@login_required
def hitlist_page():
    db = get_db()
    now_iso = datetime.utcnow().isoformat()
    bounties = db.execute(
        "SELECT b.*, u.username as target_name, up.username as placer_name, p.level as target_level "
        "FROM bounties b JOIN users u ON b.target_id=u.id JOIN users up ON b.placed_by=up.id "
        "JOIN players p ON b.target_id=p.user_id "
        "WHERE b.status='active' AND (b.expires_at IS NULL OR b.expires_at > ?) "
        "ORDER BY b.amount DESC",
        (now_iso,)
    ).fetchall()
    return render_template('rank/hitlist.html', bounties=bounties)


@bp.route('/bounty/place', methods=['POST'])
@login_required
def place_bounty():
    db = get_db()
    uid = g.player['user_id']
    target_name = request.form.get('target', '').strip()
    try:
        amount = int(request.form.get('amount', 0))
    except ValueError:
        amount = 0
    if amount < 500:
        flash(tf("Minimum bounty is $500."), 'error')
        return redirect(url_for('rank.hitlist_page'))
    target = db.execute("SELECT id FROM users WHERE username=?", (target_name,)).fetchone()
    if not target or target['id'] == uid:
        flash(tf("Player not found."), 'error')
        return redirect(url_for('rank.hitlist_page'))

    db.execute("BEGIN IMMEDIATE")
    p = dict(db.execute("SELECT cash FROM players WHERE user_id=?", (uid,)).fetchone())
    if p['cash'] < amount:
        db.execute("ROLLBACK")
        flash(tf("Not enough cash."), 'error')
        return redirect(url_for('rank.hitlist_page'))

    db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (amount, uid, amount))
    expires = (datetime.utcnow() + timedelta(days=3)).isoformat()
    db.execute(
        "INSERT INTO bounties(target_id,placed_by,amount,expires_at) VALUES(?,?,?,?)",
        (target['id'], uid, amount, expires)
    )
    db.commit()
    flash(f"☠️ Bounty of ${amount:,} placed on {target_name}.", 'success')
    return redirect(url_for('rank.hitlist_page'))
