import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import current_user
from models import db, Event, EventBooking

events_bp = Blueprint('events', __name__)


@events_bp.route('/events')
def event_list():
    events = Event.query.filter_by(is_active=True).order_by(Event.date.asc()).all()
    return render_template('events/list.html', events=events)


@events_bp.route('/events/<slug>')
def event_detail(slug):
    event = Event.query.filter_by(slug=slug, is_active=True).first_or_404()
    menu = json.loads(event.menu_json or '[]')
    user_booking = None
    if current_user.is_authenticated:
        user_booking = EventBooking.query.filter_by(event_id=event.id, user_id=current_user.id, status='confirmed').first()
    return render_template('events/detail.html', event=event, menu=menu, user_booking=user_booking)


@events_bp.route('/events/<slug>/book', methods=['POST'])
def book_event(slug):
    event = Event.query.filter_by(slug=slug, is_active=True).first_or_404()
    if event.spots_left <= 0:
        flash('Arrangementet er fullt.', 'danger')
        return redirect(url_for('events.event_detail', slug=slug))

    name    = request.form.get('name', '').strip()
    email   = request.form.get('email', '').strip()
    company = request.form.get('company', '').strip()
    phone   = request.form.get('phone', '').strip()

    if not name or not email:
        flash('Navn og e-post er påkrevd.', 'danger')
        return redirect(url_for('events.event_detail', slug=slug))

    # Collect menu item quantities
    menu = json.loads(event.menu_json or '[]')
    items = {}
    total = 0
    for item in menu:
        key = f"item_{item['id']}"
        qty = int(request.form.get(key, 0))
        if qty > 0:
            items[str(item['id'])] = qty
            total += qty * item.get('price', 0)

    if event.price > 0:
        total += event.price

    booking = EventBooking(
        event_id    = event.id,
        user_id     = current_user.id if current_user.is_authenticated else None,
        name        = name,
        email       = email,
        company     = company,
        phone       = phone,
        items_json  = json.dumps(items),
        total_price = total,
        status      = 'confirmed',
    )
    db.session.add(booking)
    db.session.commit()
    flash(f'Plass bekreftet! Ser frem til å se deg, {name}.', 'success')
    return redirect(url_for('events.event_detail', slug=slug))
