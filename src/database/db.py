from sqlalchemy import create_all, create_engine, Column, Integer, String, Float, Text, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./credit_committee.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String)
    industry = Column(String)
    country = Column(String)
    revenue = Column(Float)
    requested_amount = Column(Float)
    debt_ratio = Column(Float)
    credit_score = Column(Integer)
    status = Column(String, default="pending")
    room_id = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class AgentFinding(Base):
    __tablename__ = "agent_findings"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer)
    agent_name = Column(String)
    finding_type = Column(String) # analysis, review, consensus
    content = Column(Text)
    score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class CommitteeEvent(Base):
    __tablename__ = "committee_events"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer)
    event_type = Column(String)
    message = Column(Text)
    data = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer)
    final_outcome = Column(String) # APPROVE, REJECT, CONDITIONAL
    confidence_score = Column(Float)
    executive_summary = Column(Text)
    conditions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
