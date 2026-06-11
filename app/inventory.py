import json
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .i18n import tf
from .auth import login_required
from .db import get_db

bp = Blueprint('inventory', __name__)

EQUIP_SLOTS = {
    'weapon': 'equipped_weapon',
    'car':    'equipped_car',
    'dog':    'equipped_dog',
    'armor':  'equipped_armor',
}


@bp.route('/inventory')
@login_required
def inventory_page():
    db = get_db()
    uid = g.player['user_id']
    inv = db.execute(
        "SELECT inv.id, inv.qty, i.* FROM inventory inv JOIN items i ON inv.item_id=i.id WHERE inv.user_id=? ORDER BY i.type, i.name",
        (uid,)
    ).fetchall()
    player = g.player
    equipped = {
        'weapon': player['equipped_weapon'],
        'car':    player['equipped_car'],
        'dog':    player['equipped_dog'],
        'armor':  player['equipped_armor'],
    }
    return render_template('inventory/inventory.html', inv=inv, equipped=equipped)


@bp.route('/inventory/equip/<int:inv_id>', methods=['POST'])
@login_required
def equip(inv_id):
    db = get_db()
    uid = g.player['user_id']
    row = db.execute(
        "SELECT inv.item_id, i.type FROM inventory inv JOIN items i ON inv.item_id=i.id WHERE inv.id=? AND inv.user_id=?",
        (inv_id, uid)
    ).fetchone()
    if not row:
        flash(tf("Item not found in inventory."), 'error')
        return redirect(url_for('inventory.inventory_page'))

    slot = EQUIP_SLOTS.get(row['type'])
    if not slot:
        flash(tf("This item type cannot be equipped."), 'error')
        return redirect(url_for('inventory.inventory_page'))

    db.execute(f"UPDATE players SET {slot}=? WHERE user_id=?", (row['item_id'], uid))
    db.commit()
    item_name = db.execute("SELECT name FROM items WHERE id=?", (row['item_id'],)).fetchone()['name']
    flash(f"✅ Equipped {item_name}.", 'success')
    return redirect(url_for('inventory.inventory_page'))


@bp.route('/inventory/use/<int:inv_id>', methods=['POST'])
@login_required
def use_item(inv_id):
    db = get_db()
    uid = g.player['user_id']
    row = db.execute(
        "SELECT inv.id, inv.qty, i.name, i.type, i.effect_json FROM inventory inv JOIN items i ON inv.item_id=i.id WHERE inv.id=? AND inv.user_id=?",
        (inv_id, uid)
    ).fetchone()
    if not row:
        flash(tf("Item not found."), 'error')
        return redirect(url_for('inventory.inventory_page'))
    if row['type'] != 'consumable':
        flash("That item can't be used directly.", 'error')
        return redirect(url_for('inventory.inventory_page'))

    effects = json.loads(row['effect_json'] or '{}')
    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())

    updates = {}
    msgs = []
    energy_gain = effects.get('energy', 0)
    health_gain = effects.get('health', 0)
    if energy_gain:
        updates['energy'] = min(player['energy'] + energy_gain, player['energy_max'])
        msgs.append(f"+{energy_gain} energy")
    if health_gain:
        updates['health'] = min(player['health'] + health_gain, player['health_max'])
        msgs.append(f"+{health_gain} health")

    if updates:
        cols = ', '.join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE players SET {cols} WHERE user_id=?", list(updates.values()) + [uid])

    # Remove one from inventory
    if row['qty'] > 1:
        db.execute("UPDATE inventory SET qty=qty-1 WHERE id=?", (inv_id,))
    else:
        db.execute("DELETE FROM inventory WHERE id=?", (inv_id,))
    db.commit()

    flash(f"✅ Used {row['name']}: {', '.join(msgs) or 'no effect'}.", 'success')
    return redirect(url_for('inventory.inventory_page'))
