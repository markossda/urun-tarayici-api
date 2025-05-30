// Popup.js - Popup davranışları

// Sekme geçişi
function setupTabs() {
  const tabButtons = document.querySelectorAll('.tab-button');
  const tabPanes = document.querySelectorAll('.tab-pane');
  
  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      // Aktif sekme butonlarını güncelle
      tabButtons.forEach(btn => btn.classList.remove('active'));
      button.classList.add('active');
      
      // Aktif sekme içeriğini göster
      const tabId = button.dataset.tab;
      tabPanes.forEach(pane => {
        pane.classList.remove('active');
        if (pane.id === tabId) {
          pane.classList.add('active');
        }
      });
    });
  });
}

// Ayarları yükle
function loadSettings() {
  chrome.storage.local.get({
    apiEndpoint: 'https://api-server-url/walmart',
    trackPriceHistory: true,
    showSimilarProducts: true,
    notifyPriceDrops: true
  }, (settings) => {
    document.getElementById('api-endpoint').value = settings.apiEndpoint;
    document.getElementById('track-price-history').checked = settings.trackPriceHistory;
    document.getElementById('show-similar-products').checked = settings.showSimilarProducts;
    document.getElementById('notify-price-drops').checked = settings.notifyPriceDrops;
  });
}

// Ayarları kaydet
function saveSettings() {
  const settings = {
    apiEndpoint: document.getElementById('api-endpoint').value,
    trackPriceHistory: document.getElementById('track-price-history').checked,
    showSimilarProducts: document.getElementById('show-similar-products').checked,
    notifyPriceDrops: document.getElementById('notify-price-drops').checked
  };
  
  chrome.storage.local.set(settings, () => {
    showToast('Ayarlar kaydedildi');
  });
}

// Ayarları sıfırla
function resetSettings() {
  const defaultSettings = {
    apiEndpoint: 'https://api-server-url/walmart',
    trackPriceHistory: true,
    showSimilarProducts: true,
    notifyPriceDrops: true
  };
  
  chrome.storage.local.set(defaultSettings, () => {
    loadSettings();
    showToast('Ayarlar sıfırlandı');
  });
}

// Geçmişi yükle
function loadHistory() {
  chrome.storage.local.get('scanHistory', (data) => {
    const history = data.scanHistory || [];
    const historyEmptyState = document.getElementById('history-empty-state');
    const historyList = document.getElementById('history-list');
    
    if (history.length === 0) {
      historyEmptyState.style.display = 'flex';
      historyList.style.display = 'none';
    } else {
      historyEmptyState.style.display = 'none';
      historyList.style.display = 'block';
      
      // Geçmiş listesini oluştur
      historyList.innerHTML = '';
      history.forEach(item => {
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        historyItem.innerHTML = `
          <img src="${item.imageUrl || 'icons/placeholder.png'}" alt="${item.title}" class="history-image">
          <div class="history-details">
            <div class="history-title">${item.title}</div>
            <div class="history-meta">
              <div class="history-price">$${item.price}</div>
              <div class="history-date">${formatDate(item.scanDate)}</div>
            </div>
          </div>
        `;
        
        // Tıklandığında ürün sayfasına git
        historyItem.addEventListener('click', () => {
          chrome.tabs.create({ url: item.url });
        });
        
        historyList.appendChild(historyItem);
      });
    }
  });
}

// Aktif sekmedeki ürünü tara
function scanCurrentProduct() {
  document.getElementById('scan-button').disabled = true;
  document.getElementById('compare-button').disabled = true;
  updateStatus('Taranıyor...', 'Ürün bilgileri alınıyor, lütfen bekleyin.');
  
  // Aktif sekmedeki ürünü bul
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const activeTab = tabs[0];
    
    // Walmart sayfasında olduğunu kontrol et
    if (!activeTab.url.includes('walmart.com')) {
      updateStatus('Walmart Değil', 'Bu sayfa bir Walmart ürün sayfası değil.');
      document.getElementById('scan-button').disabled = false;
      return;
    }
    
    // Sayfadaki ürün bilgilerini çek
    chrome.scripting.executeScript({
      target: { tabId: activeTab.id },
      function: function() {
        // Content script içindeki işlevleri kullan
        if (typeof isProductPage === 'function' && typeof extractProductData === 'function') {
          return {
            isProductPage: isProductPage(),
            productData: isProductPage() ? extractProductData() : null
          };
        } else {
          // Content script yüklü değilse
          return {
            isProductPage: false,
            productData: null,
            error: 'Content script yüklü değil'
          };
        }
      }
    }, (results) => {
      if (chrome.runtime.lastError) {
        updateStatus('Hata', 'Script çalıştırılamadı: ' + chrome.runtime.lastError.message);
        document.getElementById('scan-button').disabled = false;
        return;
      }
      
      const result = results[0].result;
      
      if (result.error) {
        updateStatus('Hata', result.error);
        document.getElementById('scan-button').disabled = false;
        return;
      }
      
      if (!result.isProductPage || !result.productData) {
        updateStatus('Ürün Bulunamadı', 'Bu sayfa bir Walmart ürün sayfası değil veya ürün bilgileri çıkarılamadı.');
        document.getElementById('scan-button').disabled = false;
        return;
      }
      
      // Ürün verilerini API'ye gönder
      chrome.runtime.sendMessage(
        { action: 'scanProduct', productData: result.productData },
        (response) => {
          document.getElementById('scan-button').disabled = false;
          
          if (response && response.success) {
            updateStatus('Tarama Tamamlandı', 'Ürün başarıyla tarandı.');
            displayResults(response.data);
            
            // Karşılaştırma butonunu etkinleştir
            if (response.data.similarProducts && response.data.similarProducts.length > 0) {
              document.getElementById('compare-button').disabled = false;
            }
            
            // Geçmişe ekle
            addToHistory(result.productData, response.data);
          } else {
            updateStatus('Hata', response?.error || 'API yanıt vermedi.');
          }
        }
      );
    });
  });
}

// Sonuçları göster
function displayResults(data) {
  const resultContainer = document.getElementById('result-container');
  
  if (!data || Object.keys(data).length === 0) {
    resultContainer.innerHTML = '<p>Ürün hakkında bilgi bulunamadı.</p>';
    resultContainer.style.display = 'block';
    return;
  }
  
  let html = `
    <div class="product-card">
      <div class="product-header">
        <img src="${data.imageUrl || 'icons/placeholder.png'}" alt="${data.title}" class="product-image">
        <div>
          <div class="product-title">${data.title || 'Ürün'}</div>
          <div class="product-price">$${data.currentPrice || 'N/A'}</div>
        </div>
      </div>
      
      <div class="product-info">
  `;
  
  // Fiyat bilgisi
  if (data.priceHistory && data.priceHistory.length > 0) {
    const lowestPrice = Math.min(...data.priceHistory.map(p => p.price));
    const highestPrice = Math.max(...data.priceHistory.map(p => p.price));
    
    html += `
      <div class="info-row">
        <span class="info-label">En Düşük Fiyat</span>
        <span class="info-value">$${lowestPrice.toFixed(2)}</span>
      </div>
      <div class="info-row">
        <span class="info-label">En Yüksek Fiyat</span>
        <span class="info-value">$${highestPrice.toFixed(2)}</span>
      </div>
    `;
  }
  
  // Ek bilgiler
  if (data.additionalInfo) {
    for (const [key, value] of Object.entries(data.additionalInfo)) {
      html += `
        <div class="info-row">
          <span class="info-label">${key}</span>
          <span class="info-value">${value}</span>
        </div>
      `;
    }
  }
  
  html += `
      </div>
    </div>
  `;
  
  // Benzer ürünler varsa ekle
  if (data.similarProducts && data.similarProducts.length > 0) {
    html += `
      <h4>Benzer Ürünler</h4>
      <div class="history-list">
    `;
    
    data.similarProducts.slice(0, 3).forEach(product => {
      html += `
        <div class="history-item" data-url="${product.url}">
          <img src="${product.imageUrl || 'icons/placeholder.png'}" alt="${product.title}" class="history-image">
          <div class="history-details">
            <div class="history-title">${product.title}</div>
            <div class="history-meta">
              <div class="history-price">$${product.price}</div>
            </div>
          </div>
        </div>
      `;
    });
    
    html += `</div>`;
  }
  
  resultContainer.innerHTML = html;
  resultContainer.style.display = 'block';
  
  // Benzer ürünlere tıklama işlevi ekle
  document.querySelectorAll('.history-item[data-url]').forEach(item => {
    item.addEventListener('click', () => {
      chrome.tabs.create({ url: item.dataset.url });
    });
  });
}

// Durum güncelleme
function updateStatus(title, message) {
  document.getElementById('status-title').textContent = title;
  document.getElementById('status-message').textContent = message;
}

// Geçmişe ekle
function addToHistory(productData, apiData) {
  chrome.storage.local.get({ scanHistory: [] }, (data) => {
    const history = data.scanHistory;
    
    // Eklenecek öğe
    const historyItem = {
      url: productData.url,
      title: productData.title,
      price: apiData.currentPrice || productData.price,
      imageUrl: productData.imageUrl || apiData.imageUrl,
      scanDate: new Date().toISOString(),
      upc: productData.upc
    };
    
    // Aynı ürün varsa güncelle, yoksa ekle
    const existingIndex = history.findIndex(item => item.url === historyItem.url || item.upc === historyItem.upc);
    
    if (existingIndex !== -1) {
      history[existingIndex] = historyItem;
    } else {
      // En başa ekle ve maksimum 20 öğe tut
      history.unshift(historyItem);
      if (history.length > 20) {
        history.pop();
      }
    }
    
    chrome.storage.local.set({ scanHistory: history }, () => {
      loadHistory();
    });
  });
}

// Toast mesajı göster
function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  
  document.body.appendChild(toast);
  
  // CSS ekle
  const style = document.createElement('style');
  style.textContent = `
    .toast {
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      background-color: var(--primary-color);
      color: white;
      padding: 8px 16px;
      border-radius: 4px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      font-size: 14px;
      z-index: 1000;
      animation: fadeIn 0.3s, fadeOut 0.3s 2.7s;
    }
    
    @keyframes fadeIn {
      from { opacity: 0; transform: translate(-50%, 20px); }
      to { opacity: 1; transform: translate(-50%, 0); }
    }
    
    @keyframes fadeOut {
      from { opacity: 1; transform: translate(-50%, 0); }
      to { opacity: 0; transform: translate(-50%, 20px); }
    }
  `;
  
  document.head.appendChild(style);
  
  // 3 saniye sonra kaldır
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

// Tarih formatla
function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('tr-TR', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

// Sayfa yüklendiğinde
document.addEventListener('DOMContentLoaded', () => {
  // Sekme geçişlerini ayarla
  setupTabs();
  
  // Ayarları yükle
  loadSettings();
  
  // Geçmişi yükle
  loadHistory();
  
  // Event listener'ları ekle
  document.getElementById('scan-button').addEventListener('click', scanCurrentProduct);
  
  document.getElementById('reset-settings').addEventListener('click', () => {
    if (confirm('Ayarları sıfırlamak istediğinize emin misiniz?')) {
      resetSettings();
    }
  });
  
  // Ayar değişikliklerini kaydet
  const settingInputs = [
    'api-endpoint',
    'track-price-history',
    'show-similar-products',
    'notify-price-drops'
  ];
  
  settingInputs.forEach(id => {
    const element = document.getElementById(id);
    if (element) {
      element.addEventListener('change', saveSettings);
    }
  });
  
  // Aktif sekmeyi kontrol et
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const activeTab = tabs[0];
    
    if (activeTab.url.includes('walmart.com')) {
      // Walmart sayfasında ise scan butonunu etkinleştir
      document.getElementById('scan-button').disabled = false;
    } else {
      updateStatus('Walmart Değil', 'Tarama yapmak için bir Walmart ürün sayfasına gidin.');
    }
  });
});

// Walmart Ürün Tarama İşlevleri
async function scanCurrentPage() {
  // Tarama başlamadan önce UI güncellemesi
  const scanButton = document.getElementById('scan-button');
  const statusTitle = document.getElementById('status-title');
  const statusMessage = document.getElementById('status-message');
  const statusIcon = document.getElementById('status-icon');
  const resultContainer = document.getElementById('result-container');
  
  scanButton.disabled = true;
  statusTitle.textContent = 'Taranıyor...';
  statusMessage.textContent = 'Ürün bilgileri alınıyor, lütfen bekleyin';
  statusIcon.innerHTML = `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <animateTransform attributeName="transform" attributeType="XML" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/>
      </path>
    </svg>
  `;
  statusIcon.style.color = 'var(--primary-color)';
  
  try {
    // Mevcut sekmenin URL'sini al
    const tabs = await new Promise(resolve => chrome.tabs.query({ active: true, currentWindow: true }, resolve));
    const currentTab = tabs[0];
    const url = currentTab.url;
    
    // API'ye ürün tarama isteği gönder
    const result = await API.scanWalmartProduct(url);
    
    if (!result) {
      throw new Error('Ürün verileri alınamadı');
    }
    
    // Başarılı tarama durumunda UI güncelleme
    statusTitle.textContent = 'Tarama Tamamlandı';
    statusMessage.textContent = 'Ürün bilgileri başarıyla alındı';
    statusIcon.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M9 12l2 2 4-4M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    `;
    statusIcon.style.color = 'var(--success-color)';
    
    // Sonuçları görüntüle
    displayWalmartProductResults(result);
    
    // Karşılaştırma butonunu etkinleştir
    document.getElementById('compare-button').disabled = false;
    
    // Geçmişe ekle
    addToHistory({
      id: result.product_id,
      title: result.title,
      price: result.current_price,
      image: result.image_url,
      url: url,
      source: 'Walmart',
      timestamp: Date.now()
    });
    
  } catch (error) {
    console.error('Tarama hatası:', error);
    
    statusTitle.textContent = 'Tarama Başarısız';
    statusMessage.textContent = `Hata: ${error.message}`;
    statusIcon.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 8v4M12 16h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    `;
    statusIcon.style.color = 'var(--danger-color)';
  } finally {
    scanButton.disabled = false;
  }
}

function displayWalmartProductResults(data) {
  const resultContainer = document.getElementById('result-container');
  resultContainer.style.display = 'block';
  
  // Basit bir sonuç görünümü oluştur
  resultContainer.innerHTML = `
    <div class="result-item">
      <div class="result-header">
        <img src="${data.image_url}" alt="${data.title}" class="result-image">
        <div>
          <div class="result-title">${data.title}</div>
          <div class="result-price">
            $${data.current_price.toFixed(2)}
            ${data.original_price > data.current_price ? 
              `<span class="original">$${data.original_price.toFixed(2)}</span>` : ''}
          </div>
          <div class="result-meta">
            ${data.availability ? 
              '<span class="result-badge success">Stokta</span>' : 
              '<span class="result-badge warning">Stokta Değil</span>'}
            ${data.rating ? 
              `<span class="result-badge">${data.rating}★ (${data.review_count})</span>` : ''}
          </div>
        </div>
      </div>
      
      <table class="result-info-table">
        <tr>
          <td>Ürün ID</td>
          <td>${data.product_id}</td>
        </tr>
        <tr>
          <td>UPC</td>
          <td>${data.upc || 'Belirtilmemiş'}</td>
        </tr>
        <tr>
          <td>Marka</td>
          <td>${data.brand || 'Belirtilmemiş'}</td>
        </tr>
        <tr>
          <td>Model</td>
          <td>${data.model || 'Belirtilmemiş'}</td>
        </tr>
        <tr>
          <td>Kategori</td>
          <td>${data.category || 'Belirtilmemiş'}</td>
        </tr>
      </table>
      
      <div class="result-actions">
        <button class="result-action-button" data-action="copy-info">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 5H6C4.89543 5 4 5.89543 4 7V19C4 20.1046 4.89543 21 6 21H16C17.1046 21 18 20.1046 18 19V17M8 5C8 6.10457 8.89543 7 10 7H12C13.1046 7 14 6.10457 14 5M8 5C8 3.89543 8.89543 3 10 3H12C13.1046 3 14 3.89543 14 5M14 5H16C17.1046 5 18 5.89543 18 7V10M20 14H10M10 14L13 11M10 14L13 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Bilgileri Kopyala
        </button>
        <button class="result-action-button" data-action="open-url">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 6H6C4.89543 6 4 6.89543 4 8V18C4 19.1046 4.89543 20 6 20H16C17.1046 20 18 19.1046 18 18V14M14 4H20M20 4V10M20 4L10 14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Ürünü Aç
        </button>
      </div>
    </div>
  `;
  
  // Bilgileri kopyalama butonu
  resultContainer.querySelector('[data-action="copy-info"]').addEventListener('click', () => {
    const infoText = `
      ${data.title}
      Fiyat: $${data.current_price.toFixed(2)}
      Ürün ID: ${data.product_id}
      UPC: ${data.upc || 'Belirtilmemiş'}
      Marka: ${data.brand || 'Belirtilmemiş'}
      Model: ${data.model || 'Belirtilmemiş'}
      URL: ${data.url}
    `.trim();
    
    navigator.clipboard.writeText(infoText)
      .then(() => showToast('Ürün bilgileri kopyalandı'))
      .catch(err => showError('Kopyalama başarısız: ' + err));
  });
  
  // Ürünü açma butonu
  resultContainer.querySelector('[data-action="open-url"]').addEventListener('click', () => {
    chrome.tabs.create({ url: data.url });
  });
}

async function compareProducts() {
  // Karşılaştırma mantığı burada olacak
  showToast('Karşılaştırma işlevi geliştiriliyor');
}

// Amazon Ürün Tarama İşlevleri
async function analyzeAmazonUrl() {
  const amazonUrl = document.getElementById('amazon-url').value.trim();
  
  if (!amazonUrl) {
    showError('Lütfen bir Amazon ürün URL\'si girin');
    return;
  }
  
  if (!amazonUrl.includes('amazon.com')) {
    showError('Geçerli bir Amazon ürün URL\'si girin');
    return;
  }
  
  try {
    const resultContainer = document.getElementById('amazon-result-container');
    resultContainer.style.display = 'block';
    resultContainer.innerHTML = '<p>Ürün analiz ediliyor, lütfen bekleyin...</p>';
    
    const result = await API.scanAmazonProduct(amazonUrl);
    
    if (!result) {
      throw new Error('Ürün verileri alınamadı');
    }
    
    displayAmazonProductResults(result);
    
    // Geçmişe ekle
    addToHistory({
      id: result.product_id,
      title: result.title,
      price: result.current_price,
      image: result.image_url,
      url: amazonUrl,
      source: 'Amazon',
      timestamp: Date.now()
    });
    
  } catch (error) {
    console.error('Amazon tarama hatası:', error);
    document.getElementById('amazon-result-container').innerHTML = `
      <p>Hata: ${error.message}</p>
    `;
  }
}

async function scanAmazonPage() {
  try {
    const tabs = await new Promise(resolve => chrome.tabs.query({ active: true, currentWindow: true }, resolve));
    const currentTab = tabs[0];
    const url = currentTab.url;
    
    if (!url.includes('amazon.com')) {
      showError('Bu sayfa bir Amazon ürün sayfası değil');
      return;
    }
    
    const resultContainer = document.getElementById('amazon-result-container');
    resultContainer.style.display = 'block';
    resultContainer.innerHTML = '<p>Ürün analiz ediliyor, lütfen bekleyin...</p>';
    
    const result = await API.scanAmazonProduct(url);
    
    if (!result) {
      throw new Error('Ürün verileri alınamadı');
    }
    
    displayAmazonProductResults(result);
    
    // Geçmişe ekle
    addToHistory({
      id: result.product_id,
      title: result.title,
      price: result.current_price,
      image: result.image_url,
      url: url,
      source: 'Amazon',
      timestamp: Date.now()
    });
    
  } catch (error) {
    console.error('Amazon tarama hatası:', error);
    document.getElementById('amazon-result-container').innerHTML = `
      <p>Hata: ${error.message}</p>
    `;
  }
}

function displayAmazonProductResults(data) {
  const resultContainer = document.getElementById('amazon-result-container');
  
  // Amazon sonuç görünümü oluştur
  resultContainer.innerHTML = `
    <div class="result-item">
      <div class="result-header">
        <img src="${data.image_url}" alt="${data.title}" class="result-image">
        <div>
          <div class="result-title">${data.title}</div>
          <div class="result-price">
            $${data.current_price.toFixed(2)}
            ${data.original_price > data.current_price ? 
              `<span class="original">$${data.original_price.toFixed(2)}</span>` : ''}
          </div>
          <div class="result-meta">
            ${data.availability ? 
              '<span class="result-badge success">Stokta</span>' : 
              '<span class="result-badge warning">Stokta Değil</span>'}
            ${data.rating ? 
              `<span class="result-badge">${data.rating}★ (${data.review_count})</span>` : ''}
          </div>
        </div>
      </div>
      
      <table class="result-info-table">
        <tr>
          <td>ASIN</td>
          <td>${data.product_id}</td>
        </tr>
        <tr>
          <td>Marka</td>
          <td>${data.brand || 'Belirtilmemiş'}</td>
        </tr>
        <tr>
          <td>Satıcı</td>
          <td>${data.seller || 'Amazon'}</td>
        </tr>
        <tr>
          <td>Kargo</td>
          <td>${data.shipping || 'Belirtilmemiş'}</td>
        </tr>
      </table>
      
      <div class="result-actions">
        <button class="result-action-button" data-action="copy-info">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 5H6C4.89543 5 4 5.89543 4 7V19C4 20.1046 4.89543 21 6 21H16C17.1046 21 18 20.1046 18 19V17M8 5C8 6.10457 8.89543 7 10 7H12C13.1046 7 14 6.10457 14 5M8 5C8 3.89543 8.89543 3 10 3H12C13.1046 3 14 3.89543 14 5M14 5H16C17.1046 5 18 5.89543 18 7V10M20 14H10M10 14L13 11M10 14L13 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Bilgileri Kopyala
        </button>
        <button class="result-action-button" data-action="compare-walmart">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 16H7C5.34315 16 4 14.6569 4 13V6C4 4.34315 5.34315 3 7 3H14C15.6569 3 17 4.34315 17 6V8M14 21H17C18.6569 21 20 19.6569 20 18V11C20 9.34315 18.6569 8 17 8H10C8.34315 8 7 9.34315 7 11V13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Walmart'ta Bul
        </button>
      </div>
    </div>
  `;
  
  // Bilgileri kopyalama butonu
  resultContainer.querySelector('[data-action="copy-info"]').addEventListener('click', () => {
    const infoText = `
      ${data.title}
      Fiyat: $${data.current_price.toFixed(2)}
      ASIN: ${data.product_id}
      Marka: ${data.brand || 'Belirtilmemiş'}
      Satıcı: ${data.seller || 'Amazon'}
      URL: ${data.url}
    `.trim();
    
    navigator.clipboard.writeText(infoText)
      .then(() => showToast('Ürün bilgileri kopyalandı'))
      .catch(err => showError('Kopyalama başarısız: ' + err));
  });
  
  // Walmart'ta arama butonu
  resultContainer.querySelector('[data-action="compare-walmart"]').addEventListener('click', () => {
    const searchQuery = encodeURIComponent(data.title);
    chrome.tabs.create({ url: `https://www.walmart.com/search?q=${searchQuery}` });
  });
}

// UPC Arama İşlevleri
async function searchByUpc() {
  const upcInput = document.getElementById('upc-input').value.trim();
  
  if (!upcInput) {
    showError('Lütfen bir UPC kodu girin');
    return;
  }
  
  // Basit UPC doğrulama (12 veya 13 haneli sayı)
  if (!/^\d{12,13}$/.test(upcInput)) {
    showError('Geçerli bir UPC kodu girin (12 veya 13 haneli)');
    return;
  }
  
  try {
    const resultContainer = document.getElementById('upc-result-container');
    resultContainer.style.display = 'block';
    resultContainer.innerHTML = '<p>UPC araması yapılıyor, lütfen bekleyin...</p>';
    
    const result = await API.searchByUpc(upcInput);
    
    if (!result || !result.items || result.items.length === 0) {
      resultContainer.innerHTML = '<p>Bu UPC için ürün bulunamadı</p>';
      return;
    }
    
    displayUpcSearchResults(result);
    
  } catch (error) {
    console.error('UPC arama hatası:', error);
    document.getElementById('upc-result-container').innerHTML = `
      <p>Hata: ${error.message}</p>
    `;
  }
}

function displayUpcSearchResults(data) {
  const resultContainer = document.getElementById('upc-result-container');
  resultContainer.innerHTML = '';
  
  // Bulunan ürünleri listele
  data.items.forEach(item => {
    const resultItem = document.createElement('div');
    resultItem.className = 'result-item';
    
    resultItem.innerHTML = `
      <div class="result-header">
        <img src="${item.image_url}" alt="${item.title}" class="result-image">
        <div>
          <div class="result-title">${item.title}</div>
          <div class="result-price">
            $${item.current_price.toFixed(2)}
            ${item.original_price > item.current_price ? 
              `<span class="original">$${item.original_price.toFixed(2)}</span>` : ''}
          </div>
          <div class="result-meta">
            ${item.availability ? 
              '<span class="result-badge success">Stokta</span>' : 
              '<span class="result-badge warning">Stokta Değil</span>'}
            ${item.rating ? 
              `<span class="result-badge">${item.rating}★ (${item.review_count})</span>` : ''}
          </div>
        </div>
      </div>
      
      <div class="result-actions">
        <button class="result-action-button" data-action="open-url" data-url="${item.url}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 6H6C4.89543 6 4 6.89543 4 8V18C4 19.1046 4.89543 20 6 20H16C17.1046 20 18 19.1046 18 18V14M14 4H20M20 4V10M20 4L10 14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Ürünü Aç
        </button>
        <button class="result-action-button" data-action="view-details" data-product-id="${item.product_id}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Detayları Gör
        </button>
      </div>
    `;
    
    resultContainer.appendChild(resultItem);
  });
  
  // "Ürünü Aç" butonlarına tıklama olayı ekle
  resultContainer.querySelectorAll('[data-action="open-url"]').forEach(button => {
    button.addEventListener('click', () => {
      chrome.tabs.create({ url: button.dataset.url });
    });
  });
  
  // "Detayları Gör" butonlarına tıklama olayı ekle
  resultContainer.querySelectorAll('[data-action="view-details"]').forEach(button => {
    button.addEventListener('click', async () => {
      try {
        const productId = button.dataset.productId;
        const productDetails = await API.getProductDetails(productId);
        
        if (productDetails) {
          // Ürün detaylarını göster
          displayProductDetails(productDetails);
          
          // Geçmişe ekle
          addToHistory({
            id: productDetails.product_id,
            title: productDetails.title,
            price: productDetails.current_price,
            image: productDetails.image_url,
            url: productDetails.url,
            source: 'Walmart',
            timestamp: Date.now()
          });
        }
      } catch (error) {
        console.error('Ürün detay hatası:', error);
        showError('Ürün detayları alınamadı');
      }
    });
  });
}

// Varyasyon Bulma İşlevleri
async function findVariationsByUrl() {
  const variationsUrl = document.getElementById('variations-url').value.trim();
  
  if (!variationsUrl) {
    showError('Lütfen bir Walmart ürün URL\'si girin');
    return;
  }
  
  if (!variationsUrl.includes('walmart.com') || (!variationsUrl.includes('/ip/') && !variationsUrl.includes('/product/'))) {
    showError('Geçerli bir Walmart ürün URL\'si girin');
    return;
  }
  
  try {
    const resultContainer = document.getElementById('variations-result-container');
    resultContainer.style.display = 'block';
    resultContainer.innerHTML = '<p>Varyasyonlar aranıyor, lütfen bekleyin...</p>';
    
    const result = await API.getProductVariations(variationsUrl);
    
    if (!result || !result.variants || result.variants.length === 0) {
      resultContainer.innerHTML = '<p>Bu ürün için varyasyon bulunamadı</p>';
      return;
    }
    
    displayVariationResults(result);
    
  } catch (error) {
    console.error('Varyasyon bulma hatası:', error);
    document.getElementById('variations-result-container').innerHTML = `
      <p>Hata: ${error.message}</p>
    `;
  }
}

async function findVariationsForCurrentPage() {
  try {
    const tabs = await new Promise(resolve => chrome.tabs.query({ active: true, currentWindow: true }, resolve));
    const currentTab = tabs[0];
    const url = currentTab.url;
    
    if (!url.includes('walmart.com') || (!url.includes('/ip/') && !url.includes('/product/'))) {
      showError('Bu sayfa bir Walmart ürün sayfası değil');
      return;
    }
    
    const resultContainer = document.getElementById('variations-result-container');
    resultContainer.style.display = 'block';
    resultContainer.innerHTML = '<p>Varyasyonlar aranıyor, lütfen bekleyin...</p>';
    
    const result = await API.getProductVariations(url);
    
    if (!result || !result.variants || result.variants.length === 0) {
      resultContainer.innerHTML = '<p>Bu ürün için varyasyon bulunamadı</p>';
      return;
    }
    
    displayVariationResults(result);
    
  } catch (error) {
    console.error('Varyasyon bulma hatası:', error);
    document.getElementById('variations-result-container').innerHTML = `
      <p>Hata: ${error.message}</p>
    `;
  }
}

function displayVariationResults(data) {
  const resultContainer = document.getElementById('variations-result-container');
  resultContainer.innerHTML = '';
  
  // Ana ürün bilgisi
  const mainProductItem = document.createElement('div');
  mainProductItem.className = 'result-item';
  
  mainProductItem.innerHTML = `
    <div class="result-header">
      <img src="${data.main_product.image_url}" alt="${data.main_product.title}" class="result-image">
      <div>
        <div class="result-title">${data.main_product.title}</div>
        <div class="result-price">
          $${data.main_product.current_price.toFixed(2)}
        </div>
        <div class="result-meta">
          <span class="result-badge">Ana Ürün</span>
        </div>
      </div>
    </div>
  `;
  
  resultContainer.appendChild(mainProductItem);
  
  // Varyasyon gruplarını göster
  if (data.variation_types && data.variation_types.length > 0) {
    const variationTypesDiv = document.createElement('div');
    variationTypesDiv.className = 'variation-types';
    variationTypesDiv.innerHTML = `
      <p>Varyasyon Türleri: ${data.variation_types.join(', ')}</p>
    `;
    resultContainer.appendChild(variationTypesDiv);
  }
  
  // Varyasyonları listele
  data.variants.forEach(variant => {
    const variantItem = document.createElement('div');
    variantItem.className = 'result-item';
    
    // Farklılıkları belirle
    const differences = [];
    data.variation_types.forEach(type => {
      if (variant[type] && data.main_product[type] !== variant[type]) {
        differences.push(`${type}: ${variant[type]}`);
      }
    });
    
    // Fiyat farkını hesapla
    const priceDiff = variant.current_price - data.main_product.current_price;
    const priceDiffText = priceDiff === 0 ? 'Aynı Fiyat' : 
                         (priceDiff > 0 ? `+$${priceDiff.toFixed(2)}` : `-$${Math.abs(priceDiff).toFixed(2)}`);
    
    variantItem.innerHTML = `
      <div class="result-header">
        <img src="${variant.image_url}" alt="${variant.title}" class="result-image">
        <div>
          <div class="result-title">${variant.title}</div>
          <div class="result-price">
            $${variant.current_price.toFixed(2)}
            <span class="price-diff">(${priceDiffText})</span>
          </div>
          <div class="result-meta">
            ${differences.map(diff => `<span class="result-badge">${diff}</span>`).join('')}
          </div>
        </div>
      </div>
      
      <div class="result-actions">
        <button class="result-action-button" data-action="open-url" data-url="${variant.url}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 6H6C4.89543 6 4 6.89543 4 8V18C4 19.1046 4.89543 20 6 20H16C17.1046 20 18 19.1046 18 18V14M14 4H20M20 4V10M20 4L10 14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Varyasyonu Aç
        </button>
      </div>
    `;
    
    resultContainer.appendChild(variantItem);
  });
  
  // "Varyasyonu Aç" butonlarına tıklama olayı ekle
  resultContainer.querySelectorAll('[data-action="open-url"]').forEach(button => {
    button.addEventListener('click', () => {
      chrome.tabs.create({ url: button.dataset.url });
    });
  });
}

// Toplu İşlem Fonksiyonları
async function startBatchProcess() {
  const batchType = document.getElementById('batch-type').value;
  const batchInput = document.getElementById('batch-input').value.trim();
  
  if (!batchInput) {
    showError('Lütfen işlenecek öğeleri girin');
    return;
  }
  
  // Girdiyi satırlara böl ve boş satırları temizle
  const items = batchInput.split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0);
  
  if (items.length === 0) {
    showError('Geçerli öğe bulunamadı');
    return;
  }
  
  // UI güncellemesi
  const progressContainer = document.querySelector('.progress-container');
  const progressBar = document.getElementById('batch-progress');
  const progressText = document.getElementById('batch-progress-text');
  const resultContainer = document.getElementById('batch-result-container');
  
  progressContainer.style.display = 'block';
  progressBar.style.width = '0%';
  progressText.textContent = `0/${items.length} işlendi`;
  resultContainer.style.display = 'block';
  resultContainer.innerHTML = '<p>Toplu işlem başlatılıyor...</p>';
  
  try {
    // API'ye toplu işlem isteği gönder
    const result = await API.processBatch(batchType, items);
    
    if (!result) {
      throw new Error('Toplu işlem sonuçları alınamadı');
    }
    
    // İşlem tamamlandı
    progressBar.style.width = '100%';
    progressText.textContent = `${items.length}/${items.length} işlendi`;
    
    displayBatchResults(result);
    
  } catch (error) {
    console.error('Toplu işlem hatası:', error);
    resultContainer.innerHTML = `
      <p>Hata: ${error.message}</p>
    `;
    progressContainer.style.display = 'none';
  }
}

function displayBatchResults(data) {
  const resultContainer = document.getElementById('batch-result-container');
  
  // Özet bilgileri göster
  const summaryDiv = document.createElement('div');
  summaryDiv.className = 'batch-summary';
  summaryDiv.innerHTML = `
    <h3>İşlem Özeti</h3>
    <p>Toplam: ${data.total} | Başarılı: ${data.success_count} | Hata: ${data.error_count}</p>
  `;
  
  resultContainer.innerHTML = '';
  resultContainer.appendChild(summaryDiv);
  
  // Başarılı sonuçları göster
  if (data.results && data.results.length > 0) {
    const resultsDiv = document.createElement('div');
    resultsDiv.className = 'batch-results';
    
    data.results.forEach(item => {
      const resultItem = document.createElement('div');
      resultItem.className = 'result-item';
      
      resultItem.innerHTML = `
        <div class="result-header">
          <img src="${item.image_url}" alt="${item.title}" class="result-image">
          <div>
            <div class="result-title">${item.title}</div>
            <div class="result-price">$${item.current_price.toFixed(2)}</div>
          </div>
        </div>
        <div class="result-actions">
          <button class="result-action-button" data-action="open-url" data-url="${item.url}">
            Ürünü Aç
          </button>
        </div>
      `;
      
      resultsDiv.appendChild(resultItem);
    });
    
    resultContainer.appendChild(resultsDiv);
  }
  
  // Hataları göster
  if (data.errors && data.errors.length > 0) {
    const errorsDiv = document.createElement('div');
    errorsDiv.className = 'batch-errors';
    errorsDiv.innerHTML = '<h3>Hatalar</h3>';
    
    data.errors.forEach(error => {
      const errorItem = document.createElement('div');
      errorItem.className = 'error-item';
      errorItem.innerHTML = `
        <p><strong>${error.input}</strong>: ${error.error}</p>
      `;
      
      errorsDiv.appendChild(errorItem);
    });
    
    resultContainer.appendChild(errorsDiv);
  }
  
  // Dışa aktarma butonu ekle
  const exportButton = document.createElement('button');
  exportButton.className = 'primary-button';
  exportButton.style.marginTop = '16px';
  exportButton.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 10v6m0 0l-3-3m3 3l3-3M3 17v3a2 2 0 002 2h14a2 2 0 002-2v-3M14 7V4a2 2 0 00-2-2H7a2 2 0 00-2 2v3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    Sonuçları Dışa Aktar (CSV)
  `;
  
  exportButton.addEventListener('click', () => {
    exportBatchResults(data);
  });
  
  resultContainer.appendChild(exportButton);
  
  // "Ürünü Aç" butonlarına tıklama olayı ekle
  resultContainer.querySelectorAll('[data-action="open-url"]').forEach(button => {
    button.addEventListener('click', () => {
      chrome.tabs.create({ url: button.dataset.url });
    });
  });
}

function exportBatchResults(data) {
  // CSV başlık satırı
  let csvContent = "Title,Price,URL,Product ID,UPC,Brand\n";
  
  // Her ürün için CSV satırı ekle
  data.results.forEach(item => {
    const row = [
      `"${item.title.replace(/"/g, '""')}"`, // Çift tırnak içindeki çift tırnakları kaçış
      item.current_price,
      `"${item.url}"`,
      item.product_id,
      item.upc || '',
      item.brand || ''
    ];
    
    csvContent += row.join(',') + '\n';
  });
  
  // CSV dosyasını indir
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  
  link.setAttribute('href', url);
  link.setAttribute('download', 'batch_results.csv');
  link.style.visibility = 'hidden';
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// Ürün Detayları Görüntüleme
function displayProductDetails(product) {
  // Ürün detay görünümünü buraya ekle
  // Bu fonksiyon, geçmiş öğelerine tıkladığınızda veya detay görüntüleme istediğinizde çağrılır
  showToast('Ürün detayları görüntüleniyor');
} 