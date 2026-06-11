import os, secrets

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-change-me'
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'game.db')
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
