# TODO: KatibAgent Refactoring Required

## التعديلات المطلوبة:

1. ✅ حذف WriteDecision enum - تم
2. ✅ حذف DELETE_CREATED من RollbackStrategy - تم  
3. ⏳ إضافة approved_plan parameter لـ plan()
   - يجب أن تحتوي الخطة على: TTL + consumed + user + plan_id
4. ⏳ تعديل _determine_rollback_strategy()
   - استخدام نموذج العملية بدلاً من hr.employee
   - REVERT_VALUES يجب أن يعيد القيم من log العمليات
5. ⏳ حذف confidence الثابتة من reflect()
   - استخدام تقييم ديناميكي بناءً على النتائج
6. ⏳ إضافة التحقق من فاحص بالقيمة المتوقعة
   - بعد التنفيذ، استدعاء fahas للتحقق من القيمة الجديدة
7. ⏳ تحديث _log_audit_record()
   - إضافة: model, values, approver, plan_id

## الملفات المرتبطة:
- agents/katib_agent.py (764 سطر)
- graph/agentic_nodes.py (katib_agentic_write)
- tests/test_katib_agent.py

## الأولوية: HIGH
## الوقت المقدر: 3-4 ساعات

