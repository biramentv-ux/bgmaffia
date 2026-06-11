from flask import Blueprint, render_template, g
from .auth import login_required
from .db import get_db
from .game import xp_for_level

bp = Blueprint('home', __name__)


@bp.route('/')
@login_required
def dashboard():
    player = g.player
    db = get_db()
    xp_needed = xp_for_level(player['level'])
    recent_crimes = db.execute(
        "SELECT cl.*, c.name FROM crime_log cl JOIN crimes c ON cl.crime_id=c.id "
        "WHERE cl.user_id=? ORDER BY cl.ts DESC LIMIT 5", (player['user_id'],)
    ).fetchall()
    recent_fights = db.execute(
        "SELECT f.*, ua.username as atk_name, ud.username as def_name "
        "FROM fights f JOIN users ua ON f.attacker_id=ua.id JOIN users ud ON f.defender_id=ud.id "
        "WHERE f.attacker_id=? OR f.defender_id=? ORDER BY f.ts DESC LIMIT 5",
        (player['user_id'], player['user_id'])
    ).fetchall()
    notif_count = db.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (player['user_id'],)
    ).fetchone()[0]
    mail_count = db.execute(
        "SELECT COUNT(*) FROM messages WHERE to_id=? AND is_read=0", (player['user_id'],)
    ).fetchone()[0]
    gang = None
    if player['gang_id']:
        gang = db.execute("SELECT * FROM gangs WHERE id=?", (player['gang_id'],)).fetchone()
    return render_template('home/dashboard.html',
                           xp_needed=xp_needed,
                           recent_crimes=recent_crimes,
                           recent_fights=recent_fights,
                           notif_count=notif_count,
                           mail_count=mail_count,
                           gang=gang)


@bp.route('/profile/<int:uid>')
@login_required
def profile(uid):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        return "Player not found", 404
    player = db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone()
    achievements = db.execute(
        "SELECT a.name, a.descr, pa.earned_at FROM player_achievements pa JOIN achievements a ON a.id=pa.achievement_id WHERE pa.user_id=?",
        (uid,)
    ).fetchall()
    gang = None
    if player['gang_id']:
        gang = db.execute("SELECT * FROM gangs WHERE id=?", (player['gang_id'],)).fetchone()
    weapon = car = dog = armor = None
    if player['equipped_weapon']:
        weapon = db.execute("SELECT name FROM items WHERE id=?", (player['equipped_weapon'],)).fetchone()
    if player['equipped_car']:
        car = db.execute("SELECT name FROM items WHERE id=?", (player['equipped_car'],)).fetchone()
    if player['equipped_dog']:
        dog = db.execute("SELECT name FROM items WHERE id=?", (player['equipped_dog'],)).fetchone()
    if player['equipped_armor']:
        armor = db.execute("SELECT name FROM items WHERE id=?", (player['equipped_armor'],)).fetchone()
    return render_template('home/profile.html',
                           puser=user, player=dict(player),
                           achievements=achievements,
                           gang=gang,
                           weapon=weapon, car=car, dog=dog, armor=armor)
