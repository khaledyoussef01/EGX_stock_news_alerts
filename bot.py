import time
import json
import os
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

MUBASHER_STOCKS_URL = "https://www.mubasher.info/news/eg/pulse/stocks"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")

client = genai.Client(api_key=GEMINI_API_KEY)

processed_news_ids = set()

def fetch_mubasher_stocks_news():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.5"
    }
    try:
        response = requests.get(MUBASHER_STOCKS_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        news_items = []
        
        for article in soup.select('div.news-item, article, div.content-info'):
            title_elem = article.find(['h2', 'h3', 'a'])
            if title_elem:
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '') if title_elem.name == 'a' else (title_elem.find('a')['href'] if title_elem.find('a') else '')
                
                if link and not link.startswith('http'):
                    link = "https://www.mubasher.info" + link
                    
                if title:
                    news_items.append({"id": title, "title": title, "link": link})
                    
        return news_items[:15]
    except Exception as e:
        print(f"خطأ في جلب الأخبار: {e}")
        return []

def ai_analyze_news_smart(news_title):
    prompt = f"""
    أنت محلل مالي خبير للبورصة المصرية. قم بتحليل عنوان الخبر التالي بدقة عالية (اعتماداً على المعنى والدلالة وليس الكلمات المفتاحية فقط):
    "{news_title}"

    الشروط المطلوبة لإطلاق التنبيه (يجب أن يتوافق الخبر مع أحدها تماماً):
    1. أرباح الشركة (صافي الربح أو الإيرادات) قفزت أو ارتفعت بنسبة تساوي أو تزيد عن 30% أو عدة أضعاف مقارنة بالفترة السابقة.
    2. موافقة البورصة أو الهيئة على زيادة رأس مال الشركة بنسبة تتراوح بين 30% إلى 1500% (أو بصيغة أسهم مجانية مثل سهم لكل 3 أسهم، أو ما يعادلها).
    3. مستثمر رئيسي، مجلس إدارة، أو مجموعة مرتبطة ترفع حصتها في أسهم الشركة أو تقوم بشراء حصص مؤثرة.

    أجب بصيغة JSON صارمة تحتوي على المفاتيح التالية تماماً دون أي نص إضافي:
    {{
      "match": true أو false,
      "category": "نوع الشرط المتطابق أو 'غير مرشح'",
      "summary": "شرح موجز جداً ومركز لسبب التطابق باللغة العربية"
    }}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"خطأ في التحليل: {e}")
        return {"match": False, "category": "", "summary": ""}

def send_pushover_alert(title, message, click_url=""):
    url = "https://api.pushover.net/1/messages.json"
    payload = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "title": title,
        "message": message,
        "priority": 1,       # أولوية مرتفعة لضمان التنبيه الصوتي الفوري
        "sound": "pushover"  # يمكنك تغييره إلى أصوات أخرى مثل: gamelan, classical, siren, cash
    }
    if click_url:
        payload["url"] = click_url
        payload["url_title"] = "فتح الخبر على مباشر"
        
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"خطأ في إرسال Pushover: {response.text}")
    except Exception as e:
        print(f"خطأ في الاتصال بـ Pushover: {e}")

def main():
    news_list = fetch_mubasher_stocks_news()
    for news in news_list:
        news_id = news['id']
        if news_id in processed_news_ids:
            continue
        processed_news_ids.add(news_id)
        
        analysis = ai_analyze_news_smart(news['title'])
        if analysis.get("match") == True:
            alert_title = f"🚨 فرصة EGX: {analysis.get('category')}"
            alert_body = f"{news['title']}\n\n💡 التحليل: {analysis.get('summary')}"
            send_pushover_alert(alert_title, alert_body, click_url=news.get('link'))

if __name__ == "__main__":
    main()
