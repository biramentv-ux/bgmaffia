"""social.py — mail, chat (polling deltas), notifications, leaderboards,
achievements, hitlist/bounties, relations.
"""
from flask import Blueprint, g, render_template, request, redirect, url_for, flash, jsonify

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf
from game import notify, now, ts

bp = Blueprint("social", __name__)


# ---------------- Mail ----------------

@bp.route("/mail")
@login_required
def mail():
    con = get_db()
    uid = g.user["user_id"]
    inbox = con.execute(
        "SELECT m.*, u.username AS sender FROM messages m JOIN users u ON u.id=m.from_id "
        "WHERE m.to_id=? ORDER BY m.id DESC LIMIT 50", (uid,)).fetchall()
    con.execute("UPDATE messages SET is_read=1 WHERE to_id=?", (uid,))
    con.commit()
    return render_template("mail.html", inbox=inbox)


@bp.route("/mail/send", methods=("POST",))
@login_required
def mail_send():
    check_csrf()
    con = get_db()
    to_name = (request.form.get("to") or "").strip()
    subject = (request.form.get("subject") or "(no subject)").strip()[:120]
    body = (request.form.get("body") or "").strip()[:2000]
    if not body:
        flash("Message body is empty.")
        return redirect(url_for("social.mail"))
    target = con.execute("SELECT id FROM users WHERE username=?", (to_name,)).fetchone()
    if not target:
        flash("No player with that name.")
        return redirect(url_for("social.mail"))
    con.execute("INSERT INTO messages(from_id,to_id,subject,body) VALUES (?,?,?,?)",
                (g.user["user_id"], target["id"], subject, body))
    notify(con, target["id"], f"New mail from {g.user['username']}.")
    con.commit()
    flash("Message sent.")
    return redirect(url_for("social.mail"))


# ---------------- Chat (polling) ----------------

@bp.route("/chat")
@login_required
def chat():
    return render_template("chat.html")


@bp.route("/chat/messages")
@login_required
def chat_messages():
    con = get_db()
    since = request.args.get("since", "0")
    try:
        since = int(since)
    except ValueError:
        since = 0
    rows = con.execute(
        "SELECT c.id,c.body,c.ts,u.username FROM chat c JOIN users u ON u.id=c.user_id "
        "WHERE c.id>? ORDER BY c.id ASC LIMIT 100", (since,)).fetchall()
    return jsonify([{"id": r["id"], "user": r["username"], "body": r["body"], "ts": r["ts"]}
                    for r in rows])


@bp.route("/chat/send", methods=("POST",))
@login_required
def chat_send():
    check_csrf()
    con = get_db()
    body = (request.form.get("body") or "").strip()[:300]
    if body:
        # light rate-limit: max 1 msg / 2s per user
        last = con.execute("SELECT ts FROM chat WHERE user_id=? ORDER BY id DESC LIMIT 1",
                           (g.user["user_id"],)).fetchone()
        con.execute("INSERT INTO chat(user_id,body) VALUES (?,?)", (g.user["user_id"], body))
        con.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True})
    return redirect(url_for("social.chat"))


# ---------------- Notifications (polling) ----------------

@bp.route("/notifications/poll")
@login_required
def notifications_poll():
    con = get_db()
    uid = g.user["user_id"]
    rows = con.execute(
        "SELECT id,body,ts FROM notifications WHERE user_id=? AND is_read=0 ORDER BY id DESC LIMIT 20",
        (uid,)).fetchall()
    con.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,))
    con.commit()
    return jsonify([{"id": r["id"], "body": r["body"], "ts": r["ts"]} for r in rows])


# ---------------- Leaderboards ----------------

@bp.route("/leaderboard")
@login_required
def leaderboard():
    con = get_db()
    by = request.args.get("by", "respect")
    col = {"respect": "respect", "level": "level", "kills": "fights_won", "wealth": "bank"}.get(by, "respect")
    rows = con.execute(
        f"SELECT u.id,u.username,p.level,p.respect,p.fights_won,p.bank FROM players p "
        f"JOIN users u ON u.id=p.user_id WHERE u.is_banned=0 ORDER BY p.{col} DESC LIMIT 50").fetchall()
    return render_template("leaderboard.html", rows=rows, by=by)


@bp.route("/achievements")
@login_required
def achievements():
    con = get_db()
    uid = g.user["user_id"]
    rows = con.execute(
        "SELECT a.*, pa.earned_at FROM achievements a "
        "LEFT JOIN player_achievements pa ON pa.achievement_id=a.id AND pa.user_id=? "
        "ORDER BY a.id", (uid,)).fetchall()
    return render_template("achievements.html", rows=rows)


# ---------------- Hitlist / bounties ----------------

@bp.route("/hitlist")
@login_required
def hitlist():
    con = get_db()
    rows = con.execute(
        "SELECT b.*, t.username AS target, pl.username AS placer FROM bounties b "
        "JOIN users t ON t.id=b.target_id JOIN users pl ON pl.id=b.placed_by "
        "WHERE b.status='open' ORDER BY b.amount DESC LIMIT 50").fetchall()
    return render_template("hitlist.html", rows=rows)


@bp.route("/bounty/place", methods=("POST",))
@login_required
def bounty_place():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    target_name = (request.form.get("target") or "").strip()
    try:
        amount = int(request.form.get("amount"))
    except (TypeError, ValueError):
        flash("Enter a valid amount.")
        return redirect(url_for("social.hitlist"))
    if amount < 1000:
        flash("Minimum bounty is $1,000.")
        return redirect(url_for("social.hitlist"))
    target = con.execute("SELECT id FROM users WHERE username=?", (target_name,)).fetchone()
    if not target or target["id"] == uid:
        flash("Pick a valid target.")
        return redirect(url_for("social.hitlist"))

    def work(c):
        guarded(c, "UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (amount, uid, amount))
        c.execute("INSERT INTO bounties(target_id,placed_by,amount) VALUES (?,?,?)",
                  (target["id"], uid, amount))
        notify(c, target["id"], f"A ${amount:,} bounty was placed on your head!")
    try:
        transact(con, work)
        flash(f"Bounty of ${amount:,} placed on {target_name}.")
    except TxFailed:
        flash("Not enough cash on hand.")
    return redirect(url_for("social.hitlist"))


# ---------------- Missions ----------------

@bp.route("/missions")
@login_required
def missions():
    con = get_db()
    uid = g.user["user_id"]
    day = now().strftime("%Y-%m-%d")
    rows = con.execute(
        "SELECT m.*, COALESCE(pm.progress,0) AS progress, COALESCE(pm.completed,0) AS completed, "
        "COALESCE(pm.claimed,0) AS claimed FROM missions m "
        "LEFT JOIN player_missions pm ON pm.mission_id=m.id AND pm.user_id=? AND pm.day=? "
        "WHERE m.is_daily=1 ORDER BY m.id", (uid, day)).fetchall()
    import json as _json
    parsed = [{"m": r, "reward": _json.loads(r["reward_json"])} for r in rows]
    return render_template("missions.html", rows=parsed)


@bp.route("/missions/claim/<int:mission_id>", methods=("POST",))
@login_required
def claim_mission(mission_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    day = now().strftime("%Y-%m-%d")
    import json as _json

    def work(c):
        pm = c.execute(
            "SELECT completed,claimed FROM player_missions WHERE user_id=? AND mission_id=? AND day=?",
            (uid, mission_id, day)).fetchone()
        if not pm or not pm["completed"] or pm["claimed"]:
            raise TxFailed("nope")
        m = c.execute("SELECT reward_json FROM missions WHERE id=?", (mission_id,)).fetchone()
        reward = _json.loads(m["reward_json"])
        c.execute("UPDATE player_missions SET claimed=1 WHERE user_id=? AND mission_id=? AND day=?",
                  (uid, mission_id, day))
        c.execute("UPDATE players SET cash=cash+?, gold=gold+? WHERE user_id=?",
                  (reward.get("cash", 0), reward.get("gold", 0), uid))
        return reward
    try:
        reward = transact(con, work)
        flash(f"Reward claimed: +${reward.get('cash',0):,}, +{reward.get('gold',0)} gold.")
    except TxFailed:
        flash("Nothing to claim.")
    return redirect(url_for("social.missions"))
