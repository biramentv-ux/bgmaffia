from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, g, request, current_app
from .i18n import tf
from .auth import login_required
from .db import get_db
from .game import get_open_draw, draw_lottery

bp = Blueprint('lottery', __name__)


def _maybe_draw(db):
    """Lazy fallback: if the open draw is past due and has tickets, draw it now."""
    draw = db.execute("SELECT * FROM lottery_draws WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()
    if not draw:
        return
    due = datetime.fromisoformat(draw['opened_at']) + timedelta(
        minutes=current_app.config['LOTTERY_DRAW_MINUTES'])
    if datetime.utcnow() >= due:
        draw_lottery(db, current_app.config['LOTTERY_HOUSE_CUT'])


@bp.route('/lottery')
@login_required
def lottery_page():
    db = get_db()
    uid = g.player['user_id']
    _maybe_draw(db)
    draw = get_open_draw(db)
    my_tickets = db.execute(
        "SELECT COALESCE(SUM(qty),0) AS n FROM lottery_tickets WHERE draw_id=? AND user_id=?",
        (draw['id'], uid)).fetchone()['n']
    total_tickets = db.execute(
        "SELECT COALESCE(SUM(qty),0) AS n FROM lottery_tickets WHERE draw_id=?",
        (draw['id'],)).fetchone()['n']
    recent = db.execute(
        "SELECT d.*, u.username AS winner_name FROM lottery_draws d "
        "LEFT JOIN users u ON u.id = d.winner_id "
        "WHERE d.status='drawn' ORDER BY d.id DESC LIMIT 10").fetchall()
    next_draw_at = (datetime.fromisoformat(draw['opened_at'])
                    + timedelta(minutes=current_app.config['LOTTERY_DRAW_MINUTES'])).isoformat()
    return render_template('lottery/lottery.html',
                           draw=draw, my_tickets=my_tickets, total_tickets=total_tickets,
                           recent=recent, next_draw_at=next_draw_at,
                           ticket_price=current_app.config['LOTTERY_TICKET_PRICE'],
                           house_cut=current_app.config['LOTTERY_HOUSE_CUT'])


@bp.route('/lottery/buy', methods=['POST'])
@login_required
def buy_tickets():
    db = get_db()
    uid = g.player['user_id']
    price = current_app.config['LOTTERY_TICKET_PRICE']
    try:
        qty = int(request.form.get('qty', 0))
    except ValueError:
        qty = 0
    if qty <= 0 or qty > 100:
        flash(tf("Buy between 1 and 100 tickets."), 'error')
        return redirect(url_for('lottery.lottery_page'))

    cost = qty * price
    draw = get_open_draw(db)  # may commit if it creates a draw — keep outside the txn
    db.execute("BEGIN IMMEDIATE")
    cash = db.execute("SELECT cash FROM players WHERE user_id=?", (uid,)).fetchone()['cash']
    if cash < cost:
        db.execute("ROLLBACK")
        flash(f"Not enough cash (need ${cost:,}).", 'error')
        return redirect(url_for('lottery.lottery_page'))

    db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (cost, uid, cost))
    db.execute("INSERT INTO lottery_tickets(draw_id,user_id,qty) VALUES(?,?,?)",
               (draw['id'], uid, qty))
    db.execute("UPDATE lottery_draws SET pot=pot+? WHERE id=?", (cost, draw['id']))
    db.commit()
    flash(f"🎟️ Bought {qty} ticket{'s' if qty != 1 else ''} for ${cost:,}. Good luck!", 'success')
    return redirect(url_for('lottery.lottery_page'))
