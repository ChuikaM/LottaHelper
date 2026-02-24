from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
from PIL import Image
import io
from furniture import get_furniture_description, FurnitureFinder

app = Flask(__name__)
CORS(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    if not file or file.filename == '':
        return jsonify({"status": "failed", "msg": "No selected file"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            "status": "failed", 
            "msg": f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400
    
    try:
        # Read and convert image
        img_bytes = file.read()
        pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        
        # Get furniture description from LLaVA
        description = get_furniture_description(pil_image)
        
        # Find similar furniture items
        finder = FurnitureFinder(
            json_path="../catalog/furnitures_sorted.json",
            use_cache=True
        )
        
        # Get top 3 recommendations
        results = finder.find_similar(description, top_k=3)
        
        # Format results to match expected JSON structure
        products = []
        for item, score in results:
            # Convert similarity score (0-1) to percentage (0-100)
            match_percentage = int(round(score * 100))
            
            # Map furniture item fields to expected output format
            product = {
                "icon": item.get("image_url", item.get("url_image", "")),
                "title": item.get("name", item.get("title", item.get("furniture_name", "Unknown"))),
                "match": match_percentage,
                "cost": item.get("price", item.get("cost", 0))
            }
            products.append(product)
        
        # Return in expected format
        return jsonify({"products": products}), 200
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "failed", "msg": str(e)}), 500


@app.route('/localrecommendations', methods=['POST'])
def retreive_localrecommendations():
    if "file" not in request.form:
        return jsonify({"status": "failed", "msg": "'file' missing in request"}), 400
    
    file = request.form['file']
    if not file:
        return jsonify({"status": "failed", "msg": "No selected file"}), 400
    
    try:
        with open(file, 'rb') as image_file:
            img_bytes = image_file.read()
        pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        
        # Get furniture description from LLaVA
        description = get_furniture_description(pil_image)
        
        # Find similar furniture items
        finder = FurnitureFinder(
            json_path="../catalog/furnitures_sorted.json",
            use_cache=True
        )
        
        # Get top 3 recommendations
        results = finder.find_similar(description, top_k=3)
        
        # Format results to match expected JSON structure
        products = []
        for item, score in results:
            # Convert similarity score (0-1) to percentage (0-100)
            match_percentage = int(round(score * 100))
            
            # Map furniture item fields to expected output format
            product = {
                "icon": item.get("image_url", item.get("url_image", "")),
                "title": item.get("name", item.get("title", item.get("furniture_name", "Unknown"))),
                "match": match_percentage,
                "cost": item.get("price", item.get("cost", 0))
            }
            products.append(product)
        
        # Return in expected format
        return jsonify({"products": products}), 200
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "failed", "msg": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_image():
    """Uploads new image & stores it's description here"""
    return jsonify({"status": "success", "msg": "Image uploaded"}), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)