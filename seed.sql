-- BGMaffia seed data (CE base + bgmaffia extensions)

INSERT OR IGNORE INTO crimes (id,name,min_level,energy_cost,nerve_cost,base_success,payout_min,payout_max,xp_reward,respect_reward,cooldown_sec,jail_sec,skill_used) VALUES
 (1,'Pickpocket a skater',1,5,1,0.85,20,60,2,1,30,60,'strength'),
 (2,'Roll a drunk outside the bar',1,6,1,0.80,40,90,3,1,45,90,'strength'),
 (3,'Snatch a purse downtown',2,8,2,0.70,80,150,5,2,60,120,'strength'),
 (4,'Shoplift a kiosk',4,12,2,0.60,150,300,9,3,120,180,'intellect'),
 (5,'Racketeer the butcher',7,18,3,0.50,300,600,16,5,300,300,'strength'),
 (6,'Racketeer the watchmaker',10,24,4,0.45,600,1100,25,8,480,420,'intellect'),
 (7,'Racketeer the jeweler',14,32,5,0.38,1200,2400,40,12,720,600,'intellect'),
 (8,'Rob a warehouse',20,45,7,0.30,3000,6000,70,20,1500,900,'intellect'),
 (9,'Hit the city bank (gang job)',30,60,10,0.20,20000,80000,200,60,86400,1800,'intellect');

INSERT OR IGNORE INTO items (id,name,type,atk,def,price,min_level,stackable,effect_json) VALUES
 (1,'Brass knuckles','weapon',8,0,500,1,0,NULL),
 (2,'Baseball bat','weapon',15,0,1500,3,0,NULL),
 (3,'Switchblade','weapon',22,0,4000,5,0,NULL),
 (4,'Pistol','weapon',30,0,8000,8,0,NULL),
 (5,'Sawn-off shotgun','weapon',45,0,20000,12,0,NULL),
 (6,'Tommy gun','weapon',65,0,55000,18,0,NULL),
 (7,'Old sedan','car',10,5,5000,5,0,NULL),
 (8,'Muscle car','car',18,8,18000,10,0,NULL),
 (9,'Sports car','car',25,10,40000,15,0,NULL),
 (10,'Guard dog','dog',12,8,6000,6,0,NULL),
 (11,'Trained rottweiler','dog',20,14,16000,12,0,NULL),
 (12,'Kevlar vest','armor',0,25,12000,10,0,NULL),
 (13,'Reinforced coat','armor',0,12,4000,4,0,NULL),
 (14,'Coffee','consumable',0,0,50,1,1,'{"energy":15}'),
 (15,'Beer','consumable',0,0,80,1,1,'{"energy":25}'),
 (16,'First aid kit','consumable',0,0,400,1,1,'{"health":40}'),
 (17,'Whiskey','consumable',0,0,200,3,1,'{"energy":40,"nerve":2}');

INSERT OR IGNORE INTO territories (id,name,type,income_per_hour,claim_cost,min_respect,city_id) VALUES
 (1,'Corner newsstand','shop',120,2000,10,1),
 (2,'Butcher shop','shop',300,8000,40,1),
 (3,'Watchmaker''s atelier','shop',600,20000,120,1),
 (4,'Pawn shop','shop',900,45000,300,1),
 (5,'Jewelry store','shop',1500,90000,700,1),
 (6,'Dockside warehouse','district',2500,180000,1500,1),
 (7,'Casino back room','district',4000,350000,3000,1);

INSERT OR IGNORE INTO missions (id,code,descr,metric,target,reward_json,is_daily) VALUES
 (1,'daily_crimes_5','Commit 5 crimes','crimes',5,'{"cash":500,"gold":2}',1),
 (2,'daily_train_3','Train at the gym 3 times','trains',3,'{"cash":300,"gold":1}',1),
 (3,'daily_fight_1','Win a fight','fight_wins',1,'{"cash":800,"gold":3}',1),
 (4,'daily_gamble_1','Play a casino game','casino',1,'{"cash":200,"gold":1}',1),
 (5,'daily_bank_1','Make a bank deposit','deposits',1,'{"cash":100,"gold":1}',1);

INSERT OR IGNORE INTO achievements (id,code,name,descr,gold_reward) VALUES
 (1,'first_blood','First Blood','Win your first fight',5),
 (2,'crime_10','Petty Criminal','Commit 10 crimes',5),
 (3,'crime_100','Career Criminal','Commit 100 crimes',15),
 (4,'level_5','Made Man','Reach level 5',10),
 (5,'level_10','Capo','Reach level 10',20),
 (6,'level_20','Underboss','Reach level 20',40),
 (7,'rich_100k','Six Figures','Hold $100,000 in the bank',20),
 (8,'gang_founder','Founder','Create a gang',10),
 (9,'landlord','Landlord','Own a territory',10),
 (10,'jailbird','Jailbird','Get sent to jail',2),
 (11,'high_roller','High Roller','Win $5,000 in the casino',10),
 (12,'respect_1000','Feared','Reach 1,000 respect',25);

-- NPC enemies for PvE system
INSERT OR IGNORE INTO npc_enemies (id,name,min_level,health,strength,reward_min,reward_max,xp_reward,loot_item_id,loot_chance) VALUES
 (1,'Street Junkie',1,30,8,50,150,5,14,0.20),
 (2,'Petty Thief',3,50,14,100,300,10,13,0.15),
 (3,'Gang Prospect',5,80,20,250,600,18,2,0.15),
 (4,'Loan Shark',10,120,35,600,1400,35,3,0.12),
 (5,'Crime Lieutenant',15,200,55,1500,3500,60,4,0.10),
 (6,'Cartel Boss',25,350,85,5000,12000,120,5,0.08);

-- Passive skill tree
INSERT OR IGNORE INTO skills (id,code,name,descr,category,sp_cost,prereq_code,effect_json) VALUES
 (1,'street_brawler','Street Brawler','Deal +10% fight damage','combat',1,NULL,'{"fight_dmg":0.10}'),
 (2,'iron_skin','Iron Skin','Take -10% fight damage','combat',1,NULL,'{"fight_def":0.10}'),
 (3,'berserker','Berserker','Deal +20% fight damage (req: Street Brawler)','combat',2,'street_brawler','{"fight_dmg":0.20}'),
 (4,'five_finger','Five-Finger Discount','+10% crime success chance','criminal',1,NULL,'{"crime_success":0.10}'),
 (5,'fast_getaway','Fast Getaway','Crime cooldowns -20%','criminal',1,NULL,'{"crime_cd":0.20}'),
 (6,'crime_master','Crime Master','+15% crime cash payout (req: 5FD)','criminal',2,'five_finger','{"crime_cash":0.15}'),
 (7,'adrenaline','Adrenaline','All regen +15% faster','survival',1,NULL,'{"regen_mult":0.15}'),
 (8,'quick_healer','Quick Healer','-30% hospital time (req: Adrenaline)','survival',1,'adrenaline','{"hospital_mult":0.30}'),
 (9,'iron_will','Iron Will','+25 max health permanently','survival',2,NULL,'{"health_bonus":25}'),
 (10,'card_counter','Card Counter','+10% casino multiplier','hustle',1,NULL,'{"casino_mult":0.10}'),
 (11,'gang_connect','Gang Connect','+15% territory income','hustle',1,NULL,'{"territory_mult":0.15}'),
 (12,'kingpin','Kingpin','+15% crime cash & +10% territory (req: Crime Master)','hustle',3,'crime_master','{"crime_cash":0.15,"territory_mult":0.10}');

-- Crypto coins
INSERT OR IGNORE INTO crypto_coins (id,symbol,name,price,prev_price) VALUES
 (1,'SHD','Shadow Coin',10.00,10.00),
 (2,'BLK','Black Token',25.00,25.00),
 (3,'STR','Street Credit',5.00,5.00),
 (4,'CRT','Cartel Coin',100.00,100.00);

-- Front businesses
INSERT OR IGNORE INTO businesses (id,name,descr,price,income_per_hour,max_accrual_hours,min_level) VALUES
 (1,'Laundromat','Cleans money, literally.',5000,150,24,1),
 (2,'Pawn Shop','Fences stolen goods no questions asked.',15000,400,24,5),
 (3,'Night Club','Music, drinks, and back-room deals.',50000,1200,24,10),
 (4,'Import/Export','Shipping containers. Some contents undeclared.',150000,3500,24,15),
 (5,'Casino Front','Legitimate gambling. Mostly.',500000,12000,24,20);
