# Ürün Tarayıcı API Dokümantasyonu

Bu dokümantasyon, Ürün Tarayıcı API'sinin kullanımını açıklar.

## Kimlik Doğrulama

Tüm API istekleri, X-API-Key başlığında bir API anahtarı gerektirir:

```
X-API-Key: your_api_key
```

## Genel Endpoint'ler

### Sağlık Kontrolü

```
GET /health
```

Yanıt:

```json
{
  "status": "up",
  "timestamp": 1685436789,
  "environment": "production"
}
```

### Test

```
GET /test
```

Yanıt:

```json
{
  "status": "success",
  "message": "API bridge çalışıyor",
  "environment": "production",
  "product_module_loaded": true
}
```

## Walmart Endpoint'leri

### Ürün Tarama (URL ile)

```
POST /scan/walmart
Content-Type: application/json

{
  "url": "https://www.walmart.com/ip/product-id"
}
```

Yanıt:

```json
{
  "product": {
    "product_id": "12345",
    "upc": "123456789012",
    "title": "Ürün Adı",
    "brand": "Marka",
    "current_price": 99.99,
    "original_price": 129.99,
    "url": "https://www.walmart.com/ip/product-id",
    "image_url": "https://i5.walmartimages.com/asr/image.jpg",
    "availability": true,
    "rating": 4.5,
    "review_count": 123
  }
}
```

### Ürün Tarama (UPC ile)

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

Yanıt:

```json
{
  "items": [
    {
      "product_id": "12345",
      "upc": "123456789012",
      "title": "Ürün Adı",
      "brand": "Marka",
      "current_price": 99.99
      // Diğer ürün bilgileri...
    },
    // Diğer eşleşen ürünler...
  ]
}
```

### Varyasyon Bulma

```
POST /variations/walmart
Content-Type: application/json

{
  "url": "https://www.walmart.com/ip/product-id"
}
```

Yanıt:

```json
{
  "main_product": {
    // Ana ürün bilgileri...
  },
  "variants": [
    {
      // Varyasyon 1 bilgileri...
    },
    // Diğer varyasyonlar...
  ],
  "variation_types": ["color", "size"],
  "total_variants": 6
}
```

## Toplu İşlemler

### Toplu Ürün Tarama

```
POST /batch/process
Content-Type: application/json

{
  "type": "walmart", // veya "upc", "amazon"
  "items": [
    "https://www.walmart.com/ip/product-id-1",
    "https://www.walmart.com/ip/product-id-2"
  ]
}
```

Yanıt:

```json
{
  "success_count": 2,
  "error_count": 0,
  "total": 2,
  "results": [
    // Başarılı sonuçlar...
  ],
  "errors": [
    // Hata sonuçları...
  ]
}
```

## Amazon Endpoint'leri (Beta)

### Ürün Tarama

```
POST /scan/amazon
Content-Type: application/json

{
  "url": "https://www.amazon.com/dp/product-id"
}
```

## Bildirimler

### Fiyat Düşüşleri

```
GET /notifications/price-drops
```

## Hata Kodları

- `400` - Kötü istek (eksik parametre veya geçersiz format)
- `401` - Yetkilendirme hatası (geçersiz API anahtarı)
- `404` - Ürün bulunamadı
- `500` - Sunucu hatası

## Sınırlamalar

- API istekleri için dakikada 60 istek sınırı vardır.
- Toplu işlemler için maksimum 50 öğe.
- Maksimum istek boyutu: 1MB 