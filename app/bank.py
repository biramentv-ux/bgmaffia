from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .auth import login_required
from .db import get_db

bp = Blueprint('bank', __name__)


@bp.route('/bank')
@login_required
def bank_page():
    db = get_db()
    uid = g.player['user_id']
    history = db.execute(
        "SELECT * FROM bank_log WHERE user_id=? ORDER BY ts DESC LIMIT 20", (uid,)
    ).fetchall()
    return render_template('bank/bank.html', history=history)


@bp.route('/bank/deposit', methods=['POST'])
@login_required
def deposit():
    db = get_db()
    uid = g.player['user_id']
    try:
        amount = int(request.form.get('amount', 0))
    except ValueError:
        amount = 0
    if amount <= 0:
        flash("Invalid amount.", 'error')
        return redirect(url_for('bank.bank_page'))

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT cash, bank FROM players WHERE user_id=?", (uid,)).fetchone())
    if player['cash'] < amount:
        db.execute("ROLLBACK")
        flash(f"Not enough cash (have ${player['cash']:,}).", 'error')
        return redirect(url_for('bank.bank_page'))

    db.execute("UPDATE players SET cash=cash-?, bank=bank+? WHERE user_id=? AND cash>=?",
               (amount, amount, uid, amount))
    db.execute("INSERT INTO bank_log(user_id,kind,amount) VALUES(?,?,?)", (uid, 'deposit', amount))
    db.commit()
    flash(f"💰 Deposited ${amount:,} into bank.", 'success')
    return redirect(url_for('bank.bank_page'))


@bp.route('/bank/withdraw', methods=['POST'])
@login_required
def withdraw():
    db = get_db()
    uid = g.player['user_id']
    try:
        amount = int(request.form.get('amount', 0))
    except ValueError:
        amount = 0
    if amount <= 0:
        flash("Invalid amount.", 'error')
        return redirect(url_for('bank.bank_page'))

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT cash, bank FROM players WHERE user_id=?", (uid,)).fetchone())
    if player['bank'] < amount:
        db.execute("ROLLBACK")
        flash(f"Not enough in bank (have ${player['bank']:,}).", 'error')
        return redirect(url_for('bank.bank_page'))

    db.execute("UPDATE players SET bank=bank-?, cash=cash+? WHERE user_id=? AND bank>=?",
               (amount, amount, uid, amount))
    db.execute("INSERT INTO bank_log(user_id,kind,amount) VALUES(?,?,?)", (uid, 'withdraw', amount))
    db.commit()
    flash(f"💸 Withdrew ${amount:,} from bank.", 'success')
    return redirect(url_for('bank.bank_page'))
