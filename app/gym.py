import math
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .auth import login_required
from .db import get_db
from .game import maybe_level_up, check_achievements, mission_progress

bp = Blueprint('gym', __name__)

STATS = ['strength', 'stamina', 'intellect', 'sexappeal']
STAT_LABELS = {
    'strength':  ('⚔️ Strength',   'Increases attack power in fights'),
    'stamina':   ('🛡️ Stamina',    'Increases defense in fights'),
    'intellect': ('🧠 Intellect',  'Improves success on smart crimes'),
    'sexappeal': ('😎 Sex Appeal', 'Unlocks special interactions'),
}


def energy_cost(stat_level):
    return max(1, math.ceil(stat_level / 4))


@bp.route('/gym')
@login_required
def gym_page():
    player = g.player
    costs = {s: energy_cost(player[s]) for s in STATS}
    return render_template('gym/gym.html', stats=STATS, labels=STAT_LABELS, costs=costs)


@bp.route('/gym/train', methods=['POST'])
@login_required
def train():
    stat = request.form.get('stat')
    if stat not in STATS:
        flash("Invalid stat.", 'error')
        return redirect(url_for('gym.gym_page'))

    db = get_db()
    uid = g.player['user_id']

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())
    cost = energy_cost(player[stat])

    if player['energy'] < cost:
        db.execute("ROLLBACK")
        flash(f"Not enough energy (need {cost}).", 'error')
        return redirect(url_for('gym.gym_page'))

    db.execute(
        f"UPDATE players SET energy=energy-?, {stat}={stat}+1 WHERE user_id=? AND energy>=?",
        (cost, uid, cost)
    )
    db.commit()

    player = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())
    maybe_level_up(db, uid, player)
    mission_progress(db, uid, 'trains')
    check_achievements(db, uid)

    label = STAT_LABELS[stat][0]
    flash(f"💪 {label} is now {player[stat]}! (cost {cost} energy)", 'success')
    return redirect(url_for('gym.gym_page'))
