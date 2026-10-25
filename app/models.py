from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from . import settings

Base = declarative_base()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args={'check_same_thread':False} if settings.DATABASE_URL.startswith('sqlite:') else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def now():
    return datetime.now(timezone.utc)

class Admin(Base):
    __tablename__='admins'
    id=Column(Integer, primary_key=True)
    email=Column(String(250), unique=True, index=True, nullable=False)
    password_hash=Column(String(250), nullable=False)
    role=Column(String(20), nullable=False, default='owner')
    session_version=Column(String(100), nullable=False)
    active=Column(Boolean, nullable=False, default=True)
    created_at=Column(DateTime(timezone=True), default=now)

class Project(Base):
    __tablename__='projects'
    id=Column(Integer, primary_key=True)
    slug=Column(String(140), unique=True, index=True, nullable=False)
    title=Column(String(180), nullable=False)
    category=Column(String(50), nullable=False)
    location=Column(String(120), nullable=False, default='')
    status=Column(String(30), nullable=False, default='Concept')
    description=Column(Text, nullable=False, default='')
    featured=Column(Boolean, nullable=False, default=False)
    published=Column(Boolean, nullable=False, default=False)
    deleted=Column(Boolean, nullable=False, default=False)
    created_at=Column(DateTime(timezone=True), default=now)
    updated_at=Column(DateTime(timezone=True), default=now, onupdate=now)
    photos=relationship('ProjectPhoto',back_populates='project',order_by='ProjectPhoto.position',cascade='all, delete-orphan')

class ProjectPhoto(Base):
    __tablename__='project_photos'
    id=Column(Integer,primary_key=True)
    project_id=Column(Integer,ForeignKey('projects.id',ondelete='CASCADE'),nullable=False,index=True)
    filename=Column(String(100),nullable=False,unique=True)
    alt=Column(String(180),nullable=False,default='')
    position=Column(Integer,nullable=False,default=0)
    project=relationship('Project',back_populates='photos')

class Enquiry(Base):
    __tablename__='enquiries'
    id=Column(Integer,primary_key=True)
    name=Column(String(120),nullable=False)
    phone=Column(String(30),nullable=False)
    email=Column(String(254),nullable=False,default='')
    project_type=Column(String(60),nullable=False)
    location=Column(String(150),nullable=False,default='')
    budget=Column(String(100),nullable=False,default='')
    message=Column(Text,nullable=False,default='')
    consent=Column(Boolean,nullable=False)
    status=Column(String(30),nullable=False,default='New')
    ip_hash=Column(String(64),nullable=False,index=True)
    created_at=Column(DateTime(timezone=True),default=now)
    __table_args__=(Index('ix_enquiries_created_hash','created_at','ip_hash'),)

class LoginAttempt(Base):
    __tablename__='login_attempts'
    id=Column(Integer,primary_key=True)
    ip_hash=Column(String(64),nullable=False,index=True)
    created_at=Column(DateTime(timezone=True),default=now)

class Activity(Base):
    __tablename__='admin_activity'
    id=Column(Integer,primary_key=True)
    actor=Column(String(250),nullable=False)
    action=Column(String(120),nullable=False)
    subject=Column(String(220),nullable=False)
    created_at=Column(DateTime(timezone=True),default=now)


def init_db():
    Base.metadata.create_all(engine)
