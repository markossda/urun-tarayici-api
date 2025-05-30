# Ürün Tarayıcı API

Bu API, çeşitli e-ticaret platformlarından ürün bilgilerini almak için kullanılan bir REST API hizmetidir. Chrome eklentisi için arka uç olarak çalışır.

## Özellikler

- Walmart ürün tarama ve varyasyon bulma
- UPC kodu ile ürün arama
- Amazon ürün tarama (yakında)
- Toplu işlem desteği
- Fiyat bildirimleri (yakında)

## Gereksinimler

- Python 3.8+
- Flask ve diğer bağımlılıklar (requirements.txt dosyasında belirtilmiştir)

## Kurulum

### Yerel Geliştirme

1. Depoyu klonlayın
```bash
git clone https://github.com/kullanici-adi/urun-tarayici-api.git
cd urun-tarayici-api
```

2. Sanal ortam oluşturun ve bağımlılıkları yükleyin
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. `.env` dosyası oluşturun
```
WALMART_CLIENT_ID=sizin_client_id
WALMART_CLIENT_SECRET=sizin_client_secret
API_KEY=sizin_api_anahtari
ENVIRONMENT=development
```

4. Uygulamayı çalıştırın
```bash
python api_bridge.py
```

### Render.com'da Deploy Etme

1. Render.com hesabınıza giriş yapın

2. "New" butonuna tıklayın ve "Web Service" seçeneğini seçin

3. GitHub reponuzu bağlayın veya reponuzun URL'sini girin

4. Aşağıdaki ayarları yapılandırın:
   - **Name**: urun-tarayici-api (veya istediğiniz bir isim)
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn api_bridge:app`

5. "Environment Variables" bölümünde aşağıdaki değişkenleri ekleyin:
   - `WALMART_CLIENT_ID`: Walmart API istemci kimliği
   - `WALMART_CLIENT_SECRET`: Walmart API istemci sırrı
   - `API_KEY`: API erişim anahtarı
   - `ENVIRONMENT`: production

6. "Create Web Service" butonuna tıklayarak deploy edin

## API Kullanımı

API'ye gönderilen tüm isteklerde `X-API-Key` header'ını kullanmalısınız:

```
X-API-Key: sizin_api_anahtari
```

### Walmart Ürün Tarama

```
POST /scan/walmart
Content-Type: application/json

{
  "url": "https://www.walmart.com/ip/product-id"
}
```

veya UPC kodu ile:

```
POST /scan/walmart
Content-Type: application/json

{
  "upc": "123456789012"
}
```

### UPC ile Arama

```
GET /search/upc/123456789012
```

### Varyasyonları Bulma

```
POST /variations/walmart
Content-Type: application/json

{
  "url": "https://www.walmart.com/ip/product-id"
}
```

### Toplu İşlem

```
POST /batch/process
Content-Type: application/json

{
  "type": "walmart",
  "items": [
    "https://www.walmart.com/ip/product-id-1",
    "https://www.walmart.com/ip/product-id-2"
  ]
}
```

## Güvenlik Notları

- Üretim ortamında her zaman güçlü bir API anahtarı kullanın
- Environment variables kullanarak hassas bilgileri güvende tutun
- Render.com'da otomatik SSL/TLS kullanın

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. 