import requests
from bs4 import BeautifulSoup
import time
import logging
import os
import re
from urllib.parse import urljoin
import cloudscraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

BASE_DOMAIN = "https://sutoor.news" 
GET_SOURCES_URL = f"{BASE_DOMAIN}/news_api/get_bot_sources.php?key=Sutoor_Super_Secret_Key_2026"
PUBLISH_URL = f"{BASE_DOMAIN}/news_api/auto_publish.php"
SECRET_KEY = "Sutoor_Super_Secret_Key_2026"
SENT_FILE = "sent_news.txt"

def load_sent_links():
    if not os.path.exists(SENT_FILE): return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_sent_link(link):
    with open(SENT_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def send_skip_signal(source_url):
    try:
        requests.post(PUBLISH_URL, json={"api_key": SECRET_KEY, "action": "skip", "source_url": source_url}, timeout=10)
    except: pass

def extract_high_quality_image(soup, base_url):
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"): return urljoin(base_url, og_image.get("content"))
    for img in soup.find_all('img'):
        src = img.get('data-src') or img.get('src') 
        if src and not any(word in src.lower() for word in ['logo', 'icon', 'avatar', 'banner', 'footer', 'bg']): 
            return urljoin(base_url, src)
    return ""

def process_source(source_url, category_id, sent_links):
    logging.info(f"🔍 فحص المصدر: {source_url}")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    published_count = 0 
    
    try:
        # ==========================================
        # 🚀 نظام التليكرام المباشر (الجديد كلياً)
        # ==========================================
        if "t.me/" in source_url.lower():
            # تحويل الرابط العادي إلى رابط الويب العام (إضافة /s/)
            if "/s/" not in source_url: source_url = source_url.replace("t.me/", "t.me/s/")
            
            req = scraper.get(source_url, timeout=20)
            soup = BeautifulSoup(req.content, 'html.parser')
            
            messages = soup.find_all('div', class_='tgme_widget_message_wrap')
            if not messages:
                send_skip_signal(source_url)
                return
                
            for msg in messages[-5:]: # آخر 5 منشورات
                text_div = msg.find('div', class_='tgme_widget_message_text')
                if not text_div: continue
                
                content = text_div.get_text(separator='\n\n', strip=True)
                if len(content) < 30: continue
                
                # العنوان هو أول سطر من الخبر
                title = content.split('\n')[0][:80]
                if len(title) < 10: title = "خبر عاجل"
                
                # استخراج رابط الخبر لمنع التكرار
                date_link = msg.find('a', class_='tgme_widget_message_date')
                link = date_link.get('href') if date_link else ""
                if not link or link in sent_links: continue
                
                # استخراج الصورة من التليكرام
                image_url = ""
                photo_div = msg.find('a', class_='tgme_widget_message_photo_wrap')
                if photo_div:
                    style = photo_div.get('style', '')
                    match = re.search(r"background-image:url\('(.*?)'\)", style)
                    if match: image_url = match.group(1)
                
                payload = {"api_key": SECRET_KEY, "action": "publish", "source_url": source_url, "title": title, "content": content, "image_url": image_url, "category_id": category_id}
                res = requests.post(PUBLISH_URL, json=payload, timeout=15)
                
                if res.status_code == 201:
                    published_count += 1
                    save_sent_link(link)
                    sent_links.add(link)
                time.sleep(5)
                
            if published_count == 0: send_skip_signal(source_url)
            return

        # ==========================================
        # 🌐 نظام المواقع الحكومية واليوتيوب
        # ==========================================
        # (نفس الكود السابق للمواقع واليوتيوب هنا، مدمج لضمان استقرار العمل)
        req = scraper.get(source_url, timeout=25)
        soup = BeautifulSoup(req.content, 'html.parser')
        article_links = []
        
        # البحث عن روابط الأخبار في المواقع
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.text.strip()
            if any(kw in href.lower() for kw in ['news', 'article', 'details', 'view', 'read', 'item']) or any(kw in text for kw in ["اكمل القراءة", "التفاصيل", "المزيد", "قراءة"]):
                full_link = urljoin(source_url, href)
                if full_link not in article_links and full_link != source_url and len(full_link) > len(source_url) + 5:
                    article_links.append(full_link)
        
        if not article_links:
            send_skip_signal(source_url)
            return

        for link in article_links[:5]:
            if link in sent_links: continue 
                
            news_req = scraper.get(link, timeout=20)
            news_soup = BeautifulSoup(news_req.content, 'html.parser')
            
            title_tag = news_soup.find('h1') or news_soup.find('h2') or news_soup.find('h3')
            title = title_tag.text.strip() if title_tag else (news_soup.title.text.strip() if news_soup.title else "")
            if not title or len(title) < 10: continue
            
            paragraphs = news_soup.find_all('p')
            content = "\n\n".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 30])
            if not content:
                divs = news_soup.find_all('div')
                long_texts = [div.get_text(separator='\n', strip=True) for div in divs if len(div.get_text(strip=True)) > 150]
                if long_texts: content = max(long_texts, key=len)
            if not content or len(content) < 50: continue
                
            image_url = extract_high_quality_image(news_soup, link)
            
            payload = {"api_key": SECRET_KEY, "action": "publish", "source_url": source_url, "title": title, "content": content, "image_url": image_url, "category_id": category_id}
            post_req = requests.post(PUBLISH_URL, json=payload, timeout=15)
            
            if post_req.status_code == 201:
                published_count += 1
                save_sent_link(link)
                sent_links.add(link)
            time.sleep(5) 
            
        if published_count == 0: send_skip_signal(source_url)
            
    except Exception as e:
        logging.error(f"⚠️ خطأ: {e}")
        send_skip_signal(source_url)

def run_sutoor_engine():
    logging.info("🚀 تشغيل محرك وكالة سطور (V9 - قاهر التليكرام والمواقع)...")
    try:
        sources_req = requests.get(GET_SOURCES_URL, timeout=15)
        if sources_req.status_code == 200:
            sources = sources_req.json()
            if not sources: return
            sent_links = load_sent_links()
            for source in sources:
                process_source(source['source_url'], source['category_id'], sent_links)
    except Exception as e:
        logging.error(f"⚠️ فشل الاتصال العام: {e}")

if __name__ == "__main__":
    run_sutoor_engine()
