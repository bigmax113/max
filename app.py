from flask import Flask, request, render_template, jsonify, send_file
import tempfile, os
from translation_docx import process_docx_file
from tmx_memory import load_tmx_folder

app = Flask(__name__)

API_URL  = "https://api.x.ai/v1/chat/completions"
API_KEY  = "xai-ВАШ_КЛЮЧ"   # ← вставь свой ключ
MODEL    = "grok-4-0709"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/load_tmx", methods=["POST"])
def load_tmx():
    """Загрузка TMX или ZIP с TMX"""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "Нет файла"}), 400
    tmp_dir = tempfile.mkdtemp()
    p = os.path.join(tmp_dir, f.filename)
    f.save(p)
    load_tmx_folder(tmp_dir)
    return jsonify({"message": "✅ TMX-память загружена и активна"})

@app.route("/translate_docx", methods=["POST"])
def translate_docx():
    """Перевод DOCX-файла"""
    f = request.files.get("file")
    src_lang = request.form.get("source_lang")
    trg_lang = request.form.get("target_lang")
    if not f or not src_lang or not trg_lang:
        return jsonify({"error": "Не указаны файл или языки"}), 400

    tmp_dir = tempfile.mkdtemp()
    p = os.path.join(tmp_dir, f.filename)
    f.save(p)
    out_path = process_docx_file(p, API_URL, API_KEY, MODEL, src_lang, trg_lang)
    return send_file(out_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
