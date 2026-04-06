from PIL import Image, UnidentifiedImageError
import os
import io
import logging
logging.basicConfig(filename='/lottahelper/log/main.log', level=logging.INFO)

from celery.result import AsyncResult

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app._celery_.celery_app import celery_app
from app._celery_.tasks import process_furniture_recommendation

from app.checker.file_manager import FileChecker
from app.checker.recaptcha_manager import RecaptchaChecker

from app.db.manager.postgresql_manager import PostgreSQLManager
from app.db.manager.redis_manager import RedisManager
from app.secrets import generate_csrf_token, generate_uuid_token

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
limiter = Limiter(
    key_func=get_remote_address,
    app=app, 
    default_limits=["200 per day", "50 per hour"]
)

redis_manager = RedisManager()
postgre_manager = PostgreSQLManager(os.getenv('DATABASE_URL'))

@app.route('/captcha', methods=['POST'])
def check_captcha():
    data = request.get_json()
    if not data or 'captcha_token' not in data:
        return jsonify({"error": "Missing captcha_token"}), 400
    
    client_token = data["captcha_token"]
    recaptcha_manager = RecaptchaChecker()
    token_allowed, json_response, status_code = recaptcha_manager.token_allowed(client_token=client_token)
    if not token_allowed:
        return jsonify(
            json_response
        ), status_code
    
    token = generate_uuid_token()
    redis_manager.add_token(token=token)

    return jsonify({
        "status": "ok",
        "msg": "Success",
        "token": token
    }), 200

@app.route('/recommendations', methods=['POST'])
@limiter.limit("10 per minute")
def retrieve_recommendations():
    response_token = request.form.get('token')
    if not response_token:
        return jsonify({
            "status": "failed",
            "msg": "Token missing"
        }), 400
    if not redis_manager.token_exists(token=response_token):
        return jsonify({
            "status": "failed", 
            "msg": "token doesn't exists"
        }), 500
    redis_manager.remove_token(token=response_token)

    response_file = request.files.get('file')
    if not response_file:
        return jsonify({
            "status": "failed",
            "msg": "File missing"
        }), 400
    file_manager = FileChecker()
    file_allowed, json_response, code = file_manager.file_allowed(file=response_file)
    if not file_allowed:
        return jsonify(json_response), code
    
    try:
        task = process_furniture_recommendation.delay(
            file_bytes=file_manager.file,
            file_type=file_manager.file_type
        )
        
        new_token = generate_csrf_token()
        redis_manager.add_token(token=new_token)
        return jsonify({
            "status": "processing",
            "task_id": task.id,
            "token": new_token
        }), 202
    except Exception as e:
        logging.exception(f"Error queuing task: {e}")
        return jsonify({
            "status": "failed",
            "msg": "Failed to process image"
        }), 500


@app.route('/recommendations/<task_id>', methods=['GET'])
def get_recommendation_status(task_id):
    token = request.args.get('token')
    if not token:
        return jsonify({
            "status": "failed",
            'msg': 'Missing token'
        }), 400
    
    if not redis_manager.token_exists(token=token):
        return jsonify({
            "status": "failed",
            "msg": "Wrong token"
        }), 400
    
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
        redis_manager.remove_token(token=token)
        if isinstance(result, dict) and result.get("status") == "success":
            return jsonify(result), 200
        else:
            error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
            return jsonify({"status": "failed", "msg": error_msg}), 500
    elif task.state == 'FAILURE':
        redis_manager.remove_token(token=token)
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
    try:
        db_status = "unknown"
        try:
            postgre_manager.check_health()
            db_status = "connected"
        except Exception as e:
            logging.exception(f"redis" if os.getenv('CELERY_BROKER_URL') else "not-configured")
            logging.exception(f"error: {str(e)[:50]}")
            db_status = f"error: {str(e)[:50]}"
        
        return jsonify({
            "status": "ok",
            "service": "furniture-recommendation-api",
            "database": db_status
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


if __name__ == "__main__":
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 8000)),
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
        threaded=True
    )