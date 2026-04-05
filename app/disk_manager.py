import yadisk
import base64
import io
import os
import logging

y = yadisk.YaDisk(token = os.getenv("YANDEX_DISK_TOKEN"))

def upload_image_to_disk(image_bytes : bytes, task_id):
    file_object = io.BytesIO(image_bytes)

    if not y.check_token():
        logging.error("Error: token is not configured!")
        return None
    
    path_on_disk = f"/{task_id}.jpg"
    y.upload(file_object, path_on_disk)
    return y.get_download_link(path_on_disk)