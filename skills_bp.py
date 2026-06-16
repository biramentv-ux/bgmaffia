"""skills_bp.py — passive skill tree unlock system."""
import json

from flask import Blueprint, g, render_template, request, redirect, url_for, flash

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf
from game import SKILL_EFFECTS, notify

bp = Blueprint("skills", __name__)

SKILL_CATEGORIES = ["combat", "criminal", "survival", "hustle"]
CATEGORY_LABELS  = {"combat": "Combat", "criminal": "Criminal", "survival": "Survival", "hustle": "Hustle"}


@bp.route("/skills")
@login_required
def skills_page():
    con = get_db()
    uid = g.user["user_id"]
    all_skills = con.execute("SELECT * FROM skills ORDER BY category, sp_cost").fetchall()
    unlocked = {r["skill_code"] for r in
                con.execute("SELECT skill_code FROM player_skills WHERE user_id=?", (uid,)).fetchall()}
    grouped = {}
    for s in all_skills:
        grouped.setdefault(s["category"], []).append(s)
    return render_template("skills.html", grouped=grouped, unlocked=unlocked,
                           categories=SKILL_CATEGORIES, cat_labels=CATEGORY_LABELS)


@bp.route("/skills/unlock/<code>", methods=("POST",))
@login_required
def unlock_skill(code):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    skill = con.execute("SELECT * FROM skills WHERE code=?", (code,)).fetchone()
    if not skill:
        flash("Skill not found.")
        return redirect(url_for("skills.skills_page"))

    def work(c):
        # prereq check
        if skill["prereq_code"]:
            has = c.execute(
                "SELECT 1 FROM player_skills WHERE user_id=? AND skill_code=?",
                (uid, skill["prereq_code"])).fetchone()
            if not has:
                raise TxFailed("prereq")
        # already unlocked?
        if c.execute("SELECT 1 FROM player_skills WHERE user_id=? AND skill_code=?",
                     (uid, code)).fetchone():
            raise TxFailed("owned")
        guarded(c, "UPDATE players SET skill_points=skill_points-? WHERE user_id=? AND skill_points>=?",
                (skill["sp_cost"], uid, skill["sp_cost"]))
        c.execute("INSERT INTO player_skills(user_id,skill_code) VALUES (?,?)", (uid, code))
        # special case: iron_will grants permanent +25 health_max
        if code == "iron_will":
            c.execute("UPDATE players SET health_max=health_max+25 WHERE user_id=?", (uid,))
        notify(c, uid, f"Skill unlocked: {skill['name']}!")
    try:
        transact(con, work)
        flash(f"Unlocked: {skill['name']}!")
    except TxFailed as e:
        flash({"prereq": "You need to unlock the prerequisite skill first.",
               "owned": "You already have this skill."}.get(str(e), "Not enough skill points."))
    return redirect(url_for("skills.skills_page"))
