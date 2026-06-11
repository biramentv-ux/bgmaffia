import json
from flask import Blueprint, render_template, redirect, url_for, flash, g
from .auth import login_required
from .db import get_db

bp = Blueprint('missions', __name__)


@bp.route('/missions')
@login_required
def missions_page():
    db = get_db()
    uid = g.player['user_id']
    today = __import__('datetime').datetime.utcnow().date().isoformat()

    missions = db.execute("SELECT * FROM missions ORDER BY is_daily, id").fetchall()
    progress = {
        r['mission_id']: dict(r)
        for r in db.execute(
            "SELECT * FROM player_missions WHERE user_id=?", (uid,)
        ).fetchall()
    }
    # Reset daily missions if stale
    for m in missions:
        if m['is_daily']:
            pm = progress.get(m['id'], {})
            if pm.get('last_reset') != today and pm.get('completed'):
                db.execute(
                    "UPDATE player_missions SET progress=0, completed=0, last_reset=? WHERE user_id=? AND mission_id=?",
                    (today, uid, m['id'])
                )
                progress[m['id']] = {'progress': 0, 'completed': 0, 'last_reset': today}
    db.commit()

    missions_data = []
    for m in missions:
        pm = progress.get(m['id'], {'progress': 0, 'completed': 0})
        req = json.loads(m['req_json'] or '{}')
        target = list(req.values())[0] if req else 1
        missions_data.append({
            'id': m['id'],
            'descr': m['descr'],
            'reward': json.loads(m['reward_json']),
            'is_daily': m['is_daily'],
            'progress': pm.get('progress', 0),
            'target': target,
            'completed': pm.get('completed', 0),
        })
    return render_template('missions/missions.html', missions=missions_data)
