from pathlib import Path
import sys,os,getpass,secrets
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.models import SessionLocal, init_db, Admin
from app.security import password_hash

def main():
    init_db()
    email=os.getenv('BOOTSTRAP_ADMIN_EMAIL') or input('Admin email: ').strip().lower()
    if '@' not in email:raise SystemExit('Invalid email')
    role=os.getenv('BOOTSTRAP_ADMIN_ROLE','owner').lower()
    if role not in {'owner','editor','sales'}:raise SystemExit('Invalid role; use owner, editor or sales')
    pwd=os.getenv('BOOTSTRAP_ADMIN_PASSWORD') or getpass.getpass('Admin password (14+ chars): ')
    digest=password_hash(pwd)
    with SessionLocal() as db:
        a=db.scalar(select(Admin).where(Admin.email==email))
        if a:
            a.password_hash=digest;a.session_version=secrets.token_hex(16);a.active=True;a.role=role
            print('Existing admin credentials rotated:',email)
        else:
            db.add(Admin(email=email,password_hash=digest,role=role,session_version=secrets.token_hex(16)))
            print('Administrator created:',email)
        db.commit()
    print('Delete BOOTSTRAP_ADMIN_PASSWORD after setup; never commit credentials.')
if __name__=='__main__':main()
