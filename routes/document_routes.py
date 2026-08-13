import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from utils.file_utils import allowed_file, ensure_dir

doc_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

@doc_bp.route("/upload", methods=["POST"])
def upload():
    if "files" not in request.files: return jsonify({"error":"No files"}), 400
    files=request.files.getlist("files")
    config=current_app.config_obj; svc=current_app.doc_service
    ensure_dir(config.UPLOAD_FOLDER)
    results,pairs=[],[]
    for f in files:
        if not f or not f.filename: continue
        fn=secure_filename(f.filename)
        if not allowed_file(fn,config.ALLOWED_EXTENSIONS):
            results.append({"filename":fn,"status":"error","error":"File type not allowed"}); continue
        fp=os.path.join(config.UPLOAD_FOLDER,fn)
        try: f.save(fp); pairs.append((fp,fn)); results.append({"filename":fn,"status":"processing"})
        except Exception as e: results.append({"filename":fn,"status":"error","error":str(e)})
    if pairs: svc.index_files_async(pairs)
    return jsonify({"results":results})

@doc_bp.route("/status", methods=["GET"])
def status(): return jsonify(current_app.doc_service.get_all_status())

@doc_bp.route("/status/<filename>", methods=["GET"])
def file_status(filename): return jsonify(current_app.doc_service.get_status(filename))

@doc_bp.route("/list", methods=["GET"])
def list_docs():
    svc=current_app.doc_service; stats=current_app.vector_store.get_stats()
    return jsonify({"files":svc.list_indexed_files(),"total_chunks":stats["total_chunks"]})

@doc_bp.route("/delete/<filename>", methods=["DELETE"])
def delete(filename):
    config=current_app.config_obj; svc=current_app.doc_service
    fp=os.path.join(config.UPLOAD_FOLDER,secure_filename(filename))
    svc.delete_file(filename,fp); return jsonify({"success":True})

@doc_bp.route("/reindex/<filename>", methods=["POST"])
def reindex(filename):
    config=current_app.config_obj; svc=current_app.doc_service
    fp=os.path.join(config.UPLOAD_FOLDER,secure_filename(filename))
    if not os.path.exists(fp): return jsonify({"error":"File not found"}), 404
    svc.reindex_file(fp,filename); return jsonify({"success":True,"status":"reindexing"})
