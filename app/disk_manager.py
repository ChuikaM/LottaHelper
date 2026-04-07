import yadisk
import io
import os
import logging
from datetime import datetime, timedelta, timezone

y = yadisk.YaDisk(token = os.getenv("YANDEX_DISK_TOKEN"))

def upload_file_to_disk(file_bytes : bytes, file_type, task_id):
    if not y.check_token():
        logging.error("Error: token is not configured!")
        return None
    
    if file_type == 'image':
        ext = '.jpg'
    else:
        ext = '.pdf'
    
    path_on_disk = f"/{task_id}{ext}"
    file_object = io.BytesIO(file_bytes)
    try:
        y.upload(file_object, path_on_disk)
        download_link = y.get_download_link(path_on_disk)
        return download_link
    except Exception as e:
        logging.exception(f"Failed to upload to Yandex Disk: {e}")
        return None

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

            if now_utc - dt > timedelta(days=183):
                y.remove(item.path)
                logging.info(f"Deleted {item.path}")
    except Exception as e:
        logging.error(f"Error in cleanup: {e}")