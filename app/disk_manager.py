import yadisk
import io
import os
import logging
from datetime import datetime, timedelta

y = yadisk.YaDisk(token = os.getenv("YANDEX_DISK_TOKEN"))

def upload_image_to_disk(image_bytes : bytes, task_id):
    file_object = io.BytesIO(image_bytes)

    if not y.check_token():
        logging.error("Error: token is not configured!")
        return None
    
    path_on_disk = f"/{task_id}.jpg"
    y.upload(file_object, path_on_disk)
    return y.get_download_link(path_on_disk)

def delete_old_files_by_metadata():
    for item in y.listdir("/"):
        if item.type != "file":
            continue

        time_value = item.created or item.modified
        if not time_value:
            logging.warning(f"No time attribute for {item.path}")
            continue

        try:
            if isinstance(time_value, str):
                dt = datetime.fromisoformat(time_value.replace('Z', '+00:00'))
            elif isinstance(time_value, datetime):
                dt = time_value
            else:
                dt = datetime.fromtimestamp(time_value)
        except Exception as e:
            logging.error(f"Failed to parse time for {item.path}: {e}")
            continue

        if datetime.now() - dt > timedelta(seconds=1):
            y.remove(item.path)
            logging.info(f"Deleted {item.path} (age: {datetime.now() - dt})")