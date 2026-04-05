import requests
from bs4 import BeautifulSoup
import time
import logging
import os
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# ================= الإعدادات المركزية لوكالة سطور =================
# ⚠️ استبدل هذا الرابط بالدومين الحقيقي لوكالة سطور الخاصة بك
BASE_DOMAIN = "https://sutoor.news/" 

GET_SOURCES_URL = f"{BASE_DOMAIN}/get_bot_sources.php?key=Sutoor_Super_Secret_Key_2026"
PUBLISH_URL = f"{BASE_DOMAIN}/auto_publish.php"
SECRET_KEY = "Sutoor_Super_Secret_Key_2026"
# ==================================================================

SENT_FILE = "sent_news.txt"

def load_sent_links():
    if not os.path.exists(SENT_FILE): return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_sent_link(link):
    with open(SENT_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def extract_high_quality_image(soup, base_url):
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"): return urljoin(base_url, og_image.get("content"))
    
    twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter_image and twitter_image.get("content"): return urljoin(base_url, twitter_image.get("content"))
    
    for img in soup.find_all('img'):
        src = img.get('data-src') or img.get('src') 
        if src:
            src_lower = src.lower()
            if not any(word in src_lower for word in ['logo', 'icon', 'avatar', 'banner', 'footer', 'bg', 'header']):
                return urljoin(base_url, src)
    return ""

def process_source(source_url, category_id, sent_links):
    logging.info(f"🔍 فحص المصدر: {source_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        req = requests.get(source_url, headers=headers, timeout=20)
        soup = BeautifulSoup(req.content, 'html.parser')
        
        article_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.text.strip()
            # توسيع دائرة اصطياد الروابط لتشمل مواقع مثل وزارة الداخلية
            if any(kw in href.lower() for kw in ['news', 'article', 'details', 'view', 'read', 'item', 'id=']) or any(kw in text for kw in ["اكمل القراءة", "التفاصيل", "المزيد", "قراءة", "خبر"]):
                full_link = urljoin(source_url, href)
                if full_link not in article_links and full_link != source_url and len(full_link) > len(source_url) + 5:
                    article_links.append(full_link)
        
        if not article_links:
            logging.info(f"⚠️ لم يتم العثور على أي روابط أخبار واضحة في: {source_url}")
            return

        for link in article_links[:5]:
            if link in sent_links: continue 
                
            logging.info(f"⏳ الدخول للخبر وتحليله: {link}")
            news_req = requests.get(link, headers=headers, timeout=20)
            news_soup = BeautifulSoup(news_req.content, 'html.parser')
            
            # --- استخراج العنوان (دعم شامل للمواقع المعقدة) ---
            title_tag = news_soup.find('h1') or news_soup.find('h2') or news_soup.find('h3')
            if title_tag:
                title = title_tag.text.strip()
            else:
                title = news_soup.title.text.strip() if news_soup.title else ""
            
            if not title or len(title) < 10: continue
            
            # --- استخراج المحتوى (دعم شامل) ---
            paragraphs = news_soup.find_all('p')
            content = "\n\n".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 30])
            
            if not content:
                # إذا لم يجد فقرات <p>، يبحث عن أكبر كتلة نصية في أي <div> (لحل مشكلة وزارة الداخلية)
                divs = news_soup.find_all('div')
                long_texts = [div.get_text(separator='\n', strip=True) for div in divs if len(div.get_text(strip=True)) > 150]
                if long_texts:
                    content = max(long_texts, key=len)
            
            if not content or len(content) < 50: 
                logging.info(f"⏭️ تم تخطي الخبر لأن المحتوى قصير جداً أو فارغ: {link}")
                continue
                
            image_url = extract_high_quality_image(news_soup, link)
            
            payload = {
                "api_key": SECRET_KEY,
                "title": title,
                "content": content,
                "image_url": image_url,
                "category_id": category_id
            }
            
            logging.info(f"📤 إرسال الخبر: {title[:40]}...")
            post_req = requests.post(PUBLISH_URL, json=payload, timeout=15)
            
            if post_req.status_code == 201:
                logging.info("✅ تم النشر في وكالة سطور بنجاح!")
                save_sent_link(link)
                sent_links.add(link)
            else:
                logging.error(f"❌ فشل النشر. الكود: {post_req.status_code} - الرد: {post_req.text}")
                
            time.sleep(5) 
            
    except Exception as e:
        logging.error(f"⚠️ خطأ في معالجة المصدر {source_url}: {e}")

def run_sutoor_engine():
    logging.info("🚀 تشغيل محرك وكالة سطور الذكي (النسخة الشاملة V3)...")
    try:
        sources_req = requests.get(GET_SOURCES_URL, timeout=15)
        if sources_req.status_code == 200:
            sources = sources_req.json()
            if not sources:
                logging.info("⚠️ لم يتم العثور على أي مصادر مفعلة.")
                return
            
            sent_links = load_sent_links()
            
            for source in sources:
                process_source(source['source_url'], source['category_id'], sent_links)
        else:
            logging.error(f"❌ لا يمكن الاتصال بـ get_bot_sources.php. الكود: {sources_req.status_code}")
    except Exception as e:
        logging.error(f"⚠️ فشل الاتصال العام بالاستضافة: {e}")

if __name__ == "__main__":
    run_sutoor_engine()
