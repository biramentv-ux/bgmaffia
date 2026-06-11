from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, g, request, session
from .auth import login_required
from .db import get_db

bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        db = get_db()
        user = db.execute("SELECT is_admin FROM users WHERE id=?", (session['user_id'],)).fetchone()
        if not user or not user['is_admin']:
            flash("Admin access required.", 'error')
            return redirect(url_for('home.dashboard'))
        return f(*args, **kwargs)
    return wrapped


@bp.route('/')
@admin_required
def admin_page():
    db = get_db()
    stats = {
        'users': db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'active_today': db.execute("SELECT COUNT(*) FROM users WHERE last_active >= datetime('now','-1 day')").fetchone()[0],
        'crimes_today': db.execute("SELECT COUNT(*) FROM crime_log WHERE ts >= datetime('now','-1 day')").fetchone()[0],
        'fights_today': db.execute("SELECT COUNT(*) FROM fights WHERE ts >= datetime('now','-1 day')").fetchone()[0],
    }
    users = db.execute(
        "SELECT u.*, p.level, p.respect, p.cash+p.bank as wealth FROM users u JOIN players p ON u.id=p.user_id ORDER BY u.id DESC LIMIT 50"
    ).fetchall()
    crimes = db.execute("SELECT * FROM crimes ORDER BY min_level").fetchall()
    items  = db.execute("SELECT * FROM items ORDER BY type, price").fetchall()
    return render_template('admin/admin.html', stats=stats, users=users, crimes=crimes, items=items)


@bp.route('/ban/<int:uid>', methods=['POST'])
@admin_required
def ban_user(uid):
    db = get_db()
    db.execute("UPDATE users SET is_banned=1 WHERE id=?", (uid,))
    db.commit()
    flash(f"User {uid} banned.", 'success')
    return redirect(url_for('admin.admin_page'))


@bp.route('/unban/<int:uid>', methods=['POST'])
@admin_required
def unban_user(uid):
    db = get_db()
    db.execute("UPDATE users SET is_banned=0 WHERE id=?", (uid,))
    db.commit()
    flash(f"User {uid} unbanned.", 'success')
    return redirect(url_for('admin.admin_page'))


@bp.route('/grant_admin/<int:uid>', methods=['POST'])
@admin_required
def grant_admin(uid):
    db = get_db()
    db.execute("UPDATE users SET is_admin=1 WHERE id=?", (uid,))
    db.commit()
    flash(f"Admin granted to {uid}.", 'success')
    return redirect(url_for('admin.admin_page'))


@bp.route('/crime/edit', methods=['POST'])
@admin_required
def edit_crime():
    db = get_db()
    cid          = int(request.form['crime_id'])
    base_success = float(request.form.get('base_success', 0.5))
    payout_min   = int(request.form.get('payout_min', 0))
    payout_max   = int(request.form.get('payout_max', 0))
    db.execute(
        "UPDATE crimes SET base_success=?, payout_min=?, payout_max=? WHERE id=?",
        (base_success, payout_min, payout_max, cid)
    )
    db.commit()
    flash(f"Crime {cid} updated.", 'success')
    return redirect(url_for('admin.admin_page'))


@bp.route('/reset_db', methods=['POST'])
@admin_required
def reset_db():
    from .db import init_db
    import os
    from flask import current_app
    db_path = current_app.config['DATABASE']
    get_db().close()
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db()
    flash("Database reset.", 'success')
    return redirect(url_for('admin.admin_page'))
