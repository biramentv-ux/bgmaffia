"""Lightweight i18n: English UI strings → street Bulgarian (жаргон).

Lookup is by the English string itself; unknown strings fall back to English,
so untranslated pages keep working.
"""
from flask import session

LANGS = ('en', 'bg')
DEFAULT_LANG = 'en'

BG = {
    # ── Nav / chrome ──────────────────────────────────────────────────
    'Dashboard': 'Базата',
    'Profile': 'Профила',
    'HUSTLE': 'ЗАНАЯТ',
    'Crimes': 'Удари',
    'Gym': 'Качалката',
    'Attack': 'Бой',
    'ECONOMY': 'КИНТИ',
    'Bank': 'Банката',
    'Shop': 'Магазина',
    'Inventory': 'Багажа',
    'Black Market': 'Черната борса',
    'Crypto': 'Криптото',
    'Businesses': 'Бизнесите',
    'GANG': 'ТАЙФАТА',
    'Gangs': 'Тайфи',
    'Territory': 'Района',
    'MORE': 'ОЩЕ',
    'Casino': 'Казиното',
    'Lottery': 'Лотарията',
    'Daily Reward': 'Дневния кеш',
    'Missions': 'Мисии',
    'Mail': 'Пощата',
    'Chat': 'Чата',
    'RANKINGS': 'КЛАСАЦИИ',
    'Leaderboard': 'Класацията',
    'Achievements': 'Постижения',
    'Hitlist': 'Черния списък',
    'Logout': 'Чупка',

    # ── Stat bar ──────────────────────────────────────────────────────
    'ENERGY': 'ЕНЕРГИЯ',
    'HEALTH': 'ЖИВОТ',
    'NERVE': 'КУРАЖ',
    'IN JAIL': 'В ПАНДИЗА',
    'HOSPITAL': 'В БОЛНИЦА',
    'FREE': 'НА СВОБОДА',
    'Lv': 'Нв',

    # ── Auth ──────────────────────────────────────────────────────────
    'Enter the underworld. Respect is everything.': 'Влез в подземния свят. Респектът е всичко.',
    'Username': 'Псевдоним',
    'Password': 'Парола',
    'Enter the Streets': 'Влизай в играта',
    'No account?': 'Нямаш акаунт?',
    'Register here': 'Регай се тук',
    'Join the Streets': 'Влез в хорото',
    'Start as an ex-con with $1,000 in the bank.': 'Почваш като бивш пандизчия с $1,000 в банката.',
    'Email': 'Имейл',
    '(optional)': '(по желание)',
    '(3–20 chars)': '(3–20 знака)',
    '(min 6 chars)': '(мин. 6 знака)',
    'Confirm Password': 'Повтори паролата',
    'Start Your Hustle': 'Почвай далаверата',
    'Already have an account?': 'Вече имаш акаунт?',
    'Login': 'Влез',

    # ── Dashboard ─────────────────────────────────────────────────────
    'Welcome back,': 'Добре дошъл пак,',
    'Character': 'Образ',
    'Level': 'Ниво',
    'Respect': 'Респект',
    'Skill Points': 'Точки умения',
    'Strength': 'Сила',
    'Stamina': 'Издръжливост',
    'Intellect': 'Акъл',
    'Sex Appeal': 'Чар',
    'Finances': 'Кинтите',
    'Cash on hand': 'Кеш в джоба',
    'Bank balance': 'В банката',
    'Gold': 'Злато',
    'Gang': 'Тайфа',
    'Gang Bank': 'Каса на тайфата',
    'View Gang': 'Виж тайфата',
    "You're not in a gang.": 'Нямаш тайфа, сам си на улицата.',
    'Browse Gangs': 'Огледай тайфите',
    'Create Gang': 'Събери тайфа',
    'Need 50 respect to create a gang': 'Трябват ти 50 респект за своя тайфа',
    'Status': 'Положение',
    'Release:': 'Излизаш:',
    'Go to Jail': 'Към пандиза',
    'Go to Hospital': 'Към болницата',
    'Recent Crimes': 'Последни удари',
    'Recent Fights': 'Последни бойове',
    'Crime': 'Удар',
    'Result': 'Резултат',
    'Payout': 'Кеш',
    'Time': 'Кога',
    'No crimes yet.': 'Още нямаш удари.',
    'Start now.': 'Почвай сега.',
    'No fights yet.': 'Още не си се бил.',
    'Attack someone.': 'Сритай някого.',
    'Stolen': 'Задигнато',

    # ── Crimes ────────────────────────────────────────────────────────
    'Street Crimes': 'Улични удари',
    'Energy:': 'Енергия:',
    'Level:': 'Ниво:',
    'Commit': 'Действай',
    'No Energy': 'Скапан си',

    # ── Gym ───────────────────────────────────────────────────────────
    'Gym Training': 'Бачкане в качалката',
    'Spend energy to increase your stats. Energy:': 'Хаби енергия, за да качваш статове. Енергия:',
    'Train (+1)': 'Тренирай (+1)',
    'Cost:': 'Цена:',
    'energy': 'енергия',

    # ── Attack / Fight ────────────────────────────────────────────────
    'Attack Online Players': 'Нападни онлайн играчи',
    'Only players currently online and not in jail/hospital/protection can be attacked.':
        'Само онлайн играчи, които са свободни, могат да се нападат.',
    'HP': 'ЖП',
    'No players online to attack right now. Check back soon!':
        'Никой онлайн в момента. Провери пак след малко!',
    'You': 'Ти',

    # ── Shop ─────────────────────────────────────────────────────────
    'Syndicate Supply': 'Склада на синдиката',
    'Cash on hand:': 'Кеш в джоба:',
    '⚔️ Weapons': '⚔️ Оръжия',
    '🚗 Cars': '🚗 Коли',
    '🐕 Dogs': '🐕 Кучета',
    '🛡️ Armor': '🛡️ Доспехи',
    '🍺 Consumables': '🍺 Консумативи',
    'Item': 'Артикул',
    'ATK': 'АТК',
    'DEF': 'ДЕФ',
    'Min Lv': 'Мин. Нв',

    # ── Inventory ────────────────────────────────────────────────────
    'Equipped': 'Облечено',
    'Weapon': 'Оръжие',
    'Car': 'Кола',
    'Dog': 'Куче',
    'Armor': 'Доспех',
    'None': 'Нищо',
    'All Items': 'Всички артикули',
    'Qty': 'Бр.',
    'Actions': 'Операции',
    'equipped': 'облечено',
    'Equip': 'Облечи',
    'Use': 'Използвай',
    'List': 'Пусни',
    'List price': 'Цена за борсата',
    'Inventory empty.': 'Багажът е празен.',
    'Visit the shop.': 'Мини до магазина.',
    'Type': 'Тип',

    # ── Market ───────────────────────────────────────────────────────
    'Black Market': 'Черната борса',
    'Player-to-player listings. Cash:': 'Борса играч-играч. Кеш:',
    'Active Listings': 'Активни оферти',
    'Seller': 'Продавач',
    'Yours': 'Твоя',
    'Your Listings': 'Твои оферти',
    'Cancel': 'Откажи',
    'No listings right now. Be the first to list something!':
        'Няма оферти в момента. Бъди първи!',

    # ── Gang ─────────────────────────────────────────────────────────
    'Gangs of the City': 'Тайфите в града',
    'My Gang': 'Моята тайфа',
    'Name': 'Име',
    'Tag': 'Тег',
    'Leader': 'Бос',
    'Members': 'Членове',
    'View': 'Виж',
    'No gangs exist yet. Be the first!': 'Няма тайфи още. Бъди първи!',
    'Gang Info': 'За тайфата',
    'HQ Level': 'Ниво на щаба',
    'Invite Member': 'Покани член',
    'Player username': 'Псевдоним на играч',
    'Invite': 'Покани',
    'Donate $': 'Дари $',
    'Donate': 'Дари',
    'Rank': 'Ранг',
    'Online': 'Онлайн',
    'Kick': 'Ритни',
    'Leave Gang': 'Напусни тайфата',
    'Leave gang?': 'Напускаш тайфата?',
    'Controlled Territories': 'Контролирани райони',
    'Create a Gang': 'Събери тайфа',
    'Gang Name': 'Име на тайфата',
    '(up to 6 chars, shown in brackets)': '(до 6 знака, показва се в скоби)',
    'Requires 50 respect. You have': 'Нужни са 50 респект. Имаш',
    'respect.': 'респект.',

    # ── Territory ────────────────────────────────────────────────────
    'City Territory': 'Градски райони',
    'Claim unclaimed territories. Owned spots generate passive income.':
        'Завземи свободни райони. Завзетите носят пасивен доход.',
    'Owned by': 'Собственост на',
    'Gang:': 'Тайфа:',
    'Unclaimed': 'Свободен',
    'Claim': 'Завземи',

    # ── Casino ───────────────────────────────────────────────────────
    'Casino': 'Казиното',
    'Dice Roll': 'Зарове',
    'Guess 1–6. Win 5× your bet.': 'Познай от 1 до 6. Печелиш 5× залога.',
    'Bet ($)': 'Залог ($)',
    'Guess (1–6)': 'Познай (1–6)',
    'Roll!': 'Хвърли!',
    'Slots': 'Слотове',
    'Three matching symbols → win big.': 'Три еднакви символа → голяма печалба.',
    'Spin!': 'Върти!',
    'Blackjack': 'Блекджек',
    'Beat the dealer. Blackjack pays 2.5×.': 'Бий дилъра. Блекджек плаща 2.5×.',
    'Deal!': 'Раздай!',
    'Your Hand': 'Ти имаш',
    'Dealer Hand': 'Дилъра има',
    'Hit': 'Вземи карта',
    'Stand': 'Спри',
    'Forfeit': 'Предай се',

    # ── Mail / Chat ───────────────────────────────────────────────────
    'Mail': 'Пощата',
    'Send Message': 'Изпрати съобщение',
    'Recipient username': 'Псевдоним на получател',
    'Subject': 'Тема',
    'Message...': 'Съобщение...',
    'Send': 'Изпрати',
    'Inbox': 'Входяща кутия',
    'From:': 'От:',
    'No messages.': 'Нямаш съобщения.',
    'Global Chat': 'Общ чат',
    'Say something...': 'Кажи нещо...',

    # ── Missions ─────────────────────────────────────────────────────
    'Missions': 'Мисии',
    'Daily': 'Дневна',
    'Reward:': 'Награда:',
    'respect': 'респект',
    'Complete!': 'Изпълнено!',

    # ── Leaderboard ───────────────────────────────────────────────────
    'Leaderboard': 'Класацията',
    'By Respect': 'По респект',
    'By Level': 'По ниво',
    'By Wealth': 'По богатство',
    'Wealth': 'Богатство',

    # ── Achievements ─────────────────────────────────────────────────
    'Achievements': 'Постижения',
    'earned': 'спечелено',

    # ── Hitlist ──────────────────────────────────────────────────────
    'Hitlist': 'Черния списък',
    'Place a Bounty': 'Сложи наказание',
    'Target username': 'Псевдоним на мишена',
    'Bounty ($)': 'Наказание ($)',
    'Place Bounty': 'Обяви наказание',
    'Minimum $500. Bounty expires in 3 days.': 'Минимум $500. Изтича след 3 дни.',
    'Active Bounties': 'Активни наказания',
    'Target': 'Мишена',
    'Bounty': 'Наказание',
    'Placed By': 'Обявено от',
    'Expires': 'Изтича',
    'No active bounties.': 'Няма активни наказания.',

    # ── Bank ──────────────────────────────────────────────────────────
    'First National Bank': 'Първа национална банка',
    'Cash on Hand': 'Кеш в джоба',
    'Bank Balance': 'В банката',
    'Can be stolen by other players': 'Могат да ти го задигнат на улицата',
    'Earns 0.5% interest per hour': 'Носи 0.5% лихва на час',
    'Deposit': 'Внеси',
    'Withdraw': 'Тегли',
    'Amount': 'Сума',
    'Transaction History': 'Движение по сметката',

    # ── Jail / Hospital ───────────────────────────────────────────────
    'City Jail': 'Градския пандиз',
    'You are serving your sentence': 'Лежиш си присъдата',
    'Release in:': 'Излизаш след:',
    'Post Bail:': 'Плати гаранция:',
    '(You have': '(Имаш',
    'on hand)': 'в джоба)',
    'Your sentence ends soon – wait it out.': 'Присъдата ти изтича скоро – трай си.',
    'You are not in jail.': 'Не си в пандиза.',
    'Return to dashboard.': 'Обратно към базата.',
    'Inmates': 'Пандизчии',
    'Bust them out for 2 nerve': 'Измъкни ги срещу 2 кураж',
    'Player': 'Играч',
    'Sentence Ends': 'Излиза',
    'Action': 'Действие',
    'Bust': 'Измъкни',
    'City Hospital': 'Градската болница',
    'You are recovering in hospital': 'Лежиш в болницата',
    'Health regenerates automatically while you wait.': 'Животът ти се пълни сам, докато чакаш.',
    'Leave now for': 'Изпиши се сега за',
    'You are not in the hospital.': 'Не си в болницата.',
    'Approx.': 'Около',
    'min remaining': 'мин. остават',

    # ── Daily / Crypto / Business / Lottery ───────────────────────────
    'Log in every day to keep your streak alive. Miss a day and it resets!':
        'Влизай всеки ден, за да пазиш серията. Пропуснеш ли ден – почваш отначало!',
    'Current Streak': 'Текуща серия',
    'day in a row': 'ден поред',
    'days in a row': 'дни поред',
    'Claimed today': 'Прибрано за днес',
    'Come back tomorrow for day': 'Ела пак утре за ден',
    'Claim Day': 'Прибери ден',
    'How it works': 'Как върви схемата',
    'Reward = $500 × streak day (caps at day 30: $15,000)': 'Награда = $500 × ден от серията (таван: ден 30 = $15,000)',
    'Every 7th day pays a bonus ✨ gold': 'Всеки 7-ми ден дава бонус ✨ злато',
    'Streak resets if you skip a day (UTC)': 'Пропуснеш ли ден (UTC) – серията се нулира',
    'Shadow Exchange': 'Сенчестата борса',
    'Untraceable coins, volatile prices. Updated every 5 minutes. Buy low, sell high — or lose your shirt.':
        'Непроследими монети, луди цени. Обновява се на 5 минути. Купувай евтино, продавай скъпо — или оставаш по гащи.',
    'You hold': 'Държиш',
    'Value': 'Стойност',
    'Buy': 'Купи',
    'Sell': 'Продай',
    '$ to spend': '$ за харчене',
    'coins to sell': 'монети за продан',
    'Front Businesses': 'Бизнеси за параван',
    "Legitimate on paper. Income accrues while you're away": 'Чисти на хартия. Кешът капе и докато те няма',
    'up to': 'до',
    'h': 'ч',
    'hr': 'час',
    'collect whenever you like.': 'прибирай, когато ти скимне.',
    'Income': 'Доход',
    'Accrued': 'Натрупано',
    'Collect': 'Прибери',
    'Price': 'Цена',
    'Requires level': 'Иска ниво',
    'Street Lottery': 'Уличната лотария',
    'A draw every hour. Winner takes': 'Теглене всеки час. Печелившият гепи',
    'of the pot — the house keeps the rest. More tickets, better odds.':
        'от джакпота — останалото е за къщата. Повече билети – по-голям шанс.',
    'Current Pot': 'Текущ джакпот',
    'Next draw': 'Следващ търг',
    'Your tickets': 'Твоите билети',
    'Win chance': 'Шанс да удариш',
    'each': 'броя',
    'Recent Winners': 'Последни късметлии',
    'Winner': 'Печеливш',
    'Prize': 'Награда',
    'When': 'Кога',
    'No draws completed yet. Be the first winner!': 'Още няма теглене. Бъди първият късметлия!',

    # ── Character Classes ─────────────────────────────────────────────
    'Choose Your Class': 'Избери своя образ',
    'Class': 'Клас',

    # ── Street Encounters (PvE) ───────────────────────────────────────
    'Street Encounters': 'Улични срещи',
    'Fight NPC enemies to earn cash, XP, and rare loot drops.': 'Бий се с NPC врагове за пари, опит и рядко плячкосване.',
    'Min Level': 'Мин. ниво',
    'Fight!': 'Бий се!',
    'Recent Encounters': 'Последни срещи',
    'Enemy not found.': 'Врагът не е намерен.',
    'Reach level': 'Достигни ниво',

    # ── Skill Tree ────────────────────────────────────────────────────
    'Skill Tree': 'Дърво на уменията',
    'Unlock passive abilities that permanently boost your performance. Skill points are earned by levelling up.':
        'Отключи пасивни умения, които постоянно те засилват. Точки умения се печелят при leveling.',
    'Unlocked': 'Отключено',
    'Unlock': 'Отключи',
    'Skill not found.': 'Умението не е намерено.',

    # ── Premium Store ────────────────────────────────────────────────
    'Premium Store': 'Премиум магазин',
    'Demo mode': 'Демо режим',
    'Purchases are simulated — no real payment is charged. In production this integrates with Stripe.':
        'Покупките са симулирани — не се теглят реални пари. В продукция се интегрира със Stripe.',
    'BUY GOLD': 'КУПИ ЗЛАТО',
    'INSTANT BOOSTS': 'МОМЕНТНИ БУСТОВЕ',
    'VIP MEMBERSHIP': 'VIP ЧЛЕНСТВО',
    'Transaction History': 'История на транзакциите',
    'expires': 'изтича',
    'ACTIVE': 'АКТИВЕН',
    'Not enough Gold': 'Нямаш достатъчно злато',
    'min': 'мин',
    'days': 'дни',
    'Refresh': 'Поднови',
    'Activate': 'Активирай',
    'Extend': 'Удължи',
    'Package not found.': 'Пакетът не е намерен.',
    'Unknown boost.': 'Непознат буст.',
    'VIP tier not found.': 'VIP нивото не е намерено.',

    # ── Flash messages (server-side) ─────────────────────────────────
    # auth
    'Invalid username or password.': 'Грешен псевдоним или парола.',
    'Your account has been banned.': 'Акаунтът ти е забранен.',
    'You have been logged out.': 'Излязъл си от играта.',
    # crimes
    'Crime not found.': 'Такъв удар не съществува.',
    "You're not high enough level for that crime.": 'Нивото ти е прекалено ниско за тази далавера.',
    'This crime is still on cooldown.': 'Чакай – пак ще можеш.',
    # gym
    'Invalid stat.': 'Невалиден стат.',
    # fight
    "You can't attack yourself.": 'Не можеш да се бориш сам със себе си.',
    "You're too injured to fight (need at least 10 HP).": 'Прекалено наранен си – трябват ти поне 10 ЖП.',
    'Target not found.': 'Мишената не е намерена.',
    'That player is no longer online.': 'Играчът вече не е онлайн.',
    'That player cannot be attacked right now.': 'Играчът не може да бъде нападнат в момента.',
    # bank
    'Invalid amount.': 'Невалидна сума.',
    # shop
    'Item not found.': 'Артикулът не е намерен.',
    "You're not high enough level.": 'Нивото ти е прекалено ниско.',
    # inventory
    'Item not found in inventory.': 'Артикулът не е в багажа.',
    'This item type cannot be equipped.': 'Този тип артикул не може да се облече.',
    "That item can't be used directly.": 'Артикулът не може да се ползва директно.',
    # market
    'Invalid form data.': 'Невалидни данни.',
    'Price must be positive.': 'Цената трябва да е положителна.',
    'Item not in your inventory.': 'Артикулът не е в твоя багаж.',
    '📦 Item listed on the black market.': '📦 Артикулът е пуснат на черната борса.',
    'Listing not available.': 'Офертата не е налична.',
    "Can't buy your own listing.": 'Не можеш да купуваш от себе си.',
    'Listing cancelled, item returned.': 'Офертата е отменена, артикулът е върнат.',
    # gang
    "You're already in a gang.": 'Вече си в тайфа.',
    'Gang name must be at least 3 characters.': 'Името на тайфата трябва да е поне 3 знака.',
    'Gang name already taken.': 'Това име вече е заето.',
    "You need to be a Capo+ to invite.": 'Трябва да си поне Капо, за да каниш.',
    'Player not found.': 'Играчът не е намерен.',
    'That player is already in a gang.': 'Играчът вече е в тайфа.',
    'Gang is full.': 'Тайфата е пълна.',
    'Only Underboss+ can kick members.': 'Само Андърбос+ може да ритне член.',
    "Can't kick the leader.": 'Не може да ритнеш боса.',
    'Member kicked.': 'Членът е изваден.',
    'Not in a gang.': 'Не си в тайфа.',
    'Not enough cash.': 'Нямаш достатъчно кеш.',
    'Leaders must disband the gang or transfer leadership first.':
        'Босът трябва да разпусне тайфата или да предаде ръководството.',
    'You left the gang.': 'Напусна тайфата.',
    'Territory not found.': 'Районът не е намерен.',
    'You already own this territory.': 'Вече владееш този район.',
    'This territory is already claimed. Attack the owner to take it.':
        'Районът е завзет. Нападни собственика, за да го вземеш.',
    'Nothing to collect yet.': 'Няма какво да прибираш все още.',
    # casino
    'Invalid bet.': 'Невалиден залог.',
    'Bet must be > 0 and guess must be 1–6.': 'Залогът трябва да е > 0, а познатото – от 1 до 6.',
    'Not enough cash.': 'Нямаш достатъчно кеш.',
    'No active blackjack game.': 'Няма активна блекджек игра.',
    # social
    'Recipient and body are required.': 'Получателят и текстът са задължителни.',
    'Invalid relation type.': 'Невалиден тип връзка.',
    # jail
    "You're not in jail.": 'Не си в пандиза.',
    "You're in jail – you can't bust others.": 'В пандиза си – не можеш да измъкваш другите.',
    "That player isn't in jail.": 'Играчът не е в пандиза.',
    # hospital
    "You're not in the hospital.": 'Не си в болницата.',
    # rank / bounty
    'Minimum bounty is $500.': 'Минималното наказание е $500.',
}

_TABLES = {'bg': BG}


def translate(lang, text):
    return _TABLES.get(lang, {}).get(text, text)


def tf(text):
    """Translate a flash message using the current request's session language."""
    try:
        lang = session.get('lang', DEFAULT_LANG)
    except RuntimeError:
        lang = DEFAULT_LANG
    return _TABLES.get(lang, {}).get(text, text)
