import logging
from pathlib import Path

LOG_DIR = Path("/app/logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)
TILDA_WEB_HOOK = os.getenv("TILDA_WEB_HOOK", "")
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    if not TILDA_WEB_HOOK:
        logger.error("TILDA_WEB_HOOK is not configured")
        return jsonify({"status": "failed", "message": "TILDA_WEB_HOOK not configured"}), 500  
    data = request.get_json()
    if not data:
        logger.warning("No JSON payload received")
        return jsonify({"status": "failed", "message": "No JSON payload"}), 400

    try:
        url = data.get("img-url")
        if not url:
            logger.warning("Missing 'img-url' in request")
            return jsonify({"status": "failed", "message": "'img-url' missing in request"}), 400
       
        json = get_furniture_description(url)
        recomendations = get_recommendations(match_furniture(json))
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"status": "failed", "message": str(e)}), 500

    try:
        response = requests.post(TILDA_WEB_HOOK, json=recomendations, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error forwarding to target: {e}")
        return jsonify({"status": "failed", "message": str(e)}), 500

    return jsonify({"status": "success", "response": response.text}), 200


if __name__ == '__main__':
    app.run(port=8000)