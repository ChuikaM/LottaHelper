from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import base64
import io
import os

from PIL import Image
from celery_worker import celery_app, process_furniture_recommendation
from database import DatabaseManager, FurnitureItem

app = Flask(__name__)
CORS(app)

# Rate limiting
limiter = Limiter(
    app=app, 
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/recommendations', methods=['POST'])
@limiter.limit("10 per minute")
def retrieve_recommendations():
    """Submit image for async furniture recommendation processing"""
    
    # Validate file upload
    if "file" not in request.files:
        return jsonify({"status": "failed", "msg": "'file' field missing in request"}), 400
    
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"status": "failed", "msg": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            "status": "failed", 
            "msg": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 415
    
    # Get optional parameters
    try:
        similarity_threshold = float(request.form.get('similarity_threshold', 0.6))
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
    except ValueError as e:
        return jsonify({"status": "failed", "msg": f"Invalid parameter: {e}"}), 400
    
    try:
        # Read and validate image
        img_bytes = file.read()
        Image.open(io.BytesIO(img_bytes)).verify()
        
        # Ensure database URL is configured in environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({
                "status": "failed", 
                "msg": "DATABASE_URL not configured in environment"
            }), 500
        
        # Queue async task
        task = process_furniture_recommendation.delay(
            image_bytes=img_bytes,
            similarity_threshold=similarity_threshold
        )
        
        return jsonify({
            "status": "processing",
            "task_id": task.id,
            "message": "Request queued. Poll /recommendations/<task_id> for results.",
            "estimated_time_seconds": 30
        }), 202
        
    except Exception as e:
        app.logger.error(f"Error queuing task: {e}")
        return jsonify({"status": "failed", "msg": str(e)}), 500


@app.route('/recommendations/<task_id>', methods=['GET'])
def get_recommendation_status(task_id):
    """Check task status and retrieve results"""
    from celery.result import AsyncResult
    
    task = AsyncResult(task_id, app=celery_app)
    
    response_map = {
        'PENDING': (202, "Task is waiting to be processed"),
        'RECEIVED': (202, "Task received, waiting to start"),
        'STARTED': (202, "Task has started processing"),
    }
    
    if task.state in response_map:
        status_code, message = response_map[task.state]
        return jsonify({
            "status": task.state.lower(),
            "task_id": task_id,
            "message": message
        }), status_code
    
    elif task.state == 'PROGRESS':
        progress = task.info if isinstance(task.info, dict) else {}
        return jsonify({
            "status": "processing",
            "task_id": task_id,
            "progress": progress,
            "message": progress.get('status', 'Processing...')
        }), 202
    
    elif task.state == 'SUCCESS':
        result = task.result
        if isinstance(result, dict) and result.get("status") == "success":
            return jsonify(result), 200
        else:
            error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
            return jsonify({"status": "failed", "msg": error_msg}), 500
    
    elif task.state == 'FAILURE':
        error_info = str(task.info) if task.info else "Unknown error"
        return jsonify({
            "status": "failed",
            "msg": f"Task failed: {error_info}"
        }), 500
    
    elif task.state == 'RETRY':
        return jsonify({
            "status": "retrying",
            "task_id": task_id,
            "message": "Task failed, retrying..."
        }), 202
    
    else:
        return jsonify({"status": task.state, "task_id": task_id}), 202


@app.route('/recommendations/search', methods=['POST'])
@limiter.limit("20 per minute")
def text_search_recommendations():
    """Direct text-based furniture search using embeddings"""
    try:
        data = request.get_json() or {}
        query = data.get('query', '').strip()
        top_k = min(int(data.get('top_k', 10)), 50)
        similarity_threshold = float(data.get('similarity_threshold', 0.3))
        
        if not query:
            return jsonify({"status": "failed", "msg": "'query' is required"}), 400
        
        database_url = data.get('database_url') or os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({"status": "failed", "msg": "DATABASE_URL not configured"}), 500
        
        # Initialize finder for text search
        from furniture import FurnitureFinder
        finder = FurnitureFinder(
            database_url=database_url,
            image=None,  # No image for text search
            use_cache=True
        )
        
        results = finder.search_by_text(query, top_k=top_k)
        finder.close()
        
        # Filter by threshold and format
        products = []
        for item, score in results:
            if score >= similarity_threshold:
                products.append({
                    "id": item.get("id"),
                    "title": item.get("furniture_name") or "Unknown",
                    "category": item.get("category") or "uncategorized",
                    "match": int(round(score * 100)),
                    "cost": item.get("price") or 0,
                    "image_url": item.get("image_url") or "",
                    "product_url": item.get("product_url") or "",
                })
        
        return jsonify({
            "status": "success",
            "query": query,
            "results": products,
            "count": len(products)
        }), 200
        
    except Exception as e:
        app.logger.error(f"Search error: {e}")
        return jsonify({"status": "failed", "msg": str(e)}), 500


@app.route('/catalog/items', methods=['GET'])
@limiter.limit("100 per hour")
def list_catalog_items():
    """List furniture items from database with pagination"""
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 20))))
        category = request.args.get('category')
        search = request.args.get('search')
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({"status": "failed", "msg": "DATABASE_URL not configured"}), 500
        
        db = DatabaseManager(database_url)
        session = db.get_session()
        
        try:
            query = session.query(FurnitureItem)
            
            if category:
                query = query.filter(FurnitureItem.category.ilike(f'%{category}%'))
            if search:
                query = query.filter(FurnitureItem.description.ilike(f'%{search}%') | 
                                   FurnitureItem.furniture_name.ilike(f'%{search}%'))
            
            total = query.count()
            items = query.offset((page - 1) * per_page).limit(per_page).all()
            
            return jsonify({
                "status": "success",
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                },
                "items": [item.to_dict() for item in items]
            }), 200
        finally:
            db.close_session()
            
    except Exception as e:
        app.logger.error(f"Catalog error: {e}")
        return jsonify({"status": "failed", "msg": str(e)}), 500


@app.route('/catalog/items/<int:item_id>', methods=['GET'])
def get_catalog_item(item_id):
    """Get single furniture item by ID"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return jsonify({"status": "failed", "msg": "DATABASE_URL not configured"}), 500
        
        db = DatabaseManager(database_url)
        item = db.get_item_by_id(item_id)
        db.close_session()
        
        if not item:
            return jsonify({"status": "failed", "msg": "Item not found"}), 404
        
        return jsonify({
            "status": "success",
            "item": item.to_dict()
        }), 200
        
    except Exception as e:
        app.logger.error(f"Get item error: {e}")
        return jsonify({"status": "failed", "msg": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint with database connectivity test"""
    try:
        database_url = os.getenv('DATABASE_URL')
        db_status = "unknown"
        
        if database_url:
            try:
                db = DatabaseManager(database_url)
                session = db.get_session()
                session.execute("SELECT 1")  # Test connection
                db.close_session()
                db_status = "connected"
            except Exception as e:
                db_status = f"error: {str(e)[:50]}"
        
        return jsonify({
            "status": "ok",
            "service": "furniture-recommendation-api",
            "database": db_status,
            "queue": "redis" if os.getenv('CELERY_BROKER_URL') else "not-configured"
        }), 200
        
    except Exception as e:
        return jsonify({"status": "degraded", "error": str(e)}), 503


@app.route('/upload', methods=['POST'])
@limiter.limit("50 per hour")
def upload_image():
    """Upload image for catalog (placeholder - implement actual storage logic)"""
    if "file" not in request.files:
        return jsonify({"status": "failed", "msg": "'file' missing"}), 400
    
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"status": "failed", "msg": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"status": "failed", "msg": "Unsupported file type"}), 400
    
    # TODO: Implement actual image storage and database insertion
    # This is a placeholder response
    return jsonify({
        "status": "success", 
        "msg": "Image uploaded (storage not implemented)",
        "filename": file.filename
    }), 200


# Error handlers
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "status": "failed",
        "msg": "Rate limit exceeded. Please try again later."
    }), 429


@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        "status": "failed",
        "msg": "Internal server error"
    }), 500


if __name__ == '__main__':
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'), 
        port=int(os.getenv('FLASK_PORT', 8000)), 
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
        threaded=True
    )