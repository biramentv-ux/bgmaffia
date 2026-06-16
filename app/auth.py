from .i18n import tf
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_db
from .game import CLASSES

bp = Blueprint('auth', __name__)


def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home.dashboard'))
    if request.method == 'POST':
        username    = request.form.get('username', '').strip()
        email       = request.form.get('email', '').strip()
        password    = request.form.get('password', '')
        confirm     = request.form.get('confirm', '')
        player_class= request.form.get('player_class', 'enforcer')
        if player_class not in CLASSES:
            player_class = 'enforcer'
        db = get_db()
        error = None
        if not username or len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(username) > 20:
            error = "Username too long (max 20)."
        elif not password or len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
            error = "Username already taken."
        elif email and db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            error = "Email already registered."
        if error:
            flash(error, 'error')
            return render_template('auth/register.html', classes=CLASSES)
        ph = generate_password_hash(password)
        cur = db.execute(
            "INSERT INTO users(username,email,password_hash) VALUES(?,?,?)",
            (username, email or None, ph)
        )
        db.commit()
        uid = cur.lastrowid
        cls = CLASSES[player_class]
        s = cls['stats']
        db.execute(
            "INSERT INTO players(user_id,player_class,strength,stamina,intellect,sexappeal,"
            "energy_ts,nerve_ts,health_ts) VALUES(?,?,?,?,?,?,datetime('now'),datetime('now'),datetime('now'))",
            (uid, player_class, s['strength'], s['stamina'], s['intellect'], s['sexappeal'])
        )
        db.commit()
        session['user_id'] = uid
        flash(f"Welcome, {username}! You chose {cls['icon']} {cls['name']}. Good luck on the streets.", 'success')
        return redirect(url_for('home.dashboard'))
    return render_template('auth/register.html', classes=CLASSES)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user or not check_password_hash(user['password_hash'], password):
            flash(tf("Invalid username or password."), 'error')
            return render_template('auth/login.html')
        if user['is_banned']:
            flash(tf("Your account has been banned."), 'error')
            return render_template('auth/login.html')
        session.clear()
        session['user_id'] = user['id']
        return redirect(url_for('home.dashboard'))
    return render_template('auth/login.html')


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash(tf("You have been logged out."), 'info')
    return redirect(url_for('auth.login'))
