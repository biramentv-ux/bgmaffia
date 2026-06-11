-- Crimes (names confirmed [BGM], numbers [GENRE-STD])
INSERT OR IGNORE INTO crimes (id,name,min_level,energy_cost,nerve_cost,base_success,payout_min,payout_max,xp_reward,cooldown_sec,jail_sec,skill_used) VALUES
(1,'Rob a Skater',      1, 5, 0,0.85,  20,   60,  2,  30,  180,'strength'),
(2,'Rob a Drunk',       1, 6, 0,0.80,  40,   90,  3,  45,  240,'strength'),
(3,'Rob a Child',       2, 8, 0,0.70,  80,  150,  5,  60,  300,'strength'),
(4,'Shoplift a Kiosk',  4,12, 0,0.60, 150,  300,  9, 120,  600,'intellect'),
(5,'Racketeer a Butcher',7,18,0,0.50, 300,  600, 16, 300,  900,'intellect'),
(6,'Racketeer a Watchmaker',10,24,0,0.45,600,1100,25,480, 1200,'intellect'),
(7,'Racketeer a Jeweler',14,32,0,0.38,1200,2400, 40, 720, 1800,'intellect'),
(8,'Rob a Warehouse',  20,45, 0,0.30,3000, 6000, 70,1500, 3600,'strength');

-- Items
INSERT OR IGNORE INTO items (id,name,type,atk,def,price,min_level,stackable,effect_json) VALUES
-- Weapons
(1,'Brass Knuckles','weapon', 8, 0,   500,1,0,NULL),
(2,'Baseball Bat',  'weapon',15, 0,  1500,3,0,NULL),
(3,'Pistol',        'weapon',30, 0,  8000,8,0,NULL),
(4,'Shotgun',       'weapon',50, 0, 25000,15,0,NULL),
(5,'AK-47',         'weapon',80, 0, 80000,25,0,NULL),
-- Cars
(6,'Old Sedan',   'car',10, 5,  5000, 5,0,NULL),
(7,'Sports Car',  'car',25,10, 40000,15,0,NULL),
(8,'Armored SUV', 'car',40,20,120000,25,0,NULL),
-- Dogs
(9,'Guard Dog',   'dog',12, 8,  6000, 6,0,NULL),
(10,'Attack Dog', 'dog',20,12, 15000,12,0,NULL),
(11,'K9 Unit',    'dog',30,18, 40000,20,0,NULL),
-- Armor
(12,'Leather Jacket','armor',0,10,  2000, 1,0,NULL),
(13,'Kevlar Vest',   'armor',0,25, 12000,10,0,NULL),
(14,'Full Body Armor','armor',0,45,50000,20,0,NULL),
-- Consumables
(15,'Coffee',       'consumable',0,0,   50,1,1,'{"energy":20}'),
(16,'Beer',         'consumable',0,0,   80,1,1,'{"energy":30}'),
(17,'Energy Drink', 'consumable',0,0,  200,5,1,'{"energy":50}'),
(18,'First Aid Kit','consumable',0,0,  500,1,1,'{"health":30}'),
(19,'Medkit',       'consumable',0,0, 1500,5,1,'{"health":75}');

-- Territories in city 1
INSERT OR IGNORE INTO territories (id,name,type,income_per_hour,owner_user,owner_gang,last_collected,city_id) VALUES
(1,'Downtown Butcher Shop',  'butcher',   200,NULL,NULL,NULL,1),
(2,'Market St Watchmaker',   'watchmaker',350,NULL,NULL,NULL,1),
(3,'Gold District Jeweler',  'jeweler',   600,NULL,NULL,NULL,1),
(4,'Harbor Warehouse',       'warehouse', 800,NULL,NULL,NULL,1),
(5,'North End Bar',          'bar',       150,NULL,NULL,NULL,1),
(6,'East Side Pawn Shop',    'pawnshop',  250,NULL,NULL,NULL,1),
(7,'Uptown Casino Spot',     'casino',   1000,NULL,NULL,NULL,1),
(8,'Slaughterhouse',         'butcher',   300,NULL,NULL,NULL,1);

-- Missions
INSERT OR IGNORE INTO missions (id,code,descr,reward_json,is_daily,req_json) VALUES
(1,'first_crime',   'Commit your first crime',         '{"cash":500,"xp":50,"respect":10}',   0, '{"crimes":1}'),
(2,'win_fight',     'Win your first fight',             '{"cash":1000,"xp":100,"respect":25}', 0, '{"wins":1}'),
(3,'join_gang',     'Join or create a gang',            '{"cash":500,"xp":50,"gold":5}',       0, '{"gang":1}'),
(4,'reach_5',       'Reach level 5',                    '{"cash":2000,"gold":10,"respect":50}',0, '{"level":5}'),
(5,'reach_10',      'Reach level 10',                   '{"cash":5000,"gold":20,"respect":100}',0,'{"level":10}'),
(6,'earn_10k',      'Earn $10,000 from crimes total',   '{"cash":1000,"xp":100,"respect":20}', 0, '{"earned":10000}'),
(7,'daily_crimes',  'Commit 5 crimes today',            '{"cash":200,"xp":30,"respect":5}',    1, '{"crimes":5}'),
(8,'daily_training','Train at the gym 3 times today',   '{"cash":100,"xp":20}',                1, '{"trains":3}'),
(9,'daily_fights',  'Win 2 fights today',               '{"cash":300,"xp":50,"respect":10}',   1, '{"wins":2}'),
(10,'daily_casino', 'Play the casino once today',       '{"cash":100,"gold":2}',               1, '{"casino":1}');

-- Achievements
INSERT OR IGNORE INTO achievements (id,code,name,descr) VALUES
(1,'first_blood',    'First Blood',     'Win your first fight'),
(2,'crime_lord',     'Crime Lord',      'Commit 100 crimes'),
(3,'iron_fists',     'Iron Fists',      'Win 50 fights'),
(4,'millionaire',    'Millionaire',     'Deposit $1,000,000 in the bank'),
(5,'gang_leader',    'Gang Leader',     'Create a gang'),
(6,'made_man',       'Made Man',        'Reach level 10'),
(7,'boss',           'The Boss',        'Reach level 25'),
(8,'respectful',     'Respectful',      'Earn 1000 respect'),
(9,'territory_king', 'Territory King',  'Own 3 territories simultaneously'),
(10,'lucky',         'Lucky',           'Win at the casino 10 times');
