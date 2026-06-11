from flask import Blueprint, render_template, redirect, url_for, flash, g, request, jsonify
from .i18n import tf
from .auth import login_required
from .db import get_db
from .game import latest_crypto_prices, CRYPTO_BASE

bp = Blueprint('crypto', __name__)

COIN_NAMES = {'SHDW': 'ShadowCoin', 'OMRT': 'OmertaCoin', 'BLDD': 'BloodDiamond'}


@bp.route('/crypto')
@login_required
def crypto_page():
    db = get_db()
    uid = g.player['user_id']
    prices = latest_crypto_prices(db)
    holdings = {r['symbol']: r['amount'] for r in db.execute(
        "SELECT symbol, amount FROM crypto_holdings WHERE user_id=?", (uid,)).fetchall()}
    coins = []
    for sym in CRYPTO_BASE:
        price = prices.get(sym, CRYPTO_BASE[sym])
        amount = holdings.get(sym, 0.0)
        history = [r['price'] for r in db.execute(
            "SELECT price FROM crypto_prices WHERE symbol=? ORDER BY id DESC LIMIT 48", (sym,)).fetchall()][::-1]
        coins.append({
            'symbol': sym, 'name': COIN_NAMES[sym], 'price': price,
            'amount': amount, 'value': amount * price, 'history': history,
            'change': (history[-1] / history[0] - 1) * 100 if len(history) > 1 else 0.0,
        })
    return render_template('crypto/crypto.html', coins=coins)


@bp.route('/crypto/buy', methods=['POST'])
@login_required
def buy():
    db = get_db()
    uid = g.player['user_id']
    sym = request.form.get('symbol', '')
    try:
        spend = int(request.form.get('spend', 0))
    except ValueError:
        spend = 0
    if sym not in CRYPTO_BASE or spend <= 0:
        flash(tf("Invalid order."), 'error')
        return redirect(url_for('crypto.crypto_page'))

    db.execute("BEGIN IMMEDIATE")
    price = latest_crypto_prices(db).get(sym, CRYPTO_BASE[sym])
    cash = db.execute("SELECT cash FROM players WHERE user_id=?", (uid,)).fetchone()['cash']
    if cash < spend:
        db.execute("ROLLBACK")
        flash(f"Not enough cash (have ${cash:,}).", 'error')
        return redirect(url_for('crypto.crypto_page'))

    amount = round(spend / price, 4)
    db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (spend, uid, spend))
    db.execute(
        "INSERT INTO crypto_holdings(user_id,symbol,amount) VALUES(?,?,?) "
        "ON CONFLICT(user_id,symbol) DO UPDATE SET amount=amount+?",
        (uid, sym, amount, amount))
    db.commit()
    flash(f"📈 Bought {amount} {sym} @ ${price:,.2f}", 'success')
    return redirect(url_for('crypto.crypto_page'))


@bp.route('/crypto/sell', methods=['POST'])
@login_required
def sell():
    db = get_db()
    uid = g.player['user_id']
    sym = request.form.get('symbol', '')
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        amount = 0.0
    if sym not in CRYPTO_BASE or amount <= 0:
        flash(tf("Invalid order."), 'error')
        return redirect(url_for('crypto.crypto_page'))

    db.execute("BEGIN IMMEDIATE")
    held = db.execute("SELECT amount FROM crypto_holdings WHERE user_id=? AND symbol=?",
                      (uid, sym)).fetchone()
    if not held or held['amount'] < amount:
        db.execute("ROLLBACK")
        flash("You don't hold that much.", 'error')
        return redirect(url_for('crypto.crypto_page'))

    price = latest_crypto_prices(db).get(sym, CRYPTO_BASE[sym])
    proceeds = int(amount * price)
    db.execute("UPDATE crypto_holdings SET amount=round(amount-?,4) WHERE user_id=? AND symbol=? AND amount>=?",
               (amount, uid, sym, amount))
    db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (proceeds, uid))
    db.commit()
    flash(f"📉 Sold {amount} {sym} for ${proceeds:,}", 'success')
    return redirect(url_for('crypto.crypto_page'))
