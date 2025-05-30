/**
 * API Entegrasyon Modülü
 * Ürün Tarayıcı API ile iletişim kuran fonksiyonları içerir
 */

class ApiIntegration {
  constructor() {
    // API yapılandırmasını saklanan değerlerden yükle
    this.loadConfig();
  }

  /**
   * API yapılandırmasını yükler
   */
  async loadConfig() {
    return new Promise((resolve) => {
      chrome.storage.sync.get(
        {
          apiUrl: 'https://urun-tarayici-api.onrender.com',
          apiKey: 'default-key',
          environment: 'production'
        },
        (items) => {
          this.apiUrl = items.apiUrl;
          this.apiKey = items.apiKey;
          this.environment = items.environment;
          console.log('API yapılandırması yüklendi:', this.apiUrl);
          resolve();
        }
      );
    });
  }

  /**
   * API yapılandırmasını günceller
   * @param {Object} config - Yeni yapılandırma değerleri
   */
  async updateConfig(config) {
    return new Promise((resolve) => {
      chrome.storage.sync.set(config, () => {
        if (config.apiUrl) this.apiUrl = config.apiUrl;
        if (config.apiKey) this.apiKey = config.apiKey;
        if (config.environment) this.environment = config.environment;
        console.log('API yapılandırması güncellendi:', this.apiUrl);
        resolve();
      });
    });
  }

  /**
   * API'ye bir istek gönderir
   * @param {string} endpoint - API endpoint'i
   * @param {Object} options - Fetch options
   * @returns {Promise<Object>} API yanıtı
   */
  async apiRequest(endpoint, options = {}) {
    try {
      // Yapılandırma yüklenmemişse yükle
      if (!this.apiUrl) {
        await this.loadConfig();
      }

      const url = `${this.apiUrl}${endpoint}`;
      
      // Varsayılan header'ları ayarla
      const headers = {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey
      };

      // Özel options ile birleştir
      const requestOptions = {
        ...options,
        headers: {
          ...headers,
          ...options.headers
        }
      };

      console.log(`API isteği: ${url}`, requestOptions);
      
      // API isteğini gönder
      const response = await fetch(url, requestOptions);
      
      // Başarısız yanıtları ele al
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.error || `API isteği başarısız: ${response.status} ${response.statusText}`
        );
      }
      
      // Yanıtı JSON olarak çözümle
      const data = await response.json();
      return data;
    } catch (error) {
      console.error('API isteği hatası:', error);
      throw error;
    }
  }

  /**
   * API sunucusunun durumunu kontrol eder
   * @returns {Promise<Object>} API sağlık durumu
   */
  async checkApiHealth() {
    return this.apiRequest('/health');
  }

  /**
   * API sunucusunu test eder
   * @returns {Promise<Object>} Test sonucu
   */
  async testApi() {
    return this.apiRequest('/test');
  }

  /**
   * Walmart ürününü URL ile tarar
   * @param {string} url - Walmart ürün URL'si
   * @returns {Promise<Object>} Ürün bilgileri
   */
  async scanWalmartByUrl(url) {
    return this.apiRequest('/scan/walmart', {
      method: 'POST',
      body: JSON.stringify({ url })
    });
  }

  /**
   * Walmart ürününü UPC kodu ile tarar
   * @param {string} upc - UPC kodu
   * @returns {Promise<Object>} Ürün bilgileri
   */
  async scanWalmartByUpc(upc) {
    return this.apiRequest('/scan/walmart', {
      method: 'POST',
      body: JSON.stringify({ upc })
    });
  }

  /**
   * Amazon ürününü URL ile tarar
   * @param {string} url - Amazon ürün URL'si
   * @returns {Promise<Object>} Ürün bilgileri
   */
  async scanAmazonByUrl(url) {
    return this.apiRequest('/scan/amazon', {
      method: 'POST',
      body: JSON.stringify({ url })
    });
  }

  /**
   * UPC kodu ile ürün arar
   * @param {string} upc - UPC kodu
   * @returns {Promise<Object>} Arama sonuçları
   */
  async searchByUpc(upc) {
    return this.apiRequest(`/search/upc/${upc}`);
  }

  /**
   * Walmart ürün varyasyonlarını bulur
   * @param {string} url - Walmart ürün URL'si
   * @returns {Promise<Object>} Varyasyon bilgileri
   */
  async findWalmartVariations(url) {
    return this.apiRequest('/variations/walmart', {
      method: 'POST',
      body: JSON.stringify({ url })
    });
  }

  /**
   * Toplu işlem yapar
   * @param {string} type - İşlem türü (upc, walmart, amazon)
   * @param {Array<string>} items - İşlenecek öğeler
   * @returns {Promise<Object>} İşlem sonuçları
   */
  async processBatch(type, items) {
    return this.apiRequest('/batch/process', {
      method: 'POST',
      body: JSON.stringify({ type, items })
    });
  }

  /**
   * Fiyat bildirimlerini alır
   * @returns {Promise<Object>} Bildirim listesi
   */
  async getPriceNotifications() {
    return this.apiRequest('/notifications/price-drops');
  }
}

// Singleton instance oluştur
const apiIntegration = new ApiIntegration();

// Global namespace'e ekle
window.apiIntegration = apiIntegration;

// Export et
export default apiIntegration; 