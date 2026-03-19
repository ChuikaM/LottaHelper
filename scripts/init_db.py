#!/usr/bin/env python3
"""Initialize database and import data from JSON"""

import json
import sys
from datetime import datetime

from app.db.manager.postgresql_manager import DatabaseManager
from app.db.item.furniture_item import FurnitureItem


def import_from_json(json_path: str, database_url: str = None):
    """Import furniture data from JSON file to SQL database"""
    
    db = DatabaseManager(database_url)
    session = db.get_session()
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        if isinstance(data, dict) and 'items' in data:
            items = data['items']
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError("Unsupported JSON structure")
        
        imported = 0
        for idx, item in enumerate(items):
            if not item.get('description'):
                continue
                
            furniture = FurnitureItem(
                furniture_name=item.get('furniture_name') or item.get('name') or f"Item_{idx}",
                description=item.get('description', '').strip(),
                category=item.get('category') or item.get('type'),
                image_url=item.get('image_url') or item.get('url_image'),
                product_url=item.get('product_url') or item.get('url_furniture'),
                price=item.get('price') or item.get('cost'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(furniture)
            imported += 1
            
            if imported % 100 == 0:
                session.commit()
                print(f"✅ Imported {imported} items...")
        
        session.commit()
        print(f"🎉 Successfully imported {imported} furniture items")
        
    except FileNotFoundError:
        print(f"❌ JSON file not found: {json_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        sys.exit(1)
    except Exception as e:
        session.rollback()
        print(f"❌ Import error: {e}")
        sys.exit(1)
    finally:
        db.close_session()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Initialize furniture database')
    parser.add_argument('--json', required=True, help='Path to source JSON file')
    parser.add_argument('--db', help='Database URL (overrides env var)')
    
    args = parser.parse_args()
    import_from_json(args.json, args.db)