import re, secrets
from io import BytesIO
from bs4 import BeautifulSoup
from PIL import Image
from sqlalchemy import select,func
from app.models import SessionLocal,Admin,Project,Enquiry
from app.security import password_hash
from app.main import PAGES


def csrf(html):
    s=BeautifulSoup(html,'html.parser');el=s.select_one('input[name=csrf_token]')
    assert el,'missing CSRF field'
    return el['value']

def make_admin():
    with SessionLocal() as db:
        db.add(Admin(email='admin@spacebox.example',password_hash=password_hash('VeryStrong!AdminPassword2026'),session_version=secrets.token_hex(16)))
        db.commit()

def login(c):
    t=csrf(c.get('/admin/login').text)
    res=c.post('/admin/login',data={'csrf_token':t,'email':'admin@spacebox.example','password':'VeryStrong!AdminPassword2026'})
    assert res.status_code==303
    return csrf(c.get('/admin/').text)

def image_bytes():
    im=Image.new('RGB',(1400,900),color=(130,160,135))
    b=BytesIO();im.save(b,'JPEG',quality=85)
    return b.getvalue()


def test_all_routes_and_seo(client):
    routes=list(PAGES)+['/projects','/contact','/thank-you']
    for path in routes:
        r=client.get(path)
        assert r.status_code==200,(path,r.text[:200])
        soup=BeautifulSoup(r.text,'html.parser')
        assert soup.title and soup.select_one('h1'),path
        assert soup.select_one('link[rel=canonical]')
        assert soup.select_one('meta[name=description]')
        assert 'SpaceBox' in soup.title.text or path=='/thank-you'
        assert '#/' not in r.text, 'old single-page hash URL on '+path
    assert 'Manduva Homes' in client.get('/manduva-homes').text
    assert 'Beautiful Design' in client.get('/').text
    assert client.get('/manduva').status_code==301
    assert client.get('/sitemap.xml').status_code==200
    assert '<loc>http://testserver/manduva-homes</loc>' in client.get('/sitemap.xml').text
    assert 'Disallow: /admin/' in client.get('/robots.txt').text


def test_contact_persists_and_validates(client):
    token=csrf(client.get('/contact').text)
    data=dict(csrf_token=token,name='Asha Rao',phone='+91 9876543210',email='asha@example.com',project_type='Villa',location='Pune',budget='₹25–50 lakh',message='Need interiors',consent='yes')
    bad=client.post('/contact',data={**data,'csrf_token':'invalid'})
    assert bad.status_code==403
    r=client.post('/contact',data=data)
    assert r.status_code==303 and r.headers['location']=='/thank-you'
    with SessionLocal() as db:
        x=db.scalar(select(Enquiry))
        assert x.name=='Asha Rao' and x.project_type=='Villa' and x.consent
    token=csrf(client.get('/contact').text)
    assert client.post('/contact',data={**data,'csrf_token':token,'name':'X'}).status_code==422
    token=csrf(client.get('/contact').text)
    assert client.post('/contact',data={**data,'csrf_token':token,'website':'spam'}) .status_code==303
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Enquiry))==1


def test_contact_throttle(client):
    for i in range(5):
        token=csrf(client.get('/contact').text)
        r=client.post('/contact',data=dict(csrf_token=token,name='Asha Rao',phone='9876543210',project_type='Apartment',consent='yes'))
        assert r.status_code==303
    t=csrf(client.get('/contact').text)
    r=client.post('/contact',data=dict(csrf_token=t,name='Asha Rao',phone='9876543210',project_type='Apartment',consent='yes'))
    assert r.status_code==429


def test_admin_is_protected(client):
    for url in ['/admin/','/admin/projects','/admin/projects/new','/admin/leads','/admin/leads.csv']:
        assert client.get(url).status_code==403,url
    assert client.get('/admin/login').status_code==200
    assert client.get('/admin/').headers['X-Robots-Tag']=='noindex, nofollow'
    assert client.post('/admin/login',data={'csrf_token':'bad','email':'none','password':'bad'}).status_code==403


def test_project_workflow_and_draft_privacy(client):
    make_admin();token=login(client)
    r=client.post('/admin/projects/new',data={'csrf_token':token,'title':'Courtyard Heritage Retreat','category':'Manduva Homes','status':'Concept','location':'Andhra Pradesh','description':'Traditional courtyard with modern planning','featured':'yes'})
    assert r.status_code==303
    match=re.search(r'/admin/projects/(\d+)/edit',r.headers['location']);assert match
    project_id=int(match.group(1))
    with SessionLocal() as db:
        p=db.get(Project,project_id);slug=p.slug
    assert client.get('/projects/'+slug).status_code==404
    # Draft media cannot be public, and publishing without imagery is blocked.
    token=csrf(client.get(f'/admin/projects/{project_id}/edit').text)
    r=client.post(f'/admin/projects/{project_id}/publish',data={'csrf_token':token})
    assert 'photo-required' in r.headers['location']
    # Disallow fake image files
    token=csrf(client.get(f'/admin/projects/{project_id}/edit').text)
    r=client.post(f'/admin/projects/{project_id}/photos',data={'csrf_token':token},files={'photos':('malware.jpg',b'<script>bad</script>','image/jpeg')})
    assert r.status_code==422
    token=csrf(client.get(f'/admin/projects/{project_id}/edit').text)
    r=client.post(f'/admin/projects/{project_id}/photos',data={'csrf_token':token},files={'photos':('real.jpg',image_bytes(),'image/jpeg')})
    assert r.status_code==303
    with SessionLocal() as db:
        p=db.get(Project,project_id)
        photo=db.query(__import__('app.models',fromlist=['ProjectPhoto']).ProjectPhoto).filter_by(project_id=project_id).one()
        filename=photo.filename
    assert client.get('/media/'+filename).status_code==200  # logged in admin
    anon_type=client.cookies.get('spacebox_session')
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anon:
        assert anon.get('/media/'+filename).status_code==404
        assert anon.get('/projects/'+slug).status_code==404
    token=csrf(client.get(f'/admin/projects/{project_id}/edit').text)
    assert client.post(f'/admin/projects/{project_id}/publish',data={'csrf_token':token}).status_code==303
    with TestClient(app) as anon:
        assert anon.get('/projects/'+slug).status_code==200
        r=anon.get('/media/'+filename)
        assert r.status_code==200 and r.headers['content-type']=='image/webp'
        assert slug in anon.get('/sitemap.xml').text
        assert 'Courtyard Heritage Retreat' in anon.get('/projects').text
    # unpublish again
    token=csrf(client.get(f'/admin/projects/{project_id}/edit').text)
    client.post(f'/admin/projects/{project_id}/publish',data={'csrf_token':token})
    with TestClient(app) as anon:
        assert anon.get('/media/'+filename).status_code==404
        assert anon.get('/projects/'+slug).status_code==404


def test_admin_leads_and_csv_formula_safety(client):
    token=csrf(client.get('/contact').text)
    r=client.post('/contact',data=dict(csrf_token=token,name='Meera Shah',phone='9876543210',email='m@example.com',project_type='Apartment',message='=HYPERLINK("evil")',consent='yes'))
    assert r.status_code==303
    make_admin();admin_csrf=login(client)
    lead_list=client.get('/admin/leads')
    assert 'Meera Shah' in lead_list.text
    assert '<script>' not in lead_list.text
    csvout=client.get('/admin/leads.csv')
    assert csvout.status_code==200 and "'=HYPERLINK" in csvout.text
    with SessionLocal() as db:lid=db.scalar(select(Enquiry.id))
    assert client.post(f'/admin/leads/{lid}/status',data={'csrf_token':'invalid','status':'Contacted'}).status_code==403
    token=csrf(client.get('/admin/leads').text)
    assert client.post(f'/admin/leads/{lid}/status',data={'csrf_token':token,'status':'Contacted'}).status_code==303
    with SessionLocal() as db:assert db.get(Enquiry,lid).status=='Contacted'


def test_xss_and_security_headers(client):
    make_admin();token=login(client)
    r=client.post('/admin/projects/new',data={'csrf_token':token,'title':'<script>alert(1)</script> Riverside','category':'Villa','description':'<img src=x onerror=alert(1)>','status':'Concept'})
    assert r.status_code==303
    page=client.get('/admin/projects').text
    assert '&lt;script&gt;' in page and '<script>alert(1)</script>' not in page
    hdr=client.get('/').headers
    assert 'Content-Security-Policy' in hdr
    assert "script-src 'self'" in hdr['Content-Security-Policy']
    assert hdr['X-Frame-Options']=='DENY'
    assert hdr['X-Content-Type-Options']=='nosniff'

def test_admin_role_permissions(client):
    with SessionLocal() as db:
        db.add(Admin(email='editor@spacebox.example',password_hash=password_hash('EditorSecurePassword2026!'),session_version=secrets.token_hex(16),role='editor'))
        db.add(Admin(email='sales@spacebox.example',password_hash=password_hash('SalesSecurePassword2026!'),session_version=secrets.token_hex(16),role='sales'))
        db.commit()
    tok=csrf(client.get('/admin/login').text)
    assert client.post('/admin/login',data={'csrf_token':tok,'email':'editor@spacebox.example','password':'EditorSecurePassword2026!'}).status_code==303
    assert client.get('/admin/projects').status_code==200
    assert client.get('/admin/leads').status_code==403
    assert client.get('/admin/leads.csv').status_code==403
    tok=csrf(client.get('/admin/').text)
    client.post('/admin/logout',data={'csrf_token':tok})
    tok=csrf(client.get('/admin/login').text)
    assert client.post('/admin/login',data={'csrf_token':tok,'email':'sales@spacebox.example','password':'SalesSecurePassword2026!'}).status_code==303
    assert client.get('/admin/leads').status_code==200
    assert client.get('/admin/projects').status_code==403
    assert client.get('/admin/projects/new').status_code==403
    assert client.get('/admin/').status_code==200


def test_owner_can_delete_enquiry_with_csrf(client):
    t=csrf(client.get('/contact').text)
    client.post('/contact',data=dict(csrf_token=t,name='Ravi Kumar',phone='9876543210',project_type='Villa',consent='yes'))
    with SessionLocal() as db:
        lid=db.scalar(select(Enquiry.id))
    make_admin();login(client)
    assert client.post(f'/admin/leads/{lid}/delete',data={'csrf_token':'invalid'}).status_code==403
    t=csrf(client.get('/admin/leads').text)
    assert client.post(f'/admin/leads/{lid}/delete',data={'csrf_token':t}).status_code==303
    with SessionLocal() as db:assert db.get(Enquiry,lid) is None
