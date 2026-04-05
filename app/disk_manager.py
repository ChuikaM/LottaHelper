import yadisk
import base64
import io
import os
import logging

y = yadisk.YaDisk(token = os.getenv("YANDEX_DISK_TOKEN"))

def upload_image_to_disk(base64_string : str, task_id):
    image_data = base64.b64decode(base64_string)
    file_object = io.BytesIO(image_data)

    if not y.check_token():
        logging.error("Error: token is not configured!")
        return None
    
    path_on_disk = f"/{task_id}.jpg"
    y.upload(file_object, path_on_disk, overwrite=True)
    direct_link = y.get_download_link(path_on_disk)
    return direct_link