# ========== app/models.py ==========

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Company(Base):
    __tablename__ = 'companies'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    employee_count = Column(Integer, nullable=True)
    officers = Column(JSON)
    business_description = Column(Text)
    fast_facts = Column(JSON)
    created_at = Column(DateTime)

class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'))
    type = Column(String)
    content = Column(Text)
    summary = Column(Text)
    source_url = Column(String)
    created_at = Column(DateTime)