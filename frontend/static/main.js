const API_BASE = "/api"; // Vercel reescribe a Render vía vercel.json

const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const preview = document.getElementById("preview");
const out = document.getElementById("out");

const btnShot = document.getElementById("btnShot");
const btnSend = document.getElementById("btnSend");
const btnReset = document.getElementById("btnReset");
const fileInput = document.getElementById("fileInput");

let lastBlob = null;

(async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" } }, audio: false
    });
    video.srcObject = stream;
  } catch (e) {
    log(`⚠️ No se pudo abrir la cámara: ${e.message}`);
  }
})();

btnShot.addEventListener("click", () => {
  if (!video.videoWidth) return log("⚠️ Video no listo aún.");
  const w = video.videoWidth, h = video.videoHeight;
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, w, h);
  canvas.toBlob(blob => {
    lastBlob = blob;
    showPreview(blob);
    log("✅ Captura lista. Presiona 'Enviar a OCR'.");
  }, "image/jpeg", 0.9);
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  if (file) {
    lastBlob = file;
    showPreview(file);
    log("✅ Imagen cargada. Presiona 'Enviar a OCR'.");
  }
});

btnSend.addEventListener("click", async () => {
  if (!lastBlob) return log("⚠️ No hay imagen. Captura o sube una primero.");
  try {
    const fd = new FormData();
    fd.append("image", lastBlob, "capture.jpg");
    const res = await fetch(`${API_BASE}/ocr`, { method: "POST", body: fd });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "OCR falló");
    const best = data.best || {};
    log(`🧠 Mejor: "${best.text || ""}" (conf: ${Number(best.confidence || 0).toFixed(3)})\n` +
        `📋 Todas: ${JSON.stringify(data.items || [], null, 2)}`);
  } catch (e) {
    log(`❌ Error: ${e.message}`);
  }
});

btnReset.addEventListener("click", () => {
  lastBlob = null;
  const preview = document.getElementById("preview");
  preview.src = "";
  preview.style.display = "none";
  log("↩️ Limpio.");
});

function showPreview(blob) {
  const url = URL.createObjectURL(blob);
  const preview = document.getElementById("preview");
  preview.src = url;
  preview.style.display = "block";
}
function log(msg) { out.textContent = msg; }
