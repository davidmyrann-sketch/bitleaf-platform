from app import create_app
from models import db, User

ADMINS = ['davidmyrann@gmail.com', 'jorid@bitleaf.no']

app = create_app()
with app.app_context():
    for email in ADMINS:
        u = User.query.filter_by(email=email).first()
        if u:
            u.is_admin = True
            db.session.commit()
            print(f'Admin satt: {u.email}')
        else:
            print(f'Ikke funnet (logg inn først): {email}')
