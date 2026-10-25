from __future__ import annotations
import secrets,hmac,hashlib
from fastapi import Request, HTTPException
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError,InvalidHashError
from . import settings
from .models import Admin

hasher=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)

def password_hash(password):
    if len(password)<14:raise ValueError('Admin password must be at least 14 characters')
    return hasher.hash(password)

def verify_password(digest,password):
    try:return hasher.verify(digest,password)
    except (VerifyMismatchError,InvalidHashError):return False

def new_csrf(request:Request):
    tok=request.session.get('csrf')
    if not isinstance(tok,str) or len(tok)<40:
        tok=secrets.token_urlsafe(40)
        request.session['csrf']=tok
    return tok

def check_csrf(request:Request, given:str):
    expected=request.session.get('csrf','')
    if not expected or not hmac.compare_digest(str(expected),str(given)):
        raise HTTPException(status_code=403,detail='Invalid form security token. Refresh the page and try again.')

def ip_fingerprint(request:Request):
    # Do not blindly trust X-Forwarded-For headers. A trusted edge proxy should normalize request.client.
    ip=request.client.host if request.client else 'unknown'
    return hmac.new(settings.APP_SECRET.encode(),ip.encode(),hashlib.sha256).hexdigest()

def current_admin(request:Request,db):
    uid=request.session.get('admin_id')
    if not isinstance(uid,int):return None
    a=db.get(Admin,uid)
    if not a or not a.active or request.session.get('session_version')!=a.session_version:
        request.session.clear()
        return None
    return a
