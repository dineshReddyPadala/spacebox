from pathlib import Path
import sys, re
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.main import app,PAGES
from app import settings
root=Path(__file__).resolve().parents[1]
known=set(PAGES)|{'/contact','/projects','/thank-you','/admin/','/admin/login','/privacy'}
with TestClient(app) as client:
    issues=[]
    count=0
    for route in list(PAGES)+['/contact','/projects']:
        response=client.get(route)
        if response.status_code!=200: issues.append((route,'invalid response'))
        soup=BeautifulSoup(response.text,'html.parser')
        for a in soup.find_all('a',href=True):
            href=a['href'].split('?')[0].split('#')[0]
            if not href.startswith('/') or href.startswith('//'):continue
            if href not in known and not href.startswith('/projects/'):
                issues.append((route,'unknown link '+href))
        for img in soup.find_all('img'):
            count+=1
            if not img.get('alt'):issues.append((route,'image missing alt'))
            src=img.get('src','')
            if src.startswith('/static/') and not (root/src.lstrip('/')).exists():issues.append((route,'missing asset '+src))
        canon=soup.select_one('link[rel=canonical]')
        if not canon or canon.get('href','')!=settings.SITE_URL+route:
            issues.append((route,'canonical mismatch'))
    print('ROUTES',len(PAGES)+2,'IMAGES',count,'ISSUES',len(issues))
    for issue in issues:print(issue)
    if issues:raise SystemExit(1)
