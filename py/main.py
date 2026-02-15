from flask import Flask, request, jsonify
from flask_cors import CORS
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

@app.route('/', methods=['POST'])
def handle_webhook():
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
        queries = get_furniture_description(file)
        finder = FurnitureFinder(
            json_path="furnitures_sorted.json",
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
    return jsonify({"status": "success", "results":{recomendations}}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)