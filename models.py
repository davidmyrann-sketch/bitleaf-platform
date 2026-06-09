from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import re

db = SQLAlchemy()

ROLES = [
    ('angel_investor',  'Angel Investor'),
    ('vc_investor',     'VC Investor'),
    ('pe_investor',     'PE Investor'),
    ('founder',         'Gründer'),
    ('startup',         'Startup'),
    ('scaleup',         'Scale-up'),
    ('mature',          'Modent selskap'),
    ('sweet_equity',    'Sweet Equity'),
]

VISIBILITY = [
    ('public',       'Alle'),
    ('members',      'Kun medlemmer'),
    ('hidden',       'Skjult'),
]

INDUSTRIES = [
    ('tech',         'Tech & Software'),
    ('fintech',      'Fintech'),
    ('healthtech',   'Healthtech'),
    ('proptech',     'Proptech'),
    ('cleantech',    'Cleantech'),
    ('consumer',     'Consumer'),
    ('b2b_saas',     'B2B SaaS'),
    ('marketplace',  'Marketplace'),
    ('deep_tech',    'Deep Tech'),
    ('legal',        'Juridisk'),
    ('restaurant',   'Restaurant & Mat'),
    ('real_estate',  'Eiendom'),
    ('startups_general', 'Startups in general'),
    ('other',        'Annet'),
]


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    name          = db.Column(db.String(255))
    google_id     = db.Column(db.String(255), unique=True)
    avatar_url    = db.Column(db.Text)
    is_admin      = db.Column(db.Boolean, default=False)
    preferred_lang = db.Column(db.String(10), default='no')
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    profile       = db.relationship('Profile', backref='user', uselist=False)
    sent_messages = db.relationship('Message', foreign_keys='Message.from_user_id', backref='sender', lazy='dynamic')
    recv_messages = db.relationship('Message', foreign_keys='Message.to_user_id',   backref='recipient', lazy='dynamic')


class Profile(db.Model):
    __tablename__ = 'profiles'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    slug            = db.Column(db.String(255), unique=True)
    role            = db.Column(db.Text)  # comma-separated, e.g. "founder,angel_investor"
    bio             = db.Column(db.Text)
    photo_url       = db.Column(db.Text)
    phone           = db.Column(db.String(50))
    phone_visible   = db.Column(db.String(20), default='members')
    email_visible   = db.Column(db.String(20), default='members')
    linkedin_url    = db.Column(db.Text)
    website_url     = db.Column(db.Text)
    video_url       = db.Column(db.Text)
    looking_for     = db.Column(db.Text)
    offering        = db.Column(db.Text)
    industry        = db.Column(db.Text)  # comma-separated
    is_public       = db.Column(db.Boolean, default=True)
    membership_tier = db.Column(db.String(20), default='free')
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship('Company', backref='profile', uselist=False)

    @property
    def display_name(self):
        return self.user.name if self.user else ''

    @property
    def roles_list(self):
        return [r.strip() for r in (self.role or '').split(',') if r.strip()]

    @property
    def industries_list(self):
        return [i.strip() for i in (self.industry or '').split(',') if i.strip()]

    @property
    def role_label(self):
        role_map = dict(ROLES)
        return ', '.join(role_map.get(r, r) for r in self.roles_list) or ''

    @property
    def industry_label(self):
        ind_map = dict(INDUSTRIES)
        return ', '.join(ind_map.get(i, i) for i in self.industries_list) or ''

    def make_slug(self, name):
        s = name.lower().strip()
        s = re.sub(r'[æÆ]', 'ae', s)
        s = re.sub(r'[øØ]', 'o', s)
        s = re.sub(r'[åÅ]', 'a', s)
        s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
        base = s[:60]
        slug = base
        n = 1
        while Profile.query.filter_by(slug=slug).filter(Profile.id != self.id).first():
            slug = f"{base}-{n}"
            n += 1
        return slug


class Company(db.Model):
    __tablename__ = 'companies'
    id           = db.Column(db.Integer, primary_key=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey('profiles.id'), unique=True)
    org_nr       = db.Column(db.String(20))
    name         = db.Column(db.String(255))
    industry     = db.Column(db.String(255))
    founded_year = db.Column(db.Integer)
    employees    = db.Column(db.String(50))
    address      = db.Column(db.Text)
    logo_url     = db.Column(db.Text)
    website      = db.Column(db.Text)


class Message(db.Model):
    __tablename__ = 'messages'
    id           = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    to_user_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body         = db.Column(db.Text, nullable=False)
    read_at      = db.Column(db.DateTime)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


class Event(db.Model):
    __tablename__ = 'events'
    id          = db.Column(db.Integer, primary_key=True)
    slug        = db.Column(db.String(255), unique=True, nullable=False)
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    date        = db.Column(db.DateTime)
    location    = db.Column(db.String(255))
    address     = db.Column(db.Text)
    capacity    = db.Column(db.Integer, default=50)
    price       = db.Column(db.Integer, default=0)
    menu_json   = db.Column(db.Text, default='[]')
    banner_url  = db.Column(db.Text)
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('EventBooking', backref='event', lazy='dynamic')

    @property
    def spots_left(self):
        confirmed = self.bookings.filter_by(status='confirmed').count()
        return max(0, self.capacity - confirmed)


class EventBooking(db.Model):
    __tablename__ = 'event_bookings'
    id          = db.Column(db.Integer, primary_key=True)
    event_id    = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'))
    name        = db.Column(db.String(255))
    email       = db.Column(db.String(255))
    company     = db.Column(db.String(255))
    phone       = db.Column(db.String(50))
    items_json  = db.Column(db.Text, default='{}')
    total_price = db.Column(db.Integer, default=0)
    status      = db.Column(db.String(20), default='confirmed')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
