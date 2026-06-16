"""admin.py — admin panel for data-driven balancing: crime/item/event CRUD,
ban/unban players, grant resources. Gated by admin_required.
"""
from flask import Blueprint, g, render_template, request, redirect, url_for, flash

from db import get_db
from auth import admin_required, check_csrf
from game import notify, now, ts

bp = Blueprint("admin", __name__)


@bp.route("/admin")
@admin_required
def panel():
    con = get_db()
    crimes = con.execute("SELECT * FROM crimes ORDER BY min_level").fetchall()
    items = con.execute("SELECT * FROM items ORDER BY type, price").fetchall()
    events = con.execute("SELECT * FROM events ORDER BY id DESC").fetchall()
    players = con.execute(
        "SELECT u.id,u.username,u.is_banned,p.level,p.respect,p.cash,p.bank "
        "FROM users u JOIN players p ON p.user_id=u.id ORDER BY u.id DESC LIMIT 100").fetchall()
    stats = {
        "players": con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "online": con.execute(
            "SELECT COUNT(*) c FROM users WHERE last_active>=datetime('now','-5 minutes')"
        ).fetchone()["c"],
        "gangs": con.execute("SELECT COUNT(*) c FROM gangs").fetchone()["c"],
        "fights": con.execute("SELECT COUNT(*) c FROM fights").fetchone()["c"],
    }
    return render_template("admin.html", crimes=crimes, items=items, events=events,
                           players=players, stats=stats)


@bp.route("/admin/crime/<int:crime_id>", methods=("POST",))
@admin_required
def edit_crime(crime_id):
    check_csrf()
    con = get_db()
    fields = ("energy_cost", "nerve_cost", "base_success", "payout_min", "payout_max",
              "xp_reward", "respect_reward", "cooldown_sec", "jail_sec", "min_level")
    sets, params = [], []
    for f in fields:
        v = request.form.get(f)
        if v not in (None, ""):
            sets.append(f"{f}=?")
            params.append(float(v) if f == "base_success" else int(v))
    if sets:
        params.append(crime_id)
        con.execute(f"UPDATE crimes SET {','.join(sets)} WHERE id=?", params)
        con.commit()
        flash("Crime updated.")
    return redirect(url_for("admin.panel"))


@bp.route("/admin/item/<int:item_id>", methods=("POST",))
@admin_required
def edit_item(item_id):
    check_csrf()
    con = get_db()
    fields = ("atk", "def", "price", "min_level")
    sets, params = [], []
    for f in fields:
        v = request.form.get(f)
        if v not in (None, ""):
            sets.append(f"{f}=?")
            params.append(int(v))
    if sets:
        params.append(item_id)
        con.execute(f"UPDATE items SET {','.join(sets)} WHERE id=?", params)
        con.commit()
        flash("Item updated.")
    return redirect(url_for("admin.panel"))


@bp.route("/admin/event/create", methods=("POST",))
@admin_required
def create_event():
    check_csrf()
    con = get_db()
    code = (request.form.get("code") or "event").strip()[:40]
    descr = (request.form.get("descr") or "").strip()[:200]
    modifier = (request.form.get("modifier_json") or "{}").strip()
    import json
    try:
        json.loads(modifier)
    except ValueError:
        flash("Modifier must be valid JSON, e.g. {\"payout\":2,\"xp\":2}")
        return redirect(url_for("admin.panel"))
    con.execute(
        "INSERT INTO events(code,descr,modifier_json,is_active,starts_at) VALUES (?,?,?,1,?)",
        (code, descr, modifier, ts(now())))
    con.commit()
    flash("Event started.")
    return redirect(url_for("admin.panel"))


@bp.route("/admin/event/<int:event_id>/toggle", methods=("POST",))
@admin_required
def toggle_event(event_id):
    check_csrf()
    con = get_db()
    con.execute("UPDATE events SET is_active=1-is_active WHERE id=?", (event_id,))
    con.commit()
    flash("Event toggled.")
    return redirect(url_for("admin.panel"))


@bp.route("/admin/player/<int:user_id>/ban", methods=("POST",))
@admin_required
def ban(user_id):
    check_csrf()
    con = get_db()
    con.execute("UPDATE users SET is_banned=1-is_banned WHERE id=?", (user_id,))
    con.commit()
    flash("Player ban toggled.")
    return redirect(url_for("admin.panel"))


@bp.route("/admin/player/<int:user_id>/grant", methods=("POST",))
@admin_required
def grant(user_id):
    check_csrf()
    con = get_db()
    try:
        cash = int(request.form.get("cash") or 0)
        gold = int(request.form.get("gold") or 0)
    except ValueError:
        flash("Numbers only.")
        return redirect(url_for("admin.panel"))
    con.execute("UPDATE players SET cash=cash+?, gold=gold+? WHERE user_id=?", (cash, gold, user_id))
    if cash or gold:
        notify(con, user_id, f"An admin granted you ${cash:,} and {gold} gold.")
    con.commit()
    flash("Granted.")
    return redirect(url_for("admin.panel"))
