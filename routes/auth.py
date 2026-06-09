import os, requests as req
from flask import Blueprint, redirect, url_for, session, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from models import db, User, Profile

auth_bp = Blueprint('auth', __name__)
oauth    = OAuth()

def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )


@auth_bp.record_once
def on_load(state):
    init_oauth(state.app)


@auth_bp.route('/logg-inn')
def login():
    from flask import render_template
    if current_user.is_authenticated:
        return redirect(url_for('profiles.directory'))
    return render_template('auth/login.html')


@auth_bp.route('/auth/google')
def google_login():
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/auth/google/callback')
def google_callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    if not user_info:
        flash('Innlogging feilet.', 'danger')
        return redirect(url_for('auth.login'))

    google_id = user_info['sub']
    email     = user_info['email']
    name      = user_info.get('name', email)
    avatar    = user_info.get('picture', '')

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            user.google_id  = google_id
            user.avatar_url = avatar
        else:
            user = User(email=email, name=name, google_id=google_id, avatar_url=avatar)
            db.session.add(user)
            db.session.flush()

            profile = Profile(user_id=user.id)
            profile.slug = profile.make_slug(name)
            db.session.add(profile)

    db.session.commit()
    login_user(user, remember=True)

    if not user.profile or not user.profile.role:
        flash('Velkommen! Fullfør profilen din.', 'info')
        return redirect(url_for('profiles.edit_profile'))

    return redirect(url_for('profiles.directory'))


@auth_bp.route('/logg-ut')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
