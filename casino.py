"""casino.py — server-seeded casino games: blackjack, dice, slots, lottery.
All RNG and outcome logic stays on the server; the client only sends bets/moves.
Blackjack state is stored per-player in the session-backed table column-free
approach: we keep the hand in the player's session for simplicity and re-validate
the wager against the DB.
"""
import random

from flask import (Blueprint, g, render_template, request, redirect, url_for,
                   flash, session, jsonify)

from db import get_db, transact, guarded, TxFailed
from auth import login_required, check_csrf
from game import bump_mission, award, notify, get_class, get_skill_bonuses

bp = Blueprint("casino", __name__)

CARD_VALUES = {**{str(n): n for n in range(2, 11)}, "J": 10, "Q": 10, "K": 10, "A": 11}
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


def draw():
    return random.choice(RANKS)


def hand_value(cards):
    total = sum(CARD_VALUES[c] for c in cards)
    aces = cards.count("A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def take_bet(con, uid, bet):
    def work(c):
        guarded(c, "UPDATE players SET cash=cash-? WHERE user_id=? AND cash>=?", (bet, uid, bet))
        bump_mission(c, uid, "casino")
    transact(con, work)


def pay(con, uid, amount):
    con.execute("UPDATE players SET cash=cash+? WHERE user_id=?", (amount, uid))
    con.commit()


def casino_mult(player):
    cls = get_class(player)
    sk = get_skill_bonuses(get_db(), player["user_id"])
    return cls["casino_mult"] * (1.0 + sk["casino_mult"])


def parse_bet(raw, cash):
    try:
        bet = int(raw)
    except (TypeError, ValueError):
        return None
    if bet < 1 or bet > 1_000_000 or bet > cash:
        return None
    return bet


@bp.route("/casino")
@login_required
def casino():
    return render_template("casino.html")


# ---------------- Dice: guess high/low vs house ----------------

@bp.route("/casino/dice", methods=("POST",))
@login_required
def dice():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    bet = parse_bet(request.form.get("bet"), g.user["cash"])
    pick = request.form.get("pick")  # 'high' or 'low'
    if bet is None or pick not in ("high", "low"):
        flash("Invalid bet.")
        return redirect(url_for("casino.casino"))
    try:
        take_bet(con, uid, bet)
    except TxFailed:
        flash("Not enough cash.")
        return redirect(url_for("casino.casino"))
    roll = random.randint(1, 6)
    win = (pick == "high" and roll >= 4) or (pick == "low" and roll <= 3)
    if win:
        mult = casino_mult(g.user)
        winnings = int(bet * mult)
        pay(con, uid, bet + winnings)
        flash(f"Dice came up {roll}. You win ${winnings:,}!")
    else:
        flash(f"Dice came up {roll}. You lose ${bet:,}.")
    return redirect(url_for("casino.casino"))


# ---------------- Slots ----------------

SLOT_SYMBOLS = ["7", "BAR", "cherry", "bell", "lemon", "star"]
SLOT_PAYOUTS = {"7": 25, "BAR": 12, "star": 8, "bell": 5, "cherry": 3, "lemon": 2}


@bp.route("/casino/slots", methods=("POST",))
@login_required
def slots():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    bet = parse_bet(request.form.get("bet"), g.user["cash"])
    if bet is None:
        flash("Invalid bet.")
        return redirect(url_for("casino.casino"))
    try:
        take_bet(con, uid, bet)
    except TxFailed:
        flash("Not enough cash.")
        return redirect(url_for("casino.casino"))
    reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
    cm = casino_mult(g.user)
    if reels[0] == reels[1] == reels[2]:
        base_mult = SLOT_PAYOUTS[reels[0]]
        winnings = int(bet * base_mult * cm)
        pay(con, uid, winnings)
        _maybe_high_roller(con, uid, winnings)
        flash(f"[ {' | '.join(reels)} ]  Jackpot ×{base_mult}! +${winnings:,}")
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        pay(con, uid, bet)
        flash(f"[ {' | '.join(reels)} ]  A pair — stake returned.")
    else:
        flash(f"[ {' | '.join(reels)} ]  No match. -${bet:,}")
    return redirect(url_for("casino.casino"))


# ---------------- Lottery ----------------

@bp.route("/casino/lottery", methods=("POST",))
@login_required
def lottery():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    ticket = 100
    if g.user["cash"] < ticket:
        flash("A lottery ticket costs $100.")
        return redirect(url_for("casino.casino"))
    try:
        take_bet(con, uid, ticket)
    except TxFailed:
        flash("Not enough cash.")
        return redirect(url_for("casino.casino"))
    r = random.random()
    if r < 0.001:
        prize = 100000
    elif r < 0.02:
        prize = 2000
    elif r < 0.10:
        prize = 300
    else:
        prize = 0
    if prize:
        pay(con, uid, prize)
        _maybe_high_roller(con, uid, prize)
        flash(f"Your numbers hit! You won ${prize:,}.")
    else:
        flash("No luck this draw. Better next time.")
    return redirect(url_for("casino.casino"))


# ---------------- Blackjack (multi-step via session state) ----------------

@bp.route("/casino/blackjack/deal", methods=("POST",))
@login_required
def bj_deal():
    check_csrf()
    con = get_db()
    uid = g.user["user_id"]
    bet = parse_bet(request.form.get("bet"), g.user["cash"])
    if bet is None:
        return jsonify({"error": "Invalid bet."}), 400
    if session.get("bj"):
        return jsonify({"error": "Finish your current hand first."}), 400
    try:
        take_bet(con, uid, bet)
    except TxFailed:
        return jsonify({"error": "Not enough cash."}), 400
    player = [draw(), draw()]
    dealer = [draw()]
    session["bj"] = {"bet": bet, "player": player, "dealer": dealer, "done": False}
    pv = hand_value(player)
    if pv == 21:
        return _bj_finish(con, uid)
    return jsonify(_bj_state(reveal=False))


@bp.route("/casino/blackjack/hit", methods=("POST",))
@login_required
def bj_hit():
    check_csrf()
    state = session.get("bj")
    if not state or state["done"]:
        return jsonify({"error": "No active hand."}), 400
    state["player"].append(draw())
    session["bj"] = state
    if hand_value(state["player"]) >= 21:
        return _bj_finish(get_db(), g.user["user_id"])
    return jsonify(_bj_state(reveal=False))


@bp.route("/casino/blackjack/stand", methods=("POST",))
@login_required
def bj_stand():
    check_csrf()
    state = session.get("bj")
    if not state or state["done"]:
        return jsonify({"error": "No active hand."}), 400
    return _bj_finish(get_db(), g.user["user_id"])


def _bj_finish(con, uid):
    state = session.get("bj")
    dealer = state["dealer"]
    while hand_value(dealer) < 17:
        dealer.append(draw())
    pv, dv = hand_value(state["player"]), hand_value(dealer)
    bet = state["bet"]
    cm = casino_mult(g.user)
    if pv > 21:
        result, payout = "bust", 0
    elif dv > 21 or pv > dv:
        result = "win"
        payout = bet + int(bet * cm)
    elif pv == dv:
        result, payout = "push", bet
    else:
        result, payout = "lose", 0
    if payout:
        pay(con, uid, payout)
        if payout - bet >= 5000:
            _maybe_high_roller(con, uid, payout - bet)
    state["done"] = True
    state["dealer"] = dealer
    out = _bj_state(reveal=True)
    out["result"] = result
    out["payout"] = payout
    session.pop("bj", None)
    return jsonify(out)


def _bj_state(reveal):
    state = session.get("bj", {})
    dealer = state.get("dealer", [])
    return {
        "player": state.get("player", []),
        "player_value": hand_value(state.get("player", [])),
        "dealer": dealer if reveal else [dealer[0], "?"] if dealer else [],
        "dealer_value": hand_value(dealer) if reveal else None,
        "bet": state.get("bet", 0),
    }


def _maybe_high_roller(con, uid, winnings):
    if winnings >= 5000:
        def work(c):
            award(c, uid, "high_roller")
        try:
            transact(con, work)
        except TxFailed:
            pass
