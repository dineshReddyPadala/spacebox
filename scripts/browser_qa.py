from pathlib import Path
import sys,re,base64
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.main import app
root=Path(__file__).resolve().parents[1]
css=(root/'static/css/prototype.css').read_text()+'\n'+(root/'static/css/production.css').read_text()
js=(root/'static/js/site.js').read_text()
# Build an offline visual-test document from server-rendered HTML; no external resources.
def offline_markup(markup):
    soup=BeautifulSoup(markup,'html.parser')
    for el in soup.select('script, link[rel="stylesheet"],link[rel="preconnect"]'):
        el.decompose()
    for img in soup.select('img'):
        src=img.get('src','')
        file=None
        if src.startswith('/static/'):
            file=root/src.lstrip('/')
        elif src.startswith('/media/'):
            file=Path('/mnt/data/spacebox_production/private_media')/src.split('/')[-1]
        # external references get local representative non-watermarked heritage visual to avoid empty boxes in test
        if not file or not file.exists():file=root/'static/images/ref-01.webp'
        suffix='png' if file.suffix.lower()=='.png' else 'webp'
        img['src']='data:image/'+suffix+';base64,'+base64.b64encode(file.read_bytes()).decode('ascii')
    style=soup.new_tag('style');style.string=css;soup.head.append(style)
    # CSS from production uses external fonts but fallbacks work in screenshot.
    return str(soup)

with TestClient(app) as c,sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    errors=[]
    routes=['/','/apartments','/villas','/manduva-homes','/offices','/commercial-spaces','/wellness','/our-process','/cost-guide','/projects','/about','/spacebox-ai','/contact']
    for width in [1440,1024,768,390]:
        ctx=browser.new_context(viewport={'width':width,'height':900},device_scale_factor=1)
        page=ctx.new_page()
        for route in routes:
            response=c.get(route)
            assert response.status_code==200,(route,response.status_code)
            page.set_content(offline_markup(response.text),wait_until='load',timeout=10000)
            # local javascript includes only externally sourced application behaviors, no test-only interaction shortcuts
            page.add_script_tag(content=js)
            page.evaluate('init()')
            bad=page.evaluate("document.documentElement.scrollWidth > innerWidth + 5")
            if bad:
                wider=page.evaluate("[...document.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>innerWidth+5).slice(0,10).map(e=>[e.tagName,e.className,e.getBoundingClientRect().right])")
                errors.append((route,width,'horizontal overflow',wider))
            if route=='/manduva-homes':
                assert page.locator('#mBrief').inner_text().strip()
                page.locator('#beds').select_option('5')
                assert '5-bedroom' in page.locator('#mTitle').inner_text()
                if width in [1440,390]:page.screenshot(path=str(root/f'qa_manduva_{width}.png'),full_page=False)
            if route=='/cost-guide':
                assert 'INDICATIVE INVESTMENT RANGE' in page.locator('#estimateResult').inner_text()
                page.locator('#estHome').select_option('villa')
                assert 'Villa interiors' in page.locator('#estimateResult').inner_text()
            if route=='/our-process':
                page.locator('[data-process-step="5"]').click()
                assert 'A space ready for life.' in page.locator('#processDetail').inner_text()
            if route=='/' and width in [1440,390]:page.screenshot(path=str(root/f'qa_home_{width}.png'),full_page=False)
        ctx.close()
    browser.close()
    print('VISUAL FLOW CHECKS',len(routes)*4,'routes x viewports')
    print('OVERFLOW FAILURES',len(errors))
    for error in errors[:12]:print(error)
    if errors:raise SystemExit(1)
