from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
from PIL import Image
import io
from furniture import *

app = Flask(__name__)
CORS(app) 
# CORS(app, resources={
#     r"/upload": {
#         "origins": ["http://localhost:3000", "https://yourdomain.com"]
#     }
# })

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def base64_to_pil(base64_string):
    """Convert base64 string to PIL Image"""
    try:
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
        img_data = base64.b64decode(base64_string)
        return Image.open(io.BytesIO(img_data)).convert("RGB")
    except Exception as e:
        print(f"Image conversion error: {e}")
        return None


@app.route('/recommendations', methods=['POST'])
def retreive_recommendations():
    if "file" not in request.files:
        return jsonify({"status": "failed", "msg": "'file' missing in request"}), 400  
    file = request.files['file']
    if not file:
        return jsonify({"status": "failed", 'msg': 'It is not a file'}), 400
    if file.filename == '': 
        return jsonify({"status": "failed", 'msg': 'No selected file'}), 400
    if not allowed_file(file.filename):
        return jsonify({
            "status": "failed", 
            "msg": f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400
    try:
        img_bytes = file.read()
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        pil_image = base64_to_pil(base64_image)
        queries = get_furniture_description(pil_image)
        finder = FurnitureFinder(
            json_path="../catalog/furnitures_sorted.json",
            use_cache=True
        )
        recomendations = []    
        for query in queries:    
            results = finder.find_similar(query, top_k=1)
            serializable_results = [
                {
                    "similarity": score,
                    "item": item
                }
                for (item, score) in enumerate(results, 1)
            ]
            recomendations.append({
                "results": serializable_results
            })
    except Exception as e:
        return jsonify({"status": "failed", "msg": str(e)}), 500
    return jsonify({"status": "success", "results":"queries"}), 200

@app.route('/upload', methods=['POST'])
def upload_image():
    """Uploads new image & stores it's description here"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)