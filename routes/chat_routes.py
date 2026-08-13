import json
from flask import Blueprint, request, jsonify, session, Response, stream_with_context, current_app

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

@chat_bp.route("/message", methods=["POST"])
def send_message():
    data     = request.get_json(silent=True) or {}
    question = (data.get("message") or "").strip()
    if not question: return jsonify({"error":"Empty message"}), 400
    if len(question)>4000: return jsonify({"error":"Too long"}), 400
    rag     = current_app.rag_pipeline
    history = session.get("chat_history", [])
    def gen():
        sources,full=[],[]
        try:
            for tok in rag.generate_stream(question, history):
                if tok.startswith("__SOURCES__:") and "__END_SOURCES__" in tok:
                    sources=[s.strip() for s in tok.replace("__SOURCES__:","").replace("__END_SOURCES__","").split(",") if s.strip()]
                    yield f"data: {json.dumps({'type':'sources','sources':sources})}\n\n"
                else:
                    full.append(tok)
                    yield f"data: {json.dumps({'type':'token','content':tok})}\n\n"
            txt="".join(full)
            history.append({"role":"user","content":question})
            history.append({"role":"assistant","content":txt})
            session["chat_history"]=history[-20:]
            session.modified=True
            yield f"data: {json.dumps({'type':'done','sources':sources})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
    return Response(stream_with_context(gen()), mimetype="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})

@chat_bp.route("/history", methods=["GET"])
def get_history(): return jsonify({"history":session.get("chat_history",[])})

@chat_bp.route("/clear", methods=["POST"])
def clear_history():
    session["chat_history"]=[]; session.modified=True; return jsonify({"success":True})
