"""market.py — player-to-player marketplace. Sellers list inventory items;
buyers pay cash that transfers to the seller; the item moves to the buyer's
inventory. All inside guarded transactions.
"""
from datetime import timedelta

from flask import Blueprint, g, render_template, request, redirect, url_for, flash

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf
from game import notify, now, ts

bp = Blueprint("market", __name__)


@bp.route("/market")
@login_required
def market():
    con = get_db()
    listings = con.execute(
        "SELECT m.*, i.name AS item_name, i.type, u.username AS seller FROM marketplace m "
        "JOIN items i ON i.id=m.item_id JOIN users u ON u.id=m.seller_id "
        "WHERE m.status='open' ORDER BY m.id DESC LIMIT 80").fetchall()
    my_items = con.execute(
        "SELECT v.id,v.qty,i.name,i.type FROM inventory v JOIN items i ON i.id=v.item_id "
        "WHERE v.user_id=? ORDER BY i.type", (g.user["user_id"],)).fetchall()
    return render_template("market.html", listings=listings, my_items=my_items)


@bp.route("/market/list", methods=("POST",))
@login_required
def market_list():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    try:
        inv_id = int(request.form.get("inv_id"))
        price = int(request.form.get("price"))
    except (TypeError, ValueError):
        flash("Bad input.")
        return redirect(url_for("market.market"))
    if price < 1:
        flash("Price must be positive.")
        return redirect(url_for("market.market"))

    def work(c):
        row = c.execute("SELECT item_id,qty FROM inventory WHERE id=? AND user_id=?",
                        (inv_id, uid)).fetchone()
        if not row:
            raise TxFailed("noitem")
        # remove one unit from inventory and escrow it as a listing
        if row["qty"] > 1:
            c.execute("UPDATE inventory SET qty=qty-1 WHERE id=?", (inv_id,))
        else:
            c.execute("DELETE FROM inventory WHERE id=?", (inv_id,))
        c.execute(
            "INSERT INTO marketplace(seller_id,item_id,qty,price,kind,expires_at,status) "
            "VALUES (?,?,?,?,'listing',?, 'open')",
            (uid, row["item_id"], 1, price, ts(now() + timedelta(days=7))))
    try:
        transact(con, work)
        flash("Item listed on the black market.")
    except TxFailed:
        flash("You don't have that item.")
    return redirect(url_for("market.market"))


@bp.route("/market/buy/<int:listing_id>", methods=("POST",))
@login_required
def market_buy(listing_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        m = c.execute("SELECT * FROM marketplace WHERE id=? AND status='open'",
                      (listing_id,)).fetchone()
        if not m:
            raise TxFailed("gone")
        if m["seller_id"] == uid:
            raise TxFailed("own")
        guarded(c, "UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?",
                (m["price"], uid, m["price"]))
        # mark sold (guard against double-buy race)
        guarded(c, "UPDATE marketplace SET status='sold' WHERE id=? AND status='open'",
                (listing_id,))
        c.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (m["price"], m["seller_id"]))
        c.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES (?,?,1)", (uid, m["item_id"]))
        notify(c, m["seller_id"], f"Your market listing sold for ${m['price']:,}.")
        return m["price"]
    try:
        price = transact(con, work)
        flash(f"Bought for ${price:,}.")
    except TxFailed as e:
        flash({"gone": "That listing is gone.", "own": "You can't buy your own listing."}
              .get(str(e), "Not enough cash."))
    return redirect(url_for("market.market"))


@bp.route("/market/cancel/<int:listing_id>", methods=("POST",))
@login_required
def market_cancel(listing_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        m = c.execute("SELECT * FROM marketplace WHERE id=? AND seller_id=? AND status='open'",
                      (listing_id, uid)).fetchone()
        if not m:
            raise TxFailed("none")
        guarded(c, "UPDATE marketplace SET status='cancelled' WHERE id=? AND status='open'",
                (listing_id,))
        # return the item
        existing = c.execute("SELECT id FROM inventory WHERE user_id=? AND item_id=?",
                             (uid, m["item_id"])).fetchone()
        stackable = c.execute("SELECT stackable FROM items WHERE id=?", (m["item_id"],)).fetchone()
        if existing and stackable and stackable["stackable"]:
            c.execute("UPDATE inventory SET qty=qty+1 WHERE id=?", (existing["id"],))
        else:
            c.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES (?,?,1)", (uid, m["item_id"]))
    try:
        transact(con, work)
        flash("Listing cancelled; item returned.")
    except TxFailed:
        flash("Listing not found.")
    return redirect(url_for("market.market"))
