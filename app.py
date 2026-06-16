"""app.py — Flask application factory."""
import os
import atexit
import secrets

from flask import Flask, g, render_template, session, redirect, url_for

from db import get_db, close_db, init_db, raw_connection, migrate_db, DB_PATH
import auth
import actions
import social
import gangs
import casino
import market
import admin
import store
import pve
import skills_bp as skills_module
import crypto
import business
import daily
import lottery as lottery_module
from game import xp_needed, get_vip_tier
from i18n import translate, DEFAULT_LANG


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

    if not os.path.exists(DB_PATH):
        init_db(seed=True)
    else:
        migrate_db()

    app.teardown_appcontext(close_db)

    @app.before_request
    def _before():
        auth.load_logged_in_user()

    @app.context_processor
    def _ctx():
        user = g.get("user")
        vip = get_vip_tier(user) if user else 0
        lang = session.get('lang', DEFAULT_LANG)

        def t(text):
            return translate(lang, text)

        return {
            "user": user,
            "locks": g.get("locks", {}),
            "csrf_token": auth.csrf_token,
            "xp_needed": xp_needed,
            "vip_tier": vip,
            "lang": lang,
            "t": t,
        }

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        return resp

    from flask import Blueprint
    home = Blueprint("home", __name__)

    @home.route("/")
    def dashboard():
        if not g.get("user"):
            return redirect(url_for("auth.login"))
        return actions.dashboard()

    @home.route("/lang/<code>")
    def set_lang(code):
        from i18n import LANGS
        if code in LANGS:
            session['lang'] = code
        return redirect(request.referrer or url_for("home.dashboard"))

    app.register_blueprint(home)
    app.register_blueprint(auth.bp)
    app.register_blueprint(actions.bp)
    app.register_blueprint(social.bp)
    app.register_blueprint(gangs.bp)
    app.register_blueprint(casino.bp)
    app.register_blueprint(market.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(store.bp)
    app.register_blueprint(pve.bp)
    app.register_blueprint(skills_module.bp)
    app.register_blueprint(crypto.bp)
    app.register_blueprint(business.bp)
    app.register_blueprint(daily.bp)
    app.register_blueprint(lottery_module.bp)

    @app.errorhandler(403)
    def _403(e):
        return render_template("error.html", code=403, msg="Forbidden"), 403

    @app.errorhandler(404)
    def _404(e):
        return render_template("error.html", code=404, msg="Not found"), 404

    @app.errorhandler(400)
    def _400(e):
        return render_template("error.html", code=400, msg="Bad request"), 400

    return app


# ── Scheduler ────────────────────────────────────────────────────────────────

def hourly_interest():
    con = raw_connection()
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("UPDATE players SET bank = bank + CAST(bank * 0.01 AS INTEGER) WHERE bank > 0")
        con.commit()
    except Exception:
        con.rollback()
    finally:
        con.close()


def hourly_crypto_tick():
    """Randomise crypto prices ±15%."""
    import random
    con = raw_connection()
    try:
        con.execute("BEGIN IMMEDIATE")
        coins = con.execute("SELECT id, price FROM crypto_coins").fetchall()
        for c in coins:
            change = random.uniform(-0.15, 0.15)
            new_price = max(0.01, round(c["price"] * (1 + change), 4))
            con.execute(
                "UPDATE crypto_coins SET prev_price=price, price=?, last_updated=datetime('now') WHERE id=?",
                (new_price, c["id"]))
        con.commit()
    except Exception:
        con.rollback()
    finally:
        con.close()


def hourly_lottery_draw():
    """Run the street lottery draw if there are pending tickets."""
    import random
    con = raw_connection()
    try:
        con.execute("BEGIN IMMEDIATE")
        tickets = con.execute(
            "SELECT user_id, SUM(qty) AS qty FROM lottery_tickets WHERE draw_id IS NULL "
            "GROUP BY user_id").fetchall()
        if not tickets:
            con.commit()
            return
        total = sum(t["qty"] for t in tickets)
        pot = total * 100  # $100 per ticket
        prize = int(pot * 0.70)  # house keeps 30%

        # weighted random winner
        pool = []
        for t in tickets:
            pool.extend([t["user_id"]] * t["qty"])
        winner_id = random.choice(pool)

        cur = con.execute(
            "INSERT INTO lottery_draws(winner_id, prize, ticket_count) VALUES (?,?,?)",
            (winner_id, prize, total))
        draw_id = cur.lastrowid

        con.execute("UPDATE lottery_tickets SET draw_id=? WHERE draw_id IS NULL", (draw_id,))
        con.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (prize, winner_id))
        w = con.execute("SELECT username FROM users WHERE id=?", (winner_id,)).fetchone()
        if w:
            con.execute("INSERT INTO notifications(user_id,body) VALUES (?,?)",
                        (winner_id, f"You won the street lottery! +${prize:,}"))
        con.commit()
    except Exception:
        con.rollback()
    finally:
        con.close()


def start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(hourly_interest,      "interval", hours=1, id="interest",  replace_existing=True)
    sched.add_job(hourly_crypto_tick,   "interval", minutes=5, id="crypto",  replace_existing=True)
    sched.add_job(hourly_lottery_draw,  "interval", hours=1,   id="lottery", replace_existing=True)
    sched.start()
    atexit.register(lambda: sched.shutdown(wait=False))
    return sched


from flask import request  # noqa: E402 — needed for set_lang
app = create_app()

if __name__ == "__main__":
    if os.environ.get("RUN_MAIN") != "true":
        start_scheduler()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
