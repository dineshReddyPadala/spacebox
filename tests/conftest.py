import os,tempfile
from pathlib import Path
os.environ['APP_ENV']='development'
os.environ['APP_SECRET']='test-secret-used-only-in-isolated-automated-tests'*2
os.environ['DATABASE_URL']='sqlite:///'+str(Path(tempfile.gettempdir())/'spacebox_integration_tests.db')
os.environ['MEDIA_DIR']=str(Path(tempfile.gettempdir())/'spacebox_integration_test_media')
os.environ['SITE_URL']='http://testserver'
import pytest
from fastapi.testclient import TestClient
from app.models import Base,engine
from app.main import app

@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app,follow_redirects=False) as c:
        yield c
