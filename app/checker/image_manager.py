import logging

class ImageChecker:
    def __init__(self):
        self.file = None

        self.__ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
        self.__ALLOWED_MIMETYPES = {'image/png', 'image/jpg', 'image/jpeg'}
        self.__MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

    def __allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.__ALLOWED_EXTENSIONS
    def __allowed_mimetype(self, file):
        return file.content_type in self.__ALLOWED_MIMETYPES
    def __allowed_file_size(self, file):
        file.seek(0, 2)
        if file.tell() > self.__MAX_IMAGE_SIZE:
            return False
        file.seek(0)
        return True

    def image_allowed(self, file):
        if not file or file.filename == '':
            logging.warning("No file selected")
            json_response = {
                "status": "failed", 
                "msg": "No file selected"
            }
            code = 400
            return False, json_response, code
        
        if not self.__allowed_file(file.filename):
            logging.warning("Unsupported file type")
            json_response = {
                "status": "failed", 
                "msg": f"Unsupported file type"
            }
            code = 415
            return False, json_response, code
        if not self.__allowed_mimetype(file):
            logging.warning("Invalid MIME type")
            json_response = {
                "status": "failed",
                "msg": "Invalid MIME type"
            }
            code = 415
            return False, json_response, code
        if not self.__allowed_file_size(file):
            logging.warning("File too large")
            json_response = {
                "status": "failed",
                "msg": "File too large"
            }
            code = 413
            return False, json_response, code
        
        self.file = file
        return True, None, None