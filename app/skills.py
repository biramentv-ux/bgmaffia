from flask import Blueprint, render_template, redirect, url_for, flash, g
from .i18n import tf
from .auth import login_required
from .db import get_db

bp = Blueprint('skills', __name__)

CATEGORIES = ['combat', 'criminal', 'survival', 'hustle']
CAT_LABELS  = {'combat': '⚔️ Combat', 'criminal': '🔫 Criminal',
               'survival': '❤️ Survival', 'hustle': '💰 Hustle'}


@bp.route('/skills')
@login_required
def skills_page():
    db  = get_db()
    uid = g.player['user_id']
    all_skills = db.execute(
        "SELECT * FROM skills ORDER BY category, cost", ()
    ).fetchall()
    unlocked = {r['skill_code'] for r in db.execute(
        "SELECT skill_code FROM player_skills WHERE user_id=?", (uid,)
    ).fetchall()}
    by_cat = {c: [] for c in CATEGORIES}
    for s in all_skills:
        by_cat[s['category']].append(s)
    return render_template('skills/skills.html',
                           by_cat=by_cat, cat_labels=CAT_LABELS,
                           unlocked=unlocked, player=g.player)


@bp.route('/skills/unlock/<skill_code>', methods=['POST'])
@login_required
def unlock_skill(skill_code):
    db  = get_db()
    uid = g.player['user_id']

    skill = db.execute("SELECT * FROM skills WHERE code=?", (skill_code,)).fetchone()
    if not skill:
        flash(tf("Skill not found."), 'error')
        return redirect(url_for('skills.skills_page'))

    db.execute("BEGIN IMMEDIATE")
    player   = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())
    unlocked = {r['skill_code'] for r in db.execute(
        "SELECT skill_code FROM player_skills WHERE user_id=?", (uid,)
    ).fetchall()}

    if skill_code in unlocked:
        db.execute("ROLLBACK")
        flash("Skill already unlocked.", 'error')
        return redirect(url_for('skills.skills_page'))

    if skill['requires'] and skill['requires'] not in unlocked:
        db.execute("ROLLBACK")
        flash(f"Requires '{skill['requires']}' to be unlocked first.", 'error')
        return redirect(url_for('skills.skills_page'))

    if player['skill_points'] < skill['cost']:
        db.execute("ROLLBACK")
        flash(f"Not enough skill points (need {skill['cost']}, have {player['skill_points']}).", 'error')
        return redirect(url_for('skills.skills_page'))

    db.execute("UPDATE players SET skill_points=skill_points-? WHERE user_id=?",
               (skill['cost'], uid))
    db.execute("INSERT INTO player_skills(user_id,skill_code) VALUES(?,?)", (uid, skill_code))

    # iron_will: permanent +25 max health immediately
    if skill_code == 'iron_will':
        db.execute("UPDATE players SET health_max=health_max+25, health=MIN(health+25,health_max+25) WHERE user_id=?",
                   (uid,))

    db.commit()
    flash(f"✅ Unlocked {skill['icon']} {skill['name']}!", 'success')
    return redirect(url_for('skills.skills_page'))
