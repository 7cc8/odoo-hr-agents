"""
تصنيف النية - Classify Intent
===============================
يصنف طلبات المستخدم بناءً على قواعد حتمية بدل الثابت "read"
"""

import re
from typing import Dict, List, Optional, Tuple


def classify_intent(user_query: str, context: Optional[Dict] = None) -> Dict[str, str]:
    """
    تصنيف نية المستخدم بناءً على قواعد حتمية
    يرجع: {"intent": "read/write/archive/delete/excel_import", "confidence": "high/medium/low", "details": "..."}
    
    P4: دعم مسار Excel - إذا كان السياق يحتوي على excel_file_path
    """
    query = user_query.lower().strip()
    
    # P4: فحص وجود ملف Excel في السياق
    if context and context.get("excel_file_path"):
        return {"intent": "excel_import", "confidence": "high", "details": "استيراد من ملف Excel"}
    
    # كلمات الحدود لضمان عدم التطابق الجزئي
    def has_word_boundary(pattern: str, text: str) -> bool:
        """فحص وجود الكلمة بحدود واضحة"""
        return bool(re.search(rf'\b{re.escape(pattern)}\b', text))
    
    # ═══ تصنيف الحذف/الأرشفة ═══
    archive_keywords = ["أرشف", "أرشفة", "أرشيف", "معطل", "غير نشط", "مؤرشف", "archive", "deactivate", "disable"]
    delete_keywords = ["احذف", "حذف", "امسح", "مسح", "إزالة", "delete", "remove", "unlink"]
    
    if any(has_word_boundary(kw, query) for kw in delete_keywords):
        return {"intent": "delete", "confidence": "high", "details": "طلب حذف واضح"}
    
    if any(has_word_boundary(kw, query) for kw in archive_keywords):
        return {"intent": "archive", "confidence": "high", "details": "طلب أرشفة/تعطيل"}
    
    # ═══ تصنيف التعديل ═══
    # تجنب التطابق الجزئي مع "غير النشطين" و "معدل الراتب"
    write_keywords = ["عدل", "غير", "حدث", "أضف", "انشئ", "انشاء", "اكتب", "edit", "update", "create", "add", "modify"]
    
    # استثناءات: عبارات لا تعني التعديل
    safe_phrases = [
        "غير النشطين", "غير نشط", "غير محدد", "غير معروف", "غير المحددين",
        "معدل الراتب", "معدل العمل", "معدل الأداء", "عدد الموظفين", "الموظفين غير"
    ]
    
    # فحص الاستثناءات أولاً
    if any(phrase in query for phrase in safe_phrases):
        pass  # متابعة للتصنيف كقراءة
    elif any(has_word_boundary(kw, query) for kw in write_keywords):
        # تجاهل الكلمات الآمنة مثل "عدد" في "عدد الموظفين" أو "غير" في "غير المحددين"
        if not any(safe_word in query for safe_word in ["عدد الموظفين", "معدل", "الموظفين غير", "غير المحددين"]):
            return {"intent": "write", "confidence": "high", "details": "طلب تعديل/إنشاء"}
    
    # ═══ تصنيف القراءة المتخصصة ═══
    
    # أسئلة العد والإحصاء
    count_keywords = ["كم", "عدد", "احصاء", "إحصائية", "count", "how many"]
    if any(kw in query for kw in count_keywords):
        
        # تحديد نوع العد
        if any(word in query for word in ["كل الشركات", "النظام ككل", "الإجمالي", "جميع", "total", "all"]):
            return {"intent": "read_count_total", "confidence": "high", "details": "عد إجمالي لكل الشركات"}
        
        elif "شركة" in query and any(word in query for word in ["كل", "توزيع", "وزع"]):
            return {"intent": "read_count_by_company", "confidence": "high", "details": "عد موزع على الشركات"}
        
        elif any(word in query for word in ["شركة", "company"]):
            return {"intent": "read_count_by_company", "confidence": "high", "details": "عد لشركة محددة"}
        
        else:
            return {"intent": "read_count_single", "confidence": "medium", "details": "عد عادي"}
    
    # أسئلة التوزيع والتجميع
    distribution_keywords = ["وزع", "وزّع", "توزيع", "distribute", "group", "breakdown"]
    if any(kw in query for kw in distribution_keywords):
        return {"intent": "read_distribution", "confidence": "high", "details": "طلب توزيع البيانات"}
    
    # أسئلة الشركات
    company_keywords = ["شركة", "شركات", "منشأة", "منظمة", "company", "companies"]  
    if any(kw in query for kw in company_keywords):
        
        if any(word in query for word in ["متاحة", "المتوفرة", "الموجودة", "available"]) or "ما الشركات" in query:
            return {"intent": "read_companies_list", "confidence": "high", "details": "طلب قائمة الشركات"}
        
        # إذا كان هناك كلمات عد، يُصنف كعد
        elif any(word in query for word in ["كم", "عدد", "count"]):
            return {"intent": "read_count_by_company", "confidence": "high", "details": "عد موظفين لشركة"}
        
        else:
            return {"intent": "read_company_specific", "confidence": "medium", "details": "استعلام عن شركة محددة"}
    
    # أسئلة البحث
    search_keywords = ["ابحث", "بحث", "اعثر", "ايجاد", "search", "find", "lookup"]
    if any(kw in query for kw in search_keywords):
        return {"intent": "read_search", "confidence": "high", "details": "طلب بحث"}
    
    # ═══ تصنيف افتراضي: قراءة ═══
    return {"intent": "read", "confidence": "medium", "details": "استعلام قراءة عام"}


def detect_company_references(user_query: str) -> List[Dict[str, str]]:
    """
    اكتشاف مراجع الشركات في النص
    يرجع قائمة بالمراجع مع نوع كل مرجع
    """
    query = user_query.lower().strip()
    references = []
    
    # مراجع رقمية
    if "الثانية" in query or "الثاني" in query:
        references.append({"type": "ordinal", "value": "الثانية", "meaning": "second_company"})
    
    if "الأولى" in query or "الأول" in query:
        references.append({"type": "ordinal", "value": "الأولى", "meaning": "first_company"})
    
    if "الأخرى" in query or "الآخر" in query:
        references.append({"type": "relative", "value": "الأخرى", "meaning": "other_company"})
    
    if "نفسها" in query or "نفس" in query:
        references.append({"type": "same", "value": "نفسها", "meaning": "same_company"})
    
    # أسماء الشركات الشائعة (للمطابقة الضبابية لاحقاً)
    company_patterns = [
        r"النخبة.*الذكية",
        r"توركين.*التجزئة", 
        r"العقار.*الموحدة",
        r"my company"
    ]
    
    for pattern in company_patterns:
        if re.search(pattern, query):
            references.append({"type": "name", "value": pattern, "meaning": "company_name"})
    
    return references


def expand_query_phrases(user_query: str) -> List[str]:
    """
    توسيع العبارات الشائعة لتحسين الفهم
    """
    query = user_query.lower().strip()
    
    expansions = []
    
    # عبارات المسح الشامل
    total_phrases = [
        "في النظام ككل", "إجمالي الموظفين", "كل الموظفين", 
        "جميع الشركات", "النظام كاملاً", "الإجمالي العام"
    ]
    
    if any(phrase in query for phrase in ["ككل", "كامل", "إجمالي", "جميع", "كل"]):
        expansions.extend(total_phrases)
    
    # عبارات التوضيح
    clarification_phrases = [
        "والشركة الثانية؟", "ماذا عن الأخرى؟", "والباقي؟"
    ]
    
    if any(word in query for word in ["و", "ماذا عن", "والباقي"]):
        expansions.extend(clarification_phrases)
    
    return expansions