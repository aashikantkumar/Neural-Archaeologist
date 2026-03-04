from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base  # Use the Base from database.py


__all__ = ["User", "Investigation", "AgentLog", "RepoCache", "Base"]


def _uuid_str():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=_uuid_str)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    investigations = relationship("Investigation", back_populates="user")


class Investigation(Base):
    __tablename__ = "investigations"
    
    id = Column(String(36), primary_key=True, default=_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    repo_url = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    findings = Column(JSON, default=dict)  # Scout and Analyst data
    report = Column(Text, nullable=True)  # Final narrative from Narrator
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="investigations")
    agent_logs = relationship("AgentLog", back_populates="investigation", cascade="all, delete-orphan")


class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    investigation_id = Column(String(36), ForeignKey("investigations.id"), nullable=False)
    agent_name = Column(String, nullable=False)  # scout, analyst, narrator, coordinator
    message = Column(Text, nullable=False)
    data = Column(JSON, default=dict)  # Additional context
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    investigation = relationship("Investigation", back_populates="agent_logs")


class RepoCache(Base):
    __tablename__ = "repo_cache"
    
    repo_url = Column(Text, primary_key=True)
    git_data = Column(JSON, default=dict)  # Cached commit data
    last_updated = Column(DateTime, default=datetime.utcnow)