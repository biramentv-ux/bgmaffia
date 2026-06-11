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
