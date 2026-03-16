from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from PIL import Image, UnidentifiedImageError
import os
import io
import logging

from app.celery.tasks import celery_app, process_furniture_recommendation
from app.database import DatabaseManager
from app.image_manager import ImageManager

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app, 
    default_limits=["200 per day", "50 per hour"]
)

app.run(
    host=os.getenv('FLASK_HOST', '0.0.0.0'), 
    port=int(os.getenv('FLASK_PORT', 8000)), 
    debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
    threaded=True
)

@app.route('/recommendations', methods=['POST'])
@limiter.limit("10 per minute")
def retrieve_recommendations():
    """Submit image for async furniture recommendation processing"""
    
    imageManager = ImageManager()
    if not imageManager.image_allowed(request.files):
        return jsonify({"status":"{checker.response()}"})
    
    try:
        img_bytes = imageManager.allowed_file().read()
        try:
            with Image.open(io.BytesIO(img_bytes)) as img:
                img.verify()
            with Image.open(io.BytesIO(img_bytes)) as img:
                img.load()
        except (UnidentifiedImageError, OSError, ValueError) as e:
            logging.warning(f"Invalid image data provided: {e}")
            return jsonify({
                "status": "failed",
                "msg": "Invalid or corrupted image file"
            }), 400
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logging.warning("DATABASE_URL not configured in environment")
            return jsonify({
                "status": "failed", 
                "msg": "DATABASE_URL not configured in environment"
            }), 500
        
        task = process_furniture_recommendation.delay(
            image_bytes=img_bytes
        )
        
        return jsonify({
            "status": "processing",
            "task_id": task.id,
            "message": "Request queued. Poll /recommendations/<task_id> for results.",
            "estimated_time_seconds": 30
        }), 202
    except Exception as e:
        logging.exception(f"Error queuing task: {e}")
        return jsonify({"status": "failed", "msg": "Failed to process image"}), 500


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
        return jsonify({
            "status": task.state, 
            "task_id": task_id
        }), 202


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
        logging.exception(f"Can't check service's health. msg: {e}")
        return jsonify({
            "status": "degraded",
            "error": "Can't check service's health"
        }), 503


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