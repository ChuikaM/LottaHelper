from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime
import os

Base = declarative_base()

class FurnitureItem(Base):
    __tablename__ = 'furniture_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    furniture_name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)  # Used for embeddings
    category = Column(String(100), nullable=True, index=True)
    image_url = Column(String(512), nullable=True)
    product_url = Column(String(512), nullable=True)
    price = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Full-text search index for description (database-specific)
    __table_args__ = (
        Index('idx_furniture_description', 'description', postgresql_using='gin'),
        Index('idx_furniture_category_price', 'category', 'price'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'furniture_name': self.furniture_name,
            'description': self.description,
            'category': self.category,
            'image_url': self.image_url,
            'product_url': self.product_url,
            'price': self.price,
        }


class DatabaseManager:
    """Handles database connection and session management"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'sqlite:///./furniture_catalog.db'
        )
        
        # Configure engine based on database type
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
        
        Base.metadata.create_all(self.engine)
        self.session_factory = scoped_session(sessionmaker(bind=self.engine))
    
    def get_session(self):
        """Get a new database session"""
        return self.session_factory()
    
    def close_session(self):
        """Close the current session"""
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
    
    def search_by_category(self, category: str, limit: int = 50):
        """Search furniture by category"""
        session = self.get_session()
        try:
            return session.query(FurnitureItem).filter(
                FurnitureItem.category.ilike(f'%{category}%')
            ).limit(limit).all()
        finally:
            self.close_session()
    
    def get_item_by_id(self, item_id: int):
        """Get single furniture item by ID"""
        session = self.get_session()
        try:
            return session.query(FurnitureItem).filter(
                FurnitureItem.id == item_id
            ).first()
        finally:
            self.close_session()