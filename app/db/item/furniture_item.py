from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class FurnitureItem(Base):
    __tablename__ = 'furniture_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    furniture_name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=True, index=True)
    image_url = Column(String(512), nullable=True)
    product_url = Column(String(512), nullable=True)
    price = Column(Float, nullable=True)
    
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