from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .auth import login_required
from .db import get_db

bp = Blueprint('shop', __name__)


@bp.route('/shop')
@login_required
def shop_page():
    db = get_db()
    player = g.player
    items = db.execute(
        "SELECT * FROM items WHERE min_level <= ? ORDER BY type, price",
        (player['level'],)
    ).fetchall()
    return render_template('shop/shop.html', items=items)


@bp.route('/shop/buy/<int:item_id>', methods=['POST'])
@login_required
def buy(item_id):
    db = get_db()
    uid = g.player['user_id']

    item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        flash("Item not found.", 'error')
        return redirect(url_for('shop.shop_page'))

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT cash, level FROM players WHERE user_id=?", (uid,)).fetchone())

    if player['level'] < item['min_level']:
        db.execute("ROLLBACK")
        flash("You're not high enough level.", 'error')
        return redirect(url_for('shop.shop_page'))

    if player['cash'] < item['price']:
        db.execute("ROLLBACK")
        flash(f"Not enough cash (need ${item['price']:,}).", 'error')
        return redirect(url_for('shop.shop_page'))

    db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?",
               (item['price'], uid, item['price']))

    if item['stackable']:
        existing = db.execute("SELECT id, qty FROM inventory WHERE user_id=? AND item_id=?", (uid, item_id)).fetchone()
        if existing:
            db.execute("UPDATE inventory SET qty=qty+1 WHERE id=?", (existing['id'],))
        else:
            db.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES(?,?,1)", (uid, item_id))
    else:
        db.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES(?,?,1)", (uid, item_id))

    db.commit()
    flash(f"🛒 Purchased {item['name']} for ${item['price']:,}.", 'success')
    return redirect(url_for('shop.shop_page'))
