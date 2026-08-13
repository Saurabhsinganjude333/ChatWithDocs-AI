import os, hashlib
from pathlib import Path
from werkzeug.utils import secure_filename

def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".",1)[1].lower() in allowed_extensions

def get_secure_filename(filename): return secure_filename(filename)

def get_file_hash(filepath):
    h = hashlib.md5()
    with open(filepath,"rb") as f:
        for chunk in iter(lambda: f.read(8192), b""): h.update(chunk)
    return h.hexdigest()

def get_file_size_mb(filepath): return os.path.getsize(filepath)/(1024*1024)

def ensure_dir(path): Path(path).mkdir(parents=True, exist_ok=True)
