from flask import Flask, request, send_file, render_template, jsonify
import psycopg2
import qrcode
import io
import uuid
import os
import base64
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from urllib.parse import quote_plus

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key")

# ✅ Database connection
def get_connection():
    return psycopg2.connect(
        host="ep-fragrant-mountain-aen49lww-pooler.c-2.us-east-2.aws.neon.tech",
        dbname="neondb",
        user="neondb_owner",
        password="npg_LneS63qgCDyu",
        sslmode="require"
    )

# Ensure uploads folder exists
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate_qr", methods=["POST"])
def generate_qr():
    qr_type = request.form.get("type")
    password = request.form.get("password")
    color = request.form.get("color", "#000000")
    bg_color = request.form.get("bgColor", "#FFFFFF")

    password_hash = generate_password_hash(password) if password else None
    qr_id = str(uuid.uuid4())

    if qr_type == "text":
        text_data = request.form.get("text")
        if not text_data:
            return jsonify({"error": "No text provided"}), 400
        data = text_data

    elif qr_type == "file":
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "No files uploaded"}), 400
        saved_files = []
        for f in files:
            filename = f"{qr_id}_{f.filename}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            f.save(file_path)
            saved_files.append(file_path)
        base_url = request.host_url.rstrip('/')
        data = f"{base_url}/download/{qr_id}"

    else:
        return jsonify({"error": "Invalid QR type"}), 400

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=color, back_color=bg_color)

    img_io = io.BytesIO()
    img.save(img_io, "PNG")
    img_io.seek(0)

    # Save to database
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS qrcodes (
                id UUID PRIMARY KEY,
                qr_type TEXT,
                data TEXT,
                password_hash TEXT,
                created_at TIMESTAMP
            )
        """)
        cur.execute(
            "INSERT INTO qrcodes (id, qr_type, data, password_hash, created_at) VALUES (%s, %s, %s, %s, %s)",
            (qr_id, qr_type, data, password_hash, datetime.now())
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("DB error:", e)

    qr_b64 = base64.b64encode(img_io.getvalue()).decode("utf-8")
    wa_msg = quote_plus(f"Scan this QR: {data}")
    wa_link = f"https://wa.me/?text={wa_msg}"

    return jsonify({
        "qrImage": qr_b64,
        "downloadUrl": f"/download_qr/{qr_id}",
        "whatsappLink": wa_link
    })

@app.route("/download_qr/<qr_id>")
def download_qr(qr_id):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT data FROM qrcodes WHERE id = %s", (qr_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return "QR not found", 404
        data = row[0]
        qr = qrcode.make(data)
        img_io = io.BytesIO()
        qr.save(img_io, "PNG")
        img_io.seek(0)
        return send_file(img_io, mimetype="image/png", as_attachment=True, download_name="qrcode.png")
    except Exception as e:
        return f"Error: {e}", 500

@app.route("/download/<qr_id>")
def download_file(qr_id):
    for f in os.listdir(UPLOAD_FOLDER):
        if f.startswith(qr_id):
            return send_file(os.path.join(UPLOAD_FOLDER, f), as_attachment=True)
    return "File not found", 404

if __name__ == "__main__":
    app.run(debug=True, port=5050)