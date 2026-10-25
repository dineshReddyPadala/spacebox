from __future__ import annotations
import csv, io, re, secrets, hashlib, logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, joinedload
from PIL import Image, ImageOps, UnidentifiedImageError
from io import BytesIO
from . import settings
from .models import SessionLocal, init_db, Project, ProjectPhoto, Enquiry, Admin, LoginAttempt, Activity, now
from .security import new_csrf, check_csrf, current_admin, password_hash, verify_password, ip_fingerprint
from .mailer import notify_new_lead

log = logging.getLogger(__name__)
settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
if not settings.PRODUCTION:
    init_db()
app=FastAPI(title='SpaceBox Concepts',docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(SessionMiddleware,secret_key=settings.APP_SECRET,session_cookie='spacebox_session',same_site='lax',https_only=settings.PRODUCTION,max_age=60*60*8)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=settings.ALLOWED_HOSTS)
app.mount('/static',StaticFiles(directory=str(settings.BASE_DIR/'static')),name='static')
templates=Jinja2Templates(directory=str(settings.BASE_DIR/'templates'),autoescape=True)

@app.middleware('http')
async def security_headers(request:Request,call_next):
    request.state.csp_nonce=secrets.token_urlsafe(20)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy']=(
        "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
        f"script-src 'self' 'nonce-{request.state.csp_nonce}'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https://images.unsplash.com; connect-src 'self'; form-action 'self';"
    )
    if settings.PRODUCTION:
        response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    if request.url.path.startswith('/admin') or request.url.path.startswith('/media'):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Robots-Tag']='noindex, nofollow'
    return response

def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()

PAGES={
    '/':('home','SpaceBox Concepts | Beautiful Spaces, Better Living','Premium apartments, villas, Manduva Homes and wellness-led interiors. Beautiful Design, Wellness, Quality and Transparency.'),
    '/apartments':('apartments','Apartment Interiors | SpaceBox Concepts','Beautiful, functional apartment interiors with transparent BOQs, wellness-led details, Vastu preferences and complete execution.'),
    '/villas':('villas','Luxury Villa Interiors | SpaceBox Concepts','Personal sanctuary villa design, custom interiors and modern luxury, created with wellness, quality and thoughtful craftsmanship.'),
    '/manduva-homes':('manduva','Manduva Homes | Traditional Courtyard Homes by SpaceBox','Traditional Manduva courtyard homes with modern luxury, Vastu-conscious planning, wellness and possibilities for hosted stays.'),
    '/offices':('offices','Office Interior Design | SpaceBox Concepts','Modern workplace interiors for focus, collaboration, brand character, ergonomics, comfort and project delivery.'),
    '/commercial-spaces':('hospitality','Commercial & Hospitality Interior Design | SpaceBox','Interior design and execution for boutique hotels, restaurants, coffee shops, cafés and hospitality businesses.'),
    '/wellness':('wellness','Wellness-led Interior Design | SpaceBox Wellness+','Considered indoor air, natural light, sleep, acoustics, materials, ergonomics and accessibility in beautiful interiors.'),
    '/our-process':('process','Our Design & Delivery Process | SpaceBox','A clear six-stage journey from brief and measurements through concepts, itemised BOQs, execution, quality control and handover.'),
    '/cost-guide':('estimate','Interior Cost Guide | SpaceBox','Estimate an indicative budget for apartment and villa interiors, materials, scope and optional wellness upgrades.'),
    '/about':('about','About SpaceBox | Design, Wellness & Craftsmanship','Learn about SpaceBox, its founder-led design vision and values: Beautiful Design, Wellness, Quality and Transparency.'),
    '/spacebox-ai':('ai','SpaceBox AI — Coming Soon | SpaceBox','SpaceBox AI design visualization and intelligent planning tools are coming soon.'),
    '/privacy':('privacy','Privacy Policy | SpaceBox Concepts','How SpaceBox handles website enquiries and related personal information.'),
}
ALIASES={'/manduva':'/manduva-homes','/hospitality':'/commercial-spaces','/process':'/our-process','/estimate':'/cost-guide','/ai':'/spacebox-ai','/projects/':'/projects'}

def site_context(request,*,title,description,canonical_path,robots='index, follow',**extra):
    return dict(request=request,title=title,description=description,canonical=settings.SITE_URL+canonical_path,site_url=settings.SITE_URL,
                robots=robots,contact_email=settings.CONTACT_EMAIL,contact_phone=settings.CONTACT_PHONE,csrf=new_csrf(request),nonce=getattr(request.state,'csp_nonce',''),**extra)

def make_page_content(name:str):
    s=(settings.BASE_DIR/'templates/pages'/f'{name}.html').read_text()
    s=re.sub(r'\s+onerror="[^"]*"','',s)
    # Static pages are trusted checked-in source; remove old inline event handlers for strict CSP.
    s=re.sub(r'\s+onclick="showProcess\((\d+)\)"',r' data-process-step="\1"',s)
    s=s.replace(' onclick="saveManduva()"',' data-save-manduva="true"')
    s=s.replace(' onchange="renderManduva()"',' data-manduva-change="true"')
    s=s.replace(' onchange="updateEstimate()"',' data-estimate-change="true"')
    return s

PAGE_HTML={name:make_page_content(name) for name,_,_ in PAGES.values()}

def project_card(project:Project):
    # Use actual templates for escaping, not HTML concatenation of user content.
    photo = project.photos[0] if project.photos else None
    return dict(project=project,photo=photo)

def featured_markup(db:Session,request:Request):
    # Render project list with Jinja escaping. No fake completed work or testimonials.
    projects=db.scalars(select(Project).options(joinedload(Project.photos)).where(Project.published==True,Project.deleted==False).order_by(Project.featured.desc(),Project.updated_at.desc()).limit(3)).unique().all()
    if not projects:
        return '<div class="portfolio-empty"><h3>Real spaces, real stories.</h3><p>Our verified portfolio is being prepared. We would be happy to discuss relevant work and your project requirements.</p><a href="/contact" class="btn outline">Discuss Your Project ↗</a></div>'
    tpl=templates.env.get_template('partials/project_cards.html')
    return tpl.render(projects=projects)

def marketing(request:Request,db:Session,path:str):
    name,title,desc=PAGES[path]
    body=PAGE_HTML[name]
    if name=='home':
        body=body.replace('<div id="homeprojects" class="grid three"></div>',f'<div id="homeprojects" class="grid three">{featured_markup(db,request)}</div>')
    if name=='about':
        body=body.replace('Professional credentials and profile to be added after verification.','')
    if name=='manduva':
        body=body.replace('A home you can enjoy.<br>And potentially earn from.','A home to enjoy.<br>And potentially earn from.')
    # All form/chat/portfolio controls use server functionality, so replace old prototype-only markup.
    if name=='privacy':
        return templates.TemplateResponse(request,'privacy.html',site_context(request,title=title,description=desc,canonical_path=path))
    return templates.TemplateResponse(request,'marketing.html',site_context(request,title=title,description=desc,canonical_path=path,body=body))

def make_marketing_handler(page_path):
    def handler(request:Request,db:Session=Depends(get_db)):
        return marketing(request,db,page_path)
    return handler

for route in PAGES:
    app.add_api_route(route,make_marketing_handler(route),methods=['GET'],response_class=HTMLResponse)

def make_redirect_handler(target):
    def handler():
        return RedirectResponse(target,status_code=301)
    return handler

for alias,target in ALIASES.items():
    app.add_api_route(alias,make_redirect_handler(target),methods=['GET'],include_in_schema=False)

# Projects are private until explicitly published; all media is served through authorization checks.
@app.get('/projects',response_class=HTMLResponse)
def gallery(request:Request,category:str='',db:Session=Depends(get_db)):
    stmt=select(Project).options(joinedload(Project.photos)).where(Project.published==True,Project.deleted==False)
    if category:
        stmt=stmt.where(Project.category==category)
    items=db.scalars(stmt.order_by(desc(Project.updated_at))).unique().all()
    cats=db.scalars(select(Project.category).where(Project.published==True,Project.deleted==False).distinct().order_by(Project.category)).all()
    return templates.TemplateResponse(request,'gallery.html',site_context(request,title='Our Projects | SpaceBox Concepts',description='Explore verified completed and ongoing projects across apartments, villas, Manduva Homes, offices and commercial interiors.',canonical_path='/projects',projects=items,categories=cats,category=category))

@app.get('/projects/{slug}',response_class=HTMLResponse)
def gallery_detail(request:Request,slug:str,db:Session=Depends(get_db)):
    p=db.scalar(select(Project).options(joinedload(Project.photos)).where(Project.slug==slug,Project.published==True,Project.deleted==False).limit(1))
    if not p:raise HTTPException(404,'Project not found')
    return templates.TemplateResponse(request,'project_detail.html',site_context(request,title=p.title+' | SpaceBox Projects',description=p.description[:155] if p.description else 'A SpaceBox interiors project.',canonical_path='/projects/'+p.slug,project=p,og_image=(settings.SITE_URL+'/media/'+p.photos[0].filename if p.photos else settings.SITE_URL+'/static/images/social-preview.webp')))

# Contact intake: CSRF, consent, strict form validation, honeypot, persisted lead and optional SMTP notification.
PROJECT_TYPES={'Apartment','Villa','Manduva Homes','Office','Hospitality','Wellness','Commercial','Other'}
@app.get('/contact',response_class=HTMLResponse)
def contact(request:Request):
    return templates.TemplateResponse(request,'contact.html',site_context(request,title='Contact SpaceBox | Book a Design Consultation',description='Tell SpaceBox about your interiors, villa, Manduva or workplace project. Request a personalized design consultation.',canonical_path='/contact'))

@app.post('/contact',response_class=HTMLResponse)
def contact_submit(request:Request,background_tasks:BackgroundTasks,db:Session=Depends(get_db),
       csrf_token:str=Form(...),name:str=Form(...),phone:str=Form(...),email:str=Form(''),
       project_type:str=Form(...),location:str=Form(''),budget:str=Form(''),message:str=Form(''),
       consent:str=Form(''),website:str=Form('')):
    check_csrf(request,csrf_token)
    if website.strip():return RedirectResponse('/thank-you',status_code=303)
    name=name.strip();phone=phone.strip();email=email.strip().lower();location=location.strip();message=message.strip()
    digits=re.sub(r'\D','',phone)
    if not(2<=len(name)<=120) or not(10<=len(digits)<=15) or project_type not in PROJECT_TYPES or consent!='yes' or len(message)>3000 or len(location)>150 or len(email)>254 or (email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):
        return templates.TemplateResponse(request,'contact.html',site_context(request,title='Contact SpaceBox',description='Book your SpaceBox consultation.',canonical_path='/contact',error='Please check your name, phone number, project type, email and consent.'),status_code=422)
    fp=ip_fingerprint(request)
    since=now()-timedelta(hours=1)
    attempts=db.scalar(select(func.count()).select_from(Enquiry).where(Enquiry.ip_hash==fp,Enquiry.created_at>since))
    if attempts>=5:
        return templates.TemplateResponse(request,'contact.html',site_context(request,title='Contact SpaceBox',description='Book a consultation',canonical_path='/contact',error='Too many enquiries were submitted recently. Please contact us by phone.'),status_code=429)
    lead=Enquiry(name=name,phone=phone,email=email,project_type=project_type,location=location,budget=budget[:100],message=message,consent=True,ip_hash=fp)
    db.add(lead);db.commit();db.refresh(lead)
    background_tasks.add_task(notify_new_lead,lead)
    return RedirectResponse('/thank-you',status_code=303)

@app.get('/thank-you',response_class=HTMLResponse)
def thanks(request:Request):
    return templates.TemplateResponse(request,'thanks.html',site_context(request,title='Thank You | SpaceBox',description='Thank you for contacting SpaceBox.',canonical_path='/thank-you',robots='noindex, nofollow'))

@app.get('/healthz')
def health():return {'ok':True}

@app.get('/robots.txt',response_class=PlainTextResponse)
def robots():return f'User-agent: *\nDisallow: /admin/\nDisallow: /media/\nSitemap: {settings.SITE_URL}/sitemap.xml\n'

@app.get('/sitemap.xml')
def sitemap(db:Session=Depends(get_db)):
    from xml.sax.saxutils import escape
    slugs=list(PAGES)+['/projects','/contact']
    slugs += ['/projects/'+p for p in db.scalars(select(Project.slug).where(Project.published==True,Project.deleted==False)).all()]
    body=''.join('<url><loc>'+escape(settings.SITE_URL+p)+'</loc></url>' for p in slugs)
    return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+body+'</urlset>',media_type='application/xml')

# Admin: only signed-in staff can view draft projects, leads and management tools.
def admin_guard(request,db,scope=None):
    a=current_admin(request,db)
    if not a:raise HTTPException(403,'Administrator authentication required')
    permissions={'owner':{'projects','leads'},'editor':{'projects'},'sales':{'leads'}}
    if scope and scope not in permissions.get(a.role,set()):
        raise HTTPException(403,'Your account does not have permission for this area')
    return a

def admin_context(request:Request,admin:Admin,**kw):
    return site_context(request,title='SpaceBox Admin',description='Private content management',canonical_path=request.url.path,robots='noindex, nofollow',admin=admin,**kw)

@app.get('/admin/login',response_class=HTMLResponse)
def admin_login_page(request:Request,db:Session=Depends(get_db)):
    if current_admin(request,db):return RedirectResponse('/admin/',status_code=302)
    return templates.TemplateResponse(request,'admin/login.html',site_context(request,title='SpaceBox Admin Login',description='Administrator sign-in',canonical_path='/admin/login',robots='noindex, nofollow'))

@app.post('/admin/login')
def admin_login(request:Request,db:Session=Depends(get_db),csrf_token:str=Form(...),email:str=Form(...),password:str=Form(...)):
    check_csrf(request,csrf_token)
    fingerprint=ip_fingerprint(request)
    recent=db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.ip_hash==fingerprint,LoginAttempt.created_at>now()-timedelta(minutes=15)))
    if recent>=8:
        return templates.TemplateResponse(request,'admin/login.html',site_context(request,title='SpaceBox Admin Login',description='Administrator sign-in',canonical_path='/admin/login',robots='noindex, nofollow',error='Too many login attempts. Try again later.'),status_code=429)
    email=email.strip().lower()
    a=db.scalar(select(Admin).where(Admin.email==email))
    if not a or not a.active or not verify_password(a.password_hash,password):
        db.add(LoginAttempt(ip_hash=fingerprint));db.commit()
        return templates.TemplateResponse(request,'admin/login.html',site_context(request,title='SpaceBox Admin Login',description='Administrator sign-in',canonical_path='/admin/login',robots='noindex, nofollow',error='Incorrect credentials.'),status_code=401)
    request.session.clear()
    request.session['admin_id']=a.id
    request.session['session_version']=a.session_version
    return RedirectResponse('/admin/',status_code=303)

@app.post('/admin/logout')
def admin_logout(request:Request,db:Session=Depends(get_db),csrf_token:str=Form(...)):
    admin_guard(request,db);check_csrf(request,csrf_token)
    request.session.clear()
    return RedirectResponse('/admin/login',status_code=303)

@app.get('/admin/',response_class=HTMLResponse)
def admin_home(request:Request,db:Session=Depends(get_db)):
    a=admin_guard(request,db)
    leads=db.scalar(select(func.count()).select_from(Enquiry))
    projects=db.scalar(select(func.count()).select_from(Project).where(Project.deleted==False))
    drafts=db.scalar(select(func.count()).select_from(Project).where(Project.published==False,Project.deleted==False))
    recent=db.scalars(select(Enquiry).order_by(desc(Enquiry.created_at)).limit(5)).all() if a.role in {'owner','sales'} else []
    return templates.TemplateResponse(request,'admin/dashboard.html',admin_context(request,a,leads=leads if a.role in {'owner','sales'} else None,projects=projects if a.role in {'owner','editor'} else None,drafts=drafts if a.role in {'owner','editor'} else None,recent=recent))

CATEGORIES={'Apartment','Villa','Manduva Homes','Office','Hospitality','Wellness','Commercial'}
PROJECT_STATUSES={'Concept','Ongoing','Completed'}

def normalize_slug(text):
    import unicodedata
    t=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+','-',t.lower()).strip('-')[:100]

def unique_slug(db, title, current_id=None):
    root=normalize_slug(title) or 'spacebox-project'
    slug=root;i=2
    while True:
        p=db.scalar(select(Project).where(Project.slug==slug))
        if not p or p.id==current_id:return slug
        slug=f'{root}-{i}';i+=1

def audit(db,admin,action,subject):
    db.add(Activity(actor=admin.email,action=action,subject=subject[:220]))

@app.get('/admin/projects',response_class=HTMLResponse)
def admin_projects(request:Request,db:Session=Depends(get_db)):
    a=admin_guard(request,db,'projects')
    rows=db.scalars(select(Project).where(Project.deleted==False).order_by(desc(Project.updated_at))).all()
    return templates.TemplateResponse(request,'admin/projects.html',admin_context(request,a,projects=rows))

@app.get('/admin/projects/new',response_class=HTMLResponse)
def admin_project_new(request:Request,db:Session=Depends(get_db)):
    a=admin_guard(request,db,'projects')
    return templates.TemplateResponse(request,'admin/project_form.html',admin_context(request,a,project=None,categories=sorted(CATEGORIES),statuses=sorted(PROJECT_STATUSES)))

@app.post('/admin/projects/new')
def admin_project_create(request:Request,db:Session=Depends(get_db),csrf_token:str=Form(...),title:str=Form(...),category:str=Form(...),status:str=Form('Concept'),location:str=Form(''),description:str=Form(''),featured:str=Form('')):
    a=admin_guard(request,db,'projects');check_csrf(request,csrf_token)
    title=title.strip();location=location.strip()
    if not(3<=len(title)<=180) or category not in CATEGORIES or status not in PROJECT_STATUSES or len(description)>8000 or len(location)>120:
        raise HTTPException(422,'Invalid project details')
    p=Project(title=title,slug=unique_slug(db,title),category=category,status=status,location=location,description=description.strip(),featured=bool(featured),published=False)
    db.add(p);db.flush();audit(db,a,'Create draft project',p.title);db.commit()
    return RedirectResponse(f'/admin/projects/{p.id}/edit',status_code=303)

@app.get('/admin/projects/{id}/edit',response_class=HTMLResponse)
def admin_project_edit(request:Request,id:int,db:Session=Depends(get_db)):
    a=admin_guard(request,db,'projects')
    p=db.scalar(select(Project).options(joinedload(Project.photos)).where(Project.id==id,Project.deleted==False).limit(1))
    if not p:raise HTTPException(404)
    return templates.TemplateResponse(request,'admin/project_form.html',admin_context(request,a,project=p,categories=sorted(CATEGORIES),statuses=sorted(PROJECT_STATUSES)))

@app.post('/admin/projects/{id}/edit')
def admin_project_update(request:Request,id:int,db:Session=Depends(get_db),csrf_token:str=Form(...),title:str=Form(...),category:str=Form(...),status:str=Form('Concept'),location:str=Form(''),description:str=Form(''),featured:str=Form('')):
    a=admin_guard(request,db,'projects');check_csrf(request,csrf_token)
    p=db.get(Project,id)
    if not p or p.deleted:raise HTTPException(404)
    title=title.strip();location=location.strip()
    if not(3<=len(title)<=180) or category not in CATEGORIES or status not in PROJECT_STATUSES or len(description)>8000 or len(location)>120:
        raise HTTPException(422,'Invalid project details')
    p.title=title;p.category=category;p.status=status;p.location=location;p.description=description.strip();p.featured=bool(featured)
    audit(db,a,'Update project',title);db.commit()
    return RedirectResponse(f'/admin/projects/{id}/edit?updated=1',status_code=303)

@app.post('/admin/projects/{id}/publish')
def admin_project_publish(request:Request,id:int,db:Session=Depends(get_db),csrf_token:str=Form(...)):
    a=admin_guard(request,db,'projects');check_csrf(request,csrf_token)
    p=db.scalar(select(Project).options(joinedload(Project.photos)).where(Project.id==id,Project.deleted==False).limit(1))
    if not p:raise HTTPException(404)
    if not p.published and not p.photos:
        return RedirectResponse(f'/admin/projects/{id}/edit?error=photo-required',status_code=303)
    p.published=not p.published;audit(db,a,'Publish project' if p.published else 'Unpublish project',p.title);db.commit()
    return RedirectResponse(f'/admin/projects/{id}/edit',status_code=303)

@app.post('/admin/projects/{id}/delete')
def admin_project_delete(request:Request,id:int,db:Session=Depends(get_db),csrf_token:str=Form(...)):
    a=admin_guard(request,db,'projects');check_csrf(request,csrf_token)
    p=db.get(Project,id)
    if not p or p.deleted:raise HTTPException(404)
    p.deleted=True;p.published=False;audit(db,a,'Archive project',p.title);db.commit()
    return RedirectResponse('/admin/projects',status_code=303)

MAX_UPLOAD_BYTES=8*1024*1024
MAX_IMAGE_PIXELS=24_000_000

@app.post('/admin/projects/{id}/photos')
async def admin_photos_add(request:Request,id:int,db:Session=Depends(get_db),csrf_token:str=Form(...),photos:list[UploadFile]=File(...)):
    a=admin_guard(request,db,'projects');check_csrf(request,csrf_token)
    p=db.get(Project,id)
    if not p or p.deleted:raise HTTPException(404)
    if len(photos)>8:raise HTTPException(413,'Maximum eight photos per upload')
    prepared=[]
    for up in photos:
        raw=await up.read(MAX_UPLOAD_BYTES+1)
        if not raw or len(raw)>MAX_UPLOAD_BYTES:raise HTTPException(413,'Image exceeds 8 MB size limit')
        try:
            src=Image.open(BytesIO(raw));src.verify()
            src=Image.open(BytesIO(raw))
            if src.format not in {'JPEG','PNG','WEBP'} or src.width*src.height>MAX_IMAGE_PIXELS:
                raise ValueError('Unsupported image type or image dimensions')
            src=ImageOps.exif_transpose(src).convert('RGB')
            src.thumbnail((1800,1600),Image.Resampling.LANCZOS)
            output=BytesIO();src.save(output,'WEBP',quality=80,method=5)
            prepared.append((secrets.token_hex(16)+'.webp',output.getvalue()))
        except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
            raise HTTPException(422,'Only valid JPEG, PNG or WebP image files are allowed')
    base=db.scalar(select(func.count()).select_from(ProjectPhoto).where(ProjectPhoto.project_id==id)) or 0
    for i,(filename,content) in enumerate(prepared):
        (settings.MEDIA_DIR/filename).write_bytes(content)
        db.add(ProjectPhoto(project_id=id,filename=filename,position=base+i,alt=p.title+' — '+p.category))
    audit(db,a,'Upload project photographs',p.title);db.commit()
    return RedirectResponse(f'/admin/projects/{id}/edit',status_code=303)

@app.post('/admin/photos/{id}/delete')
def admin_photo_delete(request:Request,id:int,db:Session=Depends(get_db),csrf_token:str=Form(...)):
    a=admin_guard(request,db,'projects');check_csrf(request,csrf_token)
    photo=db.get(ProjectPhoto,id)
    if not photo:raise HTTPException(404)
    project=db.get(Project,photo.project_id)
    pid=photo.project_id
    # Unpublish if all photos removed; published projects require an image.
    num=db.scalar(select(func.count()).select_from(ProjectPhoto).where(ProjectPhoto.project_id==pid))
    if num<=1 and project:project.published=False
    filename=photo.filename
    db.delete(photo);audit(db,a,'Remove photo',filename);db.commit()
    (settings.MEDIA_DIR/filename).unlink(missing_ok=True)
    return RedirectResponse(f'/admin/projects/{pid}/edit',status_code=303)

@app.post('/admin/photos/{id}/cover')
def admin_photo_cover(request:Request,id:int,db:Session=Depends(get_db),csrf_token:str=Form(...)):
    a=admin_guard(request,db,'projects');check_csrf(request,csrf_token)
    photo=db.get(ProjectPhoto,id)
    if not photo:raise HTTPException(404)
    peers=db.scalars(select(ProjectPhoto).where(ProjectPhoto.project_id==photo.project_id).order_by(ProjectPhoto.position)).all()
    # Put selected image first; stable order thereafter.
    for i,p in enumerate([photo]+[x for x in peers if x.id!=photo.id]):p.position=i
    audit(db,a,'Set cover photo',str(photo.project_id));db.commit()
    return RedirectResponse(f'/admin/projects/{photo.project_id}/edit',status_code=303)

@app.get('/media/{filename}')
def media(request:Request,filename:str,db:Session=Depends(get_db)):
    if not re.fullmatch(r'[a-f0-9]{32}\.webp',filename):raise HTTPException(404)
    photo=db.scalar(select(ProjectPhoto).where(ProjectPhoto.filename==filename))
    if not photo:raise HTTPException(404)
    p=db.get(Project,photo.project_id)
    if not p or p.deleted:raise HTTPException(404)
    if not p.published and (not current_admin(request,db) or current_admin(request,db).role not in {'owner','editor'}):raise HTTPException(404)
    file_path=settings.MEDIA_DIR/filename
    if not file_path.exists():raise HTTPException(404)
    resp=FileResponse(file_path,media_type='image/webp')
    resp.headers['Cache-Control']='no-store' if not p.published else 'public, max-age=3600'
    return resp

@app.get('/admin/leads',response_class=HTMLResponse)
def admin_leads(request:Request,page:int=1,db:Session=Depends(get_db)):
    a=admin_guard(request,db,'leads')
    page=max(1,min(page,10000))
    total=db.scalar(select(func.count()).select_from(Enquiry))
    rows=db.scalars(select(Enquiry).order_by(desc(Enquiry.created_at)).offset((page-1)*50).limit(50)).all()
    return templates.TemplateResponse(request,'admin/leads.html',admin_context(request,a,leads=rows,page=page,total=total))

@app.post('/admin/leads/{id}/status')
def admin_lead_status(request:Request,id:int,db:Session=Depends(get_db),csrf_token:str=Form(...),status:str=Form(...)):
    a=admin_guard(request,db,'leads');check_csrf(request,csrf_token)
    lead=db.get(Enquiry,id)
    if not lead:raise HTTPException(404)
    if status not in {'New','Contacted','Qualified','Closed','Not a Fit'}:raise HTTPException(422)
    lead.status=status;audit(db,a,'Update enquiry status',str(id));db.commit()
    return RedirectResponse('/admin/leads',status_code=303)

@app.post('/admin/leads/{id}/delete')
def admin_lead_delete(request:Request,id:int,db:Session=Depends(get_db),csrf_token:str=Form(...)):
    a=admin_guard(request,db)
    if a.role!='owner':raise HTTPException(403,'Only the owner can permanently remove enquiry records')
    check_csrf(request,csrf_token)
    lead=db.get(Enquiry,id)
    if not lead:raise HTTPException(404)
    audit(db,a,'Delete enquiry',str(id))
    db.delete(lead);db.commit()
    return RedirectResponse('/admin/leads',status_code=303)

@app.get('/admin/leads.csv')
def admin_leads_csv(request:Request,db:Session=Depends(get_db)):
    admin_guard(request,db,'leads')
    buf=io.StringIO();writer=csv.writer(buf)
    writer.writerow(['ID','Date (UTC)','Name','Phone','Email','Type','Location','Budget','Message','Status','Consent'])
    def safe_cell(v):
        s=str(v if v is not None else '')
        return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
    for l in db.scalars(select(Enquiry).order_by(desc(Enquiry.created_at))).all():
        writer.writerow([safe_cell(x) for x in [l.id,l.created_at,l.name,l.phone,l.email,l.project_type,l.location,l.budget,l.message,l.status,l.consent]])
    return Response(buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="spacebox-enquiries.csv"','Cache-Control':'no-store'})

@app.exception_handler(404)
def not_found(request:Request,exc:HTTPException):
    return templates.TemplateResponse(request,'404.html',site_context(request,title='Page not found | SpaceBox',description='Page not found',canonical_path='/404',robots='noindex, nofollow'),status_code=404)
