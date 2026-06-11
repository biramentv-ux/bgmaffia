import random
from flask import Blueprint, render_template, redirect, url_for, flash, g, request, jsonify
from .i18n import tf
from .auth import login_required
from .db import get_db
from .game import mission_progress

bp = Blueprint('casino', __name__)


@bp.route('/casino')
@login_required
def casino_page():
    return render_template('casino/casino.html')


# ── Dice ─────────────────────────────────────────────────────────────────
@bp.route('/casino/dice', methods=['POST'])
@login_required
def dice():
    db = get_db()
    uid = g.player['user_id']
    try:
        bet   = int(request.form.get('bet', 0))
        guess = int(request.form.get('guess', 0))
    except ValueError:
        flash(tf("Invalid bet."), 'error')
        return redirect(url_for('casino.casino_page'))
    if bet <= 0 or guess < 1 or guess > 6:
        flash(tf("Bet must be > 0 and guess must be 1–6."), 'error')
        return redirect(url_for('casino.casino_page'))

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT cash FROM players WHERE user_id=?", (uid,)).fetchone())
    if player['cash'] < bet:
        db.execute("ROLLBACK")
        flash(tf("Not enough cash."), 'error')
        return redirect(url_for('casino.casino_page'))

    roll = random.randint(1, 6)
    if roll == guess:
        winnings = bet * 5
        db.execute("UPDATE players SET cash=cash+? WHERE user_id=? AND cash>=?", (winnings, uid, 0))
        flash(f"🎲 Rolled {roll}! You win ${winnings:,}!", 'success')
        mission_progress(db, uid, 'casino')
    else:
        db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (bet, uid, bet))
        flash(f"🎲 Rolled {roll} (you guessed {guess}). Lost ${bet:,}.", 'error')
    db.commit()
    return redirect(url_for('casino.casino_page'))


# ── Slots ────────────────────────────────────────────────────────────────
SLOT_SYMBOLS = ['🍒', '🍋', '🍊', '⭐', '💎', '7️⃣']
SLOT_PAYOUTS = {
    '💎💎💎': 50,
    '7️⃣7️⃣7️⃣': 20,
    '⭐⭐⭐': 10,
    '🍒🍒🍒': 5,
    '🍋🍋🍋': 3,
    '🍊🍊🍊': 2,
}


@bp.route('/casino/slots', methods=['POST'])
@login_required
def slots():
    db = get_db()
    uid = g.player['user_id']
    try:
        bet = int(request.form.get('bet', 0))
    except ValueError:
        bet = 0
    if bet <= 0:
        flash(tf("Invalid bet."), 'error')
        return redirect(url_for('casino.casino_page'))

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT cash FROM players WHERE user_id=?", (uid,)).fetchone())
    if player['cash'] < bet:
        db.execute("ROLLBACK")
        flash(tf("Not enough cash."), 'error')
        return redirect(url_for('casino.casino_page'))

    db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (bet, uid, bet))
    reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
    combo = ''.join(reels)
    multiplier = SLOT_PAYOUTS.get(combo, 0)
    if multiplier:
        winnings = bet * multiplier
        db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (winnings, uid))
        flash(f"🎰 {' '.join(reels)} — JACKPOT! +${winnings:,}!", 'success')
        mission_progress(db, uid, 'casino')
    else:
        flash(f"🎰 {' '.join(reels)} — No match. Lost ${bet:,}.", 'error')
    db.commit()
    return redirect(url_for('casino.casino_page'))


# ── Blackjack (server-side card logic) ──────────────────────────────────
def _card_value(card):
    rank = card[0]
    if rank in ('J', 'Q', 'K'): return 10
    if rank == 'A': return 11
    try: return int(rank)
    except: return 0


def _hand_value(hand):
    val = sum(_card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[0] == 'A')
    while val > 21 and aces:
        val -= 10; aces -= 1
    return val


def _new_deck():
    ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
    suits = ['♠','♥','♦','♣']
    deck = [f"{r}{s}" for r in ranks for s in suits]
    random.shuffle(deck)
    return deck


@bp.route('/casino/blackjack/start', methods=['POST'])
@login_required
def bj_start():
    db = get_db()
    uid = g.player['user_id']
    try:
        bet = int(request.form.get('bet', 0))
    except ValueError:
        bet = 0
    if bet <= 0:
        flash(tf("Invalid bet."), 'error')
        return redirect(url_for('casino.casino_page'))

    db.execute("BEGIN IMMEDIATE")
    player = dict(db.execute("SELECT cash FROM players WHERE user_id=?", (uid,)).fetchone())
    if player['cash'] < bet:
        db.execute("ROLLBACK")
        flash(tf("Not enough cash."), 'error')
        return redirect(url_for('casino.casino_page'))
    db.execute("UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (bet, uid, bet))
    db.commit()

    deck = _new_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    from flask import session
    session['bj'] = {'bet': bet, 'deck': deck, 'player': player_hand, 'dealer': dealer_hand}

    if _hand_value(player_hand) == 21:
        return _bj_resolve(uid, db, 'blackjack')

    return render_template('casino/blackjack.html',
                           player_hand=player_hand,
                           dealer_visible=[dealer_hand[0], '??'],
                           pv=_hand_value(player_hand), bet=bet)


@bp.route('/casino/blackjack/hit', methods=['POST'])
@login_required
def bj_hit():
    from flask import session
    bj = session.get('bj')
    if not bj:
        flash(tf("No active blackjack game."), 'error')
        return redirect(url_for('casino.casino_page'))
    db = get_db()
    uid = g.player['user_id']
    bj['player'].append(bj['deck'].pop())
    pv = _hand_value(bj['player'])
    session['bj'] = bj
    if pv > 21:
        session.pop('bj', None)
        flash(f"🃏 Bust! Hand: {' '.join(bj['player'])} ({pv}). Lost ${bj['bet']:,}.", 'error')
        mission_progress(db, uid, 'casino')
        return redirect(url_for('casino.casino_page'))
    return render_template('casino/blackjack.html',
                           player_hand=bj['player'],
                           dealer_visible=[bj['dealer'][0], '??'],
                           pv=pv, bet=bj['bet'])


@bp.route('/casino/blackjack/stand', methods=['POST'])
@login_required
def bj_stand():
    from flask import session
    bj = session.get('bj')
    if not bj:
        flash(tf("No active blackjack game."), 'error')
        return redirect(url_for('casino.casino_page'))
    session.pop('bj', None)
    db = get_db()
    uid = g.player['user_id']
    return _bj_resolve(uid, db, 'stand', bj)


def _bj_resolve(uid, db, reason, bj=None):
    from flask import session
    if bj is None:
        bj = session.pop('bj', None)
    if not bj:
        return redirect(url_for('casino.casino_page'))
    dealer_hand = bj['dealer']
    deck = bj['deck']
    while _hand_value(dealer_hand) < 17:
        dealer_hand.append(deck.pop())
    pv = _hand_value(bj['player'])
    dv = _hand_value(dealer_hand)
    bet = bj['bet']

    if reason == 'blackjack':
        winnings = int(bet * 2.5)
        db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (winnings, uid))
        db.commit()
        flash(f"🃏 Blackjack! Won ${winnings:,}!", 'success')
    elif pv > 21:
        flash(f"🃏 Bust ({pv}). Dealer: {dv}. Lost ${bet:,}.", 'error')
    elif dv > 21 or pv > dv:
        winnings = bet * 2
        db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (winnings, uid))
        db.commit()
        flash(f"🃏 You win! {pv} vs {dv}. Won ${winnings:,}!", 'success')
    elif pv == dv:
        db.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (bet, uid))
        db.commit()
        flash(f"🃏 Push! {pv} vs {dv}. Bet returned.", 'info')
    else:
        flash(f"🃏 Dealer wins. {pv} vs {dv}. Lost ${bet:,}.", 'error')
    mission_progress(db, uid, 'casino')
    return redirect(url_for('casino.casino_page'))
