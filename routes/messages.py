from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import db, User, Message, Profile
from datetime import datetime

messages_bp = Blueprint('messages', __name__)


@messages_bp.route('/meldinger')
@login_required
def inbox():
    # All unique conversations
    sent_to = db.session.query(Message.to_user_id).filter_by(from_user_id=current_user.id)
    recv_from = db.session.query(Message.from_user_id).filter_by(to_user_id=current_user.id)
    partner_ids = set(r[0] for r in sent_to.all()) | set(r[0] for r in recv_from.all())

    conversations = []
    for pid in partner_ids:
        partner = User.query.get(pid)
        if not partner:
            continue
        last_msg = Message.query.filter(
            db.or_(
                db.and_(Message.from_user_id == current_user.id, Message.to_user_id == pid),
                db.and_(Message.from_user_id == pid, Message.to_user_id == current_user.id),
            )
        ).order_by(Message.created_at.desc()).first()
        unread = Message.query.filter_by(from_user_id=pid, to_user_id=current_user.id, read_at=None).count()
        conversations.append({'partner': partner, 'last_msg': last_msg, 'unread': unread})

    conversations.sort(key=lambda c: c['last_msg'].created_at if c['last_msg'] else datetime.min, reverse=True)
    return render_template('messages/inbox.html', conversations=conversations)


@messages_bp.route('/meldinger/<int:partner_id>', methods=['GET', 'POST'])
@login_required
def conversation(partner_id):
    partner = User.query.get_or_404(partner_id)
    if partner_id == current_user.id:
        abort(400)

    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if body:
            msg = Message(from_user_id=current_user.id, to_user_id=partner_id, body=body)
            db.session.add(msg)
            db.session.commit()
        return redirect(url_for('messages.conversation', partner_id=partner_id))

    messages = Message.query.filter(
        db.or_(
            db.and_(Message.from_user_id == current_user.id, Message.to_user_id == partner_id),
            db.and_(Message.from_user_id == partner_id, Message.to_user_id == current_user.id),
        )
    ).order_by(Message.created_at.asc()).all()

    # Mark received messages as read
    for m in messages:
        if m.to_user_id == current_user.id and not m.read_at:
            m.read_at = datetime.utcnow()
    db.session.commit()

    return render_template('messages/conversation.html', partner=partner, messages=messages)


@messages_bp.route('/send-melding/<int:to_user_id>', methods=['POST'])
@login_required
def send_from_profile(to_user_id):
    body = request.form.get('body', '').strip()
    if body and to_user_id != current_user.id:
        msg = Message(from_user_id=current_user.id, to_user_id=to_user_id, body=body)
        db.session.add(msg)
        db.session.commit()
        flash('Melding sendt!', 'success')
    return redirect(url_for('messages.conversation', partner_id=to_user_id))
