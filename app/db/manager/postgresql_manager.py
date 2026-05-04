from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from app.db.item.furniture_item import FurnitureItem
import os

class PostgreSQLManager:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'sqlite:///lottahelper/data/furniture_catalog.db'
        )
        
        if self.database_url.startswith('postgresql'):
            self.engine = create_engine(
                self.database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False
            )
        elif self.database_url.startswith('mysql'):
            self.engine = create_engine(
                self.database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False
            )
        else:  # SQLite
            self.engine = create_engine(
                self.database_url,
                connect_args={'check_same_thread': False},
                echo=False
            )
        
        self.session_factory = scoped_session(sessionmaker(bind=self.engine))
    
    def get_session(self):
        return self.session_factory()
    
    def close_session(self):
        self.session_factory.remove()

    def get_furniture_items(self, has_description: bool = True, limit: int = None):
        """Fetch furniture items from database"""
        session = self.get_session()
        try:
            query = session.query(FurnitureItem)
            if has_description:
                query = query.filter(FurnitureItem.description.isnot(None))
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            self.close_session()
        
    def check_health(self):
        session = self.get_session()
        try:
            session.query(text("SELECT 1"))
        finally:
            self.close_session()
            