# Dashboard, Agents, Templates Bugfix Design

## Overview

هذا التصميم يعالج خمس مشاكل رئيسية في نظام Odoo HR Agents تمنع المستخدمين من الوصول الكامل للوظائف عبر لوحة التحكم والـ API:

1. **Template Generation** محصورة في CLI فقط - يحتاج endpoint API ودمج في Dashboard
2. **Dry-Run Results Display** لا يُظهر تفاصيل الرفض بشكل واضح - يحتاج تنسيق غني وجدول قابل للتوسيع
3. **Conditional Execution Workflow** مفقود - يحتاج منطق تفرعي يقرر بين auto-execute أو انتظار موافقة المستخدم
4. **Agent Tracing** غير مرئي للمستخدمين - يحتاج timeline عرض في Dashboard
5. **State Management** ناقص حقول - يحتاج إضافة `rejected_rows_details`, `user_execution_choice`, `auto_execute`

**التأثير**: الموظفون محبطون من عدم القدرة على توليد القوالب من Dashboard، عدم رؤية سبب رفض البيانات، وتأخير تنفيذ العمليات النظيفة التي لا تحتاج موافقة.

**استراتيجية الإصلاح**: إضافة endpoints جديدة، تحسين تنسيق البيانات المرجعة، إدخال عقدة شرطية جديدة في LangGraph، وتوسيع SerajState.

---

## Glossary

- **Bug_Condition (C)**: شرط المشكلة - الحالات التي تُظهر المشاكل الخمس
- **Property (P)**: السلوك المرغوب - النظام يعمل بشكل كامل من Dashboard/API دون CLI
- **Preservation (الحفاظ)**: API endpoints الحالية، عقد LangGraph الموجودة، اختبارات CLI
- **Template Generation**: عملية توليد ملفات Excel بقوالب company-specific
- **Dry-Run**: عملية تحقق بدون تنفيذ حقيقي لاكتشاف الأخطاء قبل الكتابة
- **Conditional Execution**: منطق تفرعي يقرر تلقائياً بين تنفيذ فوري (rejected_rows=0) أو انتظار موافقة (rejected_rows>0)
- **Seraj Meta-Agent**: وكيل التنسيق الأساسي الذي يختار ويُنسّق الوكلاء الآخرين
- **SerajState**: الحالة المشتركة في LangGraph التي تحمل جميع البيانات بين العقد
- **Agent Timeline**: عرض زمني تفاعلي لتنفيذ الوكلاء في Dashboard
- **Rejected Rows**: صفوف بيانات فشلت في التحقق خلال dry-run
- **Auto-Execute**: التنفيذ التلقائي الفوري بدون موافقة بشرية

---

## Bug Details

### Bug Condition

المشاكل تظهر عندما يحاول المستخدمون:
1. توليد قوالب من Dashboard/API (غير متاح - CLI فقط)
2. رؤية سبب رفض الصفوف في dry-run (معلومات غير كافية)
3. استيراد ملف نظيف بدون أخطاء (تأخير غير ضروري لانتظار موافقة)
4. تتبع تنفيذ الوكلاء (لا يوجد UI)
5. استخدام approval workflow مشروط (logic مفقود)

**Formal Specification:**
```
FUNCTION isBugCondition(context)
  INPUT: context of type SystemInteractionContext
  OUTPUT: boolean
  
  RETURN (
    # Bug 1: Template Generation
    (context.action == "generate_template" AND context.interface IN ["dashboard", "api"])
    OR
    # Bug 2: Dry-Run Results
    (context.action == "view_dry_run_results" AND context.rejection_count > 0 
     AND NOT hasDetailedRejectionInfo(context.response))
    OR
    # Bug 3: Conditional Execution
    (context.action == "complete_dry_run" AND context.rejection_count == 0 
     AND NOT context.auto_executed)
    OR
    # Bug 4: Agent Tracing
    (context.action == "monitor_operation" AND NOT hasAgentTimeline(context.dashboard))
    OR
    # Bug 5: State Management
    (context.graph_node == "any" AND 
     (NOT hasField(context.state, "rejected_rows_details") OR
      NOT hasField(context.state, "user_execution_choice") OR
      NOT hasField(context.state, "auto_execute")))
  )
END FUNCTION
```

### Examples

**مثال 1 - Template Generation Missing:**
- **المدخل**: مستخدم يفتح Dashboard، يبحث عن زر "Generate Template"
- **السلوك الحالي (خطأ)**: لا يوجد زر، لا يوجد خيار
- **السلوك المتوقع**: زر "Generate Template" موجود، عند الضغط يُظهر نموذج (company, template type) ثم يوفر download link

**مثال 2 - Dry-Run Rejections Unclear:**
- **المدخل**: dry-run أعاد `{"accepted": 45, "rejected": 5}`
- **السلوك الحالي (خطأ)**: عدد فقط، لا تفاصيل عن الصفوف المرفوضة
- **السلوك المتوقع**: جدول قابل للتوسيع يُظهر:
  - Row #3: "محمد أحمد" - "القسم غير موجود" - Field: `department` - Value: "قسم المبيعات" - Suggestion: "Use 'Sales'"

**مثال 3 - Clean Import Delayed:**
- **المدخل**: dry-run أعاد `{"accepted": 50, "rejected": 0}`
- **السلوك الحالي (خطأ)**: ينتظر approval من المستخدم
- **السلوك المتوقع**: "✅ All 50 rows accepted - Executing now..." ثم تنفيذ فوري

**مثال 4 - Agent Execution Hidden:**
- **المدخل**: عملية استيراد جارية
- **السلوك الحالي (خطأ)**: لا يظهر شيء في Dashboard
- **السلوك المتوقع**: 
  ```
  Agent Timeline:
  ✅ 10:15:23 - Seraj Meta-Agent - Selected agents: Fahas, Mudaqqiq, Katib
  ⏳ 10:15:25 - Fahas (Query) - Fetching departments...
  ✅ 10:15:27 - Mudaqqiq (Verify) - Checking compliance... 48/50 passed
  ⏳ 10:15:30 - Katib (Write) - Creating 48 employees...
  ```

**مثال حافة - Edge Case:**
- **المدخل**: dry-run مع rejected_rows=[{"row": 1, "reason": null}] (سبب غير معروف)
- **السلوك المتوقع**: Dashboard يُظهر "Unknown error - Contact support" مع row number

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- جميع endpoints الحالية (`/upload`, `/dry-run`, `/approve`, `/write`) تستمر في العمل بنفس JSON format
- Telegram bot integration يستمر في العمل دون تغيير
- CLI tools (`generate_employee_template.py --output-dir`) تبقى functional للـ backward compatibility
- Agent selection logic الحالي في Seraj يبقى دون تغيير (Fahas للـ query، Mudaqqiq للـ validation، Katib للـ write)
- Musleh healing logic يستمر في العمل كما هو
- LangGraph state fields الموجودة (`operation_id`, `company_id`, `user_query`, `parsed_data`) تبقى محفوظة
- Authentication (`WRITE_API_TOKEN`) و audit logging (`audit_log_access()`) يستمران
- File upload parsing (`parser.py`) و dry-run reports (`dry_run_report.py`) تبقى دون تغيير breaking
- Dashboard analytics (`/api/analytics/dashboard`) يستمر في إرجاع نفس metrics
- جميع الاختبارات الموجودة تمر بنجاح (>80% coverage)

**Scope:**
جميع المدخلات التي لا تتعلق بالوظائف الخمس الجديدة (template generation من API، عرض rejection details، conditional execution، agent timeline، state fields) يجب أن تبقى دون تأثير. هذا يشمل:
- استخدام API للعمليات العادية (upload → dry-run → approve → write)
- CLI workflows الموجودة
- Telegram bot interactions
- Dashboard analytics و overview sections

---

## Hypothesized Root Cause

بناءً على وصف المشكلة، الأسباب المحتملة:

### 1. Template Generation Issues

**السبب المحتمل الأول**: لا يوجد API endpoint لتوليد القوالب
- `web_service.py` لا يحتوي على `POST /api/template/generate`
- `generate_employee_template.py` script مستقل تماماً، غير مدمج

**السبب المحتمل الثاني**: `generate_employee_template.py` يولد قوالب generic غير مخصصة للشركة
- لا يستخدم `company_id` لتصفية departments/jobs من Odoo
- لا يدعم custom fields per company

**السبب المحتمل الثالث**: Dashboard UI لا يحتوي على section لتوليد القوالب
- المكونات HTML الموجودة لا تشمل نموذج template generation

### 2. Dry-Run Result Display Issues

**السبب المحتمل الأول**: `dry_run_report.py` يُنتج تقرير بسيط بدون تفاصيل غنية
- Rejected rows structure: `[{"row_number": N, "errors": [...]}]` بدون context
- لا يوجد formatting للأسباب بالعربية
- لا يوجد suggested fixes

**السبب المحتمل الثاني**: Seraj Meta-Agent لا يُعالج rejection details
- `agentic_nodes.py::seraj_meta_orchestration` لا يحتوي على `_format_rejection_details()` method
- Response structure بسيطة جداً

**السبب المحتمل الثالث**: Dashboard HTML لا يحتوي على جدول قابل للتوسيع
- عرض counts فقط (`45 accepted, 5 rejected`) بدون details table

**السبب المحتمل الرابع**: `template_detector.py` غير مستخدم في validation error messages
- Detection logic موجود لكن غير متكامل مع dry-run reporting

### 3. Conditional Execution Workflow Issues

**السبب المحتمل الأول**: لا توجد عقدة شرطية في LangGraph
- `agentic_nodes.py` لا يحتوي على `conditional_execution_node`
- `build_graph.py` لا يحتوي على branching logic بناءً على `rejected_rows`

**السبب المحتمل الثاني**: لا يوجد API endpoint للـ conditional approval
- `web_service.py` يفتقد `POST /api/approve-conditional`
- لا يوجد معالجة لـ user choices: "execute", "fix", "cancel"

**السبب المحتمل الثالث**: Seraj Meta-Agent لا يتخذ قرارات auto-execute
- Logic لا يفحص `rejected_rows == 0` لتفعيل auto-execution
- كل العمليات تنتظر human approval حتى النظيفة

### 4. Agent Tracing Issues

**السبب المحتمل الأول**: لا يوجد agent events service
- لا يوجد `agent_events_service.py` لتسجيل agent execution events
- Agents لا تُصدر structured events

**السبب المحتمل الثاني**: Dashboard لا يحتوي على Agent Timeline UI component
- HTML template يفتقد timeline section
- لا يوجد JavaScript لتحديث Timeline real-time

**السبب المحتمل الثالث**: لا يوجد API endpoint لاسترجاع traces
- `web_service.py` يفتقد `GET /api/agent-traces/{operation_id}`

**السبب المحتمل الرابع**: Seraj Meta-Agent لا يكشف reasoning
- Orchestration decisions غير مُسجلة في format قابل للعرض

### 5. State Management Issues

**السبب المحتمل الأول**: `SerajState` TypedDict لا يحتوي على حقول جديدة
- `graph/state.py` يفتقد:
  - `rejected_rows_details: Optional[List[Dict[str, Any]]]`
  - `user_execution_choice: Optional[str]`
  - `auto_execute: Optional[bool]`

**السبب المحتمل الثاني**: Nodes لا تملأ هذه الحقول حتى لو أضفناها
- لا يوجد logic في `agentic_nodes.py` لملء `rejected_rows_details`
- لا يوجد logic لتعيين `auto_execute = True` عندما `rejected_rows == 0`

---

## Correctness Properties

Property 1: Bug Condition - Template Generation من Dashboard/API

_For any_ طلب توليد قالب من Dashboard أو API، النظام SHALL توفير endpoint `POST /api/template/generate` يقبل `{company_id, template_type, include_example_row, language}` ويُرجع `{status, template_path, download_url, sheet_count, generated_at}` مع إمكانية download عبر `/api/template/download/{template_id}`. القوالب SHALL تكون company-specific (departments/jobs مُصفاة حسب company_id).

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Bug Condition - Dry-Run Rejection Details Display

_For any_ dry-run يُرجع rejected rows > 0، النظام SHALL إرجاع تفاصيل rejection منسّقة تحتوي على `{row_number, name, reason_ar, field, value, suggestion, can_auto_fix}` لكل صف مرفوض. Dashboard SHALL عرض جدول قابل للتوسيع بـ columns: Row #, Name, Reason (Arabic), Field, Value, Suggested Fix. Seraj Meta-Agent SHALL تطبيق `_format_rejection_details()` method لتنظيم البيانات.

**Validates: Requirements 2.5, 2.6, 2.7, 2.8**

Property 3: Bug Condition - Conditional Execution Workflow

_For any_ dry-run يكتمل، النظام SHALL تطبيق منطق شرطي:
- إذا `rejected_rows == 0`: auto-execute فوراً ويعرض "✅ All rows (X) accepted - Executing now..."
- إذا `rejected_rows > 0`: يعرض action buttons ("Execute Accepted Only (X rows)", "Try Auto-Fix (Musleh)", "Cancel - Fix Manually") وينتظر user choice عبر `POST /api/approve-conditional` مع `{operation_id, choice: "execute"|"fix"|"cancel"}`. LangGraph SHALL يحتوي على `conditional_execution_node` في `agentic_nodes.py` لتنفيذ هذا Branching.

**Validates: Requirements 2.9, 2.10, 2.11, 2.12**

Property 4: Bug Condition - Agent Tracing Visibility

_For any_ agent execution، النظام SHALL إصدار events إلى `agent_events_service` مع `{timestamp, agent, action, decision, reasoning, status}`. Dashboard SHALL عرض "Agent Timeline" section يُظهر agent execution مع icons، status indicators (✅/❌)، و reasoning tooltips. Seraj Meta-Agent SHALL كشف "Selected agents: Fahas, Mudaqqiq, Katib" مع reasoning. `GET /api/agent-traces/{operation_id}` SHALL إرجاع قائمة chronological من agent events.

**Validates: Requirements 2.13, 2.14, 2.15, 2.16**

Property 5: Bug Condition - State Management Completeness

_For any_ LangGraph node execution، `SerajState` SHALL يحتوي على:
- `rejected_rows_details: Optional[List[Dict[str, Any]]]` populated عند dry-run completion
- `user_execution_choice: Optional[str]` set إلى "execute"/"fix"/"cancel" عند user approval decision
- `auto_execute: Optional[bool]` set إلى True عندما `rejected_rows == 0`
Nodes SHALL ملء هذه الحقول في الوقت المناسب خلال workflow.

**Validates: Requirements 2.17, 2.18, 2.19**

Property 6: Preservation - Existing API Contracts

_For any_ استدعاء لـ endpoints موجودة (`/upload`, `/dry-run`, `/approve`, `/write`)، النظام SHALL إرجاع responses بنفس JSON format السابق بدون breaking changes. Telegram bot integration SHALL الاستمرار في العمل. CLI tools SHALL الاستمرار في العمل مع `--output-dir` argument.

**Validates: Requirements 3.1, 3.2, 3.3**

Property 7: Preservation - Agent Execution Logic

_For any_ orchestration بدون conditional execution، Seraj Meta-Agent SHALL الاستمرار في استخدام نفس agent selection logic (Fahas للـ query، Mudaqqiq للـ validation، Katib للـ write). Musleh healing logic SHALL الاستمرار. LangGraph state transitions SHALL الحفاظ على fields موجودة.

**Validates: Requirements 3.4, 3.5, 3.6**

Property 8: Preservation - Authentication, Security, Testing

_For any_ write operation، النظام SHALL الاستمرار في طلب `WRITE_API_TOKEN`. Audit logging SHALL الاستمرار. File upload parsing SHALL الاستمرار. Dashboard analytics SHALL الاستمرار. جميع الاختبارات الموجودة SHALL الاستمرار في النجاح (>80% coverage).

**Validates: Requirements 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16**

---

## Fix Implementation

### Changes Required

بافتراض أن تحليل الأسباب الجذرية صحيح:

#### Change Category 1: Template Generation API & Integration

**File**: `web_service.py`

**Changes**:
1. **إضافة endpoint جديد**: `POST /api/template/generate`
   - Parameters: `{company_id: int, template_type: str, include_example_row: bool = False, language: str = "ar"}`
   - Logic:
     - استدعاء `generate_employee_template.py` logic (refactor كـ function)
     - تصفية departments/jobs من Odoo باستخدام `company_id`
     - توليد Excel مع custom fields per company
     - حفظ في `UPLOAD_DIR` مع unique `template_id`
   - Response: `{"status": "success", "template_path": "...", "download_url": "/api/template/download/{template_id}", "sheet_count": 3, "generated_at": "2025-01-01T10:00:00Z"}`

2. **إضافة endpoint للتحميل**: `GET /api/template/download/{template_id}`
   - استخدام `FileResponse` لإرجاع Excel file

**File**: `generate_employee_template.py`

**Refactoring**:
- تحويل main logic إلى function: `generate_template(company_id, template_type, output_dir, ...)`
- إضافة Odoo connection للحصول على departments/jobs مُصفاة
- دعم custom fields من Odoo company settings

**File**: Dashboard HTML (embedded في `web_service.py` أو ملف منفصل)

**UI Addition**:
- إضافة section "Template Generation":
  ```html
  <div class="template-section">
    <h3>Generate Company-Specific Template</h3>
    <form id="templateForm">
      <label>Company:
        <select name="company_id">
          <option value="1">Company A</option>
          <option value="2">Company B</option>
        </select>
      </label>
      <label>Template Type:
        <select name="template_type">
          <option value="employee">Employee</option>
          <option value="contract">Contract</option>
        </select>
      </label>
      <label>
        <input type="checkbox" name="include_example_row"> Include example row
      </label>
      <button type="submit">Generate Template</button>
    </form>
    <div id="templateResult"></div>
  </div>
  ```
- JavaScript لاستدعاء `/api/template/generate` وعرض download link

#### Change Category 2: Dry-Run Rejection Details Enhancement

**File**: `graph/agentic_nodes.py`

**Method Addition في `seraj_meta_orchestration`**:
```python
def _format_rejection_details(rejected_rows: List[Dict]) -> List[Dict[str, Any]]:
    """
    تنسيق تفاصيل الصفوف المرفوضة للعرض في Dashboard.
    
    Input format (from dry_run_report.py):
    [{"row_number": 3, "errors": [{"field": "department", "message": "Department not found"}]}]
    
    Output format (enhanced):
    [{
        "row_number": 3,
        "name": "محمد أحمد",  # من parsed_data
        "reason_ar": "القسم غير موجود",  # ترجمة
        "field": "department",
        "value": "قسم المبيعات",
        "suggestion": "Use 'Sales' department",
        "can_auto_fix": True
    }]
    """
    formatted = []
    for row in rejected_rows:
        row_data = state.get("excel_parsed_data", {}).get("rows", [])[row["row_number"]]
        for error in row["errors"]:
            formatted.append({
                "row_number": row["row_number"],
                "name": row_data.get("name", "N/A"),
                "reason_ar": translate_to_arabic(error["message"]),
                "field": error["field"],
                "value": row_data.get(error["field"], ""),
                "suggestion": generate_suggestion(error),
                "can_auto_fix": is_auto_fixable(error)
            })
    return formatted
```

**Integration Point**:
- في node الذي يُعالج dry-run results، استدعاء `_format_rejection_details()` وحفظ في `state["rejected_rows_details"]`

**File**: `dry_run_report.py`

**Enhancement**:
- تحديث report structure لتشمل `row_data` في rejection info
- دمج `template_detector.py` للحصول على context أفضل

**File**: Dashboard HTML

**UI Enhancement**:
- إضافة جدول قابل للتوسيع:
  ```html
  <div id="rejectionDetails" style="display:none;">
    <h4>Rejected Rows Details</h4>
    <table>
      <thead>
        <tr>
          <th>Row #</th>
          <th>Name</th>
          <th>Reason (Arabic)</th>
          <th>Field</th>
          <th>Value</th>
          <th>Suggested Fix</th>
        </tr>
      </thead>
      <tbody id="rejectionTableBody">
        <!-- Populated dynamically -->
      </tbody>
    </table>
  </div>
  ```

#### Change Category 3: Conditional Execution Workflow

**File**: `graph/state.py`

**State Fields Addition**:
```python
class SerajState(TypedDict, total=False):
    # ... existing fields ...
    
    # Conditional Execution
    rejected_rows_details: Optional[List[Dict[str, Any]]]
    user_execution_choice: Optional[str]  # "execute" | "fix" | "cancel"
    auto_execute: Optional[bool]
```

**File**: `graph/agentic_nodes.py`

**New Node**:
```python
def conditional_execution_node(state: SerajState) -> SerajState:
    """
    عقدة شرطية تقرر بين auto-execute أو انتظار approval.
    
    Logic:
    - إذا rejected_rows == 0: set auto_execute=True → route إلى execution
    - إذا rejected_rows > 0: انتظار user_execution_choice → route حسب القرار
    """
    rejected_count = len(state.get("rejected_rows_details", []))
    
    if rejected_count == 0:
        # Auto-execute: no errors, proceed immediately
        return {
            "auto_execute": True,
            "user_execution_choice": "execute",  # implicit
            "answer": f"✅ All {state['excel_row_count']} rows accepted - Executing now..."
        }
    else:
        # Wait for user decision
        return {
            "auto_execute": False,
            "answer": f"⚠️ {rejected_count} rows rejected. Please choose an action."
        }
```

**Routing Function في `build_graph.py`**:
```python
def route_after_conditional_execution(state: SerajState) -> str:
    if state.get("auto_execute"):
        return "execute_write"  # مباشرة للكتابة
    elif state.get("user_execution_choice") == "execute":
        return "execute_write"
    elif state.get("user_execution_choice") == "fix":
        return "musleh_heal"  # إصلاح تلقائي
    else:
        return "end"  # إلغاء
```

**File**: `web_service.py`

**New Endpoint**:
```python
@app.post("/api/approve-conditional")
async def approve_conditional(
    request: Request,
    operation_id: str = Form(...),
    choice: str = Form(...)  # "execute" | "fix" | "cancel"
):
    """
    معالجة قرار المستخدم بعد dry-run مع rejected rows.
    """
    if choice not in ["execute", "fix", "cancel"]:
        raise HTTPException(400, "Invalid choice")
    
    # Update LangGraph state
    # Trigger continuation of graph execution
    
    audit_log_access("/api/approve-conditional", request, {
        "operation_id": operation_id,
        "choice": choice
    })
    
    return {"status": "choice_recorded", "operation_id": operation_id, "choice": choice}
```

**Dashboard UI**:
- إضافة action buttons عند `rejected_rows > 0`:
  ```html
  <div id="conditionalActions" style="display:none;">
    <h4>Choose Action</h4>
    <button onclick="approveConditional('execute')">
      Execute Accepted Only (<span id="acceptedCount"></span> rows)
    </button>
    <button onclick="approveConditional('fix')">
      Try Auto-Fix (Musleh)
    </button>
    <button onclick="approveConditional('cancel')">
      Cancel - Fix Manually
    </button>
  </div>
  ```

#### Change Category 4: Agent Tracing & Timeline

**File**: `agents/agent_events_service.py` (ملف جديد)

**Service Implementation**:
```python
from typing import Dict, List, Any
from datetime import datetime
import json
from pathlib import Path

EVENTS_DIR = Path("logs/agent_events")
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

def emit_agent_event(
    operation_id: str,
    agent: str,
    action: str,
    decision: Optional[str] = None,
    reasoning: Optional[str] = None,
    status: str = "in_progress"  # "in_progress" | "success" | "failed"
) -> None:
    """إصدار حدث agent للتتبع."""
    event = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent,
        "action": action,
        "decision": decision,
        "reasoning": reasoning,
        "status": status
    }
    
    event_file = EVENTS_DIR / f"{operation_id}.jsonl"
    with open(event_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def get_agent_events(operation_id: str) -> List[Dict[str, Any]]:
    """استرجاع جميع أحداث agent لعملية معينة."""
    event_file = EVENTS_DIR / f"{operation_id}.jsonl"
    if not event_file.exists():
        return []
    
    events = []
    with open(event_file, "r", encoding="utf-8") as f:
        for line in f:
            events.append(json.loads(line))
    return events
```

**Integration في Agents**:
- في كل agent (`BaseAgent` أو specific agents):
  ```python
  from agents.agent_events_service import emit_agent_event
  
  # في perceive phase:
  emit_agent_event(operation_id, "FahasAgent", "perceive", reasoning="Understanding query...")
  
  # في plan phase:
  emit_agent_event(operation_id, "FahasAgent", "plan", decision="query_odoo", reasoning="Need department list")
  
  # في execute phase:
  emit_agent_event(operation_id, "FahasAgent", "execute", status="in_progress")
  
  # بعد النجاح:
  emit_agent_event(operation_id, "FahasAgent", "execute", status="success")
  ```

**File**: `web_service.py`

**New Endpoint**:
```python
@app.get("/api/agent-traces/{operation_id}")
async def get_agent_traces(operation_id: str, request: Request):
    """استرجاع تتبع تنفيذ الوكلاء لعملية معينة."""
    from agents.agent_events_service import get_agent_events
    
    audit_log_access(f"/api/agent-traces/{operation_id}", request)
    
    events = get_agent_events(operation_id)
    return {"operation_id": operation_id, "events": events}
```

**Dashboard UI**:
- إضافة Agent Timeline section:
  ```html
  <div id="agentTimeline">
    <h3>Agent Timeline</h3>
    <div id="timelineContainer">
      <!-- Populated dynamically via JS -->
    </div>
  </div>
  
  <script>
  function updateAgentTimeline(operationId) {
      fetch(`/api/agent-traces/${operationId}`)
          .then(res => res.json())
          .then(data => {
              const container = document.getElementById('timelineContainer');
              container.innerHTML = data.events.map(event => `
                  <div class="timeline-event ${event.status}">
                      <span class="timestamp">${event.timestamp}</span>
                      <span class="agent">${event.agent}</span>
                      <span class="action">${event.action}</span>
                      ${event.status === 'success' ? '✅' : event.status === 'failed' ? '❌' : '⏳'}
                      ${event.reasoning ? `<span class="tooltip">${event.reasoning}</span>` : ''}
                  </div>
              `).join('');
          });
  }
  
  // Poll every 2 seconds during operation
  setInterval(() => {
      if (currentOperationId) {
          updateAgentTimeline(currentOperationId);
      }
  }, 2000);
  </script>
  ```

**File**: `graph/agentic_nodes.py`

**Enhancement في `seraj_meta_orchestration`**:
```python
def seraj_meta_orchestration(state: SerajState) -> SerajState:
    # ... existing logic ...
    
    # Emit orchestration decision
    operation_id = state.get("operation_id")
    selected_agents = state.get("meta_selected_agents", [])
    reasoning = state.get("meta_explanation", {}).get("reasoning", "")
    
    emit_agent_event(
        operation_id,
        "Seraj Meta-Agent",
        "orchestrate",
        decision=f"Selected agents: {', '.join(selected_agents)}",
        reasoning=reasoning,
        status="success"
    )
    
    return state
```

#### Change Category 5: State Management Expansion

**File**: `graph/state.py`

**Already covered في Change Category 3**:
```python
class SerajState(TypedDict, total=False):
    # ... existing fields ...
    
    # Conditional Execution & Rejection Details
    rejected_rows_details: Optional[List[Dict[str, Any]]]
    user_execution_choice: Optional[str]
    auto_execute: Optional[bool]
```

**Population Logic في Nodes**:
- **في dry-run node** (أو node الذي يُعالج dry-run results):
  ```python
  def process_dry_run_results(state: SerajState) -> SerajState:
      # ... existing validation logic ...
      
      rejected_rows = [...]  # من dry_run_report
      
      # Format rejection details
      rejected_rows_details = _format_rejection_details(rejected_rows, state)
      
      return {
          "rejected_rows_details": rejected_rows_details,
          "excel_validation_stats": {
              "accepted": len(accepted_rows),
              "rejected": len(rejected_rows)
          }
      }
  ```

- **في conditional execution node**:
  ```python
  def conditional_execution_node(state: SerajState) -> SerajState:
      rejected_count = len(state.get("rejected_rows_details", []))
      
      if rejected_count == 0:
          return {"auto_execute": True}
      else:
          return {"auto_execute": False}
  ```

- **في approval handling** (بعد user choice):
  ```python
  def process_user_approval_choice(state: SerajState, user_choice: str) -> SerajState:
      return {"user_execution_choice": user_choice}
  ```

---

## Testing Strategy

### Validation Approach

استراتيجية الاختبار تتبع نهج ثلاثي المراحل: أولاً، كشف counterexamples للمشاكل الخمس على الكود غير المُصلح، ثم التحقق من أن الإصلاحات تعمل بشكل صحيح، وأخيراً التأكد من الحفاظ على السلوك الموجود.

### Exploratory Bug Condition Checking

**Goal**: كشف counterexamples للمشاكل الخمس قبل تطبيق الإصلاحات. تأكيد أو نفي تحليل الأسباب الجذرية. إذا نفينا، نحتاج إعادة الافتراض.

**Test Plan**: كتابة اختبارات تحاكي السيناريوهات الخمسة وتؤكد فشلها على الكود غير المُصلح لفهم الأسباب الجذرية.

**Test Cases**:

1. **Template Generation Unavailable Test** (سيفشل على الكود غير المُصلح):
   - محاولة `POST /api/template/generate` → توقع 404
   - فتح Dashboard → توقع عدم وجود section "Generate Template"
   - **Expected Counterexample**: endpoint غير موجود، UI component مفقود

2. **Dry-Run Rejections Unclear Test** (سيفشل على الكود غير المُصلح):
   - تنفيذ dry-run مع ملف يحتوي أخطاء
   - فحص response structure → توقع عدم وجود `rejected_rows_details`
   - فحص Dashboard rendering → توقع عرض counts فقط بدون جدول
   - **Expected Counterexample**: response يحتوي `{"rejected": 5}` فقط بدون details، Dashboard لا يُظهر جدول

3. **Auto-Execute Missing Test** (سيفشل على الكود غير المُصلح):
   - تنفيذ dry-run مع ملف نظيف (0 errors)
   - توقع auto-execution فوري → الملاحظة: ينتظر approval
   - **Expected Counterexample**: `auto_execute` field غير موجود، conditional logic مفقود

4. **Agent Timeline Hidden Test** (سيفشل على الكود غير المُصلح):
   - بدء operation
   - محاولة `GET /api/agent-traces/{operation_id}` → توقع 404
   - فحص Dashboard → توقع عدم وجود timeline section
   - **Expected Counterexamples**: endpoint مفقود، agent events غير مُسجلة، UI مفقود

5. **State Fields Missing Test** (سيفشل على الكود غير المُصلح):
   - فحص `SerajState` TypedDict في `graph/state.py`
   - توقع عدم وجود: `rejected_rows_details`, `user_execution_choice`, `auto_execute`
   - **Expected Counterexample**: حقول مفقودة من definition

**Possible Causes (ستُكشف من الاختبارات)**:
- Endpoints غير مُعرّفة في `web_service.py`
- UI components مفقودة من Dashboard HTML
- LangGraph nodes لا تحتوي على logic شرطي
- State fields غير موجودة في `state.py`
- Agent events service غير مُطبق

### Fix Checking

**Goal**: التحقق من أن لجميع المدخلات التي يحملها شرط المشكلة، الوظيفة المُصلحة تُنتج السلوك المتوقع.

**Pseudocode:**
```
FOR ALL context WHERE isBugCondition(context) DO
  result := system_fixed(context)
  ASSERT expectedBehavior(result)
END FOR
```

**Test Cases**:

1. **Template Generation Works**:
   - `POST /api/template/generate` مع `{company_id: 1, template_type: "employee"}` → توقع 200 مع download_url
   - فتح Dashboard → توقع وجود section "Generate Template" مع form
   - استدعاء download endpoint → توقع Excel file مع company-specific data

2. **Dry-Run Rejection Details Visible**:
   - dry-run مع ملف يحتوي 5 أخطاء
   - فحص response → توقع `rejected_rows_details` array مع `{row_number, name, reason_ar, field, value, suggestion, can_auto_fix}`
   - فحص Dashboard → توقع جدول قابل للتوسيع بـ 5 صفوف

3. **Conditional Execution Active**:
   - dry-run مع ملف نظيف → توقع `auto_execute: true`، تنفيذ فوري، رسالة "✅ All rows accepted"
   - dry-run مع أخطاء → توقع `auto_execute: false`، action buttons، انتظار `user_execution_choice`

4. **Agent Timeline Displayed**:
   - بدء operation
   - `GET /api/agent-traces/{operation_id}` → توقع events array
   - Dashboard → توقع timeline section مع agent events مُعروضة

5. **State Fields Populated**:
   - فحص `SerajState` → تأكيد وجود الحقول الثلاثة
   - بعد dry-run → تأكيد `rejected_rows_details` populated
   - بعد conditional check → تأكيد `auto_execute` set
   - بعد user approval → تأكيد `user_execution_choice` set

### Preservation Checking

**Goal**: التحقق من أن لجميع المدخلات التي لا يحملها شرط المشكلة، الوظيفة المُصلحة تُنتج نفس النتيجة كالوظيفة الأصلية.

**Pseudocode:**
```
FOR ALL context WHERE NOT isBugCondition(context) DO
  ASSERT system_original(context) = system_fixed(context)
END FOR
```

**Testing Approach**: اختبارات property-based موصى بها لـ preservation checking لأنها:
- تولد حالات اختبار كثيرة تلقائياً عبر domain المدخلات
- تكتشف edge cases قد تفوتها اختبارات unit يدوية
- توفر ضمانات قوية أن السلوك غير متغير لجميع المدخلات غير المتعلقة بالمشاكل

**Test Plan**: ملاحظة السلوك على الكود غير المُصلح أولاً للتفاعلات الموجودة، ثم كتابة اختبارات property-based تلتقط ذلك السلوك.

**Test Cases**:

1. **Existing API Endpoints Unchanged**:
   - ملاحظة على الكود غير المُصلح: `POST /upload`, `POST /dry-run`, `POST /approve`, `POST /write` تعمل
   - كتابة PBT: لكل endpoint موجود، توليد payloads صالحة، التأكد من response format غير متغير
   - **Property**: `∀ payload ∈ ValidPayloads: response_format_original(payload) == response_format_fixed(payload)`

2. **CLI Tools Still Functional**:
   - ملاحظة على الكود غير المُصلح: `python generate_employee_template.py --output-dir output` يعمل
   - كتابة test: تنفيذ CLI command، التأكد من template generation successful
   - **Property**: CLI output format غير متغير

3. **Telegram Bot Integration**:
   - ملاحظة: Telegram bot يستدعي API endpoints
   - PBT: توليد Telegram bot requests متنوعة، التأكد من responses مطابقة
   - **Property**: Telegram integration unaffected

4. **Agent Selection Logic**:
   - ملاحظة: Seraj يختار Fahas للـ query، Mudaqqiq للـ validation، Katib للـ write
   - Test: عمليات بدون conditional execution، التأكد من agent routing غير متغير
   - **Property**: Agent orchestration decisions preserved for non-conditional workflows

5. **LangGraph State Transitions**:
   - ملاحظة: state fields موجودة (`operation_id`, `company_id`, `user_query`) محفوظة
   - PBT: توليد state transitions متنوعة، التأكد من existing fields غير mutated بشكل غير متوقع
   - **Property**: `∀ transition ∈ GraphTransitions: existing_fields_preserved(transition)`

6. **Authentication & Audit Logging**:
   - ملاحظة: `WRITE_API_TOKEN` required، `audit_log_access()` يُسجل كل request
   - Test: محاولات write بدون token → توقع 403، فحص `logs/web_access.log` للتأكد من logging
   - **Property**: Security mechanisms unchanged

7. **Test Suite Success**:
   - تشغيل جميع الاختبارات الموجودة في `tests/` → توقع >80% pass rate
   - **Property**: Existing test coverage maintained

### Unit Tests

- اختبار كل endpoint جديد (`/api/template/generate`, `/api/template/download/{template_id}`, `/api/approve-conditional`, `/api/agent-traces/{operation_id}`) بشكل منفصل
- اختبار `_format_rejection_details()` method مع rejection structures مختلفة
- اختبار `conditional_execution_node` مع scenarios: `rejected_rows == 0`, `rejected_rows > 0`, مع user choices مختلفة
- اختبار `agent_events_service` emit و retrieve functions
- اختبار State field population في nodes مختلفة

### Property-Based Tests

- توليد dry-run results عشوائية (مع/بدون rejected rows) والتحقق من conditional logic
- توليد template requests عشوائية (companies مختلفة، template types) والتأكد من generation ناجح
- توليد agent event streams عشوائية والتأكد من timeline rendering صحيح
- توليد state transitions عشوائية والتأكد من preservation existing fields
- توليد API payloads عشوائية للـ endpoints موجودة والتأكد من backward compatibility

### Integration Tests

- **Full Template Generation Flow**: Dashboard form → API call → Excel generation → download
- **Full Conditional Execution Flow**: 
  - Clean file → upload → dry-run → auto-execute
  - File with errors → upload → dry-run → display rejection details → user choice (execute/fix/cancel) → handle choice
- **Full Agent Tracing Flow**: operation start → agent events emitted → API retrieval → Dashboard timeline display
- **Multi-Agent Coordination**: Seraj orchestration → Fahas query → Mudaqqiq verify → Katib write → Agent timeline يُظهر كل step
- **Backward Compatibility**: Telegram bot → API calls → responses مطابقة للـ format قديم

---

## Notes

### Implementation Priority

1. **High Priority (Week 1)**:
   - Change Category 5 (State Management) - foundational
   - Change Category 3 (Conditional Execution) - core workflow improvement
   - Change Category 2 (Rejection Details) - critical UX

2. **Medium Priority (Week 2)**:
   - Change Category 1 (Template Generation) - important but standalone
   - Change Category 4 (Agent Tracing) - observability enhancement

3. **Testing (Week 2-3)**:
   - Exploratory tests أولاً لتأكيد المشاكل
   - Fix checking بعد كل category
   - Preservation checking مستمر
   - Integration tests في النهاية

### Rollback Strategy

إذا فشل الإصلاح:
- **Category 1-2**: إزالة endpoints جديدة، إرجاع UI changes
- **Category 3**: إزالة conditional node من graph، إرجاع state.py
- **Category 4**: إزالة agent_events_service، إرجاع UI
- **Category 5**: إرجاع state.py إلى النسخة السابقة

### Dependencies

- `generate_employee_template.py` refactoring يتطلب فهم عميق للـ logic الحالي
- Conditional execution يعتمد على State Management (Category 5 أولاً)
- Agent tracing يتطلب integration في جميع agents (BaseAgent modification)
- Dashboard UI changes تتطلب JavaScript knowledge

### Risks

1. **Breaking Changes Risk**: endpoints جديدة قد تتعارض مع integrations موجودة → التخفيف: versioned endpoints (`/api/v2/...`)
2. **Performance Risk**: agent events logging قد يبطئ execution → التخفيف: async logging، buffering
3. **State Complexity**: إضافة حقول قد يُربك existing nodes → التخفيف: توثيق واضح، optional fields
4. **UI Complexity**: Dashboard قد يصبح مزدحم → التخفيف: tabbed interface، collapsible sections

---

**End of Design Document**
