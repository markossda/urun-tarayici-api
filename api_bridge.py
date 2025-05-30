from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import json
import time
import logging
from dotenv import load_dotenv

# .env dosyasını yükle (varsa)
load_dotenv()

# product.py sınıfını import et
try:
    from product import WalmartProScanner
    PRODUCT_MODULE_LOADED = True
except ImportError:
    print("Uyarı: product.py modülü yüklenemedi. Test modunda çalışılıyor.")
    PRODUCT_MODULE_LOADED = False

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('api_bridge')

# Çevre değişkenlerinden kimlik bilgilerini al
# Render.com'da bu değerleri Environment Variables olarak ekleyebilirsiniz
CLIENT_ID = os.environ.get('WALMART_CLIENT_ID', "f0426720-c18d-4280-a07d-5e65562078de")
CLIENT_SECRET = os.environ.get('WALMART_CLIENT_SECRET', "AJLzeHoqmXLhcjuNKOuUrXdQdmpWjSF5tqP8-Yju4cAJZELxm7dAeQA6gDwthmNzT-4CSuFkQDbVjUZBpzOknRg")
API_KEY = os.environ.get('API_KEY', "test-api-key")  # API anahtarı
PORT = int(os.environ.get('PORT', 5000))

# Flask uygulamasını oluştur
app = Flask(__name__)
CORS(app)  # CORS desteği ekle

# Hangi ortamda çalıştığımızı belirle
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')
IS_PRODUCTION = ENVIRONMENT == 'production'

# API anahtarı doğrulama middleware'i
@app.before_request
def validate_api_key():
    # Eğer test rotası veya root path ise doğrulama yapma
    if request.path == '/test' or request.path == '/' or request.path == '/health':
        return
    
    # Geliştirme ortamında API anahtarı kontrolünü atla (opsiyonel)
    if not IS_PRODUCTION and ENVIRONMENT == 'development':
        return
        
    api_key = request.headers.get('X-API-Key')
    
    if not api_key or api_key != API_KEY:
        logger.warning(f"Geçersiz API anahtarı ile erişim denemesi: {request.remote_addr}")
        return jsonify({'error': 'Geçersiz API anahtarı'}), 401

# WalmartProScanner örneğini oluştur
scanner = None
if PRODUCT_MODULE_LOADED:
    try:
        scanner = WalmartProScanner(CLIENT_ID, CLIENT_SECRET)
        logger.info("WalmartProScanner başarıyla başlatıldı.")
    except Exception as e:
        logger.error(f"WalmartProScanner başlatılamadı: {e}")

# Ana sayfa
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'status': 'success',
        'message': 'Ürün Tarayıcı API',
        'version': '1.0.0',
        'environment': ENVIRONMENT
    })

# Sağlık kontrolü
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'up',
        'timestamp': int(time.time()),
        'environment': ENVIRONMENT
    })

# Test rotası
@app.route('/test', methods=['GET'])
def test():
    return jsonify({
        'status': 'success',
        'message': 'API bridge çalışıyor',
        'environment': ENVIRONMENT,
        'product_module_loaded': PRODUCT_MODULE_LOADED
    })

# Walmart ürün tarama
@app.route('/scan/walmart', methods=['POST'])
def scan_walmart():
    data = request.json
    
    if not data:
        return jsonify({'error': 'Geçersiz istek verisi'}), 400
        
    # URL, UPC veya her ikisini de al
    url = data.get('url')
    upc = data.get('upc')
    
    if not url and not upc:
        return jsonify({'error': 'URL veya UPC gerekli'}), 400
    
    # Eğer scanner yoksa test verileri döndür
    if not scanner:
        return generate_test_product_data(url, upc)
    
    try:
        # UPC verilmişse
        if upc:
            result = scanner.scan_upc_pro_enhanced(upc)
        # Yalnızca URL verilmişse
        else:
            result = scanner.scan_by_url(url)
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Walmart tarama hatası: {e}")
        return jsonify({'error': str(e)}), 500

# Amazon ürün tarama (Temel Seviye)
@app.route('/scan/amazon', methods=['POST'])
def scan_amazon():
    data = request.json
    
    if not data or not data.get('url'):
        return jsonify({'error': 'Geçersiz istek verisi'}), 400
        
    url = data.get('url')
    
    # Şimdilik örnek veri döndür
    return jsonify({
        'status': 'warning',
        'message': 'Amazon API desteği henüz eklenmedi',
        'url': url,
        'product_id': 'ASIN-SAMPLE',
        'title': 'Amazon Ürün Örneği',
        'current_price': 99.99,
        'original_price': 129.99,
        'image_url': 'https://via.placeholder.com/150',
        'brand': 'Örnek Marka',
        'rating': 4.5,
        'review_count': 123,
        'availability': True
    })

# UPC ile arama
@app.route('/search/upc/<upc>', methods=['GET'])
def search_by_upc(upc):
    if not upc or not upc.isdigit():
        return jsonify({'error': 'Geçersiz UPC kodu'}), 400
    
    # Eğer scanner yoksa test verileri döndür
    if not scanner:
        return generate_test_upc_search_results(upc)
        
    try:
        # UPC araması yap
        result = scanner.search_by_upc_advanced(upc)
        
        # Sonuçları işle
        processed_results = {
            'items': []
        }
        
        # UPC araması sonuçlarını işle
        if 'upc_search' in result and 'items' in result['upc_search']:
            for item in result['upc_search'].get('items', []):
                processed_item = scanner.extract_enhanced_data(item)
                processed_results['items'].append(processed_item)
                
        # GTIN araması sonuçlarını ekle
        if 'gtin_search' in result and 'items' in result['gtin_search']:
            for item in result['gtin_search'].get('items', []):
                # Daha önce eklenmediyse
                processed_item = scanner.extract_enhanced_data(item)
                if not any(p['product_id'] == processed_item['product_id'] for p in processed_results['items']):
                    processed_results['items'].append(processed_item)
                
        # Query araması sonuçlarını ekle
        if 'query_search' in result and 'items' in result['query_search']:
            for item in result['query_search'].get('items', []):
                # Daha önce eklenmediyse
                processed_item = scanner.extract_enhanced_data(item)
                if not any(p['product_id'] == processed_item['product_id'] for p in processed_results['items']):
                    processed_results['items'].append(processed_item)
        
        return jsonify(processed_results)
    except Exception as e:
        logger.error(f"UPC arama hatası: {e}")
        return jsonify({'error': str(e)}), 500

# Ürün varyasyonlarını bulma
@app.route('/variations/walmart', methods=['POST'])
def find_variations():
    data = request.json
    
    if not data or not data.get('url'):
        return jsonify({'error': 'Geçersiz istek verisi'}), 400
        
    url = data.get('url')
    
    # Eğer scanner yoksa test verileri döndür
    if not scanner:
        return generate_test_variations(url)
    
    try:
        # Önce URL'den ürün ID'sini çıkar
        product_id = scanner.extract_product_id_from_url(url)
        
        if not product_id:
            return jsonify({'error': 'URL\'den ürün ID\'si çıkarılamadı'}), 400
            
        # Ürün detaylarını al
        product_details = scanner.get_item_details(product_id)
        
        if not product_details:
            return jsonify({'error': 'Ürün detayları alınamadı'}), 404
            
        # Ana ürün bilgilerini çıkar
        main_product = scanner.extract_enhanced_data(product_details, is_main=True)
        
        # Varyasyonları al
        variants = scanner.get_product_variants(main_product)
        
        # Varyasyon türlerini belirle
        variation_types = []
        if len(variants) > 0:
            # İlk varyasyon üzerinden potansiyel türleri belirle
            for key in variants[0]:
                if key in ['color', 'size', 'style', 'pattern', 'material', 'configuration']:
                    if variants[0][key] and main_product.get(key):
                        variation_types.append(key)
        
        return jsonify({
            'main_product': main_product,
            'variants': variants,
            'variation_types': variation_types,
            'total_variants': len(variants)
        })
    except Exception as e:
        logger.error(f"Varyasyon bulma hatası: {e}")
        return jsonify({'error': str(e)}), 500

# Toplu işlem
@app.route('/batch/process', methods=['POST'])
def batch_process():
    data = request.json
    
    if not data or not data.get('items') or not data.get('type'):
        return jsonify({'error': 'Geçersiz istek verisi'}), 400
        
    items = data.get('items')
    batch_type = data.get('type')
    
    if not isinstance(items, list) or len(items) == 0:
        return jsonify({'error': 'Geçersiz öğe listesi'}), 400
        
    # Maksimum 50 öğe ile sınırla
    if len(items) > 50:
        items = items[:50]
    
    # Eğer scanner yoksa test verileri döndür
    if not scanner:
        return generate_test_batch_results(items, batch_type)
    
    results = []
    errors = []
    
    for index, item in enumerate(items):
        try:
            if batch_type == 'upc':
                # UPC taraması
                if not item.isdigit():
                    errors.append({
                        'input': item,
                        'error': 'Geçersiz UPC formatı'
                    })
                    continue
                    
                result = scanner.scan_upc_pro_enhanced(item)
                if result and result.get('product'):
                    results.append(result['product'])
                else:
                    errors.append({
                        'input': item,
                        'error': 'Ürün bulunamadı'
                    })
                    
            elif batch_type == 'walmart':
                # Walmart URL taraması
                if 'walmart.com' not in item:
                    errors.append({
                        'input': item,
                        'error': 'Geçersiz Walmart URL\'si'
                    })
                    continue
                    
                result = scanner.scan_by_url(item)
                if result and result.get('product'):
                    results.append(result['product'])
                else:
                    errors.append({
                        'input': item,
                        'error': 'Ürün bulunamadı'
                    })
                    
            elif batch_type == 'amazon':
                # Amazon URL taraması
                if 'amazon.com' not in item:
                    errors.append({
                        'input': item,
                        'error': 'Geçersiz Amazon URL\'si'
                    })
                    continue
                    
                # NOT: Amazon API henüz desteklenmiyor
                # Örnek sonuç döndür
                results.append({
                    'product_id': f'ASIN-SAMPLE-{index}',
                    'title': f'Amazon Ürün Örneği #{index}',
                    'current_price': 99.99,
                    'image_url': 'https://via.placeholder.com/150',
                    'url': item
                })
                
        except Exception as e:
            logger.error(f"Batch işlem hatası: {e}")
            errors.append({
                'input': item,
                'error': str(e)
            })
    
    return jsonify({
        'success_count': len(results),
        'error_count': len(errors),
        'total': len(items),
        'results': results,
        'errors': errors
    })

# Fiyat bildirimleri
@app.route('/notifications/price-drops', methods=['GET'])
def price_notifications():
    # Şimdilik örnek veri döndür
    
    return jsonify({
        'items': [
            {
                'id': 'notification-1',
                'title': 'Samsung 55" Class QLED 4K TV',
                'old_price': 799.99,
                'new_price': 699.99,
                'url': 'https://www.walmart.com/sample-product-1',
                'image_url': 'https://via.placeholder.com/150',
                'date': int(time.time() * 1000)
            }
        ]
    })

# Test verileri oluşturma fonksiyonları
def generate_test_product_data(url=None, upc=None):
    logger.info("Test modu: Örnek ürün verisi oluşturuluyor")
    product_id = "test-123456"
    
    if url:
        product_id = url.split('/')[-1] if '/' in url else "test-123456"
        
    if upc:
        product_id = f"upc-{upc}"
        
    return jsonify({
        'product': {
            'product_id': product_id,
            'upc': upc or '123456789012',
            'title': 'Test Ürün - Örnek Veri',
            'brand': 'Test Markası',
            'model': 'TM-2023',
            'current_price': 299.99,
            'original_price': 349.99,
            'url': url or 'https://www.walmart.com/ip/test-product',
            'image_url': 'https://via.placeholder.com/300',
            'availability': True,
            'rating': 4.2,
            'review_count': 123,
            'category': 'Elektronik > TV & Video'
        }
    })

def generate_test_upc_search_results(upc):
    logger.info(f"Test modu: {upc} için örnek UPC arama sonuçları oluşturuluyor")
    items = []
    
    # 3 örnek sonuç oluştur
    for i in range(3):
        items.append({
            'product_id': f'test-{upc}-{i}',
            'upc': upc,
            'title': f'Test Ürün {i+1} ({upc})',
            'brand': 'Test Markası',
            'model': f'TM-{upc[:4]}-{i}',
            'current_price': 99.99 + (i * 10),
            'original_price': 129.99 + (i * 10),
            'url': f'https://www.walmart.com/ip/test-product-{i}',
            'image_url': f'https://via.placeholder.com/300?text=Product{i+1}',
            'availability': True,
            'rating': 4.0 + (i * 0.2),
            'review_count': 50 + (i * 25)
        })
    
    return jsonify({'items': items})

def generate_test_variations(url):
    logger.info("Test modu: Örnek varyasyon verileri oluşturuluyor")
    # Ana ürün
    main_product = {
        'product_id': 'main-123456',
        'upc': '123456789012',
        'title': 'Test Ürün - Ana Model',
        'brand': 'Test Markası',
        'current_price': 299.99,
        'image_url': 'https://via.placeholder.com/300?text=MainProduct',
        'url': url or 'https://www.walmart.com/ip/test-product',
        'color': 'Siyah',
        'size': 'M'
    }
    
    # Varyasyonlar
    variants = []
    colors = ['Beyaz', 'Mavi', 'Kırmızı']
    sizes = ['S', 'L', 'XL']
    
    for i in range(3):
        variants.append({
            'product_id': f'variant-{i}',
            'upc': f'12345678901{i}',
            'title': f'Test Ürün - {colors[i]} {sizes[i]}',
            'brand': 'Test Markası',
            'current_price': 299.99 + (i * 20),
            'image_url': f'https://via.placeholder.com/300?text=Variant{i+1}',
            'url': f'https://www.walmart.com/ip/test-product-variant-{i}',
            'color': colors[i],
            'size': sizes[i]
        })
    
    return jsonify({
        'main_product': main_product,
        'variants': variants,
        'variation_types': ['color', 'size'],
        'total_variants': len(variants)
    })

def generate_test_batch_results(items, batch_type):
    logger.info("Test modu: Örnek toplu işlem sonuçları oluşturuluyor")
    results = []
    errors = []
    
    for i, item in enumerate(items):
        # Her 5 öğeden birini hata olarak işaretle
        if i % 5 == 0 and i > 0:
            errors.append({
                'input': item,
                'error': 'Test hatası: Örnek hata mesajı'
            })
        else:
            results.append({
                'product_id': f'test-{batch_type}-{i}',
                'title': f'Test Ürün #{i} ({batch_type})',
                'current_price': 99.99 + (i * 5),
                'image_url': f'https://via.placeholder.com/300?text=BatchItem{i}',
                'url': item if item.startswith('http') else f'https://www.example.com/{item}'
            })
    
    return jsonify({
        'success_count': len(results),
        'error_count': len(errors),
        'total': len(items),
        'results': results,
        'errors': errors
    })

# Ana çalıştırma kodu
if __name__ == '__main__':
    if ENVIRONMENT == 'production':
        # Güvenli üretim yapılandırması
        from waitress import serve
        logger.info(f"Üretim ortamında başlatılıyor. Port: {PORT}")
        serve(app, host="0.0.0.0", port=PORT)
    else:
        # Geliştirme ortamı
        logger.info(f"Geliştirme ortamında başlatılıyor. Port: {PORT}")
        app.run(host='0.0.0.0', port=PORT, debug=True) 