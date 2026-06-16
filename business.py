"""business.py — front businesses that generate passive income."""
from datetime import timedelta

from flask import Blueprint, g, render_template, request, redirect, url_for, flash

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf
from game import now, ts, parse

bp = Blueprint("business", __name__)


def _accrued(pb, biz):
    if not pb["last_collected"]:
        return 0
    hours = (now() - parse(pb["last_collected"])).total_seconds() / 3600
    hours = min(hours, biz["max_accrual_hours"])
    return int(hours * biz["income_per_hour"])


@bp.route("/businesses")
@login_required
def businesses_page():
    con = get_db()
    uid = g.user["user_id"]
    all_biz = con.execute("SELECT * FROM businesses ORDER BY price").fetchall()
    owned_rows = con.execute(
        "SELECT pb.*, b.name, b.income_per_hour, b.max_accrual_hours "
        "FROM player_businesses pb JOIN businesses b ON b.id=pb.business_id "
        "WHERE pb.user_id=?", (uid,)).fetchall()
    owned = {r["business_id"]: r for r in owned_rows}
    accrued = {bid: _accrued(r, r) for bid, r in owned.items()}
    return render_template("business.html", all_biz=all_biz, owned=owned, accrued=accrued)


@bp.route("/businesses/buy/<int:biz_id>", methods=("POST",))
@login_required
def buy_business(biz_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    biz = con.execute("SELECT * FROM businesses WHERE id=?", (biz_id,)).fetchone()
    if not biz:
        flash("Business not found.")
        return redirect(url_for("business.businesses_page"))
    if g.user["level"] < biz["min_level"]:
        flash(f"Requires level {biz['min_level']}.")
        return redirect(url_for("business.businesses_page"))

    def work(c):
        if c.execute("SELECT 1 FROM player_businesses WHERE user_id=? AND business_id=?",
                     (uid, biz_id)).fetchone():
            raise TxFailed("owned")
        guarded(c, "UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?",
                (biz["price"], uid, biz["price"]))
        c.execute("INSERT INTO player_businesses(user_id,business_id,last_collected) VALUES (?,?,?)",
                  (uid, biz_id, ts(now())))
    try:
        transact(con, work)
        flash(f"Purchased {biz['name']}. Income starts now.")
    except TxFailed as e:
        flash("You already own this business." if str(e) == "owned" else "Not enough cash.")
    return redirect(url_for("business.businesses_page"))


@bp.route("/businesses/collect/<int:biz_id>", methods=("POST",))
@login_required
def collect_income(biz_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        pb = c.execute(
            "SELECT pb.last_collected, b.income_per_hour, b.max_accrual_hours "
            "FROM player_businesses pb JOIN businesses b ON b.id=pb.business_id "
            "WHERE pb.user_id=? AND pb.business_id=?", (uid, biz_id)).fetchone()
        if not pb:
            raise TxFailed("nope")
        income = _accrued(pb, pb)
        if income < 1:
            raise TxFailed("nothing")
        c.execute("UPDATE player_businesses SET last_collected=? WHERE user_id=? AND business_id=?",
                  (ts(now()), uid, biz_id))
        c.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (income, uid))
        return income
    try:
        income = transact(con, work)
        flash(f"Collected ${income:,} from your business.")
    except TxFailed as e:
        flash("Nothing to collect yet." if str(e) == "nothing" else "Business not found.")
    return redirect(url_for("business.businesses_page"))
