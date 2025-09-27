# app.py
from flask import Flask, request, jsonify, send_from_directory
import easyocr
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
import time
import re
import os
import json
from datetime import datetime

# Crear aplicación Flask
app = Flask(__name__)

# Configuración
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
PENDIENTES_FILE = 'pendientes.json'

# Inicializar EasyOCR (esto puede tomar unos segundos)
print("🔄 Inicializando EasyOCR...")
try:
    reader = easyocr.Reader(['es', 'en'], gpu=False)  # Cambiar a True si tienes GPU
    print("✅ EasyOCR listo")
except Exception as e:
    print(f"❌ Error inicializando EasyOCR: {e}")
    reader = None

class GuanajuatoPlateProcessor:
    def __init__(self):
        self.stats = {
            'total_processed': 0,
            'successful_detections': 0,
            'auto_plates': 0,
            'camioneta_plates': 0
        }
    
    def preprocess_image(self, cv_image):
        """Preprocesa la imagen para mejor OCR"""
        # Convertir a escala de grises
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Para texto azul sobre fondo blanco, invertir puede ayudar
        inverted = cv2.bitwise_not(gray)
        
        # Suavizado para reducir ruido
        processed = cv2.GaussianBlur(inverted, (3, 3), 0)
        
        return processed
    
    def validate_guanajuato_plate(self, text):
        """Valida y formatea placas de Guanajuato"""
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        
        # Formato AUTOS: 3 letras + 3 números + 1 letra (7 caracteres)
        if len(cleaned) == 7 and re.match(r'^[A-Z]{3}[0-9]{3}[A-Z]$', cleaned):
            return {
                'plate': f"{cleaned[:3]}-{cleaned[3:6]}-{cleaned[6]}",
                'type': 'AUTO',
                'confidence_level': 'ALTA',
                'valid': True,
                'raw_text': cleaned
            }
        
        # Formato CAMIONETAS: 2 letras + 4 números + 1 letra (7 caracteres)
        elif len(cleaned) == 7 and re.match(r'^[A-Z]{2}[0-9]{4}[A-Z]$', cleaned):
            return {
                'plate': f"{cleaned[:2]}-{cleaned[2:6]}-{cleaned[6]}",
                'type': 'CAMIONETA',
                'confidence_level': 'ALTA',
                'valid': True,
                'raw_text': cleaned
            }
        
        # Formatos sin letra final (6 caracteres)
        elif len(cleaned) == 6:
            if re.match(r'^[A-Z]{3}[0-9]{3}$', cleaned):
                return {
                    'plate': f"{cleaned[:3]}-{cleaned[3:]}",
                    'type': 'AUTO',
                    'confidence_level': 'MEDIA',
                    'valid': True,
                    'raw_text': cleaned
                }
            elif re.match(r'^[A-Z]{2}[0-9]{4}$', cleaned):
                return {
                    'plate': f"{cleaned[:2]}-{cleaned[2:]}",
                    'type': 'CAMIONETA',
                    'confidence_level': 'MEDIA',
                    'valid': True,
                    'raw_text': cleaned
                }
        
        return {'valid': False, 'raw_text': cleaned}
    
    def process_image(self, cv_image):
        """Procesa imagen completa con OCR"""
        self.stats['total_processed'] += 1
        start_time = time.time()
        
        try:
            # Preprocesar imagen
            processed_img = self.preprocess_image(cv_image)
            
            # Ejecutar OCR
            ocr_results = reader.readtext(processed_img, paragraph=False)
            
            if not ocr_results:
                return {
                    'success': False,
                    'text': '',
                    'confidence': 0,
                    'processing_time': round(time.time() - start_time, 2),
                    'message': 'No se detectó texto en la imagen'
                }
            
            # Procesar todos los resultados y buscar placas válidas
            candidates = []
            for (bbox, text, confidence) in ocr_results:
                if confidence > 0.3:  # Umbral mínimo
                    validation = self.validate_guanajuato_plate(text)
                    if validation['valid']:
                        candidates.append({
                            'validation': validation,
                            'ocr_confidence': confidence,
                            'bbox': bbox
                        })
            
            if candidates:
                # Ordenar por: 1) Tipo (AUTO primero), 2) Confianza OCR
                candidates.sort(key=lambda x: (x['validation']['type'] != 'AUTO', -x['ocr_confidence']))
                best = candidates[0]
                
                self.stats['successful_detections'] += 1
                if best['validation']['type'] == 'AUTO':
                    self.stats['auto_plates'] += 1
                else:
                    self.stats['camioneta_plates'] += 1
                
                return {
                    'success': True,
                    'text': best['validation']['raw_text'],
                    'plate': best['validation']['plate'],
                    'vehicle_type': best['validation']['type'],
                    'confidence': best['ocr_confidence'],
                    'confidence_level': best['validation']['confidence_level'],
                    'processing_time': round(time.time() - start_time, 2),
                    'all_candidates': len(candidates)
                }
            else:
                # Devolver el mejor texto detectado aunque no sea placa válida
                best_ocr = max(ocr_results, key=lambda x: x[2])
                return {
                    'success': False,
                    'text': best_ocr[1],
                    'confidence': best_ocr[2],
                    'processing_time': round(time.time() - start_time, 2),
                    'message': 'Texto detectado pero no es placa válida de Guanajuato'
                }
                
        except Exception as e:
            return {
                'success': False,
                'text': '',
                'confidence': 0,
                'processing_time': round(time.time() - start_time, 2),
                'error': str(e)
            }

# Instanciar procesador
processor = GuanajuatoPlateProcessor()

# Funciones de utilidad para pendientes
def load_pendientes():
    """Cargar lista de pendientes desde archivo JSON"""
    try:
        if os.path.exists(PENDIENTES_FILE):
            with open(PENDIENTES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'data': []}
    except:
        return {'data': []}

def save_pendientes(pendientes_data):
    """Guardar lista de pendientes a archivo JSON"""
    try:
        with open(PENDIENTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(pendientes_data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

# ===== RUTAS DE LA API =====

@app.route('/')
def serve_index():
    """Servir el archivo index.html"""
    return send_from_directory('.', 'index.html')

@app.route('/api/ocr-local', methods=['POST'])
def ocr_local():
    """Endpoint principal de OCR"""
    if not reader:
        return jsonify({
            'success': False,
            'error': 'EasyOCR no está disponible'
        }), 500
    
    try:
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No se proporcionó imagen'
            }), 400
        
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'Archivo vacío'
            }), 400
        
        # Convertir imagen a OpenCV
        try:
            image_pil = Image.open(BytesIO(file.read()))
            cv_image = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Error procesando imagen: {str(e)}'
            }), 400
        
        # Procesar con OCR
        result = processor.process_image(cv_image)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500

@app.route('/api/pendientes', methods=['GET'])
def get_pendientes():
    """Obtener lista de pendientes"""
    try:
        pendientes = load_pendientes()
        return jsonify(pendientes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pendientes', methods=['POST'])
def add_pendiente():
    """Agregar nueva placa a pendientes"""
    try:
        data = request.get_json()
        
        if not data or 'placa' not in data:
            return jsonify({'msg': 'Placa requerida'}), 400
        
        placa = data['placa'].upper().strip()
        imagen = data.get('imagen', '')
        
        # Cargar pendientes actuales
        pendientes = load_pendientes()
        
        # Verificar duplicados
        for item in pendientes['data']:
            if item.get('placa', '').upper() == placa:
                return jsonify({'msg': f'La placa {placa} ya está en pendientes'}), 400
        
        # Agregar nuevo pendiente
        nuevo_pendiente = {
            'placa': placa,
            'imagen': imagen,
            'timestamp': datetime.now().isoformat(),
            'procesado': False
        }
        
        pendientes['data'].append(nuevo_pendiente)
        
        # Guardar
        if save_pendientes(pendientes):
            return jsonify({'msg': f'Placa {placa} agregada a pendientes'})
        else:
            return jsonify({'msg': 'Error al guardar'}), 500
            
    except Exception as e:
        return jsonify({'msg': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Obtener estadísticas del procesador"""
    success_rate = 0
    if processor.stats['total_processed'] > 0:
        success_rate = round((processor.stats['successful_detections'] / processor.stats['total_processed']) * 100, 1)
    
    return jsonify({
        'total_processed': processor.stats['total_processed'],
        'successful_detections': processor.stats['successful_detections'],
        'auto_plates': processor.stats['auto_plates'],
        'camioneta_plates': processor.stats['camioneta_plates'],
        'success_rate': success_rate
    })

@app.route('/api/reset-stats', methods=['POST'])
def reset_stats():
    """Reiniciar estadísticas"""
    processor.stats = {
        'total_processed': 0,
        'successful_detections': 0,
        'auto_plates': 0,
        'camioneta_plates': 0
    }
    return jsonify({'msg': 'Estadísticas reiniciadas'})

# Manejo de errores
@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'Archivo demasiado grande'}), 413

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Error interno del servidor'}), 500

if __name__ == '__main__':
    print("🚗 Iniciando servidor OCR Casero...")
    print("📂 Archivos esperados:")
    print("   - index.html (interfaz web)")
    print("   - pendientes.json (se creará automáticamente)")
    print("\n🌐 Accede a: http://localhost:5000")
    print("📊 Estadísticas en: http://localhost:5000/api/stats")
    
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context='adhoc')