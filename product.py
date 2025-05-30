import requests
import base64
import json
import uuid
import time
from typing import Dict, Optional, List
import re
import os

# Varsayılan kimlik bilgileri
DEFAULT_CLIENT_ID = "f0426720-c18d-4280-a07d-5e65562078de"
DEFAULT_CLIENT_SECRET = "AJLzeHoqmXLhcjuNKOuUrXdQdmpWjSF5tqP8-Yju4cAJZELxm7dAeQA6gDwthmNzT-4CSuFkQDbVjUZBpzOknRg"

class WalmartProScanner:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = 0
        
        # API endpoints
        self.auth_url = "https://marketplace.walmartapis.com/v3/token"
        self.search_url = "https://marketplace.walmartapis.com/v3/items/walmart/search"
        self.item_url = "https://marketplace.walmartapis.com/v3/items/walmart"
        self.taxonomy_url = "https://marketplace.walmartapis.com/v3/taxonomy"
        
    def get_access_token(self) -> bool:
        """OAuth 2.0 access token alma"""
        print("🔐 Token alınıyor...")
        try:
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'WM_QOS.CORRELATION_ID': str(uuid.uuid4()),
                'WM_SVC.NAME': 'Walmart Marketplace'
            }
            
            response = requests.post(self.auth_url, headers=headers,
                                   data='grant_type=client_credentials', timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = time.time() + expires_in - 60
                print("✅ Token başarıyla alındı!")
                return True
            else:
                print(f"❌ Token alma hatası: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Token hatası: {e}")
            return False
    
    def ensure_valid_token(self) -> bool:
        if not self.access_token or time.time() >= self.token_expires_at:
            return self.get_access_token()
        return True

    def get_headers(self):
        """Standard API headers"""
        return {
            'WM_SEC.ACCESS_TOKEN': self.access_token,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'WM_QOS.CORRELATION_ID': str(uuid.uuid4()),
            'WM_SVC.NAME': 'Walmart Marketplace',
            'WM_GLOBAL_VERSION': '3.1',
            'WM_MARKET': 'us'
        }

    def search_by_upc_advanced(self, upc: str) -> Optional[Dict]:
        """UPC ile gelişmiş arama - Multiple approaches"""
        if not self.ensure_valid_token():
            return None
            
        print(f"🔍 UPC '{upc}' için ADVANCED SEARCH yapılıyor...")
        
        all_results = {}
        
        # 1. UPC ile direkt arama
        try:
            params = {
                'upc': upc,
                'format': 'json',
                'numItems': 50,  # Daha fazla ürün
                'start': 1,
                'responseGroup': 'full'
            }
            
            response = requests.get(self.search_url, headers=self.get_headers(),
                                  params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                all_results['upc_search'] = data
                print(f"✅ UPC Search: {len(data.get('items', []))} ürün")
        except Exception as e:
            print(f"⚠️ UPC search hatası: {e}")
        
        # 2. GTIN ile arama (UPC alternatifi)
        try:
            params = {
                'gtin': upc,
                'format': 'json',
                'numItems': 25,
                'responseGroup': 'full'
            }
            
            response = requests.get(self.search_url, headers=self.get_headers(),
                                  params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                all_results['gtin_search'] = data
                print(f"✅ GTIN Search: {len(data.get('items', []))} ürün")
        except Exception as e:
            print(f"⚠️ GTIN search hatası: {e}")
        
        # 3. Query string ile arama
        try:
            params = {
                'query': upc,
                'format': 'json',
                'numItems': 25
            }
            
            response = requests.get(self.search_url, headers=self.get_headers(),
                                  params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                all_results['query_search'] = data
                print(f"✅ Query Search: {len(data.get('items', []))} ürün")
        except Exception as e:
            print(f"⚠️ Query search hatası: {e}")
        
        return all_results if all_results else None

    def get_item_details(self, item_id: str) -> Optional[Dict]:
        """Spesifik item detayları al"""
        if not self.ensure_valid_token():
            return None
            
        print(f"🔎 Item ID '{item_id}' detayları alınıyor...")
        
        try:
            response = requests.get(f"{self.item_url}/{item_id}",
                                  headers=self.get_headers(), timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Item detayları alındı!")
                return data
            else:
                print(f"❌ Item detay hatası: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Item detay hatası: {e}")
            return None

    def find_similar_by_brand_category(self, brand: str, category_path: str, exclude_id: str = None) -> List[Dict]:
        """Marka ve kategoriye göre benzer ürünler bul - Geliştirilmiş"""
        if not self.ensure_valid_token() or not brand:
            return []
            
        print(f"🎯 '{brand}' markasından benzer ürünler aranıyor...")
        
        # Sonuçları saklayacak liste
        all_similar = []
        
        try:
            # Kategoriden category ID çıkar
            category_id = self.extract_category_id(category_path)
            
            # 1. KATEGORİ + MARKA İLE ARAMA (En spesifik)
            if category_id:
                params = {
                    'query': brand,
                    'numItems': 30,
                    'format': 'json',
                    'categoryId': category_id,
                    'facet': 'on',
                    'facet.filter': f'brand:{brand}'
                }
                
                response = requests.get(self.search_url, headers=self.get_headers(),
                                      params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    # Mevcut ürünü çıkar
                    if exclude_id:
                        items = [item for item in items if item.get('itemId') != exclude_id]
                    
                    all_similar.extend(items)
                    print(f"✅ Kategori+Marka arama: {len(items)} benzer ürün bulundu")
            
            # Yeterince sonuç yoksa devam et
            if len(all_similar) < 10:
                # 2. MARKA + POPULER ARAMA TERİMLERİ
                search_terms = [
                    f"{brand} monitor",
                    f"{brand} display",
                    f"{brand} computer",
                    f"{brand} desktop",
                    f"{brand} laptop",
                ]
                
                # Ürün tipine göre arama terimlerini özelleştir
                if "monitor" in category_path.lower():
                    search_terms.extend([
                        f"{brand} gaming monitor",
                        f"{brand} curved monitor",
                        f"{brand} ultrawide"
                    ])
                elif "laptop" in category_path.lower():
                    search_terms.extend([
                        f"{brand} notebook",
                        f"{brand} gaming laptop",
                        f"{brand} ultrabook"
                    ])
                elif "desktop" in category_path.lower():
                    search_terms.extend([
                        f"{brand} desktop computer",
                        f"{brand} gaming desktop",
                        f"{brand} all-in-one"
                    ])
                
                # Her bir arama terimi için sorgu yap
                for term in search_terms[:3]:  # Sadece ilk 3 terimi kullan
                    if len(all_similar) >= 20:  # Yeterince sonuç varsa çık
                        break
                        
                    params = {
                        'query': term,
                        'numItems': 15,
                        'format': 'json',
                        'facet': 'on',
                        'facet.filter': f'brand:{brand}'
                    }
                    
                    response = requests.get(self.search_url, headers=self.get_headers(),
                                          params=params, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get('items', [])
                        
                        # Mevcut ürünü çıkar
                        if exclude_id:
                            items = [item for item in items if item.get('itemId') != exclude_id]
                        
                        # Zaten eklenen ürünleri filtrele
                        seen_ids = {item.get('itemId') for item in all_similar}
                        items = [item for item in items if item.get('itemId') not in seen_ids]
                        
                        all_similar.extend(items)
                        print(f"✅ '{term}' için {len(items)} benzer ürün bulundu")
            
            # 3. MARKA ANA SERİLERİ ARAMA
            if len(all_similar) < 15:
                common_series = self.get_brand_series(brand)
                
                for series in common_series:
                    if len(all_similar) >= 25:  # Yeterince sonuç varsa çık
                        break
                        
                    term = f"{brand} {series}"
                    params = {
                        'query': term,
                        'numItems': 10,
                        'format': 'json'
                    }
                    
                    response = requests.get(self.search_url, headers=self.get_headers(),
                                          params=params, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get('items', [])
                        
                        # Aynı markada olanlara filtrele
                        brand_items = [item for item in items if 
                                      item.get('brand', '').lower() == brand.lower() or
                                      brand.lower() in item.get('brand', '').lower()]
                        
                        # Mevcut ürünü çıkar
                        if exclude_id:
                            brand_items = [item for item in brand_items if item.get('itemId') != exclude_id]
                        
                        # Zaten eklenen ürünleri filtrele
                        seen_ids = {item.get('itemId') for item in all_similar}
                        brand_items = [item for item in brand_items if item.get('itemId') not in seen_ids]
                        
                        all_similar.extend(brand_items)
                        print(f"✅ Seri '{term}' için {len(brand_items)} benzer ürün bulundu")
            
            # Duplike item ID'leri temizle
            seen_ids = set()
            unique_similar = []
            for item in all_similar:
                item_id = item.get('itemId')
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    unique_similar.append(item)
            
            print(f"✅ Toplam {len(unique_similar)} benzersiz benzer ürün bulundu")
            
            # Benzer ürünleri skorlama ve sıralama
            scored_similar = []
            for similar in unique_similar:
                # Her benzer ürün için benzerlik skoru hesapla (marka, kategori, vb.)
                score = self.calculate_similar_product_score(brand, category_path, similar)
                scored_similar.append((similar, score))
            
            # Score'a göre sırala
            scored_similar.sort(key=lambda x: x[1], reverse=True)
            
            # En iyi 15 benzer ürünü döndür
            top_similar = [s[0] for s in scored_similar[:15]]
            
            return top_similar
            
        except Exception as e:
            print(f"❌ Benzer ürün arama hatası: {e}")
            return []

    def get_brand_series(self, brand: str) -> List[str]:
        """Belirli markalar için popüler seri isimlerini döndür"""
        brand_lower = brand.lower()
        
        # Dell için seriler
        if "dell" in brand_lower:
            return ["XPS", "Inspiron", "Latitude", "Precision", "Alienware", "UltraSharp", "P Series", "SE Series"]
        # HP için seriler
        elif "hp" in brand_lower:
            return ["Pavilion", "Envy", "Spectre", "EliteBook", "ProBook", "Omen", "Z Series"]
        # Lenovo için seriler
        elif "lenovo" in brand_lower:
            return ["ThinkPad", "IdeaPad", "Legion", "Yoga", "ThinkCentre", "ThinkVision"]
        # Acer için seriler
        elif "acer" in brand_lower:
            return ["Aspire", "Predator", "Nitro", "Swift", "Chromebook", "ConceptD"]
        # Asus için seriler
        elif "asus" in brand_lower:
            return ["ROG", "ZenBook", "VivoBook", "TUF", "ProArt", "Designo"]
        # Samsung için seriler
        elif "samsung" in brand_lower:
            return ["Odyssey", "ViewFinity", "Smart Monitor", "FHD", "UHD", "QLED"]
        # LG için seriler
        elif "lg" in brand_lower:
            return ["UltraGear", "UltraWide", "UltraFine", "Gram", "NanoCell"]
        # MSI için seriler
        elif "msi" in brand_lower:
            return ["Optix", "Creator", "Modern", "Prestige", "GF Series", "GP Series"]
        
        # Genel seriler
        return ["Pro", "Gaming", "Curved", "UltraWide", "4K", "QHD", "IPS"]

    def calculate_similar_product_score(self, main_brand: str, main_category: str, product: Dict) -> float:
        """Benzer ürün skoru hesapla"""
        score = 0.0
        
        # Marka eşleşmesi (çok önemli)
        product_brand = product.get('brand', '').lower()
        if product_brand and main_brand.lower() == product_brand:
            score += 40
        
        # Kategori eşleşmesi
        product_category = product.get('categoryPath', '')
        if product_category and main_category:
            # Tam kategori eşleşmesi
            if product_category == main_category:
                score += 30
            # Kısmi kategori eşleşmesi
            elif main_category in product_category or product_category in main_category:
                score += 20
            # Ana kategori seviyesi eşleşmesi
            elif main_category.split('/')[0] == product_category.split('/')[0]:
                score += 10
        
        # Ürünün diğer özellikleri
        title = product.get('title', '')
        
        # Ürün türü eşleşmesi
        if "monitor" in main_category.lower() and "monitor" in title.lower():
            score += 15
        elif "laptop" in main_category.lower() and ("laptop" in title.lower() or "notebook" in title.lower()):
            score += 15
        elif "desktop" in main_category.lower() and "desktop" in title.lower():
            score += 15
        
        # Ürün popülerliği
        try:
            num_reviews = product.get('numReviews', 0)
            if isinstance(num_reviews, str):
                num_reviews = int(num_reviews) if num_reviews.isdigit() else 0
                
            if num_reviews > 50:
                score += 10
                
            rating = product.get('customerRating', 0)
            if isinstance(rating, str):
                rating = float(rating) if rating.replace('.', '').isdigit() else 0
                
            if rating > 4:
                score += 5
        except (ValueError, TypeError):
            pass  # Sayısal değere dönüştürülemezse atla
        
        # Ürün özellikleri (bestSeller boolean olabilir veya string olabilir)
        best_seller = product.get('bestSeller', False)
        if best_seller is True or (isinstance(best_seller, str) and best_seller.lower() == 'true'):
            score += 10
        
        # Resim ve fiyat bilgisi var mı?
        if product.get('price'):
            score += 5
        if product.get('imageUrl') or product.get('thumbnailImage'):
            score += 5
        
        return min(score, 100.0)  # Maksimum 100 puan

    def extract_category_id(self, category_path: str) -> str:
        """Kategori path'inden ID çıkar"""
        if not category_path:
            return ""
        
        # Kategori path'i analiz et
        if "/" in category_path:
            parts = category_path.split("/")
            # Son bölümü al ve sayısal kısmı bul
            for part in reversed(parts):
                numbers = re.findall(r'\d+', part)
                if numbers:
                    return numbers[0]
        
        # Direkt sayı ara
        numbers = re.findall(r'\d+', category_path)
        return numbers[0] if numbers else ""

    def get_product_variants(self, main_product: Dict) -> List[Dict]:
        """Ürün varyantlarını al - Geliştirilmiş"""
        print("🔄 Ürün varyantları aranıyor...")
        
        # Ana üründen varyant ipuçları al
        variants = []
        
        # 1. Direkt variants field'ı
        if 'variants' in main_product and main_product['variants']:
            print(f"✅ {len(main_product['variants'])} direkt varyant bulundu")
            return main_product['variants']
        
        # Ana ürünün marka, model ve diğer önemli özellikleri
        brand = main_product.get('brand', main_product.get('brandName', ''))
        model_number = main_product.get('modelNumber', '').strip()
        title = main_product.get('title', main_product.get('productName', ''))
        item_id = main_product.get('itemId', main_product.get('wpid', ''))
        
        if not brand:
            print("⚠️ Marka bilgisi eksik, varyant araması yapılamıyor")
            return []
            
        # Kategori bilgisi
        category = main_product.get('categoryPath', '')
        category_id = self.extract_category_id(category)
        
        # Ekran boyutu bilgisini çıkart (monitör ürünleri için)
        screen_size = self.extract_screen_size(title)
        
        # Ürün model serisi (örn: "SE2425HM" -> "SE24")
        model_series = ""
        if model_number:
            # Model numarasından seri çıkar
            model_series = self.extract_model_series(model_number)
        else:
            # Başlıktan çıkar
            extracted_models = self.extract_model_from_title(title)
            if extracted_models:
                model_series = self.extract_model_series(extracted_models[0])
        
        # Ürün özellikleri
        product_features = self.extract_product_features(title)
        
        print(f"🔍 Varyant araması: Marka={brand}, Model Serisi={model_series}, Ekran={screen_size}, Özellikler={product_features}")
        
        # 1. KATEGORİ + MARKA + MODEL SERİSİ ARAMASI (en güvenilir)
        if brand and model_series and category_id:
            query = f"{brand} {model_series}"
            params = {
                'query': query,
                'numItems': 25,
                'format': 'json',
                'categoryId': category_id
            }
            
            try:
                response = requests.get(self.search_url, headers=self.get_headers(),
                                      params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    # Aynı markada olanlara filtrele
                    brand_items = [item for item in items if 
                                 item.get('brand', '').lower() == brand.lower() or
                                 brand.lower() in item.get('brand', '').lower()]
                    
                    # Mevcut ürünü çıkar
                    brand_items = [item for item in brand_items if item.get('itemId') != item_id]
                    
                    variants.extend(brand_items)
                    print(f"✅ Kategori+Marka+Seri '{query}' için {len(brand_items)} varyant bulundu")
            except Exception as e:
                print(f"⚠️ Kategori+Marka+Seri arama hatası: {e}")
        
        # 2. MARKA + MODEL SERİSİ ARAMASI
        if brand and model_series and len(variants) < 10:
            query = f"{brand} {model_series}"
            params = {
                'query': query,
                'numItems': 25,
                'format': 'json'
            }
            
            try:
                response = requests.get(self.search_url, headers=self.get_headers(),
                                      params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    # Aynı markada olanlara filtrele
                    brand_items = [item for item in items if 
                                 item.get('brand', '').lower() == brand.lower() or
                                 brand.lower() in item.get('brand', '').lower()]
                    
                    # Model serisi içerenleri filtrele
                    if model_series:
                        brand_items = [item for item in brand_items if 
                                     model_series.lower() in item.get('title', '').lower() or
                                     (item.get('modelNumber') and model_series.lower() in item.get('modelNumber').lower())]
                    
                    # Mevcut ürünü ve zaten bulunanları çıkar
                    seen_ids = {item.get('itemId') for item in variants}
                    seen_ids.add(item_id)
                    brand_items = [item for item in brand_items if item.get('itemId') not in seen_ids]
                    
                    variants.extend(brand_items)
                    print(f"✅ Marka+Seri '{query}' için {len(brand_items)} varyant bulundu")
            except Exception as e:
                print(f"⚠️ Marka+Seri arama hatası: {e}")
        
        # 3. MARKA + EKRAN BOYUTU + ÜRÜN TİPİ ARAMASI
        if brand and screen_size and len(variants) < 15:
            # Ürün tipini belirle (monitor, display, vb.)
            product_type = self.determine_product_type(title)
            query = f"{brand} {screen_size} {product_type}"
            
            params = {
                'query': query,
                'numItems': 20,
                'format': 'json',
                'facet': 'on',
                'facet.filter': f'brand:{brand}'
            }
            
            try:
                response = requests.get(self.search_url, headers=self.get_headers(),
                                      params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    # Benzer ekran boyutu olanları filtrele
                    if screen_size:
                        items = [item for item in items if 
                               screen_size in item.get('title', '') or
                               self.extract_screen_size(item.get('title', '')) == screen_size]
                    
                    # Mevcut ürünü ve zaten bulunanları çıkar
                    seen_ids = {item.get('itemId') for item in variants}
                    seen_ids.add(item_id)
                    items = [item for item in items if item.get('itemId') not in seen_ids]
                    
                    variants.extend(items)
                    print(f"✅ Marka+Ekran '{query}' için {len(items)} varyant bulundu")
            except Exception as e:
                print(f"⚠️ Marka+Ekran arama hatası: {e}")
        
        # 4. MARKA + ÜRÜN ÖZELLİKLERİ ARAMASI
        if brand and product_features and len(variants) < 15:
            for feature in product_features[:2]:  # En önemli 2 özelliği kullan
                query = f"{brand} {feature}"
                params = {
                    'query': query,
                    'numItems': 15,
                    'format': 'json',
                    'facet': 'on',
                    'facet.filter': f'brand:{brand}'
                }
                
                try:
                    response = requests.get(self.search_url, headers=self.get_headers(),
                                          params=params, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get('items', [])
                        
                        # Aynı özelliğe sahip olanları filtrele
                        items = [item for item in items if 
                               feature.lower() in item.get('title', '').lower()]
                        
                        # Mevcut ürünü ve zaten bulunanları çıkar
                        seen_ids = {item.get('itemId') for item in variants}
                        seen_ids.add(item_id)
                        items = [item for item in items if item.get('itemId') not in seen_ids]
                        
                        variants.extend(items)
                        print(f"✅ Marka+Özellik '{query}' için {len(items)} varyant bulundu")
                except Exception as e:
                    print(f"⚠️ Marka+Özellik arama hatası: {e}")
        
        # 5. SERİ ADINI KULLANAN GENEL ARAMA (son çare)
        if len(variants) < 5 and brand and title:
            extracted_series = self.extract_general_series(title)
            if extracted_series:
                query = f"{brand} {extracted_series}"
                params = {
                    'query': query,
                    'numItems': 15,
                    'format': 'json'
                }
                
                try:
                    response = requests.get(self.search_url, headers=self.get_headers(),
                                         params=params, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get('items', [])
                        
                        # Aynı markada olanlara filtrele
                        brand_items = [item for item in items if 
                                     item.get('brand', '').lower() == brand.lower()]
                        
                        # Mevcut ürünü ve zaten bulunanları çıkar
                        seen_ids = {item.get('itemId') for item in variants}
                        seen_ids.add(item_id)
                        brand_items = [item for item in brand_items if item.get('itemId') not in seen_ids]
                        
                        variants.extend(brand_items)
                        print(f"✅ Genel Seri '{query}' için {len(brand_items)} varyant bulundu")
                except Exception as e:
                    print(f"⚠️ Genel Seri arama hatası: {e}")
        
        # Duplike ID'leri temizle
        seen_ids = set()
        unique_variants = []
        for variant in variants:
            item_id = variant.get('itemId')
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                unique_variants.append(variant)
        
        print(f"✅ Toplam {len(unique_variants)} varyant bulundu")
        
        # Varyantları ön incelemeye tabi tut
        scored_variants = []
        for variant in unique_variants:
            # Her varyant için confidence score hesapla
            score = self.calculate_variant_similarity(main_product, variant)
            scored_variants.append((variant, score))
        
        # Score'a göre sırala
        scored_variants.sort(key=lambda x: x[1], reverse=True)
        
        # En iyi 15 varyantı döndür
        top_variants = [v[0] for v in scored_variants[:15]]
        print(f"🔍 En iyi {len(top_variants)} varyant seçildi")
        
        return top_variants

    def extract_product_features(self, title: str) -> List[str]:
        """Ürün başlığından önemli özellikleri çıkar"""
        if not title:
            return []
        
        features = []
        
        # Çözünürlük (1080p, 4K, vb.)
        resolution_patterns = [
            r'(\d+p)',
            r'(\d+K)',
            r'(UHD)',
            r'(QHD)',
            r'(WQHD)',
            r'(HD)',
            r'(FHD)',
            r'(\d+x\d+)',
        ]
        
        for pattern in resolution_patterns:
            matches = re.findall(pattern, title, re.IGNORECASE)
            features.extend(matches)
        
        # Yenileme hızı (Hz)
        hz_patterns = [
            r'(\d+Hz)',
            r'(\d+\s*Hz)',
            r'(\d+\s*Hertz)',
        ]
        
        for pattern in hz_patterns:
            matches = re.findall(pattern, title, re.IGNORECASE)
            features.extend(matches)
        
        # Diğer özellikler
        if 'curved' in title.lower():
            features.append('curved')
        if 'gaming' in title.lower():
            features.append('gaming')
        if 'ultrawide' in title.lower() or 'ultra wide' in title.lower():
            features.append('ultrawide')
        if 'touchscreen' in title.lower() or 'touch screen' in title.lower():
            features.append('touchscreen')
        if 'ips' in title.lower():
            features.append('IPS')
        if 'led' in title.lower():
            features.append('LED')
        if 'hdr' in title.lower():
            features.append('HDR')
        
        # Temizle ve eşsiz yap
        clean_features = []
        for feature in features:
            if isinstance(feature, tuple):
                for f in feature:
                    if f and len(f) > 1:
                        clean_features.append(f)
            elif feature and len(feature) > 1:
                clean_features.append(feature)
        
        return list(set(clean_features))

    def calculate_variant_similarity(self, main_product: Dict, variant: Dict) -> float:
        """Ana ürün ile varyant arasındaki benzerliği hesapla - Geliştirilmiş"""
        score = 0.0
        
        # Marka kontrolü (çok önemli)
        main_brand = main_product.get('brand', '').lower()
        variant_brand = variant.get('brand', '').lower()
        if main_brand and variant_brand:
            if main_brand == variant_brand:
                score += 30  # Tam marka eşleşmesi
            elif main_brand in variant_brand or variant_brand in main_brand:
                score += 20  # Kısmi marka eşleşmesi (örn: "Dell" ve "Dell Inc.")
        
        # Model numarası kontrolü
        main_model = main_product.get('modelNumber', '').lower()
        variant_model = variant.get('modelNumber', '').lower()
        
        if main_model and variant_model:
            # Tam eşleşme
            if main_model == variant_model:
                score += 50  # Direkt aynı model (çok güçlü eşleşme)
            # Kısmi eşleşme
            elif main_model in variant_model or variant_model in main_model:
                score += 35  # Çok benzer model
            # Model serisi eşleşmesi
            else:
                main_series = self.extract_model_series(main_model)
                variant_series = self.extract_model_series(variant_model)
                if main_series and variant_series and main_series == variant_series:
                    score += 30  # Aynı model serisi
                elif main_series and variant_series and (main_series in variant_series or variant_series in main_series):
                    score += 20  # Benzer model serisi
        
        # Başlık benzerliği
        main_title = main_product.get('title', '').lower()
        variant_title = variant.get('title', '').lower()
        
        if main_title and variant_title:
            # Başlıktaki model numarası kontrolü
            main_models_in_title = self.extract_model_from_title(main_title)
            variant_models_in_title = self.extract_model_from_title(variant_title)
            
            # Başlıkta model numarası eşleşmesi
            if main_models_in_title and variant_models_in_title:
                for m_model in main_models_in_title:
                    for v_model in variant_models_in_title:
                        if m_model == v_model:
                            score += 30  # Başlıkta aynı model kodu var
                        elif m_model in v_model or v_model in m_model:
                            score += 20  # Başlıkta benzer model kodu var
            
            # Aynı ana ürün serisi
            main_series_name = self.extract_general_series(main_title)
            variant_series_name = self.extract_general_series(variant_title)
            if main_series_name and variant_series_name and main_series_name == variant_series_name:
                score += 15
            
            # Aynı ekran boyutu
            main_size = self.extract_screen_size(main_title)
            variant_size = self.extract_screen_size(variant_title)
            if main_size and variant_size and main_size == variant_size:
                score += 20  # Aynı ekran boyutu çok önemli
            
            # Ortak özellikler
            main_features = self.extract_product_features(main_title)
            variant_features = self.extract_product_features(variant_title)
            
            common_features = set(main_features).intersection(set(variant_features))
            # Ortak özellik sayısına göre puan ver (max 25)
            feature_score = min(len(common_features) * 5, 25)
            score += feature_score
            
            # Özellik skor ayarlaması - Belirli önemli özelliklere bonus puan
            important_features = ['IPS', 'LED', 'FHD', '1080p', '4K', 'UHD', 'QHD', 'gaming']
            for feature in common_features:
                if feature.lower() in [f.lower() for f in important_features]:
                    score += 3  # Önemli ortak özellikler için ek puan
        
        # Kategori benzerliği
        main_category = main_product.get('categoryPath', '')
        variant_category = variant.get('categoryPath', '')
        if main_category and variant_category:
            if main_category == variant_category:
                score += 15  # Tam kategori eşleşmesi
            elif main_category in variant_category or variant_category in main_category:
                score += 10  # Kısmi kategori eşleşmesi
        
        # Fiyat analizi - çok benzer fiyatlı ürünler büyük olasılıkla benzer varyantlar
        try:
            main_price = float(main_product.get('price', 0))
            variant_price = float(variant.get('price', 0))
            
            if main_price > 0 and variant_price > 0:
                # Fiyat farkı oranı hesapla
                price_diff_ratio = abs(main_price - variant_price) / max(main_price, variant_price)
                
                # %10'dan az fiyat farkı varsa bonus puan
                if price_diff_ratio < 0.1:
                    score += 10  # Çok yakın fiyat
                # %20'den az fiyat farkı varsa daha az bonus
                elif price_diff_ratio < 0.2:
                    score += 5  # Yakın fiyat
        except (ValueError, TypeError):
            pass  # Fiyat karşılaştırılamazsa atla
        
        # UPC veya GTIN eşleşmesi (en güçlü eşleşme)
        main_upc = main_product.get('upc', '')
        variant_upc = variant.get('upc', '')
        main_gtin = main_product.get('gtin', '')
        variant_gtin = variant.get('gtin', '')
        
        if (main_upc and variant_upc and main_upc == variant_upc) or \
           (main_gtin and variant_gtin and main_gtin == variant_gtin):
            score += 100  # Kesin eşleşme, varyant demektir
        
        # En fazla 100 puan olabilir
        return min(score, 100.0)

    def extract_screen_size(self, title: str) -> str:
        """Ürün adından ekran boyutu çıkar"""
        if not title:
            return ""
        
        # Yaygın ekran boyutu paternleri
        patterns = [
            r'(\d{2}\.?\d?)[\s\"\']?\s*inch',
            r'(\d{2}\.?\d?)[\s\"\']?\s*in\b',
            r'(\d{2}\.?\d?)[\s\"\']?\s*\'',
            r'(\d{2})[\s\"\']?\s*"',
            r'\b(\d{2})[\"]',
            r'\b(\d{2})\.(\d)[\"]',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, title, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    return f"{matches[0][0]}.{matches[0][1]}\"" if len(matches[0]) > 1 else f"{matches[0][0]}\""
                return f"{matches[0]}\""
        
        return ""

    def extract_model_series(self, model: str) -> str:
        """Model numarasından model serisini çıkar"""
        if not model:
            return ""
        
        # SE2425HM -> SE24
        # P2422H -> P24
        # Yaygın model serisi paternleri
        patterns = [
            # Harf + sayılar (ilk 2 sayıyı al): SE2425HM -> SE24
            r'([A-Z]{1,3})(\d{2})',
            # Genel olarak ilk 4 karakter
            r'^([A-Z0-9]{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, model, re.IGNORECASE)
            if match:
                if len(match.groups()) > 1:
                    return match.group(1) + match.group(2)
                return match.group(1)
        
        # Fallback: Model numarasının ilk 4 karakteri
        return model[:4] if len(model) >= 4 else model

    def determine_product_type(self, title: str) -> str:
        """Ürün tipini belirle (monitor, display vb.)"""
        title_lower = title.lower()
        
        if "monitor" in title_lower:
            return "monitor"
        elif "display" in title_lower:
            return "display"
        elif "screen" in title_lower:
            return "screen"
        elif "tv" in title_lower or "television" in title_lower:
            return "tv"
        
        return "monitor"  # Varsayılan

    def extract_general_series(self, title: str) -> str:
        """Ürün adından genel seri adını çıkar (Pro, Inspiron, XPS gibi)"""
        common_series = ["Pro", "Inspiron", "XPS", "Latitude", "Ultrasharp", "P Series", "S Series", "E Series"]
        
        for series in common_series:
            if series.lower() in title.lower():
                return series
        
        # Yaygın paternler
        patterns = [
            r'\b(Pro|Inspiron|XPS|Latitude|Ultrasharp)\s+(\d{1,2})',
            r'\b([PES][\s-]?Series)\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return ""

    def search_by_model(self, model: str, exclude_id: str = None) -> List[Dict]:
        """Model numarasına göre ara"""
        if not model or not self.ensure_valid_token():
            return []
        
        try:
            params = {
                'query': model,
                'numItems': 15,
                'format': 'json'
            }
            
            response = requests.get(self.search_url, headers=self.get_headers(),
                                  params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                if exclude_id:
                    items = [item for item in items if item.get('itemId') != exclude_id]
                
                print(f"✅ Model '{model}' için {len(items)} ürün bulundu")
                return items
                
        except Exception as e:
            print(f"⚠️ Model arama hatası: {e}")
        
        return []

    def search_brand_model(self, brand: str, base_model: str, exclude_id: str = None) -> List[Dict]:
        """Marka + base model ile ara"""
        if not brand or not base_model or not self.ensure_valid_token():
            return []
        
        try:
            query = f"{brand} {base_model}"
            params = {
                'query': query,
                'numItems': 10,
                'format': 'json',
                'facet': 'on',
                'facet.filter': f'brand:{brand}'
            }
            
            response = requests.get(self.search_url, headers=self.get_headers(),
                                  params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                if exclude_id:
                    items = [item for item in items if item.get('itemId') != exclude_id]
                
                print(f"✅ '{query}' için {len(items)} ürün bulundu")
                return items
                
        except Exception as e:
            print(f"⚠️ Brand+Model arama hatası: {e}")
        
        return []

    def extract_model_from_title(self, title: str) -> List[str]:
        """Ürün adından model numaralarını çıkar"""
        if not title:
            return []
        
        models = []
        
        # Yaygın model pattern'leri
        patterns = [
            r'[A-Z]{2,4}\d{4,6}[A-Z]*',  # SE2425HM gibi
            r'\b[A-Z]\d{4,6}\b',         # S2425 gibi
            r'\b\d{4,6}[A-Z]{1,3}\b',   # 2425HM gibi
            r'Model\s+([A-Z0-9-]+)',     # Model SE2425HM
            r'(\d{2,4}[A-Z]{2,4})',      # 24HM gibi
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, title, re.IGNORECASE)
            models.extend(matches)
        
        # Duplikeleri temizle ve büyük harfe çevir
        unique_models = list(set([m.upper().strip() for m in models if len(m) >= 4]))
        
        return unique_models

    def extract_base_model(self, title: str) -> str:
        """Ürün adından base model çıkar"""
        if not title:
            return ""
        
        # "Dell Pro 24" -> "Pro 24"
        # "SE2425HM" -> "SE24" (base)
        
        # Önce full model bul
        models = self.extract_model_from_title(title)
        if models:
            model = models[0]
            # Base model oluştur (ilk 4-6 karakter)
            if len(model) >= 6:
                return model[:4]  # SE24
        
        # Title'dan serie çıkar
        words = title.split()
        for i, word in enumerate(words):
            if any(char.isdigit() for char in word) and len(word) >= 3:
                # Bu kelime ve bir önceki kelimeyi al
                if i > 0:
                    return f"{words[i-1]} {word}"
                else:
                    return word
        
        return ""

    def extract_enhanced_data(self, product: Dict, is_main: bool = False) -> Dict:
        """Geliştirilmiş veri çıkarma"""
        try:
            info = {}
            
            # Temel bilgiler
            info['urun_adi'] = product.get('title', product.get('productName', product.get('name', 'N/A')))
            info['marka'] = product.get('brand', product.get('brandName', 'N/A'))
            info['item_id'] = str(product.get('itemId', product.get('wpid', product.get('id', 'N/A'))))
            info['product_id'] = str(product.get('productId', info['item_id']))  # Ayrı product ID
            info['upc'] = product.get('upc', product.get('gtin', product.get('gtinNumber', 'N/A')))
            info['model_number'] = product.get('modelNumber', product.get('model', 'N/A'))
            
            # Kategori detayları
            info['kategori'] = product.get('categoryPath', product.get('category', 'N/A'))
            info['kategori_id'] = self.extract_category_id(info['kategori'])
            info['sub_category'] = product.get('subCategory', 'N/A')
            
            # Link'ler
            info['walmart_link'] = f"https://www.walmart.com/ip/{info['item_id']}"
            info['product_url'] = product.get('productUrl', info['walmart_link'])
            
            # Fiyat bilgileri (detaylı)
            price_info = self.extract_price_info(product)
            info['fiyat_bilgileri'] = price_info
            
            # Stok ve durum bilgileri
            info['stok_durumu'] = product.get('availabilityStatus', product.get('stockStatus', 'N/A'))
            info['publish_status'] = product.get('publishedStatus', 'N/A')
            info['lifecycle_status'] = product.get('lifecycleStatus', 'N/A')
            info['is_available'] = product.get('available', True)
            
            # Değerlendirmeler ve popülerlik
            info['yorumlar'] = product.get('numReviews', product.get('reviewCount', 'N/A'))
            info['puan'] = product.get('customerRating', product.get('averageRating', 'N/A'))
            info['best_seller'] = product.get('bestSeller', False)
            info['trending'] = product.get('trending', False)
            
            # Ürün detayları
            info['aciklama'] = product.get('shortDescription', product.get('description', 'N/A'))
            info['long_description'] = product.get('longDescription', 'N/A')
            info['features'] = product.get('features', [])
            info['specifications'] = product.get('specifications', {})
            
            # Fiziksel özellikler
            info['size'] = product.get('size', 'N/A')
            info['color'] = product.get('color', 'N/A')
            info['weight'] = product.get('weight', 'N/A')
            info['dimensions'] = product.get('dimensions', 'N/A')
            
            # Resimler - geliştirilmiş
            info['resimler'] = self.extract_images(product)
            
            # Satış bilgileri
            info['free_shipping'] = product.get('freeShippingOver35Dollars', product.get('freeShipping', False))
            info['marketplace'] = product.get('marketplace', False)
            info['sold_by_walmart'] = not info['marketplace']
            info['online_only'] = product.get('onlineOnly', False)
            info['bundle'] = product.get('bundle', False)
            info['clearance'] = product.get('clearance', False)
            info['rollback'] = product.get('rollback', False)
            
            # Varyant bilgileri
            info['has_variants'] = bool(product.get('variants'))
            info['variant_count'] = len(product.get('variants', []))
            
            # Ana ürün için ek bilgiler
            if is_main:
                info['extracted_models'] = self.extract_model_from_title(info['urun_adi'])
                info['base_model'] = self.extract_base_model(info['urun_adi'])
            
            # Confidence score (ne kadar doğru match)
            info['confidence_score'] = self.calculate_confidence(product, is_main)
            
            return info
            
        except Exception as e:
            print(f"❌ Veri çıkarma hatası: {e}")
            # Hata durumunda da confidence_score ekle
            return {
                'hata': str(e),
                'confidence_score': 0,  # Bu satır eklendi
                'urun_adi': 'HATA',
                'marka': 'N/A',
                'item_id': 'N/A',
                'fiyat_bilgileri': {}
            }

    def extract_price_info(self, product: Dict) -> Dict:
        """Detaylı fiyat bilgilerini çıkar"""
        price_info = {}
        
        # Ana fiyat
        if 'price' in product:
            price_data = product['price']
            if isinstance(price_data, dict):
                price_info['current_price'] = f"${price_data.get('amount', '0')} {price_data.get('currency', 'USD')}"
                price_info['price_amount'] = price_data.get('amount', 0)
                price_info['currency'] = price_data.get('currency', 'USD')
            else:
                price_info['current_price'] = f"${price_data} USD"
                price_info['price_amount'] = price_data
                price_info['currency'] = 'USD'
        
        # Detaylı fiyat bilgileri
        if 'priceInfo' in product:
            pi = product['priceInfo']
            price_info['msrp'] = pi.get('msrp', 'N/A')
            price_info['list_price'] = pi.get('listPrice', 'N/A')
            price_info['was_price'] = pi.get('wasPrice', 'N/A')
            price_info['sale_price'] = pi.get('salePrice', 'N/A')
            price_info['clearance'] = pi.get('clearance', False)
            price_info['rollback'] = pi.get('rollback', False)
            
            # İndirim hesapla
            if price_info.get('price_amount') and pi.get('listPrice'):
                try:
                    current = float(price_info['price_amount'])
                    list_price = float(pi['listPrice'])
                    if list_price > current:
                        discount = ((list_price - current) / list_price) * 100
                        price_info['discount_percent'] = round(discount, 1)
                        price_info['savings'] = round(list_price - current, 2)
                except:
                    pass
        
        return price_info

    def extract_images(self, product: Dict) -> List[str]:
        """Geliştirilmiş resim çıkarma"""
        images = []
        
        # Çeşitli resim field'larını kontrol et
        image_fields = [
            'imageInfo.allImages',
            'imageInfo.thumbnailImage',
            'imageInfo.largeImage',
            'images',
            'image',
            'thumbnailImage',
            'largeImage'
        ]
        
        # Nested field'lar için
        if 'imageInfo' in product:
            img_info = product['imageInfo']
            if 'allImages' in img_info and isinstance(img_info['allImages'], list):
                for img in img_info['allImages']:
                    if isinstance(img, dict):
                        url = img.get('url', img.get('imageUrl', ''))
                        if url and isinstance(url, str):  # String kontrolü eklendi
                            images.append(url)
                    elif isinstance(img, str):
                        images.append(img)
            
            # Tek resimler
            for field in ['thumbnailImage', 'largeImage', 'mediumImage']:
                if field in img_info and img_info[field] and isinstance(img_info[field], str):
                    images.append(img_info[field])
        
        # Direkt field'lar
        for field in ['images', 'image', 'thumbnailImage', 'largeImage']:
            if field in product and product[field]:
                value = product[field]
                if isinstance(value, list):
                    # List içindeki her elemanı kontrol et
                    for img in value:
                        if img and isinstance(img, str):
                            images.append(img)
                elif isinstance(value, str):
                    images.append(value)
        
        # Duplikeleri temizle ve geçersizleri çıkar
        unique_images = []
        for img in images:
            if img and isinstance(img, str) and img not in unique_images and img.startswith('http'):
                unique_images.append(img)
        
        return unique_images

    def calculate_confidence(self, product: Dict, is_main: bool) -> float:
        """Ürünün ne kadar doğru match olduğunu hesapla"""
        score = 0.0
        
        # Ana ürün bilgileri
        title = product.get('title', '')
        brand = product.get('brand', '')
        model_number = product.get('modelNumber', '')
        
        # Temel alanlar varsa puan ekle
        if title:
            score += 15
        if brand:
            score += 15
        if product.get('itemId'):
            score += 10
        
        # UPC/GTIN varsa +25 (çok önemli)
        if product.get('upc') or product.get('gtin'):
            score += 25
        
        # Fiyat varsa +10
        if product.get('price'):
            score += 10
        
        # Resim varsa +10
        if self.extract_images(product):
            score += 10
        
        # Model number varsa +15
        if model_number:
            score += 15
        
        # Marka ve model numarası için ek bonus puanlar
        if brand and 'Dell' in brand:  # Örnek: Aranan ürün Dell ise
            score += 10
        
        if model_number:
            # Model serisi eşleşmesi
            model_series = self.extract_model_series(model_number)
            if model_series and model_series in title:
                score += 15
        
        # Ekran boyutu eşleşmesi
        screen_size = self.extract_screen_size(title)
        if screen_size and screen_size in title:
            score += 10
            
        # Monitör tipi eşleşmesi
        if 'monitor' in title.lower():
            score += 5
            
        # Ana ürün için bonus
        if is_main:
            score += 10
        
        return min(score, 100.0)  # Max 100

    def scan_upc_pro_enhanced(self, upc: str) -> Dict:
        """UPC tarama PRO Enhanced - Comprehensive analysis"""
        print(f"\n{'='*80}")
        print(f"🛒 WALMART PRO UPC SCANNER ENHANCED: {upc}")
        print(f"{'='*80}")
        
        # 1. Multi-method search
        search_results = self.search_by_upc_advanced(upc)
        if not search_results:
            return {"hata": "UPC bulunamadı - Hiçbir yöntemle sonuç alınamadı"}
        
        # 2. En iyi sonucu seç
        main_product = None
        all_found_products = []
        
        # Tüm search sonuçlarını birleştir
        for search_type, data in search_results.items():
            if data and 'items' in data:
                all_found_products.extend(data['items'])
        
        if not all_found_products:
            return {"hata": "Ürün bulunamadı"}
        
        # En yüksek confidence score'a sahip ürünü ana ürün yap
        products_with_scores = []
        for product in all_found_products:
            enhanced_product = self.extract_enhanced_data(product, is_main=True)
            products_with_scores.append((product, enhanced_product, enhanced_product['confidence_score']))
        
        # Score'a göre sırala
        products_with_scores.sort(key=lambda x: x[2], reverse=True)
        main_product_raw, main_product_info, main_score = products_with_scores[0]
        
        print(f"✅ Ana ürün seçildi (Confidence: {main_product_info['confidence_score']}%)")
        
        # 3. Item detaylarını al
        item_id = main_product_info.get('item_id')
        if item_id and item_id != 'N/A':
            detailed_info = self.get_item_details(item_id)
            if detailed_info:
                # Detayları merge et
                main_product_info = self.merge_product_data(main_product_info, detailed_info)
        
        # Ana ürün marka ve model bilgilerini al
        main_brand = main_product_info.get('marka', '')
        main_model = main_product_info.get('model_number', '')
        
        # UPC'den marka ve model bilgisi çıkar (bazı UPC'ler bunları içerir)
        upc_brand, upc_model = self.extract_brand_model_from_upc(upc)
        
        # Eğer ana üründe marka yoksa UPC'den çıkarılan markayı kullan
        if not main_brand and upc_brand:
            main_product_info['marka'] = upc_brand
            main_brand = upc_brand
            print(f"🔍 UPC'den marka bilgisi çıkarıldı: {upc_brand}")
        
        # Eğer ana üründe model yoksa UPC'den çıkarılan modeli kullan
        if not main_model and upc_model:
            main_product_info['model_number'] = upc_model
            main_model = upc_model
            print(f"🔍 UPC'den model bilgisi çıkarıldı: {upc_model}")
        
        # 4. Varyantları bul
        print("\n🔄 Varyantlar aranıyor...")
        variants = self.get_product_variants(main_product_raw)
        variants_info = []
        
        # Varyantları score'a göre değerlendir
        for variant in variants:
            variant_info = self.extract_enhanced_data(variant)
            
            # Her varyant için benzerlik skoru hesapla
            similarity_score = self.calculate_variant_similarity(main_product_raw, variant)
            
            # Benzerlik skoru confidence score'a ekle (eğer çok yüksekse)
            if similarity_score >= 70:
                variant_info['confidence_score'] = min(variant_info.get('confidence_score', 0) + 15, 100)
            elif similarity_score >= 50:
                variant_info['confidence_score'] = min(variant_info.get('confidence_score', 0) + 10, 100)
            
            # Varyant benzerlik skorunu da ekle
            variant_info['similarity_score'] = similarity_score
            
            # Yüksek benzerlik skoru olanları al (en az %60)
            if similarity_score >= 60:
                variants_info.append(variant_info)
        
        # Eğer hiç yeterli skorlu varyant bulunamazsa, puanı biraz düşür
        if not variants_info and variants:
            for variant in variants:
                variant_info = self.extract_enhanced_data(variant)
                similarity_score = self.calculate_variant_similarity(main_product_raw, variant)
                variant_info['similarity_score'] = similarity_score
                
                # En az %50 benzerlik skoru
                if similarity_score >= 50:
                    variants_info.append(variant_info)
        
        # Varyantları similarity score'a göre sırala
        variants_info.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        
        # 5. Benzer ürünler bul
        print("\n🎯 Benzer ürünler aranıyor...")
        similar_products = []
        category = main_product_info.get('kategori')
        
        if main_brand:
            try:
                similar_raw = self.find_similar_by_brand_category(main_brand, category, item_id)
                
                for similar in similar_raw:
                    similar_info = self.extract_enhanced_data(similar)
                    
                    # Her benzer ürün için benzerlik skoru hesapla
                    similarity_score = self.calculate_similar_product_score(main_brand, category, similar)
                    similar_info['similarity_score'] = similarity_score
                    
                    # Benzerlik skoru confidence score'a ekle
                    if similarity_score >= 70:
                        similar_info['confidence_score'] = min(similar_info.get('confidence_score', 0) + 15, 100)
                    elif similarity_score >= 50:
                        similar_info['confidence_score'] = min(similar_info.get('confidence_score', 0) + 10, 100)
                    
                    # Yüksek benzerlik skoru olanları al
                    if similarity_score >= 55:
                        similar_products.append(similar_info)
                
                # Benzerlik skoruna göre sırala
                similar_products.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
                similar_products = similar_products[:8]  # En fazla 8 benzer ürün
            except Exception as e:
                print(f"❌ Benzer ürün arama hatası: {e}")
        
        # 6. Sonuç paketi oluştur
        result = {
            'ana_urun': main_product_info,
            'varyantlar': variants_info,
            'benzer_urunler': similar_products,
            'arama_detaylari': {
                'toplam_bulunan': len(all_found_products),
                'varyant_sayisi': len(variants_info),
                'benzer_urun_sayisi': len(similar_products),
                'arama_yontemleri': list(search_results.keys()),
                'confidence_scores': {
                    'ana_urun': main_product_info.get('confidence_score', 0),
                    'ortalama_varyant': sum([v.get('confidence_score', 0) for v in variants_info]) / len(variants_info) if variants_info else 0,
                    'ortalama_benzer': sum([s.get('confidence_score', 0) for s in similar_products]) / len(similar_products) if similar_products else 0,
                    'ortalama_varyant_similarity': sum([v.get('similarity_score', 0) for v in variants_info]) / len(variants_info) if variants_info else 0,
                    'ortalama_benzer_similarity': sum([s.get('similarity_score', 0) for s in similar_products]) / len(similar_products) if similar_products else 0
                }
            },
            'arama_zamani': time.strftime("%Y-%m-%d %H:%M:%S"),
            'upc_aranan': upc
        }
        
        # Sonuçları yazdır
        self.print_enhanced_results(result)
        
        return result

    def extract_brand_model_from_upc(self, upc: str) -> tuple:
        """UPC kodundan marka ve model bilgisi çıkarmaya çalış - Basitleştirilmiş"""
        # Kullanıcının talebi üzerine bu fonksiyon basitleştirildi
        # UPC'ler bağımsız ID olarak kullanıldığından karmaşık eşleştirmelere gerek yok
        return ("", "")  # Boş marka ve model döndür

    def merge_product_data(self, base_info: Dict, detailed_info: Dict) -> Dict:
        """Ana ürün bilgisi ile detaylı bilgiyi birleştir"""
        try:
            # Detailed info'dan ek bilgileri al
            if 'specifications' in detailed_info:
                base_info['specifications'] = detailed_info['specifications']
            
            if 'features' in detailed_info:
                base_info['features'] = detailed_info.get('features', [])
            
            # Eksik olan temel bilgileri tamamla
            merge_fields = [
                'longDescription', 'shortDescription', 'brand', 'modelNumber',
                'color', 'size', 'weight', 'dimensions', 'categoryPath'
            ]
            
            for field in merge_fields:
                if field in detailed_info and (field not in base_info or base_info.get(field) == 'N/A'):
                    if field == 'longDescription':
                        base_info['long_description'] = detailed_info[field]
                    elif field == 'shortDescription':
                        base_info['aciklama'] = detailed_info[field]
                    elif field == 'categoryPath':
                        base_info['kategori'] = detailed_info[field]
                        base_info['kategori_id'] = self.extract_category_id(detailed_info[field])
                    else:
                        snake_case_field = field.lower().replace('number', '_number')
                        if snake_case_field in base_info:
                            base_info[snake_case_field] = detailed_info[field]
            
            # Resim bilgilerini güncelle
            detailed_images = self.extract_images(detailed_info)
            if detailed_images:
                existing_images = base_info.get('resimler', [])
                all_images = list(set(existing_images + detailed_images))
                base_info['resimler'] = all_images
            
            # Confidence score'u artır (detaylı bilgi varsa)
            base_info['confidence_score'] = min(base_info.get('confidence_score', 0) + 10, 100)
            
            return base_info
            
        except Exception as e:
            print(f"⚠️ Veri birleştirme hatası: {e}")
            return base_info

    def print_enhanced_results(self, result: Dict):
        """Enhanced sonuçları detaylı yazdır"""
        ana = result['ana_urun']
        
        print(f"\n🎯 ANA ÜRÜN (Confidence: {ana.get('confidence_score', 0)}%):")
        print(f"   📦 {ana.get('urun_adi')}")
        print(f"   🏷️  {ana.get('marka')} | Model: {ana.get('model_number')}")
        print(f"   🆔 Item ID: {ana.get('item_id')} | Product ID: {ana.get('product_id')}")
        print(f"   📊 UPC: {ana.get('upc')} | Kategori ID: {ana.get('kategori_id')}")
        print(f"   💰 {ana['fiyat_bilgileri'].get('current_price', 'N/A')}")
        
        # İndirim varsa göster
        if ana['fiyat_bilgileri'].get('discount_percent'):
            print(f"   🔥 %{ana['fiyat_bilgileri']['discount_percent']} İndirim! (${ana['fiyat_bilgileri'].get('savings', 0)} tasarruf)")
        
        print(f"   📊 {ana.get('puan')} ⭐ ({ana.get('yorumlar')} yorum)")
        print(f"   📦 Stok: {ana.get('stok_durumu')} | Satıcı: {'Walmart' if ana.get('sold_by_walmart') else 'Marketplace'}")
        print(f"   🖼️  {len(ana.get('resimler', []))} resim mevcut")
        print(f"   🔗 {ana.get('walmart_link')}")
        
        # Extracted models göster
        if ana.get('extracted_models'):
            print(f"   🔍 Bulunan Modeller: {', '.join(ana['extracted_models'])}")
        
        # Varyantlar
        if result['varyantlar']:
            print(f"\n🔄 VARYANTLAR ({len(result['varyantlar'])} adet):")
            for i, var in enumerate(result['varyantlar'], 1):
                conf = var.get('confidence_score', 0)
                sim = var.get('similarity_score', 0)
                print(f"   {i}. {var.get('urun_adi')} (Confidence: {conf}%, Similarity: {sim}%)")
                print(f"      💰 {var['fiyat_bilgileri'].get('current_price', 'N/A')} | ID: {var.get('item_id')}")
                if var.get('model_number') != 'N/A':
                    print(f"      🏷️  Model: {var.get('model_number')}")
        
        # Benzer ürünler
        if result['benzer_urunler']:
            print(f"\n🎯 BENZER ÜRÜNLER ({len(result['benzer_urunler'])} adet):")
            for i, benzer in enumerate(result['benzer_urunler'], 1):
                conf = benzer.get('confidence_score', 0)
                sim = benzer.get('similarity_score', 0)
                print(f"   {i}. {benzer.get('urun_adi')} (Confidence: {conf}%, Similarity: {sim}%)")
                print(f"      💰 {benzer['fiyat_bilgileri'].get('current_price', 'N/A')} | {benzer.get('marka')}")
                if benzer.get('puan') != 'N/A':
                    print(f"      📊 {benzer.get('puan')} ⭐ ({benzer.get('yorumlar')} yorum)")
        
        # Arama detayları
        detay = result['arama_detaylari']
        print(f"\n📊 ARAMA DETAYLARI:")
        # Arama yöntemlerini yalnızca UPC aramasında göster
        if 'arama_yontemleri' in detay:
            print(f"   🔍 Kullanılan Yöntemler: {', '.join(detay['arama_yontemleri'])}")
        # URL ise URL göster
        if 'url' in detay:
            print(f"   🔗 Taranan URL: {detay['url']}")
        
        print(f"   📈 Confidence Scores:")
        print(f"      • Ana Ürün: {detay['confidence_scores']['ana_urun']}%")
        print(f"      • Ort. Varyant: {detay['confidence_scores']['ortalama_varyant']:.1f}%")
        print(f"      • Ort. Benzer: {detay['confidence_scores']['ortalama_benzer']:.1f}%")
        if 'ortalama_varyant_similarity' in detay['confidence_scores']:
            print(f"      • Ort. Varyant Similarity: {detay['confidence_scores']['ortalama_varyant_similarity']:.1f}%")
        if 'ortalama_benzer_similarity' in detay['confidence_scores']:
            print(f"      • Ort. Benzer Similarity: {detay['confidence_scores']['ortalama_benzer_similarity']:.1f}%")
        
        if 'toplam_bulunan' in detay:
            print(f"   💾 Toplam {detay['toplam_bulunan']} ürün bulundu")
        
        print(f"   🕐 Tarama zamanı: {result['arama_zamani']}")
        print(f"{'='*80}")

    def extract_product_id_from_url(self, url: str) -> str:
        """Walmart ürün URL'sinden ürün ID'sini çıkar"""
        if not url:
            return ""
            
        # Walmart ürün URL paternleri
        patterns = [
            r'walmart\.com/ip/(?:[^/]+/)?(\d+)',  # https://www.walmart.com/ip/item-name/123456789
            r'walmart\.com/ip/(\d+)',             # https://www.walmart.com/ip/123456789
            r'/(\d+)(?:\?|$)',                    # URL sonundaki ID
            r'p/(\d+)',                           # /p/123456789 formatı
            r'item/(\d+)',                        # /item/123456789 formatı
            r'prod(?:uct)?[_-]?id=(\d+)',         # product_id=123456789
            r'item[_-]?id=(\d+)'                  # item_id=123456789
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
                
        return ""
    
    def scan_by_url(self, url: str) -> Dict:
        """URL ile ürün tarama - Geliştirilmiş"""
        print(f"\n{'='*80}")
        print(f"🛒 WALMART URL SCANNER: {url}")
        print(f"{'='*80}")
        
        # Token kontrolü
        if not self.ensure_valid_token():
            return {"hata": "API token alınamadı"}
        
        # Önce URL'nin kategori URL'si olup olmadığını kontrol et
        category_info = self.check_if_category_url(url)
        if category_info and category_info.get("is_category", False):
            print(f"🔍 Bu bir kategori URL'si: {category_info.get('category_name', 'Bilinmeyen Kategori')}")
            # Kategori sayfası için ürünleri listele
            return self.scan_category_url(url, category_info)
        
        # URL'den ürün ID'sini çıkar
        product_id = self.extract_product_id_from_url(url)
        if not product_id:
            return {"hata": "URL'den ürün ID'si çıkarılamadı"}
            
        print(f"🔍 URL'den çıkarılan ürün ID: {product_id}")
        
        # YÖNTEM 1: Direkt ürün detayları alma
        detailed_info = self.get_item_details(product_id)
        
        # Eğer 404 hatası alındıysa, alternatif yöntemleri dene
        if not detailed_info:
            print(f"⚠️ Ürün detayları API üzerinden alınamadı. Alternatif yöntemler deneniyor...")
            
            # YÖNTEM 2: URL'den ürün bilgilerini çıkar
            extracted_info = self.extract_info_from_url(url)
            if extracted_info and "product_title" in extracted_info:
                # Başlık ve diğer bilgilerle arama yap
                search_query = extracted_info.get("product_title", "")
                if not search_query and "product_id" in extracted_info:
                    search_query = extracted_info.get("product_id")
                
                print(f"🔍 Arama sorgusu: '{search_query}'")
                
                # Arama API'si üzerinden ürünü bul
                search_results = self.search_product_by_keyword(search_query)
                
                # Sonuçlardan en iyi eşleşmeyi bul
                if search_results and "items" in search_results and search_results["items"]:
                    print(f"✅ Arama sonucunda {len(search_results['items'])} ürün bulundu")
                    
                    # En iyi eşleşen ürünü bul
                    best_match = self.find_best_match_for_url(search_results["items"], url, extracted_info)
                    
                    if best_match:
                        print(f"✅ Ürün başarıyla bulundu: {best_match.get('title', 'N/A')}")
                        detailed_info = best_match
                    else:
                        return {"hata": "Arama sonuçlarında uygun eşleşme bulunamadı"}
                else:
                    return {"hata": "Ürün araması sonuç vermedi"}
            else:
                # YÖNTEM 3: Son çare - UPC veya SKU'ya göre arama
                print("🔍 URL'den ürün kodu aranıyor...")
                upc_or_sku = self.extract_upc_or_sku_from_url(url)
                
                if upc_or_sku:
                    print(f"✅ URL'den UPC/SKU bulundu: {upc_or_sku}")
                    search_results = self.search_by_upc_advanced(upc_or_sku)
                    
                    if search_results and any(key in search_results for key in ["upc_search", "gtin_search", "query_search"]):
                        # Sonuçları birleştir
                        all_found_products = []
                        for search_type, data in search_results.items():
                            if data and "items" in data:
                                all_found_products.extend(data["items"])
                        
                        if all_found_products:
                            print(f"✅ UPC/SKU aramasında {len(all_found_products)} ürün bulundu")
                            detailed_info = all_found_products[0]  # İlk ürünü al
                        else:
                            return {"hata": "UPC/SKU aramasında ürün bulunamadı"}
                    else:
                        return {"hata": "UPC/SKU araması başarısız oldu"}
                else:
                    return {"hata": "URL'den ürün bilgisi çıkarılamadı ve alternatif arama yöntemleri başarısız oldu"}
        
        # Ürün bulunamadıysa hata döndür
        if not detailed_info:
            return {"hata": f"Ürün detayları alınamadı (ID: {product_id})"}
        
        # Ürün bilgilerini çıkar
        product_info = self.extract_enhanced_data(detailed_info, is_main=True)
        
        # Varyant ve benzer ürünleri bul
        variants = self.get_product_variants(detailed_info)
        variants_info = []
        
        for variant in variants:
            variant_info = self.extract_enhanced_data(variant)
            similarity_score = self.calculate_variant_similarity(detailed_info, variant)
            variant_info['similarity_score'] = similarity_score
            
            if similarity_score >= 60:  # Yüksek benzerlik skoru
                variants_info.append(variant_info)
        
        # Benzerlik skoruna göre sırala
        variants_info.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        
        # Benzer ürünleri bul
        similar_products = []
        brand = product_info.get('marka', '')
        category = product_info.get('kategori', '')
        
        if brand:
            try:
                similar_raw = self.find_similar_by_brand_category(brand, category, product_id)
                
                for similar in similar_raw:
                    similar_info = self.extract_enhanced_data(similar)
                    similarity_score = self.calculate_similar_product_score(brand, category, similar)
                    similar_info['similarity_score'] = similarity_score
                    
                    if similarity_score >= 55:  # Yeterince benzer
                        similar_products.append(similar_info)
                
                # Benzerlik skoruna göre sırala
                similar_products.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
                similar_products = similar_products[:8]  # Max 8 benzer ürün
            except Exception as e:
                print(f"❌ Benzer ürün arama hatası: {e}")
        
        # Sonuç paketi oluştur
        result = {
            'ana_urun': product_info,
            'varyantlar': variants_info,
            'benzer_urunler': similar_products,
            'arama_detaylari': {
                'url': url,
                'product_id': product_id,
                'varyant_sayisi': len(variants_info),
                'benzer_urun_sayisi': len(similar_products),
                'confidence_scores': {
                    'ana_urun': product_info.get('confidence_score', 0),
                    'ortalama_varyant': sum([v.get('confidence_score', 0) for v in variants_info]) / len(variants_info) if variants_info else 0,
                    'ortalama_benzer': sum([s.get('confidence_score', 0) for s in similar_products]) / len(similar_products) if similar_products else 0,
                    'ortalama_varyant_similarity': sum([v.get('similarity_score', 0) for v in variants_info]) / len(variants_info) if variants_info else 0,
                    'ortalama_benzer_similarity': sum([s.get('similarity_score', 0) for s in similar_products]) / len(similar_products) if similar_products else 0
                }
            },
            'arama_zamani': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Sonuçları yazdır
        self.print_enhanced_results(result)
        
        return result
    
    def check_if_category_url(self, url: str) -> Dict:
        """URL'nin kategori URL'si olup olmadığını kontrol et"""
        category_info = {'is_category': False}
        
        # Kategori URL paternleri
        patterns = [
            (r'walmart\.com/cp/([^/]+)/(\d+)', 'cp'),   # walmart.com/cp/category-name/123456
            (r'walmart\.com/browse/([^/]+)/(\d+)', 'browse'),  # walmart.com/browse/category/123456
            (r'walmart\.com/shop/([^/]+)/(\d+)', 'shop'),  # walmart.com/shop/category/123456
            (r'walmart\.com/c/([^/]+)/(\d+)', 'c')  # walmart.com/c/category/123456
        ]
        
        for pattern, cat_type in patterns:
            match = re.search(pattern, url)
            if match:
                category_info['is_category'] = True
                category_info['category_type'] = cat_type
                category_info['category_name'] = match.group(1).replace('-', ' ')
                category_info['category_id'] = match.group(2)
                break
        
        return category_info
    
    def scan_category_url(self, url: str, category_info: Dict) -> Dict:
        """Kategori URL'sindeki ürünleri listele"""
        print(f"🔍 Kategori taraması yapılıyor: {category_info.get('category_name', 'Bilinmeyen')}")
        
        category_id = category_info.get('category_id', '')
        category_name = category_info.get('category_name', '').replace('-', ' ')
        
        # Kategori ürünlerini ara
        products = []
        
        # Yöntem 1: Kategori ID'si ile arama
        if category_id:
            params = {
                'categoryId': category_id,
                'numItems': 40,  # Daha fazla ürün göster
                'format': 'json'
            }
            
            try:
                response = requests.get(self.search_url, headers=self.get_headers(),
                                      params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'items' in data and data['items']:
                        products = data['items']
                        print(f"✅ Kategori ID aramasıyla {len(products)} ürün bulundu")
            except Exception as e:
                print(f"❌ Kategori arama hatası: {e}")
        
        # Yöntem 2: Kategori adı ile arama
        if not products and category_name:
            params = {
                'query': category_name,
                'numItems': 40,
                'format': 'json'
            }
            
            try:
                response = requests.get(self.search_url, headers=self.get_headers(),
                                      params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'items' in data and data['items']:
                        products = data['items']
                        print(f"✅ Kategori adı aramasıyla {len(products)} ürün bulundu")
            except Exception as e:
                print(f"❌ Kategori adı arama hatası: {e}")
        
        # Ürün bulunamadıysa hata döndür
        if not products:
            return {"hata": f"Kategori için ürün bulunamadı: {category_name} (ID: {category_id})"}
        
        # Ürünleri işle
        processed_products = []
        
        for product in products[:20]:  # İlk 20 ürünü al
            try:
                # Temel ürün bilgilerini çıkar
                product_info = self.extract_enhanced_data(product)
                processed_products.append(product_info)
            except Exception as e:
                print(f"❌ Ürün işleme hatası: {e}")
        
        # Sonuç paketi oluştur
        result = {
            'kategori_bilgisi': {
                'kategori_adi': category_name,
                'kategori_id': category_id,
                'url': url
            },
            'urunler': processed_products,
            'arama_detaylari': {
                'toplam_bulunan': len(products),
                'gosterilen': len(processed_products)
            },
            'arama_zamani': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Özet yazdır
        print(f"\n{'='*80}")
        print(f"📂 KATEGORİ: {category_name}")
        print(f"🔢 Kategori ID: {category_id}")
        print(f"📊 Toplam {len(products)} ürün bulundu, {len(processed_products)} ürün gösteriliyor")
        print(f"{'='*80}")
        
        # İlk 5 ürünü yazdır
        for i, product in enumerate(processed_products[:5], 1):
            print(f"{i}. {product.get('urun_adi', 'N/A')} - {product.get('fiyat_bilgileri', {}).get('current_price', 'N/A')}")
            print(f"   Marka: {product.get('marka', 'N/A')} | Item ID: {product.get('item_id', 'N/A')}")
            print(f"   🔗 {product.get('walmart_link', 'N/A')}")
            print("-" * 40)
        
        print(f"... ve {len(processed_products) - 5} ürün daha")
        print(f"{'='*80}")
        
        return result
    
    def extract_info_from_url(self, url: str) -> Dict:
        """URL'den ürün bilgilerini çıkarma denemeleri"""
        info = {}
        
        # URL'den ürün adı çıkar
        title_patterns = [
            r'ip/([^/]+)/\d+',  # walmart.com/ip/product-name/123456
            r'ip/([^?]+)',      # walmart.com/ip/product-name?param=value
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, url)
            if match:
                # URL'deki çizgileri boşluğa çevir
                slug = match.group(1).replace('-', ' ').replace('_', ' ')
                info["product_title"] = slug
                break
        
        # Ürün ID'si (zaten diğer fonksiyonla alınıyor ama yedek olarak burada da olsun)
        id_patterns = [
            r'ip/(?:[^/]+/)?(\d+)',
            r'/(\d+)(?:\?|$)'
        ]
        
        for pattern in id_patterns:
            match = re.search(pattern, url)
            if match:
                info["product_id"] = match.group(1)
                break
        
        # Kategori bilgisi
        cat_patterns = [
            r'walmart\.com/cp/([^/]+)/(\d+)',  # walmart.com/cp/category-name/123456
            r'walmart\.com/browse/([^/]+)/(\d+)'  # walmart.com/browse/category/123456
        ]
        
        for pattern in cat_patterns:
            match = re.search(pattern, url)
            if match:
                info["category_name"] = match.group(1).replace('-', ' ')
                info["category_id"] = match.group(2)
                break
        
        return info
    
    def extract_upc_or_sku_from_url(self, url: str) -> str:
        """URL'den UPC veya SKU kodunu çıkarmaya çalış"""
        # UPC veya SKU parametreleri
        upc_patterns = [
            r'upc=(\d+)',
            r'sku=(\w+)',
            r'product_id=(\w+)',
            r'code=(\w+)'
        ]
        
        for pattern in upc_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ""
    
    def search_product_by_keyword(self, keyword: str) -> Dict:
        """Anahtar kelime ile ürün ara"""
        if not keyword or not self.ensure_valid_token():
            return {}
        
        try:
            params = {
                'query': keyword,
                'numItems': 25,
                'format': 'json'
            }
            
            response = requests.get(self.search_url, headers=self.get_headers(),
                                  params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"❌ Arama hatası: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"❌ Arama hatası: {e}")
            return {}
            
    def find_best_match_for_url(self, items: List[Dict], url: str, extracted_info: Dict) -> Optional[Dict]:
        """URL'ye en iyi uyan ürünü bul"""
        if not items:
            return None
            
        # Ürün ID'si varsa doğrudan eşleşme ara
        product_id = extracted_info.get("product_id", "")
        if product_id:
            for item in items:
                if str(item.get("itemId", "")) == product_id:
                    return item
        
        # Ürün adı eşleşmesi ara
        product_title = extracted_info.get("product_title", "").lower()
        if product_title:
            scored_items = []
            
            for item in items:
                item_title = item.get("title", "").lower()
                
                # Başlık benzerlik skoru hesapla
                score = 0
                
                # Tam kelime eşleşmeleri
                for word in product_title.split():
                    if len(word) > 3 and word in item_title:
                        score += 10
                
                # Ortak kelime oranı
                title_words = set(item_title.split())
                url_words = set(product_title.split())
                common_words = title_words.intersection(url_words)
                
                if len(url_words) > 0:
                    match_ratio = len(common_words) / len(url_words)
                    score += match_ratio * 50
                
                scored_items.append((item, score))
            
            # En yüksek skorlu ürünü döndür
            if scored_items:
                scored_items.sort(key=lambda x: x[1], reverse=True)
                best_item, best_score = scored_items[0]
                
                # Yeterince iyi eşleşme var mı?
                if best_score >= 30:
                    return best_item
        
        # Eğer burada hala bir eşleşme bulunmadıysa, ilk ürünü döndür
        return items[0]
    
    def bulk_scan(self, input_file: str, output_file: str = None, scan_type: str = "upc") -> Dict:
        """Toplu tarama işlemi
        scan_type: "upc" veya "url" - Tarama türü
        """
        print(f"\n{'='*80}")
        print(f"🛒 WALMART BULK SCANNER: {input_file}")
        print(f"{'='*80}")
        
        if not os.path.exists(input_file):
            return {"hata": f"Dosya bulunamadı: {input_file}"}
        
        results = []
        errors = []
        success_count = 0
        error_count = 0
        
        # Token kontrolü
        if not self.ensure_valid_token():
            return {"hata": "API token alınamadı"}
        
        try:
            # Dosyayı satır satır oku
            with open(input_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            total_items = len(lines)
            print(f"✅ Toplam {total_items} adet {scan_type.upper()} okundu, tarama başlıyor...")
            
            for i, line in enumerate(lines, 1):
                try:
                    print(f"\n[{i}/{total_items}] {scan_type.upper()} taranıyor: {line}")
                    
                    if scan_type.lower() == "upc":
                        result = self.scan_upc_pro_enhanced(line)
                    elif scan_type.lower() == "url":
                        result = self.scan_by_url(line)
                    else:
                        raise ValueError(f"Geçersiz tarama türü: {scan_type}")
                    
                    if "hata" in result:
                        print(f"❌ Tarama hatası: {result['hata']}")
                        errors.append({"item": line, "error": result['hata']})
                        error_count += 1
                    else:
                        results.append(result)
                        success_count += 1
                        print(f"✅ Tarama başarılı!")
                    
                    # Her 5 taramada bir token yenile
                    if i % 5 == 0:
                        self.get_access_token()
                    
                    # Dosyaya kaydet (her 10 işlemde bir)
                    if i % 10 == 0 and output_file:
                        self.save_bulk_results(output_file, results, errors, success_count, error_count, total_items)
                        print(f"💾 Ara sonuçlar kaydedildi: {output_file}")
                    
                    # Rate limiting
                    time.sleep(1)  # API rate limiting için 1 saniye bekle
                    
                except Exception as e:
                    print(f"❌ İşlem hatası: {e}")
                    errors.append({"item": line, "error": str(e)})
                    error_count += 1
            
            # Final sonuçları kaydet
            if output_file:
                final_output = self.save_bulk_results(output_file, results, errors, success_count, error_count, total_items)
                print(f"💾 Sonuçlar kaydedildi: {output_file}")
            else:
                timestamp = int(time.time())
                auto_output = f"walmart_bulk_{scan_type}_{timestamp}.json"
                final_output = self.save_bulk_results(auto_output, results, errors, success_count, error_count, total_items)
                print(f"💾 Sonuçlar otomatik kaydedildi: {auto_output}")
            
            print(f"\n{'='*80}")
            print(f"🛒 TOPLU TARAMA TAMAMLANDI")
            print(f"✅ Başarılı: {success_count}/{total_items}")
            print(f"❌ Başarısız: {error_count}/{total_items}")
            print(f"{'='*80}")
            
            return final_output
            
        except Exception as e:
            print(f"❌ Toplu tarama hatası: {e}")
            return {"hata": str(e), "sonuclar": results, "hatalar": errors}
    
    def save_bulk_results(self, output_file: str, results: List, errors: List, 
                         success_count: int, error_count: int, total_items: int) -> Dict:
        """Toplu tarama sonuçlarını dosyaya kaydet"""
        output = {
            "ozet": {
                "toplam": total_items,
                "basarili": success_count,
                "basarisiz": error_count,
                "basari_orani": f"{(success_count / total_items) * 100:.1f}%" if total_items > 0 else "0%",
                "tamamlanma_zamani": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "sonuclar": results,
            "hatalar": errors
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        return output

def main():
    print("🛒 WALMART PRO UPC SCANNER - ENHANCED VERSION")
    print("=" * 80)
    print("✨ Özellikler:")
    print("   • Multi-method UPC search (UPC, GTIN, Query)")
    print("   • URL based product scanning")
    print("   • Bulk scanning capability (UPC or URL)")
    print("   • Advanced variant detection")
    print("   • Smart similar product matching")
    print("   • Confidence scoring system")
    print("   • Enhanced data extraction")
    print("   • Separate Product ID tracking")
    print("=" * 80)
    
    scanner = WalmartProScanner(DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET)
    
    while True:
        print("\n" + "="*80)
        print("1. UPC ile tarama")
        print("2. URL ile tarama")
        print("3. Toplu UPC tarama")
        print("4. Toplu URL tarama")
        print("5. Çıkış")
        secim = input("Seçiminiz (1-5): ").strip()
        
        if secim == "5":
            print("👋 Görüşürüz!")
            break
            
        elif secim == "1":
            # UPC ile tarama
            upc = input("UPC kodu girin: ").strip()
            if not upc:
                print("❌ UPC kodu gerekli!")
                continue
                
            # Validate UPC format
            if not upc.isdigit() or len(upc) not in [8, 12, 13, 14]:
                print("⚠️  Geçersiz UPC formatı! (8, 12, 13 veya 14 haneli olmalı)")
                print("🔄 Yine de devam ediliyor...")
            
            # PRO Enhanced tarama yap
            start_time = time.time()
            result = scanner.scan_upc_pro_enhanced(upc)
            end_time = time.time()
            
            if "hata" in result:
                print(f"❌ {result['hata']}")
                continue
            
            print(f"\n⚡ Tarama süresi: {end_time - start_time:.2f} saniye")
            
            # Sonucu kaydet
            try:
                filename = f"walmart_enhanced_{upc}_{int(time.time())}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"💾 Detaylı sonuç kaydedildi: {filename}")
            except Exception as e:
                print(f"❌ Dosya kaydedilemedi: {e}")
        
        elif secim == "2":
            # URL ile tarama
            url = input("Walmart ürün URL girin: ").strip()
            if not url:
                print("❌ URL gerekli!")
                continue
                
            # URL formatı kontrolü
            if "walmart.com" not in url.lower():
                print("⚠️  URL bir Walmart ürün linki olmalı!")
                print("🔄 Yine de devam ediliyor...")
            
            # URL ile tarama yap
            start_time = time.time()
            result = scanner.scan_by_url(url)
            end_time = time.time()
            
            if "hata" in result:
                print(f"❌ {result['hata']}")
                continue
            
            print(f"\n⚡ Tarama süresi: {end_time - start_time:.2f} saniye")
            
            # Sonucu kaydet
            try:
                product_id = result["arama_detaylari"]["product_id"]
                filename = f"walmart_url_{product_id}_{int(time.time())}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"💾 Detaylı sonuç kaydedildi: {filename}")
            except Exception as e:
                print(f"❌ Dosya kaydedilemedi: {e}")
        
        elif secim == "3":
            # Toplu UPC tarama
            input_file = input("UPC listesi içeren dosya adı: ").strip()
            if not input_file:
                print("❌ Dosya adı gerekli!")
                continue
                
            output_file = input("Sonuç dosyası adı (boş bırakılabilir): ").strip()
            
            # Toplu tarama yap
            start_time = time.time()
            result = scanner.bulk_scan(input_file, output_file, scan_type="upc")
            end_time = time.time()
            
            if "hata" in result and "sonuclar" not in result:
                print(f"❌ Toplu tarama hatası: {result['hata']}")
                continue
            
            print(f"\n⚡ Toplam tarama süresi: {end_time - start_time:.2f} saniye")
            
        elif secim == "4":
            # Toplu URL tarama
            input_file = input("URL listesi içeren dosya adı: ").strip()
            if not input_file:
                print("❌ Dosya adı gerekli!")
                continue
                
            output_file = input("Sonuç dosyası adı (boş bırakılabilir): ").strip()
            
            # Toplu tarama yap
            start_time = time.time()
            result = scanner.bulk_scan(input_file, output_file, scan_type="url")
            end_time = time.time()
            
            if "hata" in result and "sonuclar" not in result:
                print(f"❌ Toplu tarama hatası: {result['hata']}")
                continue
            
            print(f"\n⚡ Toplam tarama süresi: {end_time - start_time:.2f} saniye")
        
        else:
            print("❌ Geçersiz seçim! 1-5 arasında bir seçenek girin.")

if __name__ == "__main__":
    main()
