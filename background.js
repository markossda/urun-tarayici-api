// background.js - Arka plan servisi
let apiBaseUrl = 'https://api-server-url'; // API sunucu adresinizi buraya ekleyin

// Uzantı ilk yüklendiğinde
chrome.runtime.onInstalled.addListener(() => {
  console.log('Ürün Tarayıcı eklentisi yüklendi');
  
  // Varsayılan ayarları kaydet
  chrome.storage.sync.set({
    apiEndpoint: apiBaseUrl,
    apiKey: '',
    trackPriceHistory: true,
    showSimilarProducts: true,
    notifyPriceDrops: true
  });
});

// Content script'ten gelen mesajları dinle
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'scanWalmartProduct') {
    scanWalmartProduct(request.productData)
      .then(result => sendResponse({ success: true, data: result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // Asenkron cevap için true döndür
  }
  
  if (request.action === 'scanAmazonProduct') {
    scanAmazonProduct(request.productData)
      .then(result => sendResponse({ success: true, data: result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
  
  if (request.action === 'searchByUpc') {
    searchByUpc(request.upc)
      .then(result => sendResponse({ success: true, data: result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
  
  if (request.action === 'findVariations') {
    findProductVariations(request.productData)
      .then(result => sendResponse({ success: true, data: result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
  
  if (request.action === 'processBatch') {
    processBatchItems(request.type, request.items)
      .then(result => sendResponse({ success: true, data: result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
  
  if (request.action === 'getSettings') {
    chrome.storage.sync.get(null, (settings) => {
      sendResponse({ success: true, settings });
    });
    return true;
  }
});

// API çağrıları için yardımcı fonksiyon
async function makeApiCall(endpoint, method = 'GET', data = null) {
  try {
    const settings = await new Promise(resolve => {
      chrome.storage.sync.get(['apiEndpoint', 'apiKey'], resolve);
    });
    
    const apiUrl = settings.apiEndpoint || apiBaseUrl;
    
    const headers = {
      'Content-Type': 'application/json'
    };
    
    if (settings.apiKey) {
      headers['X-API-Key'] = settings.apiKey;
    }
    
    const options = {
      method,
      headers
    };
    
    if (data && (method === 'POST' || method === 'PUT')) {
      options.body = JSON.stringify(data);
    }
    
    const response = await fetch(`${apiUrl}/${endpoint}`, options);
    
    if (!response.ok) {
      throw new Error(`Sunucu hatası: ${response.status}`);
    }
    
    return await response.json();
    
  } catch (error) {
    console.error(`API hatası (${endpoint}):`, error);
    throw error;
  }
}

// Walmart ürün tarama
async function scanWalmartProduct(productData) {
  return makeApiCall('scan/walmart', 'POST', productData);
}

// Amazon ürün tarama
async function scanAmazonProduct(productData) {
  return makeApiCall('scan/amazon', 'POST', productData);
}

// UPC ile arama
async function searchByUpc(upc) {
  return makeApiCall(`search/upc/${upc}`, 'GET');
}

// Ürün varyasyonlarını bul
async function findProductVariations(productData) {
  return makeApiCall('variations/walmart', 'POST', productData);
}

// Toplu işlem
async function processBatchItems(type, items) {
  return makeApiCall('batch/process', 'POST', { type, items });
}

// Fiyat bildirimlerini kontrol et
async function checkPriceNotifications() {
  try {
    // Bildirim izni var mı kontrol et
    if (!hasNotificationsPermission()) {
      console.log('Bildirim izni yok, fiyat kontrolü yapılmayacak');
      return;
    }

    const settings = await new Promise(resolve => {
      chrome.storage.sync.get(['notifyPriceDrops'], resolve);
    });
    
    if (!settings.notifyPriceDrops) {
      return;
    }
    
    const notifications = await makeApiCall('notifications/price-drops', 'GET');
    
    if (notifications && notifications.items && notifications.items.length > 0) {
      // Bildirimleri göster
      notifications.items.forEach(item => {
        showNotification(
          'price-drop-' + item.id,
          'Fiyat Düştü!',
          `${item.title} ürününün fiyatı $${item.old_price} → $${item.new_price} düştü!`,
          [{ title: 'Ürünü Görüntüle' }],
          item.url
        );
      });
    }
  } catch (error) {
    console.error('Bildirim kontrolü hatası:', error);
  }
}

// Bildirim izinlerini kontrol et
function hasNotificationsPermission() {
  return chrome && chrome.notifications && typeof chrome.notifications.create === 'function';
}

// Bildirim göster
function showNotification(id, title, message, buttons, url) {
  // notifications API yoksa işlem yapma
  if (!hasNotificationsPermission()) {
    console.warn('Bildirim izni yok veya API mevcut değil');
    return;
  }

  // Bildirimi oluştur
  chrome.notifications.create(id, {
    type: 'basic',
    iconUrl: 'icons/icon128.png',
    title: title,
    message: message,
    buttons: buttons
  });

  // URL bilgisini sakla
  chrome.storage.local.get(['notificationUrls'], (result) => {
    const urls = result.notificationUrls || {};
    urls[id] = url;
    chrome.storage.local.set({ notificationUrls: urls });
  });
}

// Bildirim butonuna tıklama olayı
if (chrome.notifications && chrome.notifications.onButtonClicked) {
  chrome.notifications.onButtonClicked.addListener((notificationId, buttonIndex) => {
    if (buttonIndex === 0) { // "Ürünü Görüntüle" butonu
      // Bildirim URL'sini al ve ürün sayfasını aç
      chrome.storage.local.get(['notificationUrls'], (result) => {
        const url = result.notificationUrls?.[notificationId];
        if (url) {
          chrome.tabs.create({ url });
        }
      });
    }
  });
}

// Düzenli fiyat kontrolü (her saat)
if (chrome.alarms) {
  chrome.alarms.create('checkPrices', { periodInMinutes: 60 });

  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'checkPrices') {
      checkPriceNotifications();
    }
  });
}

// İlk çalıştırmada kontrol et
chrome.runtime.onStartup.addListener(() => {
  // Bildirim izni varsa fiyat kontrolü yap
  if (hasNotificationsPermission()) {
    checkPriceNotifications();
  }
}); 