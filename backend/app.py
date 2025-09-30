from flask import Flask, request, jsonify
import io
from PIL import Image
import numpy as np
import easyocr

app = Flask(__name__)

# Idiomas mínimos; agrega 'es' si quieres probar ambos
reader = easyocr.Reader(['en'], gpu=False)

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "ocr-backend"})

@app.post("/api/ocr")
def api_ocr():
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "No llegó archivo 'image'"}), 400
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "Nombre de archivo vacío"}), 400
    try:
        image_bytes = file.read()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        np_img = np.array(img)

        results = reader.readtext(np_img)
        best_text, best_conf = "", 0.0
        items = []
        for box, text, conf in results:
            items.append({"text": text, "confidence": float(conf)})
            if conf > best_conf:
                best_conf, best_text = float(conf), text

        return jsonify({"ok": True, "best": {"text": best_text, "confidence": best_conf}, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # Para pruebas locales; Render usará el Procfile (gunicorn)
    app.run(host="0.0.0.0", port=10000)
