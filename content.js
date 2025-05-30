// content.js - Walmart sayfalarında çalışacak script

// Sayfanın Walmart ürün sayfası olup olmadığını kontrol et
function isProductPage() {
  return window.location.href.includes('/ip/') || 
         document.querySelector('[data-testid="product-title"]') !== null;
}

// Sayfadan ürün bilgilerini çıkart
function extractProductData() {
  try {
    const productData = {
      url: window.location.href,
      title: '',
      price: '',
      upc: '',
      imageUrl: '',
      brand: '',
      category: ''
    };
    
    // Başlık
    const titleElement = document.querySelector('[data-testid="product-title"]') || 
                        document.querySelector('.prod-ProductTitle');
    if (titleElement) {
      productData.title = titleElement.textContent.trim();
    }
    
    // Fiyat
    const priceElement = document.querySelector('[data-testid="price-value"]') || 
                         document.querySelector('.prod-PriceSection');
    if (priceElement) {
      const priceText = priceElement.textContent.trim();
      // Fiyat metninden sadece sayısal değeri çıkart
      const priceMatch = priceText.match(/\$?([\d,.]+)/);
      if (priceMatch && priceMatch[1]) {
        productData.price = priceMatch[1].replace(/,/g, '');
      }
    }
    
    // Ürün Resmi
    const imageElement = document.querySelector('[data-testid="hero-image"]') || 
                         document.querySelector('.prod-HeroImage img');
    if (imageElement && imageElement.src) {
      productData.imageUrl = imageElement.src;
    }
    
    // UPC Kodu
    // Genelde sayfa kaynak kodunda veya gizli meta etiketlerinde bulunur
    const pageSource = document.documentElement.innerHTML;
    const upcMatch = pageSource.match(/"upc":"([0-9]+)"/);
    if (upcMatch && upcMatch[1]) {
      productData.upc = upcMatch[1];
    }
    
    // Marka
    const brandElement = document.querySelector('[data-testid="product-brand"]') || 
                         document.querySelector('.prod-BrandName');
    if (brandElement) {
      productData.brand = brandElement.textContent.trim();
    }
    
    // Kategori - genelde breadcrumb'dan alınabilir
    const breadcrumbs = document.querySelectorAll('.breadcrumb span');
    if (breadcrumbs.length > 0) {
      productData.category = Array.from(breadcrumbs)
                               .map(crumb => crumb.textContent.trim())
                               .filter(text => text !== '>' && text !== '')
                               .join(' > ');
    }
    
    return productData;
    
  } catch (error) {
    console.error('Ürün verisi çıkarma hatası:', error);
    return null;
  }
}

// Overlay UI bileşeni ekle
function createOverlayUI() {
  // Varolan overlay'i kaldır
  const existingOverlay = document.getElementById('walmart-scanner-overlay');
  if (existingOverlay) {
    existingOverlay.remove();
  }
  
  // Yeni overlay oluştur
  const overlay = document.createElement('div');
  overlay.id = 'walmart-scanner-overlay';
  overlay.innerHTML = `
    <div class="scanner-header">
      <img src="${chrome.runtime.getURL('icons/icon48.png')}" alt="Logo" class="scanner-logo">
      <h3>Walmart Ürün Tarayıcı</h3>
      <button id="close-scanner" aria-label="Kapat">✕</button>
    </div>
    <div class="scanner-content">
      <div id="scanner-loading">
        <div class="spinner"></div>
        <p>Ürün taranıyor...</p>
      </div>
      <div id="scanner-results" style="display: none;"></div>
      <div id="scanner-error" style="display: none;">
        <p>Hata oluştu. Tekrar deneyin.</p>
      </div>
    </div>
    <div class="scanner-footer">
      <button id="scan-button">Ürünü Tara</button>
    </div>
  `;
  
  document.body.appendChild(overlay);
  
  // Stil ekle
  const style = document.createElement('style');
  style.textContent = `
    #walmart-scanner-overlay {
      position: fixed;
      top: 20px;
      right: 20px;
      width: 350px;
      background: white;
      border-radius: 10px;
      box-shadow: 0 0 20px rgba(0,0,0,0.2);
      z-index: 9999;
      font-family: Arial, sans-serif;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .scanner-header {
      display: flex;
      align-items: center;
      padding: 10px 15px;
      background: #0071dc;
      color: white;
    }
    .scanner-logo {
      width: 24px;
      height: 24px;
      margin-right: 10px;
    }
    .scanner-header h3 {
      flex: 1;
      margin: 0;
      font-size: 16px;
    }
    #close-scanner {
      background: none;
      border: none;
      color: white;
      font-size: 18px;
      cursor: pointer;
    }
    .scanner-content {
      padding: 15px;
      max-height: 400px;
      overflow-y: auto;
    }
    .scanner-footer {
      padding: 10px 15px;
      border-top: 1px solid #eee;
      text-align: right;
    }
    #scan-button {
      background: #0071dc;
      color: white;
      border: none;
      padding: 8px 15px;
      border-radius: 4px;
      cursor: pointer;
    }
    .spinner {
      width: 30px;
      height: 30px;
      border: 3px solid #eee;
      border-top: 3px solid #0071dc;
      border-radius: 50%;
      margin: 10px auto;
      animation: spin 1s linear infinite;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `;
  
  document.head.appendChild(style);
  
  // Event listener'ları ekle
  document.getElementById('close-scanner').addEventListener('click', () => {
    overlay.remove();
  });
  
  document.getElementById('scan-button').addEventListener('click', () => {
    scanCurrentProduct();
  });
  
  return overlay;
}

// Ürün tarama işlemini yap
function scanCurrentProduct() {
  if (!isProductPage()) {
    alert('Bu sayfa bir Walmart ürün sayfası değil.');
    return;
  }
  
  const productData = extractProductData();
  if (!productData) {
    showError('Ürün bilgileri çıkarılamadı.');
    return;
  }
  
  // Tarama başlat
  const resultsDiv = document.getElementById('scanner-results');
  const loadingDiv = document.getElementById('scanner-loading');
  const errorDiv = document.getElementById('scanner-error');
  
  resultsDiv.style.display = 'none';
  errorDiv.style.display = 'none';
  loadingDiv.style.display = 'block';
  
  // Background script'e mesaj gönder
  chrome.runtime.sendMessage(
    { action: 'scanProduct', productData },
    response => {
      loadingDiv.style.display = 'none';
      
      if (response && response.success) {
        displayResults(response.data);
        resultsDiv.style.display = 'block';
      } else {
        showError(response?.error || 'Bilinmeyen hata');
        errorDiv.style.display = 'block';
      }
    }
  );
}

// Sonuçları göster
function displayResults(data) {
  const resultsDiv = document.getElementById('scanner-results');
  
  if (!data || Object.keys(data).length === 0) {
    resultsDiv.innerHTML = '<p>Ürün hakkında bilgi bulunamadı.</p>';
    return;
  }
  
  let html = `
    <div class="product-info">
      <h4>${data.title || 'Ürün'}</h4>
      <div class="price-info">
        <span class="current-price">$${data.currentPrice || 'N/A'}</span>
  `;
  
  if (data.priceHistory && data.priceHistory.length > 0) {
    const lowestPrice = Math.min(...data.priceHistory.map(p => p.price));
    html += `
      <span class="lowest-price">En Düşük: $${lowestPrice.toFixed(2)}</span>
    `;
  }
  
  html += `</div>`;
  
  // Fiyat değişim grafiği eklenebilir
  
  // Benzer ürünler
  if (data.similarProducts && data.similarProducts.length > 0) {
    html += `
      <div class="similar-products">
        <h5>Benzer Ürünler</h5>
        <div class="product-list">
    `;
    
    data.similarProducts.slice(0, 3).forEach(product => {
      html += `
        <div class="similar-product">
          <img src="${product.imageUrl || ''}" alt="${product.title}">
          <div class="product-details">
            <p class="product-title">${product.title}</p>
            <p class="product-price">$${product.price}</p>
          </div>
        </div>
      `;
    });
    
    html += `
        </div>
      </div>
    `;
  }
  
  // Ek bilgiler
  if (data.additionalInfo) {
    html += `
      <div class="additional-info">
        <h5>Ürün Bilgileri</h5>
        <ul>
    `;
    
    for (const [key, value] of Object.entries(data.additionalInfo)) {
      html += `<li><strong>${key}:</strong> ${value}</li>`;
    }
    
    html += `
        </ul>
      </div>
    `;
  }
  
  html += `</div>`;
  
  resultsDiv.innerHTML = html;
  
  // Stil ekle
  const style = document.createElement('style');
  style.textContent = `
    .product-info h4 {
      margin-top: 0;
      margin-bottom: 10px;
    }
    .price-info {
      display: flex;
      align-items: center;
      margin-bottom: 15px;
    }
    .current-price {
      font-size: 18px;
      font-weight: bold;
      color: #0071dc;
      margin-right: 10px;
    }
    .lowest-price {
      font-size: 14px;
      color: #ff5722;
    }
    .similar-products {
      margin-top: 15px;
    }
    .similar-products h5 {
      margin-bottom: 10px;
    }
    .product-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .similar-product {
      display: flex;
      align-items: center;
      padding: 8px;
      border: 1px solid #eee;
      border-radius: 4px;
    }
    .similar-product img {
      width: 50px;
      height: 50px;
      object-fit: contain;
      margin-right: 10px;
    }
    .product-details {
      flex: 1;
    }
    .product-title {
      font-size: 14px;
      margin: 0 0 5px;
    }
    .product-price {
      font-size: 14px;
      font-weight: bold;
      margin: 0;
      color: #0071dc;
    }
    .additional-info {
      margin-top: 15px;
    }
    .additional-info h5 {
      margin-bottom: 10px;
    }
    .additional-info ul {
      padding-left: 20px;
      margin: 0;
    }
    .additional-info li {
      margin-bottom: 5px;
    }
  `;
  
  document.head.appendChild(style);
}

// Hata göster
function showError(errorMessage) {
  const errorDiv = document.getElementById('scanner-error');
  errorDiv.innerHTML = `<p>${errorMessage || 'Bilinmeyen hata oluştu. Tekrar deneyin.'}</p>`;
}

// Sayfa yüklendiğinde
window.addEventListener('load', () => {
  // Sadece Walmart ürün sayfalarında çalış
  if (isProductPage()) {
    // Sayfaya buton ekle
    const button = document.createElement('button');
    button.id = 'walmart-scanner-button';
    button.innerHTML = `
      <img src="${chrome.runtime.getURL('icons/icon16.png')}" alt="Tara">
      <span>Ürünü Tara</span>
    `;
    
    // Butonu sayfaya ekle (ürün bilgilerinin yanına)
    const addToCartBtn = document.querySelector('[data-testid="add-to-cart-btn"]');
    if (addToCartBtn && addToCartBtn.parentNode) {
      addToCartBtn.parentNode.appendChild(button);
    } else {
      // Alternatif ekleme
      const priceSection = document.querySelector('.prod-PriceSection');
      if (priceSection) {
        priceSection.parentNode.appendChild(button);
      } else {
        // En son alternatif
        document.body.appendChild(button);
        button.style.position = 'fixed';
        button.style.bottom = '20px';
        button.style.right = '20px';
      }
    }
    
    // Buton stili
    const style = document.createElement('style');
    style.textContent = `
      #walmart-scanner-button {
        display: flex;
        align-items: center;
        gap: 8px;
        background: #0071dc;
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        margin-top: 10px;
      }
      #walmart-scanner-button img {
        width: 16px;
        height: 16px;
      }
    `;
    document.head.appendChild(style);
    
    // Butona tıklandığında
    button.addEventListener('click', () => {
      createOverlayUI();
      scanCurrentProduct();
    });
  }
  
  // Sayfada pop-up mesajı göster
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'showNotification') {
      // Bildirim göster
      const notification = document.createElement('div');
      notification.className = 'walmart-scanner-notification';
      notification.innerHTML = `
        <div class="notification-content">
          <p>${request.message}</p>
        </div>
        <button class="notification-close">✕</button>
      `;
      
      document.body.appendChild(notification);
      
      // Bildirim stili
      const style = document.createElement('style');
      style.textContent = `
        .walmart-scanner-notification {
          position: fixed;
          bottom: 20px;
          right: 20px;
          background: white;
          border-left: 4px solid #0071dc;
          box-shadow: 0 2px 10px rgba(0,0,0,0.1);
          padding: 10px 15px;
          display: flex;
          align-items: center;
          z-index: 10000;
          max-width: 300px;
          animation: slideIn 0.3s forwards;
        }
        .notification-content {
          flex: 1;
        }
        .notification-close {
          background: none;
          border: none;
          cursor: pointer;
          font-size: 16px;
          color: #999;
        }
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `;
      document.head.appendChild(style);
      
      // Otomatik kapanma
      setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s forwards';
        setTimeout(() => notification.remove(), 300);
      }, 5000);
      
      // Manuel kapanma
      notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.remove();
      });
      
      sendResponse({ success: true });
    }
  });
}); 