import logging
from PIL import Image, UnidentifiedImageError
import io

class FileChecker:
    def __init__(self):
        self.file = None
        self.file_type = None

        self.__ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
        self.__ALLOWED_MIMETYPES = {'image/png', 'image/jpg', 'image/jpeg', 'application/pdf'}
        self.__MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
        self.__MAX_PDF_SIZE = 10 * 1024 * 1024  # 10MB

    def __allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.__ALLOWED_EXTENSIONS
    def __allowed_mimetype(self, file):
        return file.content_type in self.__ALLOWED_MIMETYPES
    def __allowed_file_size(self, file, file_type):
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if file_type == 'image':
            return size <= self.__MAX_IMAGE_SIZE
        else:
            return size <= self.__MAX_PDF_SIZE
        
    def __is_valid_pdf(self, file_bytes: bytes) -> bool:
        """Check PDF signature (starts with %PDF)."""
        return file_bytes.startswith(b'%PDF')

    def file_allowed(self, file):
        """Validate file presence, extension, MIME type, size, and content."""
        if not file or file.filename == '':
            logging.warning("No file selected")
            return False, {"status": "failed", "msg": "No file selected"}, 400

        if not self.__allowed_file(file.filename):
            logging.warning("Unsupported file type")
            return False, {"status": "failed", "msg": f"Unsupported file type"}, 415

        if not self.__allowed_mimetype(file):
            logging.warning("Invalid MIME type")
            return False, {"status": "failed", "msg": "Invalid MIME type"}, 415
        
        ext = file.filename.rsplit('.', 1)[1].lower()
        if ext in {'png', 'jpg', 'jpeg'}:
            file_type = 'image'
        elif ext == 'pdf':
            file_type = 'pdf'
        else:
            return False, {"status": "failed", "msg": "Unsupported file type"}, 415

        if not self.__allowed_file_size(file, file_type):
            logging.warning(f"File too large for type {file_type}")
            msg = "File too large" if file_type == 'image' else "PDF too large (max 20MB)"
            return False, {"status": "failed", "msg": msg}, 413

        file_bytes = file.read()
        if file_type == 'image':
            try:
                with Image.open(io.BytesIO(file_bytes)) as img:
                    img.verify()
                with Image.open(io.BytesIO(file_bytes)) as img:
                    img.load()
            except (UnidentifiedImageError, OSError, ValueError) as e:
                logging.warning(f"Invalid image data: {e}")
                return False, {"status": "failed", "msg": "Invalid or corrupted image file"}, 400
        else:  # pdf
            if not self.__is_valid_pdf(file_bytes):
                logging.warning("Invalid PDF signature")
                return False, {"status": "failed", "msg": "Invalid or corrupted PDF file"}, 400

        self.file = file_bytes
        self.file_type = file_type
        return True, None, None