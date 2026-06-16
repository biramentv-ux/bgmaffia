"""Lightweight i18n: English → street Bulgarian (жаргон).

Unknown strings fall back to English so untranslated pages keep working.
"""
from flask import session

LANGS = ('en', 'bg')
DEFAULT_LANG = 'en'

BG = {
    # Nav
    'Dashboard': 'Базата', 'Crimes': 'Удари', 'Gym': 'Качалката',
    'Attack': 'Бой', 'Territory': 'Района', 'Hospital': 'Болница', 'Jail': 'Пандиза',
    'Bank': 'Банката', 'Shop': 'Магазина', 'Inventory': 'Багажа',
    'Black Market': 'Черната борса', 'Casino': 'Казиното',
    'Gangs': 'Тайфите', 'Mail': 'Пощата', 'Chat': 'Чата',
    'Missions': 'Мисии', 'Leaderboard': 'Класацията', 'Achievements': 'Постижения',
    'Hitlist': 'Черния списък', 'Log out': 'Чупка',
    'Street Encounters': 'Улични срещи', 'Skill Tree': 'Дърво на уменията',
    'Premium Store': 'Премиум магазин', 'Crypto': 'Криптото',
    'Businesses': 'Бизнесите', 'Daily Reward': 'Дневния кеш',
    'Street Lottery': 'Уличната лотария', 'Admin': 'Администрация',

    # Auth
    'Username': 'Псевдоним', 'Password': 'Парола', 'Email': 'Имейл',
    'Register': 'Регистрирай се', 'Login': 'Влез',
    'Choose Your Class': 'Избери своя образ',

    # Stats sidebar
    'Energy': 'Енергия', 'Nerve': 'Кураж', 'Health': 'Живот',
    'Cash': 'Кеш', 'Gold': 'Злато',
    'In jail': 'В пандиза', 'In hospital': 'В болница', 'On the street': 'На свобода',

    # Dashboard
    'The Street': 'Улицата', 'Respect': 'Респект', 'Level': 'Ниво',
    'Cash on hand': 'Кеш в джоба', 'Crimes pulled': 'Удари', 'Fights won': 'Победи',
    'Pull a job': 'Направи удар', 'Train up': 'Бачкай', 'Find a mark': 'Намери жертва',
    'Run a racket': 'Завземи район', 'Word on the street': 'Слухове',

    # Class names
    'Enforcer': 'Изпълнителят', 'Hacker': 'Хакерът',
    'Conman': 'Измамникът', 'Ghost': 'Призракът',
}

_TABLES = {'bg': BG}


def translate(lang, text):
    return _TABLES.get(lang, {}).get(text, text)


def tf(text):
    try:
        lang = session.get('lang', DEFAULT_LANG)
    except RuntimeError:
        lang = DEFAULT_LANG
    return _TABLES.get(lang, {}).get(text, text)
