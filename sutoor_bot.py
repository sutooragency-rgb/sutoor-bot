import os
import requests
import time # مكتبة الوقت لعمل استراحة للبوت
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from google import genai

API_KEY_GEMINI = os.environ.get("GEMINI_API_KEY")
SECRET_KEY = os.environ.get("SUTOOR_SECRET")

SITE_API_URL = "https://sutoor.news/news_api/auto_publish.php"
SOURCES_URL = f"https://sutoor.news/news_api/get_bot_sources.php?key={SECRET_KEY}"

client = genai.Client(api_key=API_KEY_GEMINI)

def get_latest_links(category_url):
    print(f"🔍 جاري مسح صفحة القسم: {category_url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        if "t.me" in category_url:
            if "/s/" not in category_url:
                category_url = category_url.replace("t.me/", "t.me/s/")
            response = requests.get(category_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            for a_tag in soup.find_all('a', class_='tgme_widget_message_date'):
                full_url = a_tag.get('href')
                if full_url and full_url not in links:
                    links.append(full_url)
            return links[-3:] # سحب أحدث 3 منشورات لتقليل الضغط على جوجل

        response = requests.get(category_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        base_domain = urlparse(category_url).netloc
        links = []
        for a_tag in soup.find_all('a', href=True):
            full_url = urljoin(category_url, a_tag['href'])
            parsed = urlparse(full_url)
            if parsed.netloc == base_domain and len(parsed.path) > 15:
                if full_url not in links:
                    links.append(full_url)
        return links[:3]
    except Exception as e:
        return []

def extract_news_content(article_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        if "t.me" in article_url:
            if "?embed=1" not in article_url:
                article_url += "?embed=1"
            response = requests.get(article_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            text_div = soup.find("div", class_="tgme_widget_message_text")
            text = text_div.get_text(separator=" ") if text_div else ""
            image_url = ""
            img_a = soup.find("a", class_="tgme_widget_message_photo_wrap")
            if img_a and img_a.get("style") and "url(" in img_a["style"]:
                image_url = img_a["style"].split("url('")[1].split("')")[0]
            return text.strip(), image_url

        response = requests.get(article_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        image_url = ""
        og_image = soup.find("meta", property="og:image")
        tw_image = soup.find("meta", attrs={"name": "twitter:image"})
        if og_image and og_image.get("content"):
            image_url = og_image["content"]
        elif tw_image and tw_image.get("content"):
            image_url = tw_image["content"]
        else:
            first_img = soup.find("img")
            if first_img and first_img.get("src"):
                image_url = first_img["src"]

        if image_url and not image_url.startswith("http"):
            image_url = urljoin(article_url, image_url)

        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        return text.strip(), image_url
    except Exception as e:
        return "", ""

def process_and_publish():
    print("🤖 الصياد الآلي بدأ العمل (مع فرامل الذكاء الاصطناعي لحماية الحساب)...")
    try:
        response = requests.get(SOURCES_URL)
        sources = response.json()
    except Exception as e:
        print("❌ فشل الاتصال بقاعدة البيانات.")
        return

    for src in sources:
        category_url = src['source_url']
        cat_id = src['category_id']
        
        if "facebook.com" in category_url:
            continue
            
        article_links = get_latest_links(category_url)
        
        for url in article_links:
            print(f"📡 فحص الرابط: {url}")
            raw_text, image_url = extract_news_content(url)
            
            if len(raw_text) < 40:
                print("⚠️ النص قصير جداً، سيتم تخطيه.")
                continue

            prompt = f"""
            أنت محرر صحفي محترف في وكالة سطور الإخبارية.
            أعد صياغة هذا الخبر بشكل حصري:
            1. عنوان رئيسي جذاب ومختصر في السطر الأول.
            2. السطر الثاني يبدأ بـ "سطور الإخبارية / بغداد" أو مكان الحدث.
            3. تفاصيل الخبر بأسلوب رصين.
            4. لا تضع أي روابط أو تشير للمصدر الأصلي.
            
            النص الخام:
            {raw_text[:4000]}
            """
            
            try:
                print("🧠 جاري التحرير بالذكاء الاصطناعي (يرجى الانتظار لتجنب الحظر)...")
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                edited_news = response.text
                
                parts = edited_news.strip().split('\n', 1)
                title = parts[0].replace('*', '').strip()
                content = parts[1].strip() if len(parts) > 1 else edited_news

                payload = {
                    "api_key": SECRET_KEY,
                    "title": title,
                    "content": content,
                    "category_id": cat_id,
                    "image_url": image_url,
                    "original_url": url 
                }
                
                pub_response = requests.post(SITE_API_URL, json=payload)
                try:
                    resp_json = pub_response.json()
                except:
                    resp_json = {}
                
                if pub_response.status_code == 201:
                    print(f"✅ تم النشر بنجاح (مع الصورة): {title}")
                elif pub_response.status_code == 200 and resp_json.get("status") == "ignored":
                    print(f"⏭️ تم التخطي (الخبر منشور مسبقاً)")
                else:
                    print(f"❌ خطأ النشر: {pub_response.text}")
                
                # إعطاء استراحة للبوت لمدة 10 ثوانٍ لحماية حسابك في جوجل من الحظر المؤقت
                time.sleep(10)
                
            except Exception as e:
                print(f"❌ خطأ في المعالجة: {e}")
                time.sleep(10) # حتى لو حدث خطأ، نريحه قليلاً

if __name__ == "__main__":
    process_and_publish()
