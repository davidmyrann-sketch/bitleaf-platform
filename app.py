import os
from flask import Flask
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, User

def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-bitleaf-2026')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///bitleaf.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['GOOGLE_CLIENT_ID']     = os.environ.get('GOOGLE_CLIENT_ID', '')
    app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    app.config['CLOUDINARY_CLOUD']    = os.environ.get('CLOUDINARY_CLOUD_NAME', 'dbfdriulu')
    app.config['CLOUDINARY_KEY']      = os.environ.get('CLOUDINARY_API_KEY', '771919697856992')
    app.config['CLOUDINARY_SECRET']   = os.environ.get('CLOUDINARY_API_SECRET', 'f995Buu7jx1d-pi1bJWpVFrQbG4')
    app.config['STRIPE_SECRET_KEY']   = os.environ.get('STRIPE_SECRET_KEY', '')
    app.config['STRIPE_WEBHOOK_SECRET'] = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Logg inn for å se denne siden.'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes.auth     import auth_bp
    from routes.profiles import profiles_bp
    from routes.messages import messages_bp
    from routes.events   import events_bp
    from routes.admin    import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(admin_bp)

    import requests as _req, json as _json

    @app.route('/api/translate', methods=['POST'])
    def translate_text():
        from flask import request as _r, jsonify, session
        data   = _r.get_json()
        text   = (data or {}).get('text', '').strip()
        target = (data or {}).get('target', 'no')
        if not text:
            return jsonify({'translated': ''})
        try:
            r = _req.get(
                'https://api.mymemory.translated.net/get',
                params={'q': text[:500], 'langpair': f'autodetect|{target}'},
                timeout=5
            )
            translated = r.json()['responseData']['translatedText']
            return jsonify({'translated': translated})
        except Exception:
            return jsonify({'translated': text})

    @app.route('/set-lang/<lang>')
    def set_lang(lang):
        from flask import session, redirect, request as _r
        from flask_login import current_user
        allowed = ['no','en','fr','de','es','pt','pl','uk','ar','zh','ja','ko','hi','nl','sv','da','fi']
        if lang in allowed:
            session['lang'] = lang
            session.permanent = True
        return redirect(_r.referrer or '/')

    @app.template_filter('from_json')
    def from_json_filter(s):
        try:
            return _json.loads(s or '{}')
        except Exception:
            return {}

    with app.app_context():
        db.create_all()
        # Safe migrations for new columns on existing tables
        from sqlalchemy import text
        migrations = [
            "ALTER TABLE event_bookings ADD COLUMN IF NOT EXISTS stripe_session_id TEXT",
            "ALTER TABLE event_bookings ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'pending'",
            "ALTER TABLE event_bookings ADD COLUMN IF NOT EXISTS food_choice TEXT",
            "ALTER TABLE event_bookings ADD COLUMN IF NOT EXISTS drink_choice TEXT",
        ]
        for sql in migrations:
            try:
                db.session.execute(text(sql))
            except Exception:
                db.session.rollback()
        db.session.commit()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
