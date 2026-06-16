import os, secrets
from datetime import datetime
from flask import Flask, g, session, redirect, url_for, request
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object('config.Config')
    if config:
        app.config.update(config)

    csrf.init_app(app)

    from .db import get_db, close_db, init_db, migrate_db
    app.teardown_appcontext(close_db)

    # Initialise DB and apply forward migrations on every startup
    with app.app_context():
        if not os.path.exists(app.config['DATABASE']):
            init_db()
        migrate_db()

    # ── Context processor ────────────────────────────────────────────────
    @app.context_processor
    def inject_globals():
        from .game import is_in_jail, is_in_hospital, get_vip_tier
        from .i18n import translate, DEFAULT_LANG
        player = g.get('player')
        username = None
        vip_tier = 0
        if player:
            db = get_db()
            u = db.execute("SELECT username FROM users WHERE id=?", (player['user_id'],)).fetchone()
            if u:
                username = u['username']
            vip_tier = get_vip_tier(player)
        lang = session.get('lang', DEFAULT_LANG)
        return {
            'player': player,
            'username': username,
            'now_iso': datetime.utcnow().isoformat(),
            'is_in_jail': is_in_jail(player) if player else False,
            'is_in_hospital': is_in_hospital(player) if player else False,
            'enumerate': enumerate,
            'lang': lang,
            't': lambda s: translate(lang, s),
            'vip_tier': vip_tier,
        }

    # ── Before every request ────────────────────────────────────────────
    OPEN_ENDPOINTS = {
        'auth.login', 'auth.register', 'auth.logout',
        'set_lang', 'static', None,
    }
    LOCK_BYPASS = {
        'jail.jail_page', 'jail.bail', 'jail.bust',
        'hospital.hospital_page', 'hospital.heal',
        'social.notifications_poll', 'social.chat_poll',
    }

    @app.before_request
    def load_player():
        g.player = None
        uid = session.get('user_id')
        if not uid:
            return
        from .db import get_db
        from .game import lazy_regen, is_in_jail, is_in_hospital
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not user or user['is_banned']:
            session.clear()
            return
        db.execute("UPDATE users SET last_active=datetime('now') WHERE id=?", (uid,))
        db.commit()
        player = lazy_regen(db, uid)
        g.player = player
        if player is None:
            return
        ep = request.endpoint
        if ep in OPEN_ENDPOINTS or ep in LOCK_BYPASS:
            return
        if is_in_jail(player) and ep != 'jail.jail_page':
            return redirect(url_for('jail.jail_page'))
        if is_in_hospital(player) and ep != 'hospital.hospital_page':
            return redirect(url_for('hospital.hospital_page'))

    # ── Register blueprints ──────────────────────────────────────────────
    from .auth      import bp as auth_bp
    from .home      import bp as home_bp
    from .crimes    import bp as crimes_bp
    from .gym       import bp as gym_bp
    from .fight     import bp as fight_bp
    from .hospital  import bp as hospital_bp
    from .jail      import bp as jail_bp
    from .bank      import bp as bank_bp
    from .shop      import bp as shop_bp
    from .inventory import bp as inventory_bp
    from .market    import bp as market_bp
    from .gang      import bp as gang_bp
    from .casino    import bp as casino_bp
    from .social    import bp as social_bp
    from .missions  import bp as missions_bp
    from .rank      import bp as rank_bp
    from .admin     import bp as admin_bp
    from .daily     import bp as daily_bp
    from .crypto    import bp as crypto_bp
    from .business  import bp as business_bp
    from .lottery   import bp as lottery_bp
    from .store     import bp as store_bp
    from .pve       import bp as pve_bp
    from .skills    import bp as skills_bp

    for bp in [auth_bp, home_bp, crimes_bp, gym_bp, fight_bp, hospital_bp,
               jail_bp, bank_bp, shop_bp, inventory_bp, market_bp, gang_bp,
               casino_bp, social_bp, missions_bp, rank_bp, admin_bp,
               daily_bp, crypto_bp, business_bp, lottery_bp, store_bp,
               pve_bp, skills_bp]:
        app.register_blueprint(bp)

    # Serve the service worker from the root so it can control the whole app
    @app.route('/sw.js')
    def service_worker():
        return app.send_static_file('sw.js')

    # ── Language switch ──────────────────────────────────────────────────
    @app.route('/lang/<code>')
    def set_lang(code):
        from .i18n import LANGS
        if code in LANGS:
            session['lang'] = code
        return redirect(request.referrer or url_for('home.dashboard'))

    # ── Start scheduler ──────────────────────────────────────────────────
    from .scheduler import start_scheduler
    start_scheduler(app)

    return app
