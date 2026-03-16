import logging

class ImageManager:
    def __init__(self):
        self._json_response = None
        self._code = None
        self._file = None

        self.ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
        self.ALLOWED_MIMETYPES = {'image/png', 'image/jpg', 'image/jpeg'}
        self.MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

    def _allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS
    def _allowed_mimetype(self, file):
        return file.content_type in self.ALLOWED_MIMETYPES
    def _allowed_file_size(self, file):
        file.seek(0, 2)
        if file.tell() > self.MAX_IMAGE_SIZE:
            return False
        file.seek(0)
        return True

    def image_allowed(self, files):
        if "file" not in files:
            logging.warning("'file' field missing in request")
            self._json_response = {
                "status": "failed", 
                "msg": "'file' field missing in request"
            }
            self._code = 400
            return False
        
        file = files['file']
        if not file or file.filename == '':
            logging.warning("No file selected")
            self._json_response = {
                "status": "failed", 
                "msg": "No file selected"
            }
            self._code = 400
            return False
        
        if not self._allowed_file(file.filename):
            logging.warning("Unsupported file type")
            self._json_response = {
                "status": "failed", 
                "msg": f"Unsupported file type"
            }
            self._code = 415
            return False
        if not self._allowed_mimetype(file):
            logging.warning("Invalid MIME type")
            self._json_response = {
                "status": "failed",
                "msg": "Invalid MIME type"
            }
            self._code = 415
            return False
        if not self._allowed_file_size(file):
            logging.warning("File too large")
            self._json_response = {
                "status": "failed",
                "msg": "File too large"
            }
            self._code = 413
            return False
        
        self._file = file
        return True
    
    def response(self):
        return self._json_response
    
    def status_code(self):
        return self._code
    
    def file(self):
        return self._file