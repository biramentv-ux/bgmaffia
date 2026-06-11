from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, g, current_app
from .i18n import tf
from .auth import login_required
from .db import get_db

bp = Blueprint('business', __name__)


def _accrued(owned, income_per_hour, cap_hours):
    """Earnings since last collection, capped (computed-on-read, no tick needed)."""
    last = datetime.fromisoformat(owned['last_collected'])
    hours = min((datetime.utcnow() - last).total_seconds() / 3600, cap_hours)
    return int(hours * income_per_hour)


@bp.route('/business')
@login_required
def business_page():
    db = get_db()
    uid = g.player['user_id']
    cap = current_app.config['BUSINESS_ACCRUAL_CAP_H']
    owned_rows = {r['business_id']: dict(r) for r in db.execute(
        "SELECT * FROM player_businesses WHERE user_id=?", (uid,)).fetchall()}
    businesses = []
    for b in db.execute("SELECT * FROM businesses ORDER BY price").fetchall():
        entry = dict(b)
        owned = owned_rows.get(b['id'])
        entry['owned'] = owned is not None
        entry['accrued'] = _accrued(owned, b['income_per_hour'], cap) if owned else 0
        businesses.append(entry)
    return render_template('business/business.html', businesses=businesses, cap_hours=cap)


@bp.route('/business/buy/<int:biz_id>', methods=['POST'])
@login_required
def buy(biz_id):
    db = get_db()
    uid = g.player['user_id']
    biz = db.execute("SELECT * FROM businesses WHERE id=?", (biz_id,)).fetchone()
    if not biz:
        flash(tf("Unknown business."), 'error')
        return redirect(url_for('business.business_page'))
    if g.player['level'] < biz['min_level']:
        flash(f"Requires level {biz['min_level']}.", 'error')
        return redirect(url_for('business.business_page'))

    db.execute("BEGIN IMMEDIATE")
    already = db.execute("SELECT 1 FROM player_businesses WHERE user_id=? AND business_id=?",
                         (uid, biz_id)).fetchone()
    cash = db.execute("SELECT cash FROM players WHERE user_id=?", (uid,)).fetchone()['cash']
    if already:
        db.execute("ROLLBACK")
        flash(tf("You already own this business."), 'error')
        return redirect(url_for('business.business_page'))
    if cash < biz['price']:
        db.execute("ROLLBACK")
        flash(f"Not enough cash (need ${biz['price']:,}).", 'error')
        return redirect(url_for('business.business_page'))

    db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?",
               (biz['price'], uid, biz['price']))
    db.execute("INSERT INTO player_businesses(user_id,business_id) VALUES(?,?)", (uid, biz_id))
    db.commit()
    flash(f"🏢 You now own {biz['name']}! It earns ${biz['income_per_hour']:,}/hour.", 'success')
    return redirect(url_for('business.business_page'))


@bp.route('/business/collect/<int:biz_id>', methods=['POST'])
@login_required
def collect(biz_id):
    db = get_db()
    uid = g.player['user_id']
    cap = current_app.config['BUSINESS_ACCRUAL_CAP_H']

    db.execute("BEGIN IMMEDIATE")
    owned = db.execute("SELECT * FROM player_businesses WHERE user_id=? AND business_id=?",
                       (uid, biz_id)).fetchone()
    if not owned:
        db.execute("ROLLBACK")
        flash("You don't own that business.", 'error')
        return redirect(url_for('business.business_page'))
    biz = db.execute("SELECT * FROM businesses WHERE id=?", (biz_id,)).fetchone()
    earned = _accrued(dict(owned), biz['income_per_hour'], cap)
    if earned <= 0:
        db.execute("ROLLBACK")
        flash(tf("Nothing to collect yet."), 'error')
        return redirect(url_for('business.business_page'))

    db.execute("UPDATE players SET cash=cash+?, total_earned=total_earned+? WHERE user_id=?",
               (earned, earned, uid))
    db.execute("UPDATE player_businesses SET last_collected=? WHERE user_id=? AND business_id=?",
               (datetime.utcnow().isoformat(), uid, biz_id))
    db.commit()
    flash(f"💵 Collected ${earned:,} from {biz['name']}.", 'success')
    return redirect(url_for('business.business_page'))
