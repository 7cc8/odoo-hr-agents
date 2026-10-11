#!/usr/bin/env python3
"""
فحص اتصال LangGraph Studio
============================
يتحقق من أن LangGraph Studio يعمل محلياً على المنفذ الافتراضي
"""

import os
import sys
from dotenv import load_dotenv

def check_studio():
    """فحص LangGraph Studio"""
    
    # تحميل متغيرات البيئة
    load_dotenv()
    
    studio_url = os.environ.get("LANGGRAPH_STUDIO_URL", "http://localhost:54321")
    
    print(f"🔍 فحص LangGraph Studio على: {studio_url}")
    
    try:
        import httpx
        
        # فحص الاتصال
        response = httpx.get(f"{studio_url}/health", timeout=5)
        
        if response.status_code == 200:
            print("✅ LangGraph Studio متصل ويعمل!")
            print(f"   الرابط: {studio_url}")
            
            # تجربة استدعاء بسيط
            test_payload = {
                "messages": [{"role": "user", "content": "اهلا"}],
                "temperature": 0.7,
                "stream": False
            }
            
            chat_response = httpx.post(
                f"{studio_url}/chat/completions",
                json=test_payload,
                timeout=10.0,
                headers={"Content-Type": "application/json"}
            )
            
            if chat_response.status_code == 200:
                print("✅ استجابة الدردشة تعمل!")
                return True
            else:
                print(f"⚠️  دردشة لا تعمل: {chat_response.status_code}")
                return False
                
        else:
            print(f"❌ LangGraph Studio غير متاح: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {e}")
        print("\n💡 تأكد من:")
        print("   1. تشغيل LangGraph Studio")
        print("   2. المنفذ 54321 متاح")
        print("   3. لا يوجد برامج حماية تمنع الاتصال")
        return False

if __name__ == "__main__":
    success = check_studio()
    sys.exit(0 if success else 1)