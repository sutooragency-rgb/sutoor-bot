import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from google import genai

API_KEY_GEMINI = os.environ.get("GEMINI_API_KEY")
SECRET_KEY = os.environ.get("SUTOOR_SECRET")

SITE_API_URL = "https://sutoor.news/news_api/auto_publish.php"
SOURCES_URL = f"https://sutoor.news/news_api/get_bot_sources.php?key={SECRET_KEY}"

# تفعيل الذكاء الاصطناعي بالمكتبة الجديدة لجوجل
client = genai.Client(api_key=API_KEY_GEMINI)

def get_latest_links(category_url):
    """صيد الروابط من صفحة القسم"""
    print(f"🔍 جاري مسح صفحة القسم: {category_url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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
        return links[:4] # سحب أحدث 4 روابط
    except Exception as e:
        print(f"❌ خطأ في مسح القسم: {e}")
        return []

def extract_news_content(article_url):
    """سحب النص والصورة من الخبر"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(article_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        image_url = "https://sutoor.news/assets/images/default.jpg"
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]

        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        
        return text.strip(), image_url
    except Exception as e:
        return "", ""

def process_and_publish():
    print("🤖 الصياد الآلي لوكالة سطور بدأ العمل...")
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
            print(f"⚠️ جاري تخطي رابط فيسبوك (غير مدعوم برمجياً): {category_url}")
            continue
            
        article_links = get_latest_links(category_url)
        
        for url in article_links:
            print(f"📡 فحص الرابط: {url}")
            raw_text, image_url = extract_news_content(url)
            
            if len(raw_text) < 150:
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
                print("🧠 جاري التحرير بالذكاء الاصطناعي...")
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
                    print(f"✅ تم النشر بنجاح: {title}")
                elif pub_response.status_code == 200 and resp_json.get("status") == "ignored":
                    print(f"⏭️ تم التخطي (الخبر منشور مسبقاً في وكالتك)")
                else:
                    print(f"❌ خطأ النشر: {pub_response.text}")
                    
            except Exception as e:
                print(f"❌ خطأ في المعالجة: {e}")

if __name__ == "__main__":
    process_and_publish()
