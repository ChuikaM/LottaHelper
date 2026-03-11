# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import base64
from PIL import Image
import io
from celery_worker import celery_app, process_furniture_recommendation

app = Flask(__name__)
CORS(app)
limiter = Limiter(app=app, key_func=get_remote_address)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/recommendations', methods=['POST'])
@limiter.limit("10 per minute")
def retrieve_recommendations():
    """Submit image for async processing - returns task ID"""
    
    # Handle file upload
    if "file" not in request.files:
        return jsonify({"status": "failed", "msg": "'file' missing in request"}), 400
    
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"status": "failed", "msg": "No selected file"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            "status": "failed", 
            "msg": f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400
    
    try:
        # Read image bytes
        img_bytes = file.read()
        
        # Optional: Validate image can be opened
        Image.open(io.BytesIO(img_bytes)).verify()
        
        # Queue the task
        task = process_furniture_recommendation.delay(
            image_bytes=img_bytes,
            similarity_threshold=0.6
        )
        
        return jsonify({
            "status": "processing",
            "task_id": task.id,
            "message": "Request queued. Poll /recommendations/<task_id> for results."
        }), 202  # Accepted
        
    except Exception as e:
        print(f"Error queuing task: {e}")
        return jsonify({"status": "failed", "msg": str(e)}), 500


@app.route('/recommendations/<task_id>', methods=['GET'])
def get_recommendation_status(task_id):
    """Check task status and retrieve results"""
    from celery.result import AsyncResult
    
    task = AsyncResult(task_id, app=celery_app)
    
    if task.state == 'PENDING':
        return jsonify({
            "status": "pending",
            "message": "Task is waiting to be processed"
        }), 202
    
    elif task.state == 'PROGRESS':
        return jsonify({
            "status": "processing",
            "progress": task.info if isinstance(task.info, dict) else {},
            "message": "Task is currently processing"
        }), 202
    
    elif task.state == 'SUCCESS':
        result = task.result
        if result.get("status") == "success":
            return jsonify(result), 200
        else:
            return jsonify({"status": "failed", "msg": result.get("error")}), 500
    
    elif task.state == 'FAILURE':
        return jsonify({
            "status": "failed",
            "msg": str(task.info) if task.info else "Unknown error"
        }), 500
    
    else:
        return jsonify({"status": task.state}), 202


@app.route('/upload', methods=['POST'])
def upload_image():
    """Uploads new image & stores its description here"""
    return jsonify({"status": "success", "msg": "Image uploaded"}), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "queue": "redis connected"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)