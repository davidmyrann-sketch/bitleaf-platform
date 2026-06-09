import json, stripe
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import current_user
from models import db, Event, EventBooking

events_bp = Blueprint('events', __name__)

CANCEL_EMAIL = 'post@bitleaf.no'
CANCEL_DAYS  = 3


def _stripe():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    return stripe


@events_bp.route('/events')
def event_list():
    events = Event.query.filter_by(is_active=True).order_by(Event.date.asc()).all()
    return render_template('events/list.html', events=events)


@events_bp.route('/events/<slug>')
def event_detail(slug):
    event = Event.query.filter_by(slug=slug, is_active=True).first_or_404()
    menu  = json.loads(event.menu_json or '[]')
    food_items  = [m for m in menu if m.get('type') == 'food']
    drink_items = [m for m in menu if m.get('type') == 'drink']

    user_booking = None
    prefill = {'name': '', 'phone': ''}
    if current_user.is_authenticated:
        user_booking = EventBooking.query.filter(
            EventBooking.event_id == event.id,
            EventBooking.user_id  == current_user.id,
            EventBooking.payment_status == 'paid'
        ).first()
        prefill['name']  = current_user.name or ''
        prefill['phone'] = (current_user.profile.phone if current_user.profile else '') or ''

    return render_template('events/detail.html',
        event=event, food_items=food_items, drink_items=drink_items,
        user_booking=user_booking, prefill=prefill,
        cancel_email=CANCEL_EMAIL, cancel_days=CANCEL_DAYS)


@events_bp.route('/events/<slug>/checkout', methods=['POST'])
def checkout(slug):
    event = Event.query.filter_by(slug=slug, is_active=True).first_or_404()

    if event.spots_left <= 0:
        flash('Arrangementet er fullt.', 'danger')
        return redirect(url_for('events.event_detail', slug=slug))

    name       = request.form.get('name', '').strip()
    phone      = request.form.get('phone', '').strip()
    food_id    = request.form.get('food_item', '').strip()
    drink_id   = request.form.get('drink_item', '').strip()

    if not name or not phone:
        flash('Navn og telefon er påkrevd.', 'danger')
        return redirect(url_for('events.event_detail', slug=slug))

    menu = json.loads(event.menu_json or '[]')
    menu_map = {str(m['id']): m['name'] for m in menu}

    food_name  = menu_map.get(food_id, food_id)
    drink_name = menu_map.get(drink_id, drink_id)

    booking = EventBooking(
        event_id       = event.id,
        user_id        = current_user.id if current_user.is_authenticated else None,
        name           = name,
        email          = current_user.email if current_user.is_authenticated else '',
        phone          = phone,
        food_choice    = food_name,
        drink_choice   = drink_name,
        items_json     = json.dumps({'food': food_id, 'drink': drink_id}),
        total_price    = event.price,
        status         = 'pending',
        payment_status = 'pending',
    )
    db.session.add(booking)
    db.session.flush()

    s = _stripe()
    description = f'{event.title} — {food_name} + {drink_name}'
    session = s.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'nok',
                'product_data': {
                    'name': event.title,
                    'description': description,
                },
                'unit_amount': event.price * 100,
            },
            'quantity': 1,
        }],
        mode='payment',
        customer_email=current_user.email if current_user.is_authenticated else None,
        success_url=url_for('events.booking_success', slug=slug, _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('events.event_detail', slug=slug, _external=True),
        metadata={'booking_id': str(booking.id)},
    )

    booking.stripe_session_id = session.id
    db.session.commit()
    return redirect(session.url, code=303)


@events_bp.route('/events/<slug>/bekreftet')
def booking_success(slug):
    event      = Event.query.filter_by(slug=slug).first_or_404()
    session_id = request.args.get('session_id', '')
    booking    = EventBooking.query.filter_by(stripe_session_id=session_id).first()
    return render_template('events/booking_success.html',
        event=event, booking=booking,
        cancel_email=CANCEL_EMAIL, cancel_days=CANCEL_DAYS)


@events_bp.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    s              = _stripe()
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']
    payload        = request.get_data()
    sig_header     = request.headers.get('Stripe-Signature', '')

    try:
        event = s.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception:
        return 'Invalid signature', 400

    if event['type'] == 'checkout.session.completed':
        session    = event['data']['object']
        booking_id = (session.get('metadata') or {}).get('booking_id')
        if booking_id:
            booking = EventBooking.query.get(int(booking_id))
            if booking:
                booking.status         = 'confirmed'
                booking.payment_status = 'paid'
                db.session.commit()

    return 'OK', 200
