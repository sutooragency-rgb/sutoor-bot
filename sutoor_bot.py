import requests
from bs4 import BeautifulSoup
import time
import logging
import os
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# ================= الإعدادات المركزية لوكالة سطور =================
# ⚠️ استبدل هذا الرابط بالدومين الحقيقي لوكالة سطور الخاصة بك
BASE_DOMAIN = "https://sutoor.com" 

# روابط الاتصال بملفات الـ PHP الموجودة في استضافة هوستنجر
GET_SOURCES_URL = f"{BASE_DOMAIN}/get_bot_sources.php?key=Sutoor_Super_Secret_Key_2026"
PUBLISH_URL = f"{BASE_DOMAIN}/auto_publish.php"
SECRET_KEY = "Sutoor_Super_Secret_Key_2026"
# ==================================================================

# ملف الأرشيف (لضمان عدم نشر الخبر مرتين)
SENT_FILE = "sent_news.txt"

def load_sent_links():
    if not os.path.exists(SENT_FILE): return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_sent_link(link):
    with open(SENT_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def extract_high_quality_image(soup, base_url):
    """
    قناص الصور: يبحث عن الصورة الرسمية للخبر بأعلى جودة.
    يتجاوز الحماية ويتجاوز التحميل البطيء (Lazy Load) العشوائي في المواقع.
    """
    # 1. المحاولة الذهبية: صورة الـ Open Graph (التي تظهر عند مشاركة الرابط في فيسبوك)
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        return urljoin(base_url, og_image.get("content"))
    
    # 2. المحاولة الفضية: صورة تويتر الرسمية للخبر
    twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter_image and twitter_image.get("content"):
        return urljoin(base_url, twitter_image.get("content"))
    
    # 3. المحاولة البرونزية: البحث اليدوي في المقال وتجاوز اللوجو والأيقونات
    for img in soup.find_all('img'):
        # استخدام data-src لاصطياد الصور المخفية بـ Lazy Load
        src = img.get('data-src') or img.get('src') 
        if src:
            src_lower = src.lower()
            if not any(word in src_lower for word in ['logo', 'icon', 'avatar', 'banner', 'footer', 'bg']):
                return urljoin(base_url, src)
    return ""

def process_source(source_url, category_id, sent_links):
    logging.info(f"🔍 فحص المصدر: {source_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        req = requests.get(source_url, headers=headers, timeout=20)
        soup = BeautifulSoup(req.content, 'html.parser')
        
        # استخراج روابط الأخبار الفردية (الغوص العميق في بطاقات الأخبار)
        article_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.text.strip()
            # فلترة الروابط لاختيار تفاصيل الأخبار الحقيقية فقط
            if any(kw in href.lower() for kw in ['news', 'article', 'details', 'view', 'read', 'item']) or "اكمل القراءة" in text or "التفاصيل" in text or "المزيد" in text:
                full_link = urljoin(source_url, href)
                if full_link not in article_links and full_link != source_url:
                    article_links.append(full_link)
        
        # معالجة أحدث 5 أخبار فقط لتجنب الضغط على سيرفرات هوستنجر
        for link in article_links[:5]:
            if link in sent_links:
                continue 
                
            logging.info(f"⏳ الدخول للخبر وتحليله: {link}")
            news_req = requests.get(link, headers=headers, timeout=20)
            news_soup = BeautifulSoup(news_req.content, 'html.parser')
            
            # --- استخراج العنوان ---
            title_tag = news_soup.find('h1') or news_soup.find('h2')
            if not title_tag: continue
            title = title_tag.text.strip()
            
            # --- استخراج المحتوى ---
            paragraphs = news_soup.find_all('p')
            # نأخذ الفقرات التي تحتوي على نصوص طويلة نسبياً لتجنب الكلمات القصيرة
            content = "\n\n".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 30])
            if not content: continue
                
            # --- استخراج الصورة (عن طريق قناص الصور V2) ---
            image_url = extract_high_quality_image(news_soup, link)
            
            # --- الإرسال إلى ملف الاستقبال في وكالة سطور ---
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
                logging.info("✅ تم النشر في وكالة سطور بنجاح (مع الصورة)!")
                save_sent_link(link)
                sent_links.add(link)
            else:
                logging.error(f"❌ فشل النشر. الكود: {post_req.status_code}")
                
            time.sleep(5) # استراحة بين كل خبر وآخر لتجنب حظر الآي بي
            
    except Exception as e:
        logging.error(f"⚠️ خطأ في معالجة المصدر {source_url}: {e}")

def run_sutoor_engine():
    logging.info("🚀 تشغيل محرك وكالة سطور الذكي (النسخة الثانية V2)...")
    try:
        # 1. الاتصال العكسي: جلب المواقع ديناميكياً من لوحة تحكم وكالة سطور
        sources_req = requests.get(GET_SOURCES_URL, timeout=15)
        if sources_req.status_code == 200:
            sources = sources_req.json()
            if not sources:
                logging.info("⚠️ لم يتم العثور على أي مصادر مفعلة. يرجى إضافتها من لوحة تحكم الوكالة.")
                return
            
            sent_links = load_sent_links()
            
            # 2. تشغيل عملية المعالجة لكل موقع مضاف
            for source in sources:
                process_source(source['source_url'], source['category_id'], sent_links)
        else:
            logging.error(f"❌ لا يمكن الاتصال بملف get_bot_sources.php. تأكد من الرابط. الكود: {sources_req.status_code}")
    except Exception as e:
        logging.error(f"⚠️ فشل الاتصال العام بالاستضافة: {e}")

if __name__ == "__main__":
    # تشغيل مباشر لمرة واحدة (GitHub Actions سيتولى تكرار هذه العملية)
    run_sutoor_engine()
