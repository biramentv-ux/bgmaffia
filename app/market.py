from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .i18n import tf
from .auth import login_required
from .db import get_db

bp = Blueprint('market', __name__)


@bp.route('/market')
@login_required
def market_page():
    db = get_db()
    now_iso = datetime.utcnow().isoformat()
    listings = db.execute(
        "SELECT mp.*, i.name, i.type, i.atk, i.def, u.username as seller_name "
        "FROM marketplace mp JOIN items i ON mp.item_id=i.id JOIN users u ON mp.seller_id=u.id "
        "WHERE mp.status='active' AND (mp.expires_at IS NULL OR mp.expires_at > ?) "
        "ORDER BY mp.price ASC",
        (now_iso,)
    ).fetchall()
    my_listings = db.execute(
        "SELECT mp.*, i.name FROM marketplace mp JOIN items i ON mp.item_id=i.id "
        "WHERE mp.seller_id=? AND mp.status='active' ORDER BY mp.id DESC",
        (g.player['user_id'],)
    ).fetchall()
    return render_template('market/market.html', listings=listings, my_listings=my_listings)


@bp.route('/market/list', methods=['POST'])
@login_required
def list_item():
    db = get_db()
    uid = g.player['user_id']
    try:
        inv_id = int(request.form['inv_id'])
        price  = int(request.form['price'])
    except (KeyError, ValueError):
        flash(tf("Invalid form data."), 'error')
        return redirect(url_for('market.market_page'))

    if price <= 0:
        flash(tf("Price must be positive."), 'error')
        return redirect(url_for('market.market_page'))

    inv = db.execute(
        "SELECT inv.item_id, inv.qty, i.stackable FROM inventory inv JOIN items i ON inv.item_id=i.id WHERE inv.id=? AND inv.user_id=?",
        (inv_id, uid)
    ).fetchone()
    if not inv:
        flash(tf("Item not in your inventory."), 'error')
        return redirect(url_for('market.market_page'))

    expires = (datetime.utcnow() + timedelta(days=7)).isoformat()
    db.execute("BEGIN IMMEDIATE")
    if inv['qty'] > 1 and inv['stackable']:
        db.execute("UPDATE inventory SET qty=qty-1 WHERE id=?", (inv_id,))
    else:
        db.execute("DELETE FROM inventory WHERE id=?", (inv_id,))
        # Clear any equipped slot that referenced this item so the seller
        # doesn't keep combat bonuses from an item they no longer own.
        item_id = inv['item_id']
        db.execute(
            "UPDATE players SET "
            "equipped_weapon = CASE WHEN equipped_weapon=? THEN NULL ELSE equipped_weapon END,"
            "equipped_car    = CASE WHEN equipped_car=?    THEN NULL ELSE equipped_car    END,"
            "equipped_dog    = CASE WHEN equipped_dog=?    THEN NULL ELSE equipped_dog    END,"
            "equipped_armor  = CASE WHEN equipped_armor=?  THEN NULL ELSE equipped_armor  END "
            "WHERE user_id=?",
            (item_id, item_id, item_id, item_id, uid)
        )
    db.execute(
        "INSERT INTO marketplace(seller_id,item_id,qty,price,expires_at) VALUES(?,?,?,?,?)",
        (uid, inv['item_id'], 1, price, expires)
    )
    db.commit()
    flash(tf("📦 Item listed on the black market."), 'success')
    return redirect(url_for('market.market_page'))


@bp.route('/market/buy/<int:listing_id>', methods=['POST'])
@login_required
def buy_listing(listing_id):
    db = get_db()
    uid = g.player['user_id']
    now_iso = datetime.utcnow().isoformat()

    db.execute("BEGIN IMMEDIATE")
    listing = db.execute("SELECT * FROM marketplace WHERE id=? AND status='active'", (listing_id,)).fetchone()
    if not listing or (listing['expires_at'] and listing['expires_at'] < now_iso):
        db.execute("ROLLBACK")
        flash(tf("Listing not available."), 'error')
        return redirect(url_for('market.market_page'))
    if listing['seller_id'] == uid:
        db.execute("ROLLBACK")
        flash("Can't buy your own listing.", 'error')
        return redirect(url_for('market.market_page'))

    player = dict(db.execute("SELECT cash FROM players WHERE user_id=?", (uid,)).fetchone())
    if player['cash'] < listing['price']:
        db.execute("ROLLBACK")
        flash(f"Not enough cash (need ${listing['price']:,}).", 'error')
        return redirect(url_for('market.market_page'))

    db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?",
               (listing['price'], uid, listing['price']))
    db.execute("UPDATE players SET cash=cash+? WHERE user_id=?",
               (listing['price'], listing['seller_id']))
    db.execute("UPDATE marketplace SET status='sold' WHERE id=?", (listing_id,))

    existing = db.execute("SELECT id,qty FROM inventory WHERE user_id=? AND item_id=?", (uid, listing['item_id'])).fetchone()
    item = db.execute("SELECT stackable FROM items WHERE id=?", (listing['item_id'],)).fetchone()
    if existing and item['stackable']:
        db.execute("UPDATE inventory SET qty=qty+1 WHERE id=?", (existing['id'],))
    else:
        db.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES(?,?,1)", (uid, listing['item_id']))
    db.commit()

    from .game import _notify
    _notify(db, listing['seller_id'], f"💰 Your market listing sold for ${listing['price']:,}!")
    db.commit()
    flash(f"✅ Purchased for ${listing['price']:,}.", 'success')
    return redirect(url_for('market.market_page'))


@bp.route('/market/cancel/<int:listing_id>', methods=['POST'])
@login_required
def cancel_listing(listing_id):
    db = get_db()
    uid = g.player['user_id']
    listing = db.execute("SELECT * FROM marketplace WHERE id=? AND seller_id=? AND status='active'", (listing_id, uid)).fetchone()
    if not listing:
        flash(tf("Listing not found."), 'error')
        return redirect(url_for('market.market_page'))
    db.execute("UPDATE marketplace SET status='cancelled' WHERE id=?", (listing_id,))
    db.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES(?,?,1)", (uid, listing['item_id']))
    db.commit()
    flash(tf("Listing cancelled, item returned."), 'success')
    return redirect(url_for('market.market_page'))
