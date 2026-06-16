"""auth.py — registration/login, sessions, CSRF, and the before_request hook."""
import secrets
import functools

from flask import (Blueprint, request, session, redirect, url_for, render_template,
                   flash, g, abort)
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db
from game import (lazy_regen, get_player, status_locks, ts, now, check_achievements,
                  CLASSES)

bp = Blueprint("auth", __name__)


# ── CSRF ─────────────────────────────────────────────────────────────────────

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def check_csrf():
    sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
    if not sent or sent != session.get("_csrf"):
        abort(400, "Bad CSRF token")


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if not g.get("user"):
            return redirect(url_for("auth.login"))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if not g.get("user") or not g.user["is_admin"]:
            abort(403)
        return view(*a, **kw)
    return wrapped


# ── Request lifecycle ─────────────────────────────────────────────────────────

def load_logged_in_user():
    uid = session.get("user_id")
    g.user = None
    g.locks = {}
    if uid is None:
        return
    con = get_db()
    lazy_regen(con, uid)
    con.execute("UPDATE users SET last_active=? WHERE id=?", (ts(now()), uid))
    con.commit()
    g.user = get_player(con, uid)
    if g.user is None:
        session.clear()
        return
    if g.user["is_banned"]:
        session.clear()
        g.user = None
        return
    g.locks = status_locks(g.user)


# ── Routes ────────────────────────────────────────────────────────────────────

@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.get("user"):
        return redirect(url_for("home.dashboard"))
    if request.method == "POST":
        check_csrf()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        email = (request.form.get("email") or "").strip()
        player_class = (request.form.get("player_class") or "enforcer").strip()
        if player_class not in CLASSES:
            player_class = "enforcer"

        error = None
        if not (3 <= len(username) <= 20) or not username.replace("_", "").isalnum():
            error = "Username must be 3-20 letters, numbers or underscore."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        if error:
            flash(error)
        else:
            con = get_db()
            cls = CLASSES[player_class]
            starting = cls['stats']
            try:
                con.execute("BEGIN IMMEDIATE")
                cur = con.execute(
                    "INSERT INTO users(username,email,password_hash,last_active) VALUES (?,?,?,?)",
                    (username, email, generate_password_hash(password), ts(now())))
                uid = cur.lastrowid
                con.execute(
                    "INSERT INTO players(user_id,energy_ts,nerve_ts,health_ts,"
                    "strength,stamina,intellect,sexappeal,player_class) VALUES (?,?,?,?,?,?,?,?,?)",
                    (uid, ts(now()), ts(now()), ts(now()),
                     starting['strength'], starting['stamina'],
                     starting['intellect'], starting['sexappeal'], player_class))
                con.commit()
            except Exception:
                con.rollback()
                flash("That name is already taken.")
            else:
                session.clear()
                session["user_id"] = uid
                return redirect(url_for("home.dashboard"))
    return render_template("register.html", classes=CLASSES)


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.get("user"):
        return redirect(url_for("home.dashboard"))
    if request.method == "POST":
        check_csrf()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        con = get_db()
        user = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Wrong username or password.")
        elif user["is_banned"]:
            flash("This account is banned.")
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("home.dashboard"))
    return render_template("login.html")


@bp.route("/logout", methods=("POST",))
def logout():
    check_csrf()
    session.clear()
    return redirect(url_for("auth.login"))
