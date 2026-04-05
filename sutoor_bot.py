import requests
from bs4 import BeautifulSoup
import time
import logging
import os
import re
from urllib.parse import urljoin
import cloudscraper # السلاح السري لاختراق حماية RSS.app

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
        payload = {"api_key": SECRET_KEY, "action": "skip", "source_url": source_url}
        requests.post(PUBLISH_URL, json=payload, timeout=10)
    except: pass

def extract_high_quality_image(soup, base_url):
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"): return urljoin(base_url, og_image.get("content"))
    for img in soup.find_all('img'):
        src = img.get('data-src') or img.get('src') 
        if src:
            src_lower = src.lower()
            if not any(word in src_lower for word in ['logo', 'icon', 'avatar', 'banner']): return urljoin(base_url, src)
    return ""

def process_source(source_url, category_id, sent_links):
    logging.info(f"🔍 فحص المصدر: {source_url}")
    
    # 🌟 تشغيل المتصفح الشبح (Cloudscraper) لتخطي الحظر
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    published_count = 0 
    
    try:
        req = scraper.get(source_url, timeout=25) # استخدام السكرابر بدلاً من requests العادي
        
        # ==========================================
        # 🌟 نظام السوشيال ميديا (RSS)
        # ==========================================
        if "rss" in source_url.lower() or "youtube.com/feeds" in source_url.lower() or source_url.endswith('.xml'):
            soup = BeautifulSoup(req.content, 'html.parser')
            items = soup.find_all('item') or soup.find_all('entry')
            
            if not items:
                logging.error(f"⚠️ الرابط لا يحتوي بيانات، قد يكون الحظر قوياً أو الرابط فارغ. الكود: {req.status_code}")
                send_skip_signal(source_url)
                return

            for item in items[:5]:
                link_tag = item.find('link')
                link = link_tag.get('href') if link_tag and link_tag.has_attr('href') else (link_tag.text.strip() if link_tag else "")
                
                if not link or link in sent_links: continue
                
                title_tag = item.find('title')
                title = title_tag.text.strip() if title_tag else "خبر عاجل"
                
                desc_tag = item.find('description') or item.find('content')
                raw_desc = desc_tag.text if desc_tag else ""
                desc_soup = BeautifulSoup(raw_desc, 'html.parser')
                content = desc_soup.get_text(separator='\n\n', strip=True)
                
                # إذا كان الوصف فارغاً في الفيس بوك، اجعل العنوان هو النص
                if not content or len(content) < 10: 
                    content = title
                
                image_url = ""
                is_youtube = False
                video_id = ""
                
                if "youtube.com/watch" in link or "youtu.be/" in link:
                    match = re.search(r"(v=|youtu\.be/)([a-zA-Z0-9_-]+)", link)
                    if match: video_id, is_youtube = match.group(2), True
                
                if is_youtube:
                    iframe_html = f'<div style="text-align:center; margin-bottom: 20px;"><iframe width="100%" height="450" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe></div>'
                    content = iframe_html + "\n\n" + content
                    image_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                else:
                    media_tag = item.find('media:content') or item.find('enclosure')
                    if media_tag and media_tag.get('url'): image_url = media_tag.get('url')
                    elif desc_soup.find('img'): image_url = desc_soup.find('img').get('src')
                
                payload = {"api_key": SECRET_KEY, "action": "publish", "source_url": source_url, "title": title, "content": content, "image_url": image_url, "category_id": category_id}
                
                # نرسل الخبر لوكالتك باستخدام requests السريع العادي
                post_req = requests.post(PUBLISH_URL, json=payload, timeout=15)
                
                if post_req.status_code == 201:
                    published_count += 1
                    save_sent_link(link)
                    sent_links.add(link)
                    logging.info(f"✅ تم سحب ونشر خبر السوشيال ميديا: {title[:30]}")
                time.sleep(5)
                
            if published_count == 0: send_skip_signal(source_url)
            return 
        
        # ==========================================
        # 🌐 نظام المواقع العادية
        # ==========================================
        soup = BeautifulSoup(req.content, 'html.parser')
        article_links = []
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
    logging.info("🚀 تشغيل محرك وكالة سطور (V7 - كاسر حماية السوشيال ميديا)...")
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
