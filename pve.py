"""pve.py — Player vs Environment: fight NPC enemies for cash, XP, loot."""
import random
from datetime import timedelta

from flask import Blueprint, g, render_template, request, redirect, url_for, flash

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf
from game import (grant_xp, notify, now, ts, get_class, get_vip_tier,
                  get_active_boost, VIP_XP_MULT, VIP_CASH_MULT, status_locks)

bp = Blueprint("pve", __name__)

ENERGY_COST = 10


def _fight_npc(player, enemy):
    cls = get_class(player)
    p_atk = player["strength"] * cls["fight_dmg"]
    p_def = (player["strength"] * 0.5 + player["stamina"] * 0.5) * cls["fight_def"]
    e_atk = float(enemy["strength"])
    e_def = float(enemy["strength"]) * 0.4
    p_hp = float(player["health"])
    e_hp = float(enemy["health"])
    log, turns = [], 0

    def hit_chance(atk, dfn):
        return max(0.05, min(0.95, 0.5 + (atk - dfn) / (atk + dfn + 1)))

    while turns < 20 and p_hp > 0 and e_hp > 0:
        turns += 1
        if random.random() < hit_chance(p_atk, e_def):
            dmg = max(1, int(p_atk * random.uniform(0.8, 1.2)))
            e_hp -= dmg
            log.append(f"You hit {enemy['name']} for {dmg}.")
        else:
            log.append(f"You miss {enemy['name']}.")
        if e_hp <= 0:
            break
        if random.random() < hit_chance(e_atk, p_def):
            dmg = max(1, int(e_atk * random.uniform(0.8, 1.2)))
            p_hp -= dmg
            log.append(f"{enemy['name']} hits you for {dmg}.")
        else:
            log.append(f"{enemy['name']} misses.")

    outcome = "win" if e_hp <= 0 else ("loss" if p_hp <= 0 else "stalemate")
    return {"outcome": outcome, "a_hp": max(0, p_hp), "log": log}


@bp.route("/pve")
@login_required
def pve_page():
    con = get_db()
    enemies = con.execute("SELECT * FROM npc_enemies ORDER BY min_level").fetchall()
    return render_template("pve.html", enemies=enemies)


@bp.route("/pve/fight/<int:enemy_id>", methods=("POST",))
@login_required
def fight_npc(enemy_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    if status_locks(g.user):
        flash("You're locked up — can't fight right now.")
        return redirect(url_for("pve.pve_page"))

    enemy = con.execute("SELECT * FROM npc_enemies WHERE id=?", (enemy_id,)).fetchone()
    if not enemy:
        flash("Enemy not found.")
        return redirect(url_for("pve.pve_page"))
    if g.user["level"] < enemy["min_level"]:
        flash(f"You need level {enemy['min_level']} for this encounter.")
        return redirect(url_for("pve.pve_page"))

    result = _fight_npc(g.user, enemy)

    def work(c):
        guarded(c, "UPDATE players SET energy=energy-? WHERE user_id=? AND energy>=?",
                (ENERGY_COST, uid, ENERGY_COST))
        vip = get_vip_tier(g.user)
        xp_boost = 2.0 if get_active_boost(c, uid, "xp_boost") else 1.0
        cash_boost = 2.0 if get_active_boost(c, uid, "cash_boost") else 1.0

        if result["outcome"] == "win":
            base_payout = random.randint(enemy["reward_min"], enemy["reward_max"])
            payout = int(base_payout * VIP_CASH_MULT.get(vip, 1.0) * cash_boost)
            xp = int(enemy["xp_reward"] * VIP_XP_MULT.get(vip, 1.0) * xp_boost)
            c.execute("UPDATE players SET cash=cash+?, health=? WHERE user_id=?",
                      (payout, int(result["a_hp"]), uid))
            grant_xp(c, uid, xp, 1)
            # possible loot drop
            loot_name = None
            if enemy["loot_item_id"] and random.random() < enemy["loot_chance"]:
                c.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES (?,?,1)",
                          (uid, enemy["loot_item_id"]))
                item = c.execute("SELECT name FROM items WHERE id=?",
                                 (enemy["loot_item_id"],)).fetchone()
                loot_name = item["name"] if item else "item"
            c.execute(
                "INSERT INTO pve_log(user_id,enemy_id,outcome,payout,xp) VALUES (?,?,?,?,?)",
                (uid, enemy_id, "win", payout, xp))
            return "win", payout, xp, loot_name
        else:
            # lost: hospitalise
            hosp = ts(now() + timedelta(minutes=5))
            c.execute("UPDATE players SET health=1, hospital_until=? WHERE user_id=?", (hosp, uid))
            c.execute(
                "INSERT INTO pve_log(user_id,enemy_id,outcome,payout,xp) VALUES (?,?,?,0,0)",
                (uid, enemy_id, result["outcome"]))
            return result["outcome"], 0, 0, None

    outcome, payout, xp, loot = transact(con, work)

    if outcome == "win":
        msg = f"Defeated {enemy['name']}! +${payout:,} · +{xp} XP."
        if loot:
            msg += f" Looted: {loot}!"
        flash(msg)
    else:
        flash(f"{enemy['name']} beat you. You've been rushed to hospital.")

    return redirect(url_for("pve.pve_page"))
