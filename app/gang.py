from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from .i18n import tf
from .auth import login_required
from .db import get_db
from .game import _notify, check_achievements

bp = Blueprint('gang', __name__)

RANKS = {0: 'Associate', 1: 'Soldier', 2: 'Capo', 3: 'Underboss', 4: 'Boss'}
CREATE_RESPECT = 50


@bp.route('/gangs')
@login_required
def gangs_page():
    db = get_db()
    gangs = db.execute(
        "SELECT g.*, COUNT(gm.user_id) as member_count, u.username as leader_name "
        "FROM gangs g JOIN gang_members gm ON g.id=gm.gang_id "
        "JOIN users u ON g.leader_id=u.id GROUP BY g.id ORDER BY g.respect DESC"
    ).fetchall()
    return render_template('gang/gangs.html', gangs=gangs)


@bp.route('/gang/create', methods=['GET', 'POST'])
@login_required
def create_gang():
    player = g.player
    if player['gang_id']:
        flash("You're already in a gang.", 'error')
        return redirect(url_for('gang.gang_detail', gang_id=player['gang_id']))
    if player['respect'] < CREATE_RESPECT:
        flash(f"Need {CREATE_RESPECT} respect to create a gang (you have {player['respect']}).", 'error')
        return redirect(url_for('gang.gangs_page'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        tag  = request.form.get('tag', '').strip()[:6].upper()
        db = get_db()
        if not name or len(name) < 3:
            flash(tf("Gang name must be at least 3 characters."), 'error')
            return render_template('gang/create.html')
        if db.execute("SELECT id FROM gangs WHERE name=?", (name,)).fetchone():
            flash(tf("Gang name already taken."), 'error')
            return render_template('gang/create.html')
        uid = player['user_id']
        cur = db.execute(
            "INSERT INTO gangs(name,tag,leader_id) VALUES(?,?,?)", (name, tag, uid)
        )
        gang_id = cur.lastrowid
        db.execute("INSERT INTO gang_members(gang_id,user_id,rank) VALUES(?,?,4)", (gang_id, uid))
        db.execute("UPDATE players SET gang_id=?, gang_rank=4 WHERE user_id=?", (gang_id, uid))
        db.commit()
        check_achievements(db, uid)
        flash(f"🏴 Gang '{name}' [{tag}] created!", 'success')
        return redirect(url_for('gang.gang_detail', gang_id=gang_id))
    return render_template('gang/create.html')


@bp.route('/gang/<int:gang_id>')
@login_required
def gang_detail(gang_id):
    db = get_db()
    gang = db.execute("SELECT * FROM gangs WHERE id=?", (gang_id,)).fetchone()
    if not gang:
        return "Gang not found", 404
    members = db.execute(
        "SELECT u.id, u.username, u.last_active, p.level, p.respect, gm.rank "
        "FROM gang_members gm JOIN users u ON gm.user_id=u.id JOIN players p ON p.user_id=u.id "
        "WHERE gm.gang_id=? ORDER BY gm.rank DESC, p.respect DESC",
        (gang_id,)
    ).fetchall()
    wars = db.execute(
        "SELECT gw.*, ga.name as atk_name, gd.name as def_name "
        "FROM gang_wars gw JOIN gangs ga ON gw.attacker_gang=ga.id JOIN gangs gd ON gw.defender_gang=gd.id "
        "WHERE (gw.attacker_gang=? OR gw.defender_gang=?) AND gw.status='active'",
        (gang_id, gang_id)
    ).fetchall()
    territories = db.execute(
        "SELECT * FROM territories WHERE owner_gang=?", (gang_id,)
    ).fetchall()
    is_member = g.player['gang_id'] == gang_id
    my_rank = g.player['gang_rank'] if is_member else None
    return render_template('gang/gang_detail.html',
                           gang=gang, members=members, wars=wars,
                           territories=territories, is_member=is_member,
                           my_rank=my_rank, ranks=RANKS)


@bp.route('/gang/invite', methods=['POST'])
@login_required
def invite():
    db = get_db()
    uid = g.player['user_id']
    gang_id = g.player['gang_id']
    if not gang_id or g.player['gang_rank'] < 2:
        flash(tf("You need to be a Capo+ to invite."), 'error')
        return redirect(url_for('gang.gangs_page'))
    target_name = request.form.get('username', '').strip()
    target = db.execute("SELECT id FROM users WHERE username=?", (target_name,)).fetchone()
    if not target:
        flash(tf("Player not found."), 'error')
        return redirect(url_for('gang.gang_detail', gang_id=gang_id))
    target_p = db.execute("SELECT gang_id FROM players WHERE user_id=?", (target['id'],)).fetchone()
    if target_p['gang_id']:
        flash(tf("That player is already in a gang."), 'error')
        return redirect(url_for('gang.gang_detail', gang_id=gang_id))
    gang = db.execute("SELECT max_members FROM gangs WHERE id=?", (gang_id,)).fetchone()
    count = db.execute("SELECT COUNT(*) FROM gang_members WHERE gang_id=?", (gang_id,)).fetchone()[0]
    if count >= gang['max_members']:
        flash(tf("Gang is full."), 'error')
        return redirect(url_for('gang.gang_detail', gang_id=gang_id))
    db.execute("INSERT INTO gang_members(gang_id,user_id,rank) VALUES(?,?,1)", (gang_id, target['id']))
    db.execute("UPDATE players SET gang_id=?, gang_rank=1 WHERE user_id=?", (gang_id, target['id']))
    db.commit()
    _notify(db, target['id'], f"👥 You've been invited to join a gang!")
    db.commit()
    flash(f"✅ {target_name} added to gang.", 'success')
    return redirect(url_for('gang.gang_detail', gang_id=gang_id))


@bp.route('/gang/kick', methods=['POST'])
@login_required
def kick():
    db = get_db()
    uid = g.player['user_id']
    gang_id = g.player['gang_id']
    if not gang_id or g.player['gang_rank'] < 3:
        flash(tf("Only Underboss+ can kick members."), 'error')
        return redirect(url_for('gang.gang_detail', gang_id=gang_id))
    target_id = int(request.form.get('target_id', 0))
    gang = db.execute("SELECT leader_id FROM gangs WHERE id=?", (gang_id,)).fetchone()
    if target_id == gang['leader_id']:
        flash("Can't kick the leader.", 'error')
        return redirect(url_for('gang.gang_detail', gang_id=gang_id))
    db.execute("DELETE FROM gang_members WHERE gang_id=? AND user_id=?", (gang_id, target_id))
    db.execute("UPDATE players SET gang_id=NULL, gang_rank=0 WHERE user_id=?", (target_id,))
    db.commit()
    flash(tf("Member kicked."), 'success')
    return redirect(url_for('gang.gang_detail', gang_id=gang_id))


@bp.route('/gang/donate', methods=['POST'])
@login_required
def donate():
    db = get_db()
    uid = g.player['user_id']
    gang_id = g.player['gang_id']
    if not gang_id:
        flash(tf("Not in a gang."), 'error')
        return redirect(url_for('gang.gangs_page'))
    try:
        amount = int(request.form.get('amount', 0))
    except ValueError:
        amount = 0
    if amount <= 0:
        flash(tf("Invalid amount."), 'error')
        return redirect(url_for('gang.gang_detail', gang_id=gang_id))
    db.execute("BEGIN IMMEDIATE")
    p = dict(db.execute("SELECT cash FROM players WHERE user_id=?", (uid,)).fetchone())
    if p['cash'] < amount:
        db.execute("ROLLBACK")
        flash(tf("Not enough cash."), 'error')
        return redirect(url_for('gang.gang_detail', gang_id=gang_id))
    db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (amount, uid, amount))
    db.execute("UPDATE gangs SET bank=bank+? WHERE id=?", (amount, gang_id))
    db.commit()
    flash(f"💰 Donated ${amount:,} to gang bank.", 'success')
    return redirect(url_for('gang.gang_detail', gang_id=gang_id))


@bp.route('/gang/leave', methods=['POST'])
@login_required
def leave_gang():
    db = get_db()
    uid = g.player['user_id']
    gang_id = g.player['gang_id']
    if not gang_id:
        flash(tf("Not in a gang."), 'error')
        return redirect(url_for('gang.gangs_page'))
    gang = db.execute("SELECT leader_id FROM gangs WHERE id=?", (gang_id,)).fetchone()
    if gang['leader_id'] == uid:
        flash(tf("Leaders must disband the gang or transfer leadership first."), 'error')
        return redirect(url_for('gang.gang_detail', gang_id=gang_id))
    db.execute("DELETE FROM gang_members WHERE gang_id=? AND user_id=?", (gang_id, uid))
    db.execute("UPDATE players SET gang_id=NULL, gang_rank=0 WHERE user_id=?", (uid,))
    db.commit()
    flash(tf("You left the gang."), 'info')
    return redirect(url_for('gang.gangs_page'))


# ── Territory ────────────────────────────────────────────────────────────
@bp.route('/territory')
@login_required
def territory_page():
    db = get_db()
    uid = g.player['user_id']
    territories = db.execute(
        "SELECT t.*, u.username as owner_name, g.name as gang_name "
        "FROM territories t LEFT JOIN users u ON t.owner_user=u.id "
        "LEFT JOIN gangs g ON t.owner_gang=g.id WHERE t.city_id=1 ORDER BY t.income_per_hour DESC"
    ).fetchall()
    return render_template('gang/territory.html', territories=territories)


@bp.route('/territory/claim/<int:tid>', methods=['POST'])
@login_required
def claim_territory(tid):
    db = get_db()
    uid = g.player['user_id']
    territory = db.execute("SELECT * FROM territories WHERE id=?", (tid,)).fetchone()
    if not territory:
        flash(tf("Territory not found."), 'error')
        return redirect(url_for('gang.territory_page'))
    if territory['owner_user'] == uid:
        flash(tf("You already own this territory."), 'info')
        return redirect(url_for('gang.territory_page'))
    if territory['owner_user'] is not None or territory['owner_gang'] is not None:
        flash(tf("This territory is already claimed. Attack the owner to take it."), 'error')
        return redirect(url_for('gang.territory_page'))
    db.execute("UPDATE territories SET owner_user=?, last_collected=datetime('now') WHERE id=?", (uid, tid))
    db.commit()
    from .game import _check_achievements
    _check_achievements(db, uid)
    flash(f"🏴 You claimed {territory['name']}!", 'success')
    return redirect(url_for('gang.territory_page'))


@bp.route('/territory/collect/<int:tid>', methods=['POST'])
@login_required
def collect_territory(tid):
    db = get_db()
    uid = g.player['user_id']
    now = datetime.utcnow()
    territory = db.execute("SELECT * FROM territories WHERE id=? AND owner_user=?", (tid, uid)).fetchone()
    if not territory:
        flash("You don't own this territory.", 'error')
        return redirect(url_for('gang.territory_page'))
    last = territory['last_collected']
    if last:
        try:
            elapsed_hours = (now - datetime.fromisoformat(last)).total_seconds() / 3600
        except Exception:
            elapsed_hours = 0
    else:
        elapsed_hours = 0
    income = int(territory['income_per_hour'] * elapsed_hours)
    if income <= 0:
        flash(tf("Nothing to collect yet."), 'info')
        return redirect(url_for('gang.territory_page'))
    db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (income, uid))
    db.execute("UPDATE territories SET last_collected=? WHERE id=?", (now.isoformat(), tid))
    db.commit()
    flash(f"💰 Collected ${income:,} from {territory['name']}.", 'success')
    return redirect(url_for('gang.territory_page'))
