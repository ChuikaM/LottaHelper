# celery_worker.py
from celery import Celery
from PIL import Image
import io
from furniture_local import FurnitureFinder

# Configure Celery
celery_app = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes timeout
    task_soft_time_limit=240
)

@celery_app.task(bind=True, name='process_furniture_recommendation')
def process_furniture_recommendation(self, image_bytes, similarity_threshold=0.6):
    """Background task to process furniture recommendations"""
    try:
        # Update task state to PROGRESS
        self.update_state(state='PROGRESS', meta={'current': 10, 'total': 100, 'status': 'Loading image...'})
        
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        self.update_state(state='PROGRESS', meta={'current': 40, 'total': 100, 'status': 'Initializing finder...'})
        
        finder = FurnitureFinder(
            json_path="../catalog/furnitures_sorted.json",
            image=pil_image
        )
        
        self.update_state(state='PROGRESS', meta={'current': 70, 'total': 100, 'status': 'Finding similar items...'})
        
        results = finder.find_similar(similarity_threshold)
        
        self.update_state(state='PROGRESS', meta={'current': 90, 'total': 100, 'status': 'Formatting results...'})
        
        products = []
        for item, score in results:
            match_percentage = int(round(score * 100))
            product = {
                "icon": item.get("image_url", item.get("url_image", "")),
                "product": item.get("product_url", item.get("url_furniture", "")),
                "title": item.get("name", item.get("title", item.get("furniture_name", "Unknown"))),
                "match": match_percentage,
                "cost": item.get("price", item.get("cost", 0))
            }
            products.append(product)
        
        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100, 'status': 'Complete!'})
        
        return {"status": "success", "products": products}
        
    except Exception as e:
        return {"status": "failed", "error": str(e)}