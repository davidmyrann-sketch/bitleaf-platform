import os, requests, json, re, cloudinary, cloudinary.uploader
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, current_app
from flask_login import login_required, current_user
from models import db, User, Profile, Company, ROLES, INDUSTRIES, VISIBILITY

profiles_bp = Blueprint('profiles', __name__)


def _init_cloudinary():
    cloudinary.config(
        cloud_name=current_app.config['CLOUDINARY_CLOUD'],
        api_key=current_app.config['CLOUDINARY_KEY'],
        api_secret=current_app.config['CLOUDINARY_SECRET'],
    )


def _brreg_lookup(org_nr):
    org_nr = re.sub(r'\D', '', org_nr)
    try:
        r = requests.get(f'https://data.brreg.no/enhetsregisteret/api/enheter/{org_nr}', timeout=8)
        if r.status_code == 200:
            d = r.json()
            adr = d.get('forretningsadresse', {})
            address = ', '.join(filter(None, [
                ' '.join(adr.get('adresse', [])),
                adr.get('postnummer', ''),
                adr.get('poststed', ''),
            ]))
            return {
                'name':         d.get('navn', ''),
                'industry':     d.get('naeringskode1', {}).get('beskrivelse', ''),
                'founded_year': d.get('stiftelsesdato', '')[:4] if d.get('stiftelsesdato') else '',
                'employees':    str(d.get('antallAnsatte', '')),
                'address':      address,
            }
    except Exception:
        pass
    return None


@profiles_bp.route('/')
def directory():
    q       = request.args.get('q', '').strip()
    role    = request.args.get('role', '')
    industry = request.args.get('industry', '')
    page    = request.args.get('page', 1, type=int)

    query = Profile.query.join(User).filter(Profile.role != None, Profile.role != '')

    if not (current_user.is_authenticated):
        query = query.filter(Profile.is_public == True)

    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(User.name.ilike(like), Profile.bio.ilike(like), Profile.looking_for.ilike(like))
        )
    if role:
        query = query.filter(Profile.role.ilike(f'%{role}%'))
    if industry:
        query = query.filter(Profile.industry.ilike(f'%{industry}%'))

    profiles = query.order_by(Profile.updated_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('profiles/directory.html',
        profiles=profiles, roles=ROLES, industries=INDUSTRIES,
        q=q, selected_role=role, selected_industry=industry)


@profiles_bp.route('/profil/<slug>')
def detail(slug):
    profile = Profile.query.filter_by(slug=slug).first_or_404()
    if not profile.is_public and not current_user.is_authenticated:
        abort(403)
    show_phone = (
        profile.phone_visible == 'public' or
        (profile.phone_visible == 'members' and current_user.is_authenticated)
    )
    show_email = (
        profile.email_visible == 'public' or
        (profile.email_visible == 'members' and current_user.is_authenticated)
    )
    return render_template('profiles/detail.html',
        profile=profile, show_phone=show_phone, show_email=show_email,
        roles=dict(ROLES), industries=dict(INDUSTRIES))


@profiles_bp.route('/min-profil', methods=['GET', 'POST'])
@login_required
def edit_profile():
    profile = current_user.profile
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.session.add(profile)

    company = profile.company
    if not company:
        company = Company(profile=profile)
        db.session.add(company)

    if request.method == 'POST':
        _init_cloudinary()

        # User fields
        current_user.name = request.form.get('name', current_user.name).strip()

        # Profile fields
        profile.role          = ','.join(request.form.getlist('role'))
        profile.bio           = request.form.get('bio', '')
        profile.phone         = request.form.get('phone', '')
        profile.phone_visible = request.form.get('phone_visible', 'members')
        profile.email_visible = request.form.get('email_visible', 'members')
        profile.linkedin_url  = request.form.get('linkedin_url', '')
        profile.website_url   = request.form.get('website_url', '')
        profile.video_url     = request.form.get('video_url', '')
        profile.looking_for   = request.form.get('looking_for', '')
        profile.offering      = request.form.get('offering', '')
        profile.industry      = ','.join(request.form.getlist('industry'))
        profile.is_public     = request.form.get('is_public') == 'on'

        if not profile.slug:
            profile.slug = profile.make_slug(current_user.name or current_user.email)

        # Profile photo
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename:
            result = cloudinary.uploader.upload(photo_file, folder='bitleaf/profiles', transformation=[{'width': 400, 'height': 400, 'crop': 'fill'}])
            profile.photo_url = result['secure_url']

        # Company fields
        company.org_nr       = request.form.get('org_nr', '').strip()
        company.name         = request.form.get('company_name', '').strip()
        company.industry     = request.form.get('company_industry', '').strip()
        company.founded_year = request.form.get('founded_year', None) or None
        company.employees    = request.form.get('employees', '').strip()
        company.address      = request.form.get('address', '').strip()
        company.website      = request.form.get('company_website', '').strip()

        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            result = cloudinary.uploader.upload(logo_file, folder='bitleaf/logos', transformation=[{'width': 300, 'height': 300, 'crop': 'fill'}])
            company.logo_url = result['secure_url']

        db.session.commit()
        flash('Profil oppdatert!', 'success')
        return redirect(url_for('profiles.detail', slug=profile.slug))

    return render_template('profiles/edit.html',
        profile=profile, company=company,
        roles=ROLES, industries=INDUSTRIES, visibility=VISIBILITY)


@profiles_bp.route('/slett-profil', methods=['POST'])
@login_required
def delete_profile():
    profile = current_user.profile
    if profile:
        if profile.company:
            db.session.delete(profile.company)
        db.session.delete(profile)
    db.session.delete(current_user)
    db.session.commit()
    from flask_login import logout_user
    logout_user()
    flash('Profilen din er slettet.', 'info')
    return redirect(url_for('auth.login'))


@profiles_bp.route('/api/brreg/<org_nr>')
@login_required
def brreg_api(org_nr):
    data = _brreg_lookup(org_nr)
    if data:
        return jsonify(data)
    return jsonify({'error': 'Ikke funnet'}), 404
