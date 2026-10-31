#!/usr/bin/env python3
"""
اختبار نظام الدردشة
==================
"""

import requests
import json

def test_chat():
    url = "http://localhost:8000/api/chat"
    
    test_messages = [
        "هلا",
        "مساعدة", 
        "كم عدد الموظفين؟",
        "شكراً"
    ]
    
    print("🧪 اختبار نظام الدردشة المحسن...")
    print("=" * 50)
    
    for i, msg in enumerate(test_messages, 1):
        print(f"\n{i}. إرسال: '{msg}'")
        
        try:
            response = requests.post(
                url,
                json={"message": msg},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("response", {}).get("content", "")
                print(f"   ✅ الرد: {content[:100]}{'...' if len(content) > 100 else ''}")
                print(f"   📊 المزود: {data.get('response', {}).get('provider', 'unknown')}")
            else:
                print(f"   ❌ خطأ HTTP: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ خطأ: {e}")
    
    print("\n" + "=" * 50)
    print("✅ انتهاء الاختبار")

if __name__ == "__main__":
    test_chat()