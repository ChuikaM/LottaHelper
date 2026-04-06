import yadisk
import io
import os
import logging
from datetime import datetime, timedelta, timezone

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
    now_utc = datetime.now(timezone.utc)
    try:
        for item in y.listdir("/"):
            if item.type != "file":
                continue

            dt = item.created or item.modified
            if not dt:
                continue

            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            if now_utc - dt > timedelta(hours=24):
                y.remove(item.path)
                logging.info(f"Deleted {item.path}")
    except Exception as e:
        logging.error(f"Error in cleanup: {e}")