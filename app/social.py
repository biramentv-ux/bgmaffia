from flask import Blueprint, render_template, redirect, url_for, flash, g, request, jsonify
from .auth import login_required
from .db import get_db

bp = Blueprint('social', __name__)

MAX_CHAT_MSG_LEN = 200


@bp.route('/mail')
@login_required
def mail_page():
    db = get_db()
    uid = g.player['user_id']
    inbox = db.execute(
        "SELECT m.*, u.username as sender_name FROM messages m JOIN users u ON m.from_id=u.id "
        "WHERE m.to_id=? ORDER BY m.ts DESC LIMIT 50", (uid,)
    ).fetchall()
    sent = db.execute(
        "SELECT m.*, u.username as recip_name FROM messages m JOIN users u ON m.to_id=u.id "
        "WHERE m.from_id=? ORDER BY m.ts DESC LIMIT 20", (uid,)
    ).fetchall()
    # Mark all as read
    db.execute("UPDATE messages SET is_read=1 WHERE to_id=?", (uid,))
    db.commit()
    return render_template('social/mail.html', inbox=inbox, sent=sent)


@bp.route('/mail/send', methods=['POST'])
@login_required
def send_mail():
    db = get_db()
    uid = g.player['user_id']
    to_name = request.form.get('to', '').strip()
    subject = request.form.get('subject', '').strip()[:100]
    body    = request.form.get('body', '').strip()[:2000]
    if not to_name or not body:
        flash("Recipient and body are required.", 'error')
        return redirect(url_for('social.mail_page'))
    target = db.execute("SELECT id FROM users WHERE username=?", (to_name,)).fetchone()
    if not target:
        flash("Player not found.", 'error')
        return redirect(url_for('social.mail_page'))
    db.execute("INSERT INTO messages(from_id,to_id,subject,body) VALUES(?,?,?,?)",
               (uid, target['id'], subject, body))
    db.commit()
    flash(f"✉️ Message sent to {to_name}.", 'success')
    return redirect(url_for('social.mail_page'))


@bp.route('/chat')
@login_required
def chat_page():
    db = get_db()
    messages = db.execute(
        "SELECT c.*, u.username FROM chat c JOIN users u ON c.user_id=u.id "
        "WHERE c.channel='global' ORDER BY c.ts DESC LIMIT 50"
    ).fetchall()
    return render_template('social/chat.html', messages=list(reversed(messages)))


@bp.route('/chat/send', methods=['POST'])
@login_required
def chat_send():
    db = get_db()
    uid = g.player['user_id']
    body = request.form.get('body', '').strip()[:MAX_CHAT_MSG_LEN]
    if not body:
        return redirect(url_for('social.chat_page'))
    db.execute("INSERT INTO chat(user_id,body) VALUES(?,?)", (uid, body))
    db.commit()
    return redirect(url_for('social.chat_page'))


@bp.route('/chat/poll')
@login_required
def chat_poll():
    """Returns new chat messages since a given id (for JS polling)."""
    db = get_db()
    since = request.args.get('since', 0, type=int)
    rows = db.execute(
        "SELECT c.id, c.body, c.ts, u.username FROM chat c JOIN users u ON c.user_id=u.id "
        "WHERE c.channel='global' AND c.id > ? ORDER BY c.id ASC LIMIT 30",
        (since,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route('/notifications/poll')
@login_required
def notifications_poll():
    db = get_db()
    uid = g.player['user_id']
    since = request.args.get('since', 0, type=int)
    rows = db.execute(
        "SELECT id, body, ts FROM notifications WHERE user_id=? AND id > ? ORDER BY id ASC LIMIT 20",
        (uid, since)
    ).fetchall()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND id <= ?",
               (uid, rows[-1]['id'] if rows else since))
    db.commit()
    return jsonify([dict(r) for r in rows])


@bp.route('/notifications')
@login_required
def notifications_page():
    db = get_db()
    uid = g.player['user_id']
    notifs = db.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY ts DESC LIMIT 50", (uid,)
    ).fetchall()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,))
    db.commit()
    return render_template('social/notifications.html', notifs=notifs)


@bp.route('/relations/add', methods=['POST'])
@login_required
def add_relation():
    db = get_db()
    uid = g.player['user_id']
    other_name = request.form.get('username', '').strip()
    kind = request.form.get('kind', 'friend')
    if kind not in ('friend', 'enemy'):
        flash("Invalid relation type.", 'error')
        return redirect(url_for('home.dashboard'))
    target = db.execute("SELECT id FROM users WHERE username=?", (other_name,)).fetchone()
    if not target or target['id'] == uid:
        flash("Player not found.", 'error')
        return redirect(url_for('home.dashboard'))
    db.execute(
        "INSERT INTO relations(user_id,other_id,kind) VALUES(?,?,?) "
        "ON CONFLICT(user_id,other_id) DO UPDATE SET kind=?",
        (uid, target['id'], kind, kind)
    )
    db.commit()
    flash(f"Added {other_name} as {kind}.", 'success')
    return redirect(url_for('home.profile', uid=target['id']))
