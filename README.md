# Ürün Tarayıcı API ve Chrome Eklentisi

Bu proje, Walmart ve Amazon gibi e-ticaret platformlarından ürün verilerini çeken bir Chrome eklentisi ve arka uç API'sinden oluşur.

## Proje Yapısı

Proje iki ana bileşenden oluşur:

1. **Chrome Eklentisi** - Kullanıcı arayüzü (Manifest V3)
2. **API Servisi** - Flask tabanlı arka uç (Python)

## Kurulum

### API Servisi

#### Yerel Geliştirme

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. `.env` dosyası oluşturun:
```
WALMART_CLIENT_ID=sizin_client_id
WALMART_CLIENT_SECRET=sizin_client_secret
API_KEY=sizin_api_anahtari
ENVIRONMENT=development
```

3. API'yi çalıştırın:
```bash
python api_bridge.py
```

#### Render.com'da Deploy Etme

1. Render.com hesabınıza giriş yapın ve "New Web Service" seçin
2. Aşağıdaki ayarları yapılandırın:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn api_bridge:app`
3. Environment Variables bölümünde:
   - `WALMART_CLIENT_ID`
   - `WALMART_CLIENT_SECRET`
   - `API_KEY`
   - `ENVIRONMENT=production`

### Chrome Eklentisi

1. Chrome tarayıcınızda `chrome://extensions/` adresine gidin
2. "Geliştirici modu"nu açın (sağ üst köşe)
3. "Paketlenmemiş öğe yükle" düğmesine tıklayın
4. Bu projenin kök klasörünü seçin

## API Referansı

API belgeleri için [API.md](API.md) dosyasına bakın veya [API Endpoint](#) adresini ziyaret edin.

## Özellikler

- Walmart ürün bilgilerini otomatik tarama
- UPC kodu ile ürün arama
- Ürün varyasyonlarını bulma
- Toplu işlem desteği
- Amazon ürün entegrasyonu (yakında)
- Fiyat takibi ve bildirimleri (yakında)

## Ekran Görüntüleri

![Ürün Tarayıcı Arayüzü](screenshots/preview.png)

## Teknolojiler

- **Ön Uç**: HTML, CSS, JavaScript (Vanilla)
- **Arka Uç**: Python, Flask
- **Bulut**: Render.com

## Katkıda Bulunma

1. Bu depoyu fork edin
2. Yeni bir özellik dalı oluşturun (`git checkout -b yeni-ozellik`)
3. Değişikliklerinizi commit edin (`git commit -am 'Yeni özellik: X'`)
4. Dalınızı push edin (`git push origin yeni-ozellik`)
5. Bir Pull Request oluşturun

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Daha fazla bilgi için [LICENSE](LICENSE) dosyasına bakın. 