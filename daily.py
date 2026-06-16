"""daily.py — daily login reward with streak system."""
from datetime import timedelta

from flask import Blueprint, g, render_template, redirect, url_for, flash, request

from db import get_db, transact, TxFailed
from auth import login_required, check_csrf
from game import now, notify

bp = Blueprint("daily", __name__)

BONUS_DAYS = {7, 14, 21, 28, 30}


def daily_reward(streak):
    cash = min(500 * streak, 15000)
    gold = 5 if streak in BONUS_DAYS else 0
    return cash, gold


@bp.route("/daily")
@login_required
def daily_page():
    con = get_db()
    uid = g.user["user_id"]
    row = con.execute("SELECT * FROM daily_log WHERE user_id=?", (uid,)).fetchone()
    today = now().strftime("%Y-%m-%d")
    claimed_today = row and row["last_claim"] == today
    streak = row["streak"] if row else 0
    cash, gold = daily_reward(streak + 1) if not claimed_today else daily_reward(streak)
    return render_template("daily.html",
                           streak=streak, claimed_today=claimed_today,
                           next_cash=cash, next_gold=gold, bonus_days=BONUS_DAYS)


@bp.route("/daily/claim", methods=("POST",))
@login_required
def claim_daily():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    today = now().strftime("%Y-%m-%d")
    yesterday = (now() - timedelta(days=1)).strftime("%Y-%m-%d")

    def work(c):
        row = c.execute("SELECT * FROM daily_log WHERE user_id=?", (uid,)).fetchone()
        if row and row["last_claim"] == today:
            raise TxFailed("already")
        if row:
            streak = row["streak"] + 1 if row["last_claim"] == yesterday else 1
        else:
            streak = 1
        cash, gold = daily_reward(streak)
        c.execute(
            "INSERT INTO daily_log(user_id, last_claim, streak) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET last_claim=?, streak=?",
            (uid, today, streak, today, streak))
        c.execute("UPDATE players SET cash=cash+?, gold=gold+? WHERE user_id=?",
                  (cash, gold, uid))
        notify(c, uid, f"Daily reward claimed: +${cash:,}" + (f" +{gold} gold!" if gold else "!"))
        return streak, cash, gold
    try:
        streak, cash, gold = transact(con, work)
        msg = f"Day {streak} claimed: +${cash:,}"
        if gold:
            msg += f" +{gold} ✨ gold (bonus day!)"
        flash(msg)
    except TxFailed:
        flash("Already claimed today. Come back tomorrow!")
    return redirect(url_for("daily.daily_page"))
