import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# جلب المفاتيح السرية التي قمت بتخزينها
API_KEY_GEMINI = os.environ.get("GEMINI_API_KEY")
SECRET_KEY = os.environ.get("SUTOOR_SECRET")

# روابط وكالة سطور
SITE_API_URL = "https://sutoor.news/news_api/auto_publish.php"
SOURCES_URL = f"https://sutoor.news/news_api/get_bot_sources.php?key={SECRET_KEY}"

# إعداد الذكاء الاصطناعي
genai.configure(api_key=API_KEY_GEMINI)
model = genai.GenerativeModel('gemini-1.5-flash') # نستخدم الموديل الأسرع والأكثر كفاءة

def fetch_news_text(url):
    """دالة لسحب النص من الروابط"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        # جلب جميع الفقرات النصية في المقال
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        return text.strip()
    except Exception as e:
        print(f"❌ خطأ في سحب الرابط {url}: {e}")
        return ""

def process_and_publish():
    print("🤖 جاري الاتصال بوكالة سطور لجلب روابط المصادر...")
    try:
        response = requests.get(SOURCES_URL)
        sources = response.json()
        if not sources:
            print("⚠️ لا توجد روابط مفعلة في لوحة التحكم حتى الآن.")
            return
    except Exception as e:
        print("❌ فشل الاتصال بلوحة تحكم الوكالة:", e)
        return

    for src in sources:
        url = src['source_url']
        category_id = src['category_id']
        
        print(f"📡 جاري قراءة الخبر من: {url}")
        raw_text = fetch_news_text(url)
        
        if len(raw_text) < 150:
            print("⚠️ النص قصير جداً أو لم يتم العثور على خبر واضح، سيتم تخطيه.")
            continue

        prompt = f"""
        أنت محرر صحفي محترف تعمل في (وكالة سطور الإخبارية).
        قم بإعادة صياغة هذا الخبر بشكل حصري واحترافي، مع الالتزام التام بالشروط التالية:
        1. اكتب عنواناً رئيسياً جذاباً ومختصراً جداً في السطر الأول فقط.
        2. ابدأ السطر الثاني بالديباجة التالية بالضبط: "سطور الإخبارية / [استنتج مكان الحدث أو اكتب بغداد]"
        3. اكتب تفاصيل الخبر بأسلوب صحفي رصين وخالي من الحشو.
        4. يُمنع منعاً باتاً وضع أي روابط، أو ذكر اسم الوكالة الأصلية التي نُقل منها الخبر.
        5. افصل بين العنوان والديباجة والنص بأسطر فارغة.

        النص الخام:
        {raw_text[:4000]}
        """
        
        try:
            print("🧠 يتم الآن إعادة صياغة الخبر بالذكاء الاصطناعي...")
            edited_news = model.generate_content(prompt).text
            
            # فصل العنوان عن بقية الخبر
            parts = edited_news.strip().split('\n', 1)
            title = parts[0].replace('*', '').strip()
            content = parts[1].strip() if len(parts) > 1 else edited_news

            payload = {
                "api_key": SECRET_KEY,
                "title": title,
                "content": content,
                "category_id": category_id,
                "image_url": "https://sutoor.news/assets/images/default.jpg" # صورة مؤقتة
            }
            
            # إرسال الخبر المحرر إلى الموقع
            pub_response = requests.post(SITE_API_URL, json=payload)
            if pub_response.status_code == 201:
                print(f"✅ تم النشر بنجاح: {title}")
            else:
                print(f"❌ خطأ أثناء النشر في الموقع: {pub_response.text}")
                
        except Exception as e:
            print(f"❌ خطأ في الذكاء الاصطناعي: {e}")

if __name__ == "__main__":
    process_and_publish()
