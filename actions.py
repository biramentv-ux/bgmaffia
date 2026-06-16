"""actions.py — the core single-player loop blueprints:
dashboard, crimes, gym, attack/fight, hospital, jail, bank, shop, inventory.
Every cost, cooldown and roll is computed server-side inside BEGIN IMMEDIATE.
"""
import json
import random
from datetime import timedelta

from flask import (Blueprint, g, render_template, request, redirect, url_for,
                   flash, jsonify)

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf
from game import (lazy_regen, now, ts, parse, grant_xp, notify, resolve_fight,
                  equipment_bonus, bump_mission, check_achievements, award,
                  status_locks, event_modifiers, get_class, get_skill_bonuses,
                  VIP_XP_MULT, VIP_CASH_MULT, get_vip_tier, get_active_boost)

bp = Blueprint("game", __name__)


def require_free():
    """Return an error string if the player is locked in jail/hospital."""
    locks = status_locks(g.user)
    if "jail" in locks:
        return "You're in jail."
    if "hospital" in locks:
        return "You're in the hospital."
    return None


# =================== Dashboard ===================

@bp.route("/")
@login_required
def dashboard():
    con = get_db()
    feed = con.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 8",
        (g.user["user_id"],)).fetchall()
    online = con.execute(
        "SELECT COUNT(*) c FROM users WHERE last_active >= datetime('now','-5 minutes')"
    ).fetchone()["c"]
    return render_template("dashboard.html", feed=feed, online=online)


# =================== Crimes ===================

@bp.route("/crimes")
@login_required
def crimes():
    con = get_db()
    rows = con.execute("SELECT * FROM crimes ORDER BY min_level").fetchall()
    cds = {r["crime_id"]: r["next_at"] for r in con.execute(
        "SELECT crime_id,next_at FROM crime_cooldowns WHERE user_id=?",
        (g.user["user_id"],)).fetchall()}
    crime_list = []
    for c in rows:
        nxt = cds.get(c["id"])
        remaining = 0
        if nxt and parse(nxt) > now():
            remaining = int((parse(nxt) - now()).total_seconds())
        crime_list.append({"c": c, "remaining": remaining})
    return render_template("crimes.html", crimes=crime_list)


@bp.route("/crimes/<int:crime_id>/commit", methods=("POST",))
@login_required
def commit_crime(crime_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    locked = require_free()
    if locked:
        return _crime_response(False, locked)

    crime = con.execute("SELECT * FROM crimes WHERE id=?", (crime_id,)).fetchone()
    if not crime:
        return _crime_response(False, "No such crime.")
    mods = event_modifiers(con)

    def work(c):
        lazy_regen(c, uid)
        p = c.execute(
            "SELECT level,energy,nerve,strength,intellect,player_class,vip_tier,vip_until "
            "FROM players WHERE user_id=?", (uid,)).fetchone()
        if p["level"] < crime["min_level"]:
            raise TxFailed("level")
        if p["energy"] < crime["energy_cost"] or p["nerve"] < crime["nerve_cost"]:
            raise TxFailed("resources")
        cd = c.execute(
            "SELECT next_at FROM crime_cooldowns WHERE user_id=? AND crime_id=?",
            (uid, crime_id)).fetchone()
        if cd and parse(cd["next_at"]) > now():
            raise TxFailed("cooldown")

        guarded(c,
                "UPDATE players SET energy=energy-?, nerve=nerve-? "
                "WHERE user_id=? AND energy>=? AND nerve>=?",
                (crime["energy_cost"], crime["nerve_cost"], uid,
                 crime["energy_cost"], crime["nerve_cost"]))

        # success roll with class/skill bonuses applied before rolling
        cls = get_class(p)
        sk = get_skill_bonuses(c, uid)
        vip = get_vip_tier(p)
        stat_val = p[crime["skill_used"]] if crime["skill_used"] in p.keys() else p["strength"]
        chance = min(0.95, crime["base_success"] * cls['crime_mult']
                     + (stat_val - 10) * 0.004 + mods["success"] + sk['crime_success'])
        success = random.random() < chance

        cd_secs = max(10, int(crime["cooldown_sec"] * (1.0 - sk['crime_cd'])))
        nxt = ts(now() + timedelta(seconds=cd_secs))
        c.execute(
            "INSERT INTO crime_cooldowns(user_id,crime_id,next_at) VALUES (?,?,?) "
            "ON CONFLICT(user_id,crime_id) DO UPDATE SET next_at=?",
            (uid, crime_id, nxt, nxt))
        c.execute("UPDATE players SET crimes_done=crimes_done+1 WHERE user_id=?", (uid,))
        bump_mission(c, uid, "crimes")

        if success:
            cash_mult = VIP_CASH_MULT.get(vip, 1.0) * cls['crime_payout'] * (1 + sk['crime_cash'])
            cash_boost = 2.0 if get_active_boost(c, uid, "cash_boost") else 1.0
            payout = int(random.randint(crime["payout_min"], crime["payout_max"])
                         * mods["payout"] * cash_mult * cash_boost)
            xp_mult = VIP_XP_MULT.get(vip, 1.0) * (2.0 if get_active_boost(c, uid, "xp_boost") else 1.0)
            xp = int(crime["xp_reward"] * mods["xp"] * xp_mult)
            c.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (payout, uid))
            grant_xp(c, uid, xp, crime["respect_reward"])
            c.execute("INSERT INTO crime_log(user_id,crime_id,success,payout) VALUES (?,?,1,?)",
                      (uid, crime_id, payout))
            check_achievements(c, uid)
            return {"ok": True, "success": True,
                    "msg": f"Success! +${payout:,} and +{xp} XP."}
        else:
            jail = crime["jail_sec"]
            c.execute("UPDATE players SET jail_until=? WHERE user_id=?",
                      (ts(now() + timedelta(seconds=jail)), uid))
            c.execute("INSERT INTO crime_log(user_id,crime_id,success,payout) VALUES (?,?,0,0)",
                      (uid, crime_id))
            award(c, uid, "jailbird")
            return {"ok": True, "success": False,
                    "msg": f"Busted! You're in jail for {jail // 60}m {jail % 60}s."}

    try:
        res = transact(con, work)
    except TxFailed as e:
        reason = {"level": "Your level is too low.",
                  "resources": "Not enough energy or nerve.",
                  "cooldown": "That crime is still on cooldown."}.get(str(e), "Can't do that.")
        return _crime_response(False, reason)
    return _crime_response(res["success"], res["msg"])


def _crime_response(success, msg):
    con = get_db()
    lazy_regen(con, g.user["user_id"])
    con.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        p = con.execute("SELECT energy,nerve,cash,health FROM players WHERE user_id=?",
                        (g.user["user_id"],)).fetchone()
        return jsonify({"ok": True, "success": success, "msg": msg,
                        "energy": p["energy"], "nerve": p["nerve"],
                        "cash": p["cash"], "health": p["health"]})
    flash(msg)
    return redirect(url_for("game.crimes"))


# =================== Gym ===================

@bp.route("/gym")
@login_required
def gym():
    return render_template("gym.html")


@bp.route("/gym/train", methods=("POST",))
@login_required
def train():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    stat = request.form.get("stat")
    if stat not in ("strength", "stamina", "intellect", "sexappeal"):
        flash("Unknown skill.")
        return redirect(url_for("game.gym"))
    locked = require_free()
    if locked:
        flash(locked)
        return redirect(url_for("game.gym"))

    def work(c):
        lazy_regen(c, uid)
        p = c.execute(f"SELECT energy,{stat} AS s FROM players WHERE user_id=?", (uid,)).fetchone()
        cost = max(1, -(-p["s"] // 4))  # ceil(stat/4)
        if p["energy"] < cost:
            raise TxFailed("energy")
        guarded(c, "UPDATE players SET energy=energy-? WHERE user_id=? AND energy>=?",
                (cost, uid, cost))
        c.execute(f"UPDATE players SET {stat}={stat}+1 WHERE user_id=?", (uid,))
        bump_mission(c, uid, "trains")
        return cost

    try:
        cost = transact(con, work)
    except TxFailed:
        flash("Not enough energy to train.")
    else:
        flash(f"You trained {stat}. (-{cost} energy)")
    return redirect(url_for("game.gym"))


@bp.route("/skills/spend", methods=("POST",))
@login_required
def spend_skill():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    stat = request.form.get("stat")
    if stat not in ("strength", "stamina", "intellect", "sexappeal"):
        flash("Unknown skill.")
        return redirect(url_for("game.gym"))

    def work(c):
        guarded(c, "UPDATE players SET skill_points=skill_points-1 WHERE user_id=? AND skill_points>=1",
                (uid,))
        c.execute(f"UPDATE players SET {stat}={stat}+1 WHERE user_id=?", (uid,))
    try:
        transact(con, work)
        flash(f"+1 {stat} from a skill point.")
    except TxFailed:
        flash("No skill points to spend.")
    return redirect(url_for("game.gym"))


# =================== Attack / Fight ===================

@bp.route("/attack")
@login_required
def attack_list():
    con = get_db()
    uid = g.user["user_id"]
    targets = con.execute(
        "SELECT u.id,u.username,p.level,p.respect FROM users u JOIN players p ON p.user_id=u.id "
        "WHERE u.id!=? AND u.is_banned=0 AND u.last_active>=datetime('now','-5 minutes') "
        "AND (p.protection_until IS NULL OR p.protection_until<datetime('now')) "
        "AND (p.jail_until IS NULL OR p.jail_until<datetime('now')) "
        "AND (p.hospital_until IS NULL OR p.hospital_until<datetime('now')) "
        "ORDER BY p.level DESC LIMIT 50", (uid,)).fetchall()
    return render_template("attack.html", targets=targets)


@bp.route("/attack/<int:target_id>", methods=("POST",))
@login_required
def attack(target_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    if target_id == uid:
        flash("You can't attack yourself.")
        return redirect(url_for("game.attack_list"))
    locked = require_free()
    if locked:
        flash(locked)
        return redirect(url_for("game.attack_list"))

    attacker = g.user
    defender = con.execute(
        "SELECT p.*, u.username,u.last_active FROM players p JOIN users u ON u.id=p.user_id "
        "WHERE p.user_id=?", (target_id,)).fetchone()
    if not defender:
        flash("No such player.")
        return redirect(url_for("game.attack_list"))

    # server-side eligibility
    locks = status_locks(defender)
    online = defender["last_active"] and parse(defender["last_active"]) > now() - timedelta(minutes=5)
    if not online:
        flash("That player went offline.")
        return redirect(url_for("game.attack_list"))
    if locks:
        flash("That player is protected, in jail, or hospitalized.")
        return redirect(url_for("game.attack_list"))
    if attacker["energy"] < 10:
        flash("You need at least 10 energy to attack.")
        return redirect(url_for("game.attack_list"))

    result = resolve_fight(con, attacker, defender)

    def _hosp_mins(player_row, base_mins):
        """Apply class + skill hospital_mult to reduce hospital time."""
        from game import get_class as _gc, get_skill_bonuses as _gsb
        cls = _gc(player_row)
        sk = _gsb(con, player_row["user_id"])
        mult = cls["hospital_mult"] * max(0.1, 1.0 - sk["hospital_mult"])
        return max(1, int(base_mins * mult))

    def work(c):
        lazy_regen(c, uid)
        guarded(c, "UPDATE players SET energy=energy-10 WHERE user_id=? AND energy>=10", (uid,))
        cash_stolen = respect_gain = 0
        winner = None
        if result["outcome"] == "win":
            winner = uid
            victim_cash = c.execute("SELECT cash FROM players WHERE user_id=?",
                                    (target_id,)).fetchone()["cash"]
            cash_stolen = int(victim_cash * random.uniform(0.10, 0.20))
            respect_gain = max(1, 5 + (defender["level"] - attacker["level"]) * 2)
            def_hosp_mins = _hosp_mins(defender, random.randint(15, 30))
            hosp = ts(now() + timedelta(minutes=def_hosp_mins))
            prot = ts(now() + timedelta(minutes=15))
            c.execute("UPDATE players SET cash=cash+?, fights_won=fights_won+1, health=? WHERE user_id=?",
                      (cash_stolen, result["a_hp"], uid))
            c.execute("UPDATE players SET cash=cash-?, fights_lost=fights_lost+1, "
                      "hospital_until=?, protection_until=?, health=health_max WHERE user_id=?",
                      (cash_stolen, hosp, prot, target_id))
            grant_xp(c, uid, 15, respect_gain)
            bump_mission(c, uid, "fight_wins")
            notify(c, target_id,
                   f"{attacker['username']} beat you and stole ${cash_stolen:,}.")
            notify(c, uid, f"You beat {defender['username']} and took ${cash_stolen:,}.")
            check_achievements(c, uid)
            # bounty payout
            b = c.execute("SELECT id,amount FROM bounties WHERE target_id=? AND status='open' "
                          "ORDER BY amount DESC LIMIT 1", (target_id,)).fetchone()
            if b:
                c.execute("UPDATE bounties SET status='claimed', claimed_by=? WHERE id=?", (uid, b["id"]))
                c.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (b["amount"], uid))
                notify(c, uid, f"Bounty claimed on {defender['username']}: +${b['amount']:,}.")
        elif result["outcome"] == "loss":
            winner = target_id
            atk_hosp_mins = _hosp_mins(attacker, random.randint(15, 30))
            hosp = ts(now() + timedelta(minutes=atk_hosp_mins))
            c.execute("UPDATE players SET health=health_max, hospital_until=?, "
                      "fights_lost=fights_lost+1 WHERE user_id=?", (hosp, uid))
            # defender wins — count their victory and check achievements
            c.execute("UPDATE players SET fights_won=fights_won+1 WHERE user_id=?", (target_id,))
            check_achievements(c, target_id)
            notify(c, target_id, f"You fought off {attacker['username']}.")
        else:
            c.execute("UPDATE players SET health=? WHERE user_id=?", (result["a_hp"], uid))

        c.execute(
            "INSERT INTO fights(attacker_id,defender_id,winner_id,cash_stolen,respect_gain,"
            "turns,outcome,log_json) VALUES (?,?,?,?,?,?,?,?)",
            (uid, target_id, winner, cash_stolen, respect_gain, result["turns"],
             result["outcome"], json.dumps(result["log"])))
        return c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    fight_id = transact(con, work)
    return redirect(url_for("game.fight_detail", fight_id=fight_id))


@bp.route("/fight/<int:fight_id>")
@login_required
def fight_detail(fight_id):
    con = get_db()
    f = con.execute(
        "SELECT f.*, a.username AS attacker, d.username AS defender FROM fights f "
        "JOIN users a ON a.id=f.attacker_id JOIN users d ON d.id=f.defender_id WHERE f.id=?",
        (fight_id,)).fetchone()
    if not f or g.user["user_id"] not in (f["attacker_id"], f["defender_id"]):
        flash("Fight not found.")
        return redirect(url_for("game.attack_list"))
    log = json.loads(f["log_json"] or "[]")
    return render_template("fight.html", f=f, log=log)


# =================== Hospital ===================

@bp.route("/hospital")
@login_required
def hospital():
    return render_template("hospital.html")


@bp.route("/hospital/heal", methods=("POST",))
@login_required
def heal():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        p = c.execute("SELECT hospital_until,cash FROM players WHERE user_id=?", (uid,)).fetchone()
        until = parse(p["hospital_until"]) if p["hospital_until"] else None
        if not until or until <= now():
            raise TxFailed("free")
        mins = max(1, int((until - now()).total_seconds() // 60) + 1)
        cost = mins * 200  # plastic surgery: $200/min
        if p["cash"] < cost:
            raise TxFailed("cash")
        guarded(c, "UPDATE players SET cash=cash-?, hospital_until=NULL, health=health_max "
                "WHERE user_id=? AND cash>=?", (cost, uid, cost))
        return cost

    try:
        cost = transact(con, work)
        flash(f"Patched up by the back-alley surgeon for ${cost:,}.")
    except TxFailed as e:
        flash("You're not hurt." if str(e) == "free" else "Not enough cash to heal.")
    return redirect(url_for("game.hospital"))


# =================== Jail ===================

@bp.route("/jail")
@login_required
def jail():
    con = get_db()
    inmates = con.execute(
        "SELECT u.id,u.username,p.jail_until,p.level FROM players p JOIN users u ON u.id=p.user_id "
        "WHERE p.jail_until>datetime('now') ORDER BY p.jail_until DESC LIMIT 30").fetchall()
    return render_template("jail.html", inmates=inmates)


@bp.route("/jail/bail", methods=("POST",))
@login_required
def bail():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        p = c.execute("SELECT jail_until,cash FROM players WHERE user_id=?", (uid,)).fetchone()
        until = parse(p["jail_until"]) if p["jail_until"] else None
        if not until or until <= now():
            raise TxFailed("free")
        mins = max(1, int((until - now()).total_seconds() // 60) + 1)
        cost = mins * 500
        if p["cash"] < cost:
            raise TxFailed("cash")
        guarded(c, "UPDATE players SET cash=cash-?, jail_until=NULL WHERE user_id=? AND cash>=?",
                (cost, uid, cost))
        return cost
    try:
        cost = transact(con, work)
        flash(f"You posted ${cost:,} bail and walked free.")
    except TxFailed as e:
        flash("You're not in jail." if str(e) == "free" else "Not enough cash for bail.")
    return redirect(url_for("game.jail"))


@bp.route("/jail/bust/<int:target_id>", methods=("POST",))
@login_required
def bust(target_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    if status_locks(g.user):
        flash("You can't bust people while locked up.")
        return redirect(url_for("game.jail"))

    def work(c):
        lazy_regen(c, uid)
        me = c.execute("SELECT nerve FROM players WHERE user_id=?", (uid,)).fetchone()
        if me["nerve"] < 3:
            raise TxFailed("nerve")
        tgt = c.execute("SELECT jail_until,intellect FROM players WHERE user_id=?",
                        (target_id,)).fetchone()
        if not tgt or not tgt["jail_until"] or parse(tgt["jail_until"]) <= now():
            raise TxFailed("notjailed")
        guarded(c, "UPDATE players SET nerve=nerve-3 WHERE user_id=? AND nerve>=3", (uid,))
        success = random.random() < 0.45
        if success:
            c.execute("UPDATE players SET jail_until=NULL WHERE user_id=?", (target_id,))
            grant_xp(c, uid, 10, 2)
            notify(c, target_id, "Someone busted you out of jail!")
            return True
        return False
    try:
        ok = transact(con, work)
        flash("You busted them out! +10 XP." if ok else "The guards spotted you. No luck.")
    except TxFailed as e:
        flash({"nerve": "You need 3 nerve to attempt a bust.",
               "notjailed": "That player isn't in jail."}.get(str(e), "Can't do that."))
    return redirect(url_for("game.jail"))


# =================== Bank ===================

@bp.route("/bank")
@login_required
def bank():
    con = get_db()
    log = con.execute("SELECT * FROM bank_log WHERE user_id=? ORDER BY id DESC LIMIT 10",
                      (g.user["user_id"],)).fetchall()
    return render_template("bank.html", log=log)


@bp.route("/bank/deposit", methods=("POST",))
@login_required
def deposit():
    check_csrf()
    return _bank_move(request.form.get("amount"), "deposit")


@bp.route("/bank/withdraw", methods=("POST",))
@login_required
def withdraw():
    check_csrf()
    return _bank_move(request.form.get("amount"), "withdraw")


def _bank_move(amount, kind):
    con = get_db()
    uid = g.user["user_id"]
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        flash("Enter a number.")
        return redirect(url_for("game.bank"))
    if amount <= 0:
        flash("Amount must be positive.")
        return redirect(url_for("game.bank"))

    def work(c):
        if kind == "deposit":
            guarded(c, "UPDATE players SET cash=cash-?, bank=bank+? WHERE user_id=? AND cash>=?",
                    (amount, amount, uid, amount))
            bump_mission(c, uid, "deposits")
        else:
            guarded(c, "UPDATE players SET bank=bank-?, cash=cash+? WHERE user_id=? AND bank>=?",
                    (amount, amount, uid, amount))
        c.execute("INSERT INTO bank_log(user_id,kind,amount) VALUES (?,?,?)", (uid, kind, amount))
        check_achievements(c, uid)
    try:
        transact(con, work)
        flash(f"{kind.title()} of ${amount:,} done.")
    except TxFailed:
        flash("You don't have that much.")
    return redirect(url_for("game.bank"))


# =================== Shop & Inventory ===================

@bp.route("/shop")
@login_required
def shop():
    con = get_db()
    items = con.execute("SELECT * FROM items ORDER BY type, price").fetchall()
    return render_template("shop.html", items=items)


@bp.route("/shop/buy/<int:item_id>", methods=("POST",))
@login_required
def buy(item_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    item = con.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        flash("No such item.")
        return redirect(url_for("game.shop"))

    def work(c):
        p = c.execute("SELECT cash,level FROM players WHERE user_id=?", (uid,)).fetchone()
        if p["level"] < item["min_level"]:
            raise TxFailed("level")
        guarded(c, "UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?",
                (item["price"], uid, item["price"]))
        if item["stackable"]:
            existing = c.execute("SELECT id FROM inventory WHERE user_id=? AND item_id=?",
                                 (uid, item_id)).fetchone()
            if existing:
                c.execute("UPDATE inventory SET qty=qty+1 WHERE id=?", (existing["id"],))
            else:
                c.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES (?,?,1)", (uid, item_id))
        else:
            c.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES (?,?,1)", (uid, item_id))
    try:
        transact(con, work)
        flash(f"Bought {item['name']} for ${item['price']:,}.")
    except TxFailed as e:
        flash("Your level is too low for that." if str(e) == "level" else "Not enough cash.")
    return redirect(url_for("game.shop"))


@bp.route("/inventory")
@login_required
def inventory():
    con = get_db()
    inv = con.execute(
        "SELECT v.id,v.qty,i.* FROM inventory v JOIN items i ON i.id=v.item_id "
        "WHERE v.user_id=? ORDER BY i.type", (g.user["user_id"],)).fetchall()
    return render_template("inventory.html", inv=inv)


@bp.route("/equip/<int:inv_id>", methods=("POST",))
@login_required
def equip(inv_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    row = con.execute(
        "SELECT v.id,i.type FROM inventory v JOIN items i ON i.id=v.item_id "
        "WHERE v.id=? AND v.user_id=?", (inv_id, uid)).fetchone()
    if not row:
        flash("Item not found.")
        return redirect(url_for("game.inventory"))
    slot = {"weapon": "equipped_weapon", "car": "equipped_car",
            "dog": "equipped_dog", "armor": "equipped_armor"}.get(row["type"])
    if not slot:
        flash("That item can't be equipped.")
        return redirect(url_for("game.inventory"))
    con.execute(f"UPDATE players SET {slot}=? WHERE user_id=?", (inv_id, uid))
    con.commit()
    flash("Equipped.")
    return redirect(url_for("game.inventory"))


@bp.route("/use/<int:inv_id>", methods=("POST",))
@login_required
def use_item(inv_id):
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]

    def work(c):
        row = c.execute(
            "SELECT v.id,v.qty,i.effect_json,i.name FROM inventory v JOIN items i ON i.id=v.item_id "
            "WHERE v.id=? AND v.user_id=?", (inv_id, uid)).fetchone()
        if not row or not row["effect_json"]:
            raise TxFailed("noeffect")
        lazy_regen(c, uid)
        effect = json.loads(row["effect_json"])
        for key, amt in effect.items():
            if key in ("energy", "nerve", "health"):
                c.execute(
                    f"UPDATE players SET {key}=MIN({key}_max,{key}+?) WHERE user_id=?", (amt, uid))
        if row["qty"] > 1:
            c.execute("UPDATE inventory SET qty=qty-1 WHERE id=?", (inv_id,))
        else:
            c.execute("DELETE FROM inventory WHERE id=?", (inv_id,))
        return row["name"]
    try:
        name = transact(con, work)
        flash(f"Used {name}.")
    except TxFailed:
        flash("That item can't be used.")
    return redirect(url_for("game.inventory"))


@bp.route("/profile/<int:user_id>")
@login_required
def profile(user_id):
    con = get_db()
    p = con.execute(
        "SELECT p.*, u.username,u.created_at,u.last_active, g.name AS gang_name "
        "FROM players p JOIN users u ON u.id=p.user_id LEFT JOIN gangs g ON g.id=p.gang_id "
        "WHERE p.user_id=?", (user_id,)).fetchone()
    if not p:
        flash("No such player.")
        return redirect(url_for("home.dashboard"))
    return render_template("profile.html", p=p)
