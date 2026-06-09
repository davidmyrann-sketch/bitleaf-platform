import json, cloudinary, cloudinary.uploader
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from models import db, User, Profile, Event, EventBooking
from functools import wraps
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _init_cloudinary():
    cloudinary.config(
        cloud_name=current_app.config['CLOUDINARY_CLOUD'],
        api_key=current_app.config['CLOUDINARY_KEY'],
        api_secret=current_app.config['CLOUDINARY_SECRET'],
    )


@admin_bp.route('/')
@admin_required
def index():
    users_count    = User.query.count()
    profiles_count = Profile.query.filter(Profile.role != None, Profile.role != '').count()
    events_count   = Event.query.count()
    bookings_count = EventBooking.query.filter_by(status='confirmed').count()
    recent_users   = User.query.order_by(User.created_at.desc()).limit(10).all()
    return render_template('admin/index.html',
        users_count=users_count, profiles_count=profiles_count,
        events_count=events_count, bookings_count=bookings_count,
        recent_users=recent_users)


@admin_bp.route('/brukere')
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/users.html', users=users)


@admin_bp.route('/brukere/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Kan ikke endre din egen admin-status.', 'warning')
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
    return redirect(url_for('admin.users'))


@admin_bp.route('/events')
@admin_required
def events():
    events = Event.query.order_by(Event.date.desc()).all()
    return render_template('admin/events.html', events=events)


@admin_bp.route('/events/ny', methods=['GET', 'POST'])
@admin_required
def new_event():
    if request.method == 'POST':
        return _save_event(None)
    return render_template('admin/event_form.html', event=None)


@admin_bp.route('/events/<int:event_id>/rediger', methods=['GET', 'POST'])
@admin_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        return _save_event(event)
    return render_template('admin/event_form.html', event=event)


def _save_event(event):
    _init_cloudinary()
    is_new = event is None
    if is_new:
        event = Event()
        db.session.add(event)

    event.title       = request.form.get('title', '').strip()
    event.description = request.form.get('description', '').strip()
    event.location    = request.form.get('location', '').strip()
    event.address     = request.form.get('address', '').strip()
    event.capacity    = int(request.form.get('capacity', 50))
    event.price       = int(request.form.get('price', 0))
    event.is_active   = request.form.get('is_active') == 'on'

    date_str = request.form.get('date', '').strip()
    if date_str:
        event.date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')

    # Slug
    if not event.slug or is_new:
        base = event.title.lower()
        import re
        base = re.sub(r'[æÆ]', 'ae', base)
        base = re.sub(r'[øØ]', 'o', base)
        base = re.sub(r'[åÅ]', 'a', base)
        base = re.sub(r'[^a-z0-9]+', '-', base).strip('-')[:60]
        slug = base
        n = 1
        while Event.query.filter(Event.slug == slug, Event.id != (event.id or -1)).first():
            slug = f'{base}-{n}'
            n += 1
        event.slug = slug

    # Menu JSON
    menu_items = []
    names  = request.form.getlist('menu_name[]')
    prices = request.form.getlist('menu_price[]')
    for i, (n, p) in enumerate(zip(names, prices)):
        n = n.strip()
        if n:
            menu_items.append({'id': i + 1, 'name': n, 'price': int(p or 0)})
    event.menu_json = json.dumps(menu_items, ensure_ascii=False)

    # Banner image
    banner = request.files.get('banner')
    if banner and banner.filename:
        result = cloudinary.uploader.upload(banner, folder='bitleaf/events', transformation=[{'width': 1200, 'height': 600, 'crop': 'fill'}])
        event.banner_url = result['secure_url']

    db.session.commit()
    flash('Arrangement lagret!', 'success')
    return redirect(url_for('admin.events'))


@admin_bp.route('/events/<int:event_id>/pameldte')
@admin_required
def event_bookings(event_id):
    event    = Event.query.get_or_404(event_id)
    bookings = event.bookings.filter_by(status='confirmed').all()
    menu     = json.loads(event.menu_json or '[]')
    menu_map = {str(item['id']): item['name'] for item in menu}
    return render_template('admin/event_bookings.html', event=event, bookings=bookings, menu_map=menu_map)
