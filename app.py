import os
from flask import Flask
from flask_login import LoginManager
from models import db, User

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-bitleaf-2026')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///bitleaf.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['GOOGLE_CLIENT_ID']     = os.environ.get('GOOGLE_CLIENT_ID', '')
    app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    app.config['CLOUDINARY_CLOUD']  = os.environ.get('CLOUDINARY_CLOUD_NAME', 'dbfdriulu')
    app.config['CLOUDINARY_KEY']    = os.environ.get('CLOUDINARY_API_KEY', '771919697856992')
    app.config['CLOUDINARY_SECRET'] = os.environ.get('CLOUDINARY_API_SECRET', 'f995Buu7jx1d-pi1bJWpVFrQbG4')

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

    import json as _json
    @app.template_filter('from_json')
    def from_json_filter(s):
        try:
            return _json.loads(s or '{}')
        except Exception:
            return {}

    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
