import os, secrets

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_or_create_secret():
    """Use SECRET_KEY from the environment, or generate one and persist it to
    a local file so sessions survive restarts. Never ship a fixed fallback —
    a known key lets anyone forge session cookies."""
    env = os.environ.get('SECRET_KEY')
    if env:
        return env
    path = os.path.join(_BASE_DIR, '.secret_key')
    try:
        with open(path) as f:
            key = f.read().strip()
            if key:
                return key
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(key)
    return key


class Config:
    SECRET_KEY = _load_or_create_secret()
    DATABASE = os.path.join(_BASE_DIR, 'game.db')
    ONLINE_TIMEOUT_MINUTES = 5
    PROTECTION_MINUTES = 15
    BANK_INTEREST_RATE_PER_HOUR = 0.005

    ENERGY_REGEN_RATE  = 5;  ENERGY_TICK_SECS  = 300
    NERVE_REGEN_RATE   = 1;  NERVE_TICK_SECS   = 300
    HEALTH_REGEN_RATE  = 1;  HEALTH_TICK_SECS  = 60

    # 2026 update
    DAILY_REWARD_BASE       = 500    # cash per streak day (capped at 30 days)
    DAILY_STREAK_CAP        = 30
    LOTTERY_TICKET_PRICE    = 500
    LOTTERY_HOUSE_CUT       = 0.10
    LOTTERY_DRAW_MINUTES    = 60
    CRYPTO_TICK_MINUTES     = 5
    BUSINESS_ACCRUAL_CAP_H  = 24     # offline earnings cap in hours
