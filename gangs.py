"""gangs.py — gang creation/management, ranks, shared bank, invites,
territory claim/collect (passive income), and gang wars.
"""
from datetime import timedelta

from flask import Blueprint, g, render_template, request, redirect, url_for, flash

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf
from game import notify, now, ts, parse, get_skill_bonuses

bp = Blueprint("gangs", __name__)

GANG_CREATE_RESPECT = 50
RANKS = {0: "Recruit", 1: "Soldier", 2: "Lieutenant", 3: "Underboss", 4: "Boss"}


@bp.route("/gangs")
@login_required
def gangs():
    con = get_db()
    rows = con.execute(
        "SELECT g.*, (SELECT COUNT(*) FROM gang_members WHERE gang_id=g.id) AS members "
        "FROM gangs g ORDER BY g.respect DESC LIMIT 50").fetchall()
    invites = con.execute(
        "SELECT gi.gang_id, g.name FROM gang_invites gi JOIN gangs g ON g.id=gi.gang_id "
        "WHERE gi.user_id=?", (g.user["user_id"],)).fetchall()
    return render_template("gangs.html", rows=rows, invites=invites)


@bp.route("/gang/create", methods=("POST",))
@login_required
def gang_create():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    name = (request.form.get("name") or "").strip()[:30]
    tag = (request.form.get("tag") or "").strip()[:5].upper()
    if len(name) < 3:
        flash("Gang name must be at least 3 characters.")
        return redirect(url_for("gangs.gangs"))

    def work(c):
        p = c.execute("SELECT respect,gang_id FROM players WHERE user_id=?", (uid,)).fetchone()
        if p["gang_id"]:
            raise TxFailed("ingang")
        if p["respect"] < GANG_CREATE_RESPECT:
            raise TxFailed("respect")
        cur = c.execute("INSERT INTO gangs(name,tag,leader_id) VALUES (?,?,?)", (name, tag, uid))
        gid = cur.lastrowid
        c.execute("INSERT INTO gang_members(gang_id,user_id,rank) VALUES (?,?,4)", (gid, uid))
        c.execute("UPDATE players SET gang_id=?, gang_rank=4 WHERE user_id=?", (gid, uid))
        from game import award
        award(c, uid, "gang_founder")
        return gid
    try:
        gid = transact(con, work)
        flash("Gang founded. You're the Boss.")
        return redirect(url_for("gangs.gang_detail", gid=gid))
    except TxFailed as e:
        if str(e) == "ingang":
            flash("Leave your current gang first.")
        elif str(e) == "respect":
            flash(f"You need {GANG_CREATE_RESPECT} respect to found a gang.")
        else:
            flash("That gang name is taken.")
    except Exception:
        con.rollback()
        flash("That gang name is taken.")
    return redirect(url_for("gangs.gangs"))


@bp.route("/gang/<int:gid>")
@login_required
def gang_detail(gid):
    con = get_db()
    gang = con.execute("SELECT * FROM gangs WHERE id=?", (gid,)).fetchone()
    if not gang:
        flash("Gang not found.")
        return redirect(url_for("gangs.gangs"))
    members = con.execute(
        "SELECT gm.rank,u.id,u.username,p.level,p.respect,u.last_active FROM gang_members gm "
        "JOIN users u ON u.id=gm.user_id JOIN players p ON p.user_id=u.id "
        "WHERE gm.gang_id=? ORDER BY gm.rank DESC", (gid,)).fetchall()
    wars = con.execute(
        "SELECT w.*, ag.name AS a_name, dg.name AS d_name FROM gang_wars w "
        "JOIN gangs ag ON ag.id=w.attacker_gang JOIN gangs dg ON dg.id=w.defender_gang "
        "WHERE (w.attacker_gang=? OR w.defender_gang=?) ORDER BY w.id DESC LIMIT 10",
        (gid, gid)).fetchall()
    is_member = g.user["gang_id"] == gid
    is_boss = gang["leader_id"] == g.user["user_id"]
    return render_template("gang_detail.html", gang=gang, members=members, wars=wars,
                           is_member=is_member, is_boss=is_boss, ranks=RANKS)


@bp.route("/gang/<int:gid>/invite", methods=("POST",))
@login_required
def gang_invite(gid):
    check_csrf()
    con = get_db()
    if g.user["gang_id"] != gid or (g.user["gang_rank"] or 0) < 2:
        flash("Only lieutenants and up can invite.")
        return redirect(url_for("gangs.gang_detail", gid=gid))
    name = (request.form.get("username") or "").strip()
    target = con.execute("SELECT id,gang_id FROM players p JOIN users u ON u.id=p.user_id "
                         "WHERE u.username=?", (name,)).fetchone()
    if not target:
        flash("No such player.")
    elif target["gang_id"]:
        flash("That player is already in a gang.")
    else:
        con.execute("INSERT OR IGNORE INTO gang_invites(gang_id,user_id) VALUES (?,?)",
                    (gid, target["id"]))
        notify(con, target["id"], f"You were invited to a gang by {g.user['username']}.")
        con.commit()
        flash("Invitation sent.")
    return redirect(url_for("gangs.gang_detail", gid=gid))


@bp.route("/gang/<int:gid>/join", methods=("POST",))
@login_required
def gang_join(gid):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        inv = c.execute("SELECT 1 FROM gang_invites WHERE gang_id=? AND user_id=?",
                        (gid, uid)).fetchone()
        if not inv:
            raise TxFailed("noinvite")
        p = c.execute("SELECT gang_id FROM players WHERE user_id=?", (uid,)).fetchone()
        if p["gang_id"]:
            raise TxFailed("ingang")
        gang = c.execute(
            "SELECT max_members,(SELECT COUNT(*) FROM gang_members WHERE gang_id=?) AS n "
            "FROM gangs WHERE id=?", (gid, gid)).fetchone()
        if gang["n"] >= gang["max_members"]:
            raise TxFailed("full")
        c.execute("INSERT INTO gang_members(gang_id,user_id,rank) VALUES (?,?,1)", (gid, uid))
        c.execute("UPDATE players SET gang_id=?, gang_rank=1 WHERE user_id=?", (gid, uid))
        c.execute("DELETE FROM gang_invites WHERE user_id=?", (uid,))
    try:
        transact(con, work)
        flash("You joined the gang.")
    except TxFailed as e:
        flash({"noinvite": "No invite from that gang.", "ingang": "Leave your gang first.",
               "full": "That gang is full."}.get(str(e), "Can't join."))
    return redirect(url_for("gangs.gang_detail", gid=gid))


@bp.route("/gang/<int:gid>/leave", methods=("POST",))
@login_required
def gang_leave(gid):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    gang = con.execute("SELECT leader_id FROM gangs WHERE id=?", (gid,)).fetchone()
    if gang and gang["leader_id"] == uid:
        flash("The boss can't leave; disband or promote someone first.")
        return redirect(url_for("gangs.gang_detail", gid=gid))
    con.execute("DELETE FROM gang_members WHERE gang_id=? AND user_id=?", (gid, uid))
    con.execute("UPDATE players SET gang_id=NULL, gang_rank=NULL WHERE user_id=?", (uid,))
    con.commit()
    flash("You left the gang.")
    return redirect(url_for("gangs.gangs"))


@bp.route("/gang/<int:gid>/donate", methods=("POST",))
@login_required
def gang_donate(gid):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    if g.user["gang_id"] != gid:
        flash("You're not in that gang.")
        return redirect(url_for("gangs.gang_detail", gid=gid))
    try:
        amount = int(request.form.get("amount"))
    except (TypeError, ValueError):
        flash("Enter a number.")
        return redirect(url_for("gangs.gang_detail", gid=gid))
    if amount <= 0:
        flash("Amount must be positive.")
        return redirect(url_for("gangs.gang_detail", gid=gid))

    def work(c):
        guarded(c, "UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (amount, uid, amount))
        c.execute("UPDATE gangs SET bank=bank+? WHERE id=?", (amount, gid))
    try:
        transact(con, work)
        flash(f"Donated ${amount:,} to the gang bank.")
    except TxFailed:
        flash("Not enough cash on hand.")
    return redirect(url_for("gangs.gang_detail", gid=gid))


@bp.route("/gang/<int:gid>/promote", methods=("POST",))
@login_required
def gang_promote(gid):
    check_csrf()
    con = get_db()
    gang = con.execute("SELECT leader_id FROM gangs WHERE id=?", (gid,)).fetchone()
    if not gang or gang["leader_id"] != g.user["user_id"]:
        flash("Only the boss can promote.")
        return redirect(url_for("gangs.gang_detail", gid=gid))
    try:
        target_id = int(request.form.get("user_id"))
        new_rank = max(0, min(3, int(request.form.get("rank"))))
    except (TypeError, ValueError):
        flash("Bad input.")
        return redirect(url_for("gangs.gang_detail", gid=gid))
    con.execute("UPDATE gang_members SET rank=? WHERE gang_id=? AND user_id=?",
                (new_rank, gid, target_id))
    con.execute("UPDATE players SET gang_rank=? WHERE user_id=? AND gang_id=?",
                (new_rank, target_id, gid))
    con.commit()
    flash("Member rank updated.")
    return redirect(url_for("gangs.gang_detail", gid=gid))


@bp.route("/gang/<int:gid>/kick", methods=("POST",))
@login_required
def gang_kick(gid):
    check_csrf()
    con = get_db()
    gang = con.execute("SELECT leader_id FROM gangs WHERE id=?", (gid,)).fetchone()
    if not gang or (gang["leader_id"] != g.user["user_id"] and (g.user["gang_rank"] or 0) < 3):
        flash("Not allowed.")
        return redirect(url_for("gangs.gang_detail", gid=gid))
    try:
        target_id = int(request.form.get("user_id"))
    except (TypeError, ValueError):
        return redirect(url_for("gangs.gang_detail", gid=gid))
    if target_id == gang["leader_id"]:
        flash("Can't kick the boss.")
        return redirect(url_for("gangs.gang_detail", gid=gid))
    con.execute("DELETE FROM gang_members WHERE gang_id=? AND user_id=?", (gid, target_id))
    con.execute("UPDATE players SET gang_id=NULL, gang_rank=NULL WHERE user_id=?", (target_id,))
    notify(con, target_id, "You were kicked from your gang.")
    con.commit()
    flash("Member removed.")
    return redirect(url_for("gangs.gang_detail", gid=gid))


@bp.route("/gang/war/<int:target_gang>", methods=("POST",))
@login_required
def gang_war(target_gang):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    my_gang = g.user["gang_id"]
    if not my_gang or (g.user["gang_rank"] or 0) < 3:
        flash("Only underbosses and up can declare war.")
        return redirect(url_for("gangs.gangs"))
    if my_gang == target_gang:
        flash("You can't war your own gang.")
        return redirect(url_for("gangs.gang_detail", gid=my_gang))
    existing = con.execute(
        "SELECT 1 FROM gang_wars WHERE status='active' AND "
        "((attacker_gang=? AND defender_gang=?) OR (attacker_gang=? AND defender_gang=?))",
        (my_gang, target_gang, target_gang, my_gang)).fetchone()
    if existing:
        flash("A war is already active between these gangs.")
        return redirect(url_for("gangs.gang_detail", gid=my_gang))
    con.execute("INSERT INTO gang_wars(attacker_gang,defender_gang) VALUES (?,?)",
                (my_gang, target_gang))
    con.commit()
    flash("War declared! Beat their members to score points.")
    return redirect(url_for("gangs.gang_detail", gid=my_gang))


# ---------------- Territory ----------------

@bp.route("/territory")
@login_required
def territory():
    con = get_db()
    rows = con.execute(
        "SELECT t.*, u.username AS owner_name, g.name AS gang_name FROM territories t "
        "LEFT JOIN users u ON u.id=t.owner_user LEFT JOIN gangs g ON g.id=t.owner_gang "
        "ORDER BY t.min_respect").fetchall()
    spots = []
    for t in rows:
        accrued = 0
        if t["owner_user"] == g.user["user_id"] and t["last_collected"]:
            hrs = (now() - parse(t["last_collected"])).total_seconds() / 3600
            accrued = int(hrs * t["income_per_hour"])
        spots.append({"t": t, "accrued": accrued, "mine": t["owner_user"] == g.user["user_id"]})
    return render_template("territory.html", spots=spots)


@bp.route("/territory/claim/<int:tid>", methods=("POST",))
@login_required
def territory_claim(tid):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        t = c.execute("SELECT * FROM territories WHERE id=?", (tid,)).fetchone()
        if not t:
            raise TxFailed("none")
        p = c.execute("SELECT cash,respect FROM players WHERE user_id=?", (uid,)).fetchone()
        if p["respect"] < t["min_respect"]:
            raise TxFailed("respect")
        if p["cash"] < t["claim_cost"]:
            raise TxFailed("cash")
        guarded(c, "UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?",
                (t["claim_cost"], uid, t["claim_cost"]))
        # if someone owns it, they get muscled out
        if t["owner_user"] and t["owner_user"] != uid:
            notify(c, t["owner_user"], f"You lost control of {t['name']}.")
        c.execute("UPDATE territories SET owner_user=?, owner_gang=?, last_collected=? WHERE id=?",
                  (uid, g.user["gang_id"], ts(now()), tid))
        from game import award
        award(c, uid, "landlord")
    try:
        transact(con, work)
        flash("Territory claimed. It now earns passive income.")
    except TxFailed as e:
        flash({"respect": "You don't have enough respect for this turf.",
               "cash": "Not enough cash to take this turf.",
               "none": "No such territory."}.get(str(e), "Can't claim that."))
    return redirect(url_for("gangs.territory"))


@bp.route("/territory/collect/<int:tid>", methods=("POST",))
@login_required
def territory_collect(tid):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        t = c.execute("SELECT * FROM territories WHERE id=? AND owner_user=?", (tid, uid)).fetchone()
        if not t:
            raise TxFailed("notyours")
        hrs = (now() - parse(t["last_collected"])).total_seconds() / 3600 if t["last_collected"] else 0
        sk = get_skill_bonuses(c, uid)
        territory_mult = 1.0 + sk["territory_mult"]
        income = int(hrs * t["income_per_hour"] * territory_mult)
        if income < 1:
            raise TxFailed("empty")
        c.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (income, uid))
        c.execute("UPDATE territories SET last_collected=? WHERE id=?", (ts(now()), tid))
        return income
    try:
        income = transact(con, work)
        flash(f"Collected ${income:,} in protection money.")
    except TxFailed as e:
        flash("Nothing to collect yet." if str(e) == "empty" else "That's not your turf.")
    return redirect(url_for("gangs.territory"))
