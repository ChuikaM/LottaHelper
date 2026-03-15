"""Celery workers"""

from celery import Celery
from PIL import Image
import io
import os
import logging

from furniture import FurnitureFinder

celery_app = Celery(
    'tasks',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)
celery_app.conf.update(
    worker_pool='solo',
    worker_concurrency=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,
    task_soft_time_limit=240
)


@celery_app.task(bind=True, name='process_furniture_recommendation')
def process_furniture_recommendation(
    self, 
    image_bytes: bytes
):
    """Background task to process furniture recommendations"""
    finder = None
    
    try:
        self.update_state(state='PROGRESS', meta={
            'current': 10, 'total': 100, 'status': 'Loading image...'
        })
        
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        self.update_state(state='PROGRESS', meta={
            'current': 30, 'total': 100, 'status': 'Connecting to database...'
        })
        
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL not configured")
        
        self.update_state(state='PROGRESS', meta={
            'current': 50, 'total': 100, 'status': 'Initializing furniture finder...'
        })
        
        finder = FurnitureFinder(
            database_url=db_url,
            image=pil_image,
            use_cache=True
        )
        
        self.update_state(state='PROGRESS', meta={
            'current': 75, 'total': 100, 'status': 'Finding similar items...'
        })

        similarity_threshold_env = os.getenv('SIMILARITY_THRESHOLD')
        try:
            similarity_threshold = float(similarity_threshold_env) if similarity_threshold_env is not None else 0.6
        except ValueError:
            similarity_threshold = 0.6

        results = finder.find_similar(
            similarity_threshold=0.6,
            similarity_threshold=similarity_threshold,
            max_per_category=3
        )
        
        self.update_state(state='PROGRESS', meta={
            'current': 90, 'total': 100, 'status': 'Formatting results...'
        })
        
        products = []
        for item, score in results:
            product = {
                "id": item.get("id"),
                "icon": item.get("image_url") or item.get("url_image") or "",
                "product": item.get("product_url") or item.get("url_furniture") or "",
                "title": item.get("furniture_name") or item.get("name") or item.get("title") or "Unknown",
                "category": item.get("category") or item.get("type") or "uncategorized",
                "match": int(round(score * 100)),
                "cost": item.get("price") or item.get("cost") or 0,
                "description": item.get("description", "")[:200] + "..." if len(item.get("description", "")) > 200 else item.get("description", "")
            }
            products.append(product)
        
        self.update_state(state='PROGRESS', meta={
            'current': 100, 'total': 100, 'status': 'Complete!'
        })
        
        return {
            "status": "success", 
            "products": products,
            "count": len(products)
        }
        
    except Exception as e:
        logging.exception("Error while processing furniture recommendation task")
        return {"status": "failed", "error": str(e)}
    
    finally:
        if finder:
            finder.close()