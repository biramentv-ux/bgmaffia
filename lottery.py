"""lottery.py — Street Lottery: buy tickets, hourly draws via APScheduler."""
from flask import Blueprint, g, render_template, request, redirect, url_for, flash

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf

bp = Blueprint("lottery", __name__)

TICKET_PRICE = 100


@bp.route("/lottery")
@login_required
def lottery_page():
    con = get_db()
    uid = g.user["user_id"]
    pending = con.execute(
        "SELECT COALESCE(SUM(qty),0) AS qty FROM lottery_tickets WHERE user_id=? AND draw_id IS NULL",
        (uid,)).fetchone()["qty"]
    total_tickets = con.execute(
        "SELECT COALESCE(SUM(qty),0) AS qty FROM lottery_tickets WHERE draw_id IS NULL"
    ).fetchone()["qty"]
    pot = total_tickets * TICKET_PRICE
    prize = int(pot * 0.70)
    recent = con.execute(
        "SELECT ld.*, u.username FROM lottery_draws ld LEFT JOIN users u ON u.id=ld.winner_id "
        "ORDER BY ld.id DESC LIMIT 10").fetchall()
    return render_template("lottery.html",
                           pending=pending, total_tickets=total_tickets,
                           pot=pot, prize=prize, recent=recent)


@bp.route("/lottery/buy", methods=("POST",))
@login_required
def buy_tickets():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    try:
        qty = max(1, min(100, int(request.form.get("qty", 1))))
    except (TypeError, ValueError):
        qty = 1
    cost = qty * TICKET_PRICE

    def work(c):
        guarded(c, "UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?",
                (cost, uid, cost))
        c.execute("INSERT INTO lottery_tickets(user_id,qty) VALUES (?,?)", (uid, qty))
    try:
        transact(con, work)
        flash(f"Bought {qty} ticket{'s' if qty > 1 else ''} for ${cost:,}.")
    except TxFailed:
        flash("Not enough cash.")
    return redirect(url_for("lottery.lottery_page"))
