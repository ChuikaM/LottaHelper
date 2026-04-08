"""Celery workers"""

from PIL import Image
import io
import os
import logging
import math

from app.furniture import FurnitureFinder
from app.disk_manager import upload_file_to_disk, delete_old_files_by_metadata
from .celery_app import celery_app
import fitz 

@celery_app.task(bind=True, name='process_furniture_recommendation')
def process_furniture_recommendation(
    self, 
    file_bytes: bytes,
    file_type
):
    finder = None

    try:
        self.update_state(state='PROGRESS', meta={
            'current': 10, 'total': 100, 'status': 'Loading image...'
        })
        if file_type == "image":
            pil_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        else:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            try:
                page = doc.load_page(0)
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_data)).convert("RGB")
            finally:
                doc.close()
        
        self.update_state(state='PROGRESS', meta={
            'current': 30, 'total': 100, 'status': 'Connecting to database...'
        })
        
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logging.error("DATABASE_URL not configured")
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
            if similarity_threshold < 0.0:
                similarity_threshold = 0.0
            elif similarity_threshold > 1.0:
                similarity_threshold = 1.0
            if not math.isfinite(similarity_threshold):
                similarity_threshold = 0.6
        except ValueError:
            similarity_threshold = 0.6
        
        results = finder.find_similar(
            similarity_threshold=similarity_threshold,
            max_per_category=3
        )
        
        self.update_state(state='PROGRESS', meta={
            'current': 90, 'total': 100, 'status': 'Formatting results...'
        })
        
        products = []
        for item, score in results:
            product = {
                "icon": item.get("image_url") or item.get("url_image") or "",
                "product": item.get("product_url") or item.get("url_furniture") or "",
                "title": item.get("furniture_name") or item.get("name") or item.get("title") or "Unknown",
                "category": item.get("category") or item.get("type") or "uncategorized",
                "match": int(round(score * 100)),
                "cost": item.get("price") or item.get("cost") or 0,
                "description": item.get("description", "")[:200] + "..." if len(item.get("description", "")) > 200 else item.get("description", "")
            }
            products.append(product)
        
        task_id = self.request.id

        delete_old_files_by_metadata()
        url_to_interior = upload_file_to_disk(file_bytes, file_type, task_id)

        self.update_state(state='PROGRESS', meta={
            'current': 100, 'total': 100, 'status': 'Complete!'
        })
        
        return {
            "status": "success", 
            "products": products,
            "imageUrl": url_to_interior
        }
        
    except Exception as e:
        logging.error(f"Task {self.request.id} failed: {e}")
        logging.exception("Error while processing furniture recommendation task")
        return {"status": "failed", "error": str(e)}
    
    finally:
        if finder:
            finder.close()