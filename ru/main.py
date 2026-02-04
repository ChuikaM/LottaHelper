import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TARGET_URL = "https://external-service.com"

@app.route('/webhook', methods=['POST'])
def handle_and_forward():
    incoming_data = request.json
    
    try:
        response = requests.post(
            TARGET_URL, 
            json=incoming_data, 
            timeout=5
        )
        print(f"Статус отправки: {response.status_code}")
    except Exception as e:
        print(f"Ошибка при пересылке: {e}")

    return jsonify({"status": "received & forwarded"}), 200

if __name__ == '__main__':
    app.run(port=5000)
