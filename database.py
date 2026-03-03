import os
import datetime
from datetime import timezone

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    history = relationship("SearchHistory", back_populates="owner")


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    filename = Column(String)
    risks = Column(Integer)
    download_url = Column(String)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(timezone.utc))

    owner = relationship("User", back_populates="history")


def init_db():
    print("Connecting to supabase and creating tables")
    Base.metadata.create_all(bind=engine)

    print("Tables created successfully!")


if __name__ == '__main__':
    init_db()
