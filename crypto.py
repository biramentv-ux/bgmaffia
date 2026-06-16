"""crypto.py — Shadow Exchange: volatile untraceable crypto coins."""
from flask import Blueprint, g, render_template, request, redirect, url_for, flash

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf

bp = Blueprint("crypto", __name__)


@bp.route("/crypto")
@login_required
def crypto_page():
    con = get_db()
    uid = g.user["user_id"]
    coins = con.execute("SELECT * FROM crypto_coins ORDER BY id").fetchall()
    holdings = {r["coin_id"]: r["amount"] for r in
                con.execute("SELECT coin_id, amount FROM crypto_holdings WHERE user_id=?",
                            (uid,)).fetchall()}
    return render_template("crypto.html", coins=coins, holdings=holdings)


@bp.route("/crypto/buy/<int:coin_id>", methods=("POST",))
@login_required
def buy_coin(coin_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    try:
        spend = int(request.form.get("spend", 0))
    except (TypeError, ValueError):
        flash("Invalid amount.")
        return redirect(url_for("crypto.crypto_page"))
    if spend < 1:
        flash("Amount must be positive.")
        return redirect(url_for("crypto.crypto_page"))

    def work(c):
        coin = c.execute("SELECT * FROM crypto_coins WHERE id=?", (coin_id,)).fetchone()
        if not coin or coin["price"] <= 0:
            raise TxFailed("coin")
        coins_bought = spend / coin["price"]
        guarded(c, "UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?",
                (spend, uid, spend))
        existing = c.execute(
            "SELECT amount FROM crypto_holdings WHERE user_id=? AND coin_id=?",
            (uid, coin_id)).fetchone()
        if existing:
            c.execute("UPDATE crypto_holdings SET amount=amount+? WHERE user_id=? AND coin_id=?",
                      (coins_bought, uid, coin_id))
        else:
            c.execute("INSERT INTO crypto_holdings(user_id,coin_id,amount) VALUES (?,?,?)",
                      (uid, coin_id, coins_bought))
        return coin["symbol"], coins_bought
    try:
        symbol, bought = transact(con, work)
        flash(f"Bought {bought:.4f} {symbol} for ${spend:,}.")
    except TxFailed as e:
        flash("Not enough cash." if str(e) != "coin" else "Coin not found.")
    return redirect(url_for("crypto.crypto_page"))


@bp.route("/crypto/sell/<int:coin_id>", methods=("POST",))
@login_required
def sell_coin(coin_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    try:
        amount = float(request.form.get("amount", 0))
    except (TypeError, ValueError):
        flash("Invalid amount.")
        return redirect(url_for("crypto.crypto_page"))
    if amount <= 0:
        flash("Amount must be positive.")
        return redirect(url_for("crypto.crypto_page"))

    def work(c):
        coin = c.execute("SELECT * FROM crypto_coins WHERE id=?", (coin_id,)).fetchone()
        if not coin:
            raise TxFailed("coin")
        holding = c.execute(
            "SELECT amount FROM crypto_holdings WHERE user_id=? AND coin_id=?",
            (uid, coin_id)).fetchone()
        if not holding or holding["amount"] < amount:
            raise TxFailed("holding")
        proceeds = int(amount * coin["price"])
        c.execute(
            "UPDATE crypto_holdings SET amount=amount-? WHERE user_id=? AND coin_id=?",
            (amount, uid, coin_id))
        c.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (proceeds, uid))
        return coin["symbol"], proceeds
    try:
        symbol, proceeds = transact(con, work)
        flash(f"Sold {amount:.4f} {symbol} for ${proceeds:,}.")
    except TxFailed as e:
        flash("Not enough coins." if str(e) != "coin" else "Coin not found.")
    return redirect(url_for("crypto.crypto_page"))
