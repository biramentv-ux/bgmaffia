import random
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .i18n import tf
from .auth import login_required
from .db import get_db
from .game import (maybe_level_up, mission_progress, check_achievements,
                   get_class, get_skill_bonuses, get_vip_tier,
                   VIP_XP_MULT, get_active_boost, _effective_stats)

bp = Blueprint('pve', __name__)


def _fight_npc(player, enemy):
    """Simulate fight between player and NPC. Returns (won, hp_lost)."""
    # Player effective attack and defense (simplified, no DB needed for NPC)
    p_str  = player['strength']
    p_sta  = player['stamina']
    cls    = get_class(player)
    p_atk  = p_str * cls['fight_dmg']
    p_def  = (p_str * 0.5 + p_sta * 0.5) * cls['fight_def']

    e_atk  = enemy['atk']
    e_def  = enemy['def']
    e_hp   = enemy['hp']
    p_hp   = player['health']

    for _ in range(30):
        # Player hits NPC
        total = p_atk + e_def + 1
        hit   = max(0.05, min(0.95, 0.5 + (p_atk - e_def) / total))
        if random.random() < hit:
            dmg   = p_atk * random.uniform(0.8, 1.2) * (1 - e_def / (e_def + p_atk + 1))
            e_hp -= max(1, int(dmg))
        if e_hp <= 0:
            break
        # NPC hits player
        total2  = e_atk + p_def + 1
        nhit    = max(0.05, min(0.90, 0.5 + (e_atk - p_def) / total2))
        if random.random() < nhit:
            ndmg  = e_atk * random.uniform(0.8, 1.2) * (1 - p_def / (p_def + e_atk + 1))
            p_hp -= max(1, int(ndmg))
        if p_hp <= 0:
            break

    won     = e_hp <= 0 and p_hp > 0
    hp_lost = player['health'] - max(0, p_hp)
    return won, hp_lost


@bp.route('/pve')
@login_required
def pve_page():
    db      = get_db()
    uid     = g.player['user_id']
    enemies = db.execute("SELECT * FROM npc_enemies ORDER BY min_level").fetchall()
    recent  = db.execute(
        "SELECT pve_log.*, npc_enemies.name as enemy_name, npc_enemies.icon as enemy_icon "
        "FROM pve_log JOIN npc_enemies ON pve_log.enemy_id=npc_enemies.id "
        "WHERE pve_log.user_id=? ORDER BY pve_log.ts DESC LIMIT 10",
        (uid,)
    ).fetchall()
    return render_template('pve/pve.html', enemies=enemies, recent=recent, player=g.player)


@bp.route('/pve/fight/<int:enemy_id>', methods=['POST'])
@login_required
def fight_npc(enemy_id):
    db  = get_db()
    uid = g.player['user_id']

    enemy = db.execute("SELECT * FROM npc_enemies WHERE id=?", (enemy_id,)).fetchone()
    if not enemy:
        flash(tf("Enemy not found."), 'error')
        return redirect(url_for('pve.pve_page'))

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())

    if player['level'] < enemy['min_level']:
        db.execute("ROLLBACK")
        flash(f"You need to be level {enemy['min_level']} to fight this enemy.", 'error')
        return redirect(url_for('pve.pve_page'))

    if player['energy'] < enemy['energy_cost']:
        db.execute("ROLLBACK")
        flash(f"Not enough energy (need {enemy['energy_cost']}).", 'error')
        return redirect(url_for('pve.pve_page'))

    if player['health'] < 10:
        db.execute("ROLLBACK")
        flash("Too injured to fight. Heal up first.", 'error')
        return redirect(url_for('pve.pve_page'))

    won, hp_lost = _fight_npc(player, enemy)

    if won:
        payout  = random.randint(enemy['payout_min'], enemy['payout_max'])
        # Apply bonuses
        vip     = get_vip_tier(player)
        xp_mult = VIP_XP_MULT.get(vip, 1.0) * (get_active_boost(db, uid, 'xp_boost') or 1.0)
        xp_gain = max(1, int(enemy['xp_reward'] * xp_mult))

        db.execute(
            "UPDATE players SET energy=energy-?, cash=cash+?, xp=xp+?, "
            "health=MAX(1,health-?) WHERE user_id=? AND energy>=?",
            (enemy['energy_cost'], payout, xp_gain, min(hp_lost, player['health'] - 1),
             uid, enemy['energy_cost'])
        )

        # Possible item drop
        dropped = None
        if enemy['drop_item_id'] and random.random() < (enemy['drop_chance'] or 0.10):
            item = db.execute("SELECT * FROM items WHERE id=?", (enemy['drop_item_id'],)).fetchone()
            if item:
                existing = db.execute("SELECT id,qty FROM inventory WHERE user_id=? AND item_id=?",
                                      (uid, item['id'])).fetchone()
                if existing and item['stackable']:
                    db.execute("UPDATE inventory SET qty=qty+1 WHERE id=?", (existing['id'],))
                else:
                    db.execute("INSERT INTO inventory(user_id,item_id,qty) VALUES(?,?,1)",
                               (uid, item['id']))
                dropped = item['name']

        db.execute("INSERT INTO pve_log(user_id,enemy_id,won,payout,xp_gain) VALUES(?,?,1,?,?)",
                   (uid, enemy_id, payout, xp_gain))
        db.commit()

        player = dict(db.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone())
        maybe_level_up(db, uid, player)
        check_achievements(db, uid)

        msg = f"🏆 Defeated {enemy['icon']} {enemy['name']}! +${payout:,} +{xp_gain} XP"
        if dropped:
            msg += f" · 🎁 Dropped: {dropped}"
        flash(msg, 'success')
    else:
        # Player lost — take heavy damage, possible hospital
        damage = max(10, int(player['health'] * 0.60))
        new_hp = max(0, player['health'] - damage)
        db.execute("UPDATE players SET energy=energy-?, health=? WHERE user_id=? AND energy>=?",
                   (enemy['energy_cost'], new_hp, uid, enemy['energy_cost']))
        if new_hp == 0:
            db.execute(
                "UPDATE players SET hospital_until=datetime('now','+10 minutes'), health=1 WHERE user_id=?",
                (uid,)
            )
        db.execute("INSERT INTO pve_log(user_id,enemy_id,won,payout,xp_gain) VALUES(?,?,0,0,0)",
                   (uid, enemy_id))
        db.commit()
        flash(f"💀 {enemy['icon']} {enemy['name']} defeated you! -{damage} HP", 'error')
        if new_hp == 0:
            return redirect(url_for('hospital.hospital_page'))

    return redirect(url_for('pve.pve_page'))
