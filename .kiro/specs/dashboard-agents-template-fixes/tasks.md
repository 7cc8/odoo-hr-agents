# Implementation Plan

## Overview

هذا المخطط التنفيذي يعالج خمس مشاكل رئيسية في نظام Odoo HR Agents تم تحديدها في التصميم. المهام مُرتبة حسب الأولوية والتبعيات لضمان تنفيذ سلس.

---

## Phase 1: تطوير Bug Condition Exploration Tests ✅

### 1.1 كتابة Bug Condition Exploration Tests (قبل تطبيق الإصلاحات)

- [x] 1.1.1 **Property 1: Bug Condition** - Template Generation Unavailable Test
  - **CRITICAL**: هذا الاختبار يجب أن يفشل على الكود غير المُصلح - الفشل يُثبت وجود المشكلة
  - **DO NOT attempt to fix the test or code when it fails**
  - **NOTE**: هذا الاختبار يُعبّر عن السلوك المتوقع - سيُصادق على الإصلاح عندما ينجح بعد التنفيذ
  - **GOAL**: كشف counterexamples تُثبت أن template generation غير متاحة من Dashboard/API
  - **Test Implementation**:
    - محاولة `POST /api/template/generate` مع `{company_id: 1, template_type: "employee"}` → توقع **404 Not Found**
    - فتح Dashboard HTML → البحث عن section "Generate Template" → توقع **عدم وجوده**
    - محاولة download من `/api/template/download/test-id` → توقع **404**
  - **Expected Outcome**: الاختبار **يفشل** (هذا صحيح - يُثبت وجود المشكلة)
  - **Counterexamples to Document**:
    - Endpoint `/api/template/generate` غير موجود في `web_service.py`
    - Dashboard لا يحتوي على UI component لتوليد القوالب
    - لا يوجد integration بين `generate_employee_template.py` و API
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 1.1.2 **Property 1: Bug Condition** - Dry-Run Rejection Details Unclear Test
  - **CRITICAL**: هذا الاختبار يجب أن يفشل على الكود غير المُصلح
  - **GOAL**: كشف أن dry-run response لا يحتوي على تفاصيل rejection كافية
  - **Test Implementation**:
    - رفع ملف Excel يحتوي 5 صفوف بها أخطاء (قسم غير موجود، job title خاطئ، إلخ)
    - تنفيذ dry-run عبر `/dry-run`
    - فحص response structure → توقع عدم وجود حقل `rejected_rows_details` مع معلومات `{row_number, name, reason_ar, field, value, suggestion}`
    - فحص Dashboard rendering → توقع عرض counts فقط (`45 accepted, 5 rejected`) بدون جدول تفصيلي
  - **Expected Outcome**: الاختبار **يفشل** (response يحتوي على `{"rejected": 5}` فقط، Dashboard لا يُظهر details)
  - **Counterexamples to Document**:
    - `dry_run_report.py` يُنتج structure بسيط بدون تفاصيل غنية
    - `agentic_nodes.py::seraj_meta_orchestration` لا يحتوي على `_format_rejection_details()` method
    - Dashboard HTML لا يحتوي على expandable table
  - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [x] 1.1.3 **Property 1: Bug Condition** - Auto-Execute Missing Test
  - **CRITICAL**: هذا الاختبار يجب أن يفشل على الكود غير المُصلح
  - **GOAL**: كشف أن الملفات النظيفة (بدون أخطاء) لا تُنفذ تلقائياً
  - **Test Implementation**:
    - رفع ملف Excel نظيف (جميع البيانات صحيحة، 0 errors)
    - تنفيذ dry-run → توقع `{"accepted": 50, "rejected": 0}`
    - فحص LangGraph execution → توقع **عدم** تنفيذ auto-execute (ينتظر approval)
    - فحص `SerajState` → توقع عدم وجود حقل `auto_execute` أو قيمته False
  - **Expected Outcome**: الاختبار **يفشل** (النظام ينتظر approval حتى للملفات النظيفة)
  - **Counterexamples to Document**:
    - لا توجد `conditional_execution_node` في `agentic_nodes.py`
    - `build_graph.py` لا يحتوي على branching logic بناءً على `rejected_rows`
    - لا يوجد logic لتعيين `auto_execute = True` عندما `rejected_rows == 0`
  - _Requirements: 2.9, 2.10, 2.11, 2.12_

- [x] 1.1.4 **Property 1: Bug Condition** - Agent Timeline Hidden Test
  - **CRITICAL**: هذا الاختبار يجب أن يفشل على الكود غير المُصلح
  - **GOAL**: كشف أن agent execution غير مرئي للمستخدمين
  - **Test Implementation**:
    - بدء operation (upload → dry-run)
    - محاولة `GET /api/agent-traces/{operation_id}` → توقع **404 Not Found**
    - فحص Dashboard HTML → البحث عن "Agent Timeline" section → توقع **عدم وجوده**
    - فحص `agent_events_service.py` → توقع **الملف غير موجود**
  - **Expected Outcome**: الاختبار **يفشل** (endpoint مفقود، UI مفقود، events غير مُسجلة)
  - **Counterexamples to Document**:
    - لا يوجد `agent_events_service.py`
    - Agents لا تُصدر events مُهيكلة
    - Dashboard لا يحتوي على timeline UI component
    - لا يوجد API endpoint لاسترجاع traces
  - _Requirements: 2.13, 2.14, 2.15, 2.16_

- [x] 1.1.5 **Property 1: Bug Condition** - State Fields Missing Test
  - **CRITICAL**: هذا الاختبار يجب أن يفشل على الكود غير المُصلح
  - **GOAL**: كشف أن `SerajState` لا يحتوي على الحقول المطلوبة
  - **Test Implementation**:
    - قراءة `graph/state.py` → فحص `SerajState` TypedDict
    - توقع **عدم وجود**: `rejected_rows_details`, `user_execution_choice`, `auto_execute`
    - محاولة الوصول لهذه الحقول في LangGraph execution → توقع KeyError أو None
  - **Expected Outcome**: الاختبار **يفشل** (الحقول مفقودة من definition)
  - **Counterexamples to Document**:
    - `SerajState` في `graph/state.py` لا يُعرّف الحقول الثلاثة
    - Nodes لا تملأ هذه الحقول حتى لو أضفناها
  - _Requirements: 2.17, 2.18, 2.19_

---

## Phase 2: Preservation Property Tests (قبل تطبيق الإصلاحات) ✅

### 2.1 كتابة Preservation Property Tests

- [x] 2.1.1 **Property 2: Preservation** - Existing API Endpoints Behavior
  - **IMPORTANT**: اتباع منهجية observation-first
  - **Observe**: تشغيل الكود غير المُصلح ومراقبة سلوك endpoints الموجودة
    - `POST /upload` مع ملف Excel → مراقبة response structure
    - `POST /dry-run` مع operation_id → مراقبة validation results
    - `POST /approve` مع operation_id → مراقبة approval flow
    - `POST /write` مع operation_id → مراقبة write execution
  - **Write property-based tests**:
    - لكل endpoint موجود، أكتب اختبار يُؤكد أن JSON format يبقى unchanged
    - Telegram bot integration يستمر في العمل (mock telegram calls)
    - CLI tools مثل `generate_employee_template.py --output-dir` تنتج outputs صحيحة
  - **Verify tests pass on UNFIXED code**: تأكيد أن جميع اختبارات preservation تنجح قبل الإصلاحات
  - **EXPECTED OUTCOME**: الاختبارات **تنجح** (تُؤكد baseline behavior للحفاظ عليه)
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 2.1.2 **Property 2: Preservation** - Agent Execution Logic Unchanged
  - **Observe**: تشغيل orchestration على الكود غير المُصلح
    - Seraj Meta-Agent يختار agents (Fahas للـ query، Mudaqqiq للـ validation، Katib للـ write)
    - Musleh healing logic ينشط عند الحاجة
    - LangGraph state transitions تحافظ على fields موجودة
  - **Write property-based tests**:
    - Agent selection logic يبقى دون تغيير
    - State fields الموجودة (`operation_id`, `company_id`, `user_query`, `parsed_data`) محفوظة
    - Musleh يستمر في العمل لنفس السيناريوهات
  - **Verify tests pass on UNFIXED code**
  - **EXPECTED OUTCOME**: الاختبارات **تنجح**
  - _Requirements: 3.4, 3.5, 3.6_

- [x] 2.1.3 **Property 2: Preservation** - Security, Auth, Logging Unchanged
  - **Observe**: التحقق من أن الكود غير المُصلح يحافظ على:
    - Write operations تطلب `WRITE_API_TOKEN`
    - Audit logging يُسجل جميع accesses
    - File upload parsing يعمل بشكل صحيح
    - Dashboard analytics `/api/analytics/dashboard` يُرجع metrics
  - **Write property-based tests**:
    - Authentication enforcement على write endpoints
    - Audit log entries تُسجل بشكل صحيح
    - Parser يُعالج Excel files بدون errors
    - Analytics endpoint يُرجع expected data structure
  - **Verify tests pass on UNFIXED code**
  - **EXPECTED OUTCOME**: الاختبارات **تنجح**
  - _Requirements: 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16_

- [x] 2.1.4 **Property 2: Preservation** - Existing Tests Coverage
  - **Observe**: تشغيل test suite الموجود على الكود غير المُصلح
    - تأكيد coverage >80%
    - تأكيد أن جميع الاختبارات الموجودة تنجح
  - **Document baseline**: حفظ test results كـ baseline للمقارنة بعد الإصلاحات
  - **EXPECTED OUTCOME**: جميع الاختبارات الموجودة **تنجح** (baseline للحفاظ عليه)
  - _Requirements: جميع متطلبات Preservation_

---

## Phase 3: تطبيق الإصلاحات 🔧

### 3.1 State Management Expansion (أعلى أولوية - تبعيات لباقي المهام)

- [x] 3.1.1 إضافة حقول جديدة لـ `SerajState`
  - **File**: `graph/state.py`
  - **Changes**:

    ```python
    class SerajState(TypedDict, total=False):
        # ... existing fields ...

        # Conditional Execution & Rejection Details
        rejected_rows_details: Optional[List[Dict[str, Any]]]
        user_execution_choice: Optional[str]  # "execute" | "fix" | "cancel"
        auto_execute: Optional[bool]
    ```

  - **Validation**: قراءة الملف والتأكد من أن type hints صحيحة
  - _Bug_Condition: state fields مفقودة_
  - _Expected_Behavior: SerajState يحتوي على الحقول الثلاثة مع types صحيحة_
  - _Preservation: جميع state fields الموجودة (`operation_id`, `company_id`, etc.) تبقى unchanged_
  - _Requirements: 2.17, 2.18, 2.19_

- [x] 3.1.2 إضافة helper functions لـ state field validation
  - **File**: `graph/state.py`
  - **Add utility functions**:

    ```python
    def has_rejection_details(state: SerajState) -> bool:
        """Check if state has rejection details populated."""
        return "rejected_rows_details" in state and state["rejected_rows_details"] is not None

    def is_auto_executable(state: SerajState) -> bool:
        """Check if operation can be auto-executed."""
        return state.get("auto_execute", False) is True
    ```

  - _Requirements: 2.17, 2.18, 2.19_

---

### 3.2 Dry-Run Rejection Details Enhancement

- [x] 3.2.1 إضافة `_format_rejection_details()` method في Seraj Meta-Agent
  - **File**: `graph/agentic_nodes.py`
  - **Add method**:

    ```python
    def _format_rejection_details(
        rejected_rows: List[Dict],
        state: SerajState
    ) -> List[Dict[str, Any]]:
        """
        تنسيق تفاصيل الصفوف المرفوضة للعرض في Dashboard.

        Input format (from dry_run_report.py):
        [{"row_number": 3, "errors": [{"field": "department", "message": "Department not found"}]}]

        Output format (enhanced):
        [{
            "row_number": 3,
            "name": "محمد أحمد",
            "reason_ar": "القسم غير موجود",
            "field": "department",
            "value": "قسم المبيعات",
            "suggestion": "Use 'Sales' department",
            "can_auto_fix": True
        }]
        """
        formatted = []
        parsed_data = state.get("excel_parsed_data", {}).get("rows", [])

        for row in rejected_rows:
            row_idx = row["row_number"]
            row_data = parsed_data[row_idx] if row_idx < len(parsed_data) else {}

            for error in row["errors"]:
                formatted.append({
                    "row_number": row_idx,
                    "name": row_data.get("name", "N/A"),
                    "reason_ar": _translate_to_arabic(error["message"]),
                    "field": error["field"],
                    "value": row_data.get(error["field"], ""),
                    "suggestion": _generate_suggestion(error, row_data),
                    "can_auto_fix": _is_auto_fixable(error)
                })

        return formatted
    ```

  - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [x] 3.2.2 إضافة helper functions للترجمة والاقتراحات
  - **File**: `graph/agentic_nodes.py`
  - **Add helpers**:

    ```python
    def _translate_to_arabic(message: str) -> str:
        """Translate error message to Arabic."""
        translations = {
            "Department not found": "القسم غير موجود",
            "Job not found": "المسمى الوظيفي غير موجود",
            "Invalid email": "البريد الإلكتروني غير صالح",
            "Invalid date format": "تنسيق التاريخ غير صحيح",
            # ... more translations
        }
        return translations.get(message, message)

    def _generate_suggestion(error: Dict, row_data: Dict) -> str:
        """Generate fix suggestion based on error type."""
        if error["field"] == "department":
            return "Use 'Sales' or 'HR' department"
        elif error["field"] == "job_id":
            return "Check job title spelling"
        # ... more suggestions
        return "Please review and correct"

    def _is_auto_fixable(error: Dict) -> bool:
        """Determine if error can be auto-fixed by Musleh."""
        fixable_fields = ["department", "job_id", "date_format"]
        return error["field"] in fixable_fields
    ```

  - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [x] 3.2.3 دمج `_format_rejection_details()` في dry-run processing node
  - **File**: `graph/agentic_nodes.py`
  - **Update dry-run processing node** (أو إضافة node جديد إذا لزم الأمر):

    ```python
    def process_dry_run_results(state: SerajState) -> SerajState:
        # ... existing validation logic ...

        rejected_rows = [...]  # من dry_run_report

        # Format rejection details
        if len(rejected_rows) > 0:
            rejected_rows_details = _format_rejection_details(rejected_rows, state)
        else:
            rejected_rows_details = []

        return {
            "rejected_rows_details": rejected_rows_details,
            "excel_validation_stats": {
                "accepted": len(accepted_rows),
                "rejected": len(rejected_rows)
            }
        }
    ```

  - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [x] 3.2.4 تحديث `dry_run_report.py` لتشمل row data في rejection info
  - **File**: `dry_run_report.py`
  - **Enhancement**: تأكيد أن rejection structure يحتوي على معلومات كافية للـ formatting
  - **Integration**: دمج `template_detector.py` للحصول على context أفضل
  - _Requirements: 2.5, 2.6, 2.7, 2.8_

---

### 3.3 Conditional Execution Workflow Implementation

- [x] 3.3.1 إضافة `conditional_execution_node` في LangGraph
  - **File**: `graph/agentic_nodes.py`
  - **Add new node**:

    ```python
    def conditional_execution_node(state: SerajState) -> SerajState:
        """
        عقدة شرطية تقرر بين auto-execute أو انتظار approval.

        Logic:
        - إذا rejected_rows == 0: set auto_execute=True → route إلى execution
        - إذا rejected_rows > 0: انتظار user_execution_choice → route حسب القرار
        """
        rejected_count = len(state.get("rejected_rows_details", []))
        accepted_count = state.get("excel_validation_stats", {}).get("accepted", 0)

        if rejected_count == 0 and accepted_count > 0:
            # Auto-execute: no errors, proceed immediately
            return {
                "auto_execute": True,
                "user_execution_choice": "execute",  # implicit
                "answer": f"✅ All {accepted_count} rows accepted - Executing now..."
            }
        else:
            # Wait for user decision
            return {
                "auto_execute": False,
                "answer": f"⚠️ {rejected_count} rows rejected, {accepted_count} accepted. Please choose an action."
            }
    ```

  - _Requirements: 2.9, 2.10, 2.11, 2.12_

- [x] 3.3.2 إضافة routing function في `build_graph.py`
  - **File**: `graph/build_graph.py`
  - **Add routing logic**:

    ```python
    def route_after_conditional_execution(state: SerajState) -> str:
        """
        Route based on conditional execution decision.

        Returns:
        - "execute_write": للتنفيذ الفوري
        - "musleh_heal": للإصلاح التلقائي
        - "end": للإلغاء
        """
        if state.get("auto_execute"):
            return "execute_write"  # مباشرة للكتابة
        elif state.get("user_execution_choice") == "execute":
            return "execute_write"
        elif state.get("user_execution_choice") == "fix":
            return "musleh_heal"  # إصلاح تلقائي
        else:
            return "end"  # إلغاء
    ```

  - **Update graph construction**: دمج conditional node في graph flow:

    ```python
    # Add conditional execution node
    graph.add_node("conditional_execution", conditional_execution_node)

    # Add edge from dry-run to conditional
    graph.add_edge("dry_run_processing", "conditional_execution")

    # Add conditional edges based on routing
    graph.add_conditional_edges(
        "conditional_execution",
        route_after_conditional_execution,
        {
            "execute_write": "katib_write",
            "musleh_heal": "musleh_heal",
            "end": END
        }
    )
    ```

  - _Requirements: 2.9, 2.10, 2.11, 2.12_

- [x] 3.3.3 إضافة API endpoint `/api/approve-conditional`
  - **File**: `web_service.py`
  - **Add new endpoint**:

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
            raise HTTPException(400, "Invalid choice. Must be 'execute', 'fix', or 'cancel'")

        # Get operation from storage
        operation = await get_operation(operation_id)
        if not operation:
            raise HTTPException(404, "Operation not found")

        # Update LangGraph state
        operation["state"]["user_execution_choice"] = choice

        # Trigger continuation of graph execution
        result = await continue_graph_execution(operation_id, operation["state"])

        audit_log_access("/api/approve-conditional", request, {
            "operation_id": operation_id,
            "choice": choice
        })

        return {
            "status": "choice_recorded",
            "operation_id": operation_id,
            "choice": choice,
            "next_step": result.get("next_step")
        }
    ```

  - _Requirements: 2.9, 2.10, 2.11, 2.12_

- [x] 3.3.4 إضافة helper function لـ continue graph execution
  - **File**: `web_service.py` أو ملف منفصل للـ graph execution
  - **Add helper**:

    ```python
    async def continue_graph_execution(operation_id: str, state: SerajState):
        """
        Continue LangGraph execution after user decision.
        """
        from graph.build_graph import get_graph

        graph = get_graph()

        # Resume execution from conditional_execution node
        result = await graph.ainvoke(state, config={"recursion_limit": 100})

        return result
    ```

  - _Requirements: 2.9, 2.10, 2.11, 2.12_

---

### 3.4 Agent Tracing & Timeline Implementation

- [x] 3.4.1 إنشاء `agent_events_service.py`
  - **File**: `agents/agent_events_service.py` (ملف جديد)
  - **Service Implementation**:

    ```python
    from typing import Dict, List, Any, Optional
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
                if line.strip():
                    events.append(json.loads(line))
        return events

    def clear_agent_events(operation_id: str) -> None:
        """مسح أحداث agent لعملية معينة (للاختبارات)."""
        event_file = EVENTS_DIR / f"{operation_id}.jsonl"
        if event_file.exists():
            event_file.unlink()
    ```

  - _Requirements: 2.13, 2.14, 2.15, 2.16_

- [x] 3.4.2 دمج event emission في Seraj Meta-Agent
  - **File**: `graph/agentic_nodes.py`
  - **Update `seraj_meta_orchestration`**:

    ```python
    def seraj_meta_orchestration(state: SerajState) -> SerajState:
        from agents.agent_events_service import emit_agent_event

        operation_id = state.get("operation_id")

        # Emit start event
        emit_agent_event(
            operation_id,
            "Seraj Meta-Agent",
            "orchestrate",
            status="in_progress",
            reasoning="Analyzing user query and selecting agents..."
        )

        # ... existing orchestration logic ...

        selected_agents = state.get("meta_selected_agents", [])
        reasoning = state.get("meta_explanation", {}).get("reasoning", "")

        # Emit completion event
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

  - _Requirements: 2.13, 2.14, 2.15, 2.16_

- [x] 3.4.3 دمج event emission في جميع Agents (Fahas, Mudaqqiq, Katib, Musleh)
  - **Files**: `agents/fahas_agent.py`, `agents/mudaqqiq_agent.py`, `agents/katib_agent.py`, `agents/musleh_agent.py`
  - **Pattern to apply**:

    ```python
    from agents.agent_events_service import emit_agent_event

    class FahasAgent(BaseAgent):
        def perceive(self, state: SerajState) -> SerajState:
            operation_id = state.get("operation_id")

            emit_agent_event(
                operation_id,
                "Fahas (Query)",
                "perceive",
                reasoning="Understanding data requirements...",
                status="in_progress"
            )

            # ... existing logic ...

            emit_agent_event(
                operation_id,
                "Fahas (Query)",
                "perceive",
                status="success"
            )

            return state

        def plan(self, state: SerajState) -> SerajState:
            operation_id = state.get("operation_id")

            emit_agent_event(
                operation_id,
                "Fahas (Query)",
                "plan",
                decision="query_odoo",
                reasoning="Need to fetch departments and jobs from Odoo",
                status="in_progress"
            )

            # ... existing logic ...

            return state

        def execute(self, state: SerajState) -> SerajState:
            operation_id = state.get("operation_id")

            emit_agent_event(
                operation_id,
                "Fahas (Query)",
                "execute",
                status="in_progress",
                reasoning="Fetching data from Odoo..."
            )

            # ... existing logic ...

            emit_agent_event(
                operation_id,
                "Fahas (Query)",
                "execute",
                status="success",
                decision=f"Fetched {len(results)} records"
            )

            return state
    ```

  - **Repeat for all agents** with appropriate agent names and actions
  - _Requirements: 2.13, 2.14, 2.15, 2.16_

- [x] 3.4.4 إضافة API endpoint `/api/agent-traces/{operation_id}`
  - **File**: `web_service.py`
  - **Add endpoint**:

    ```python
    @app.get("/api/agent-traces/{operation_id}")
    async def get_agent_traces(operation_id: str, request: Request):
        """استرجاع تتبع تنفيذ الوكلاء لعملية معينة."""
        from agents.agent_events_service import get_agent_events

        audit_log_access(f"/api/agent-traces/{operation_id}", request)

        events = get_agent_events(operation_id)

        return {
            "operation_id": operation_id,
            "events": events,
            "total_events": len(events)
        }
    ```

  - _Requirements: 2.13, 2.14, 2.15, 2.16_

---

### 3.5 Template Generation API & Dashboard Integration

- [x] 3.5.1 Refactor `generate_employee_template.py` إلى function
  - **File**: `generate_employee_template.py`
  - **Refactoring**:

    ```python
    def generate_template(
        company_id: int,
        template_type: str,
        output_dir: str,
        include_example_row: bool = False,
        language: str = "ar"
    ) -> Dict[str, Any]:
        """
        Generate company-specific Excel template.

        Returns:
        {
            "template_path": "path/to/file.xlsx",
            "sheet_count": 3,
            "generated_at": "2025-01-01T10:00:00Z",
            "metadata": {...}
        }
        """
        # ... existing template generation logic ...
        # Add Odoo connection to fetch company-specific data

        # Connect to Odoo
        from odoo_connection import get_odoo_connection
        odoo = get_odoo_connection()

        # Fetch departments for company
        departments = odoo.search_read(
            'hr.department',
            [('company_id', '=', company_id)],
            ['name']
        )

        # Fetch jobs for company
        jobs = odoo.search_read(
            'hr.job',
            [('company_id', '=', company_id)],
            ['name']
        )

        # Generate Excel with company-specific data
        # ... (existing Excel generation logic updated with fetched data)

        return {
            "template_path": output_path,
            "sheet_count": len(workbook.worksheets),
            "generated_at": datetime.now().isoformat(),
            "metadata": {
                "company_id": company_id,
                "template_type": template_type,
                "departments_count": len(departments),
                "jobs_count": len(jobs)
            }
        }

    # Keep CLI interface for backward compatibility
    if __name__ == "__main__":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--company-id", type=int, required=True)
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--template-type", default="employee")
        parser.add_argument("--include-example", action="store_true")
        parser.add_argument("--language", default="ar")
        args = parser.parse_args()

        result = generate_template(
            args.company_id,
            args.template_type,
            args.output_dir,
            args.include_example,
            args.language
        )
        print(f"Template generated: {result['template_path']}")
    ```

  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3.5.2 إضافة endpoint `/api/template/generate`
  - **File**: `web_service.py`
  - **Add endpoint**:

    ```python
    @app.post("/api/template/generate")
    async def generate_template_endpoint(
        request: Request,
        company_id: int = Form(...),
        template_type: str = Form("employee"),
        include_example_row: bool = Form(False),
        language: str = Form("ar")
    ):
        """
        Generate company-specific template via API.
        """
        from generate_employee_template import generate_template
        import uuid

        audit_log_access("/api/template/generate", request, {
            "company_id": company_id,
            "template_type": template_type
        })

        # Generate unique template ID
        template_id = str(uuid.uuid4())
        output_dir = UPLOAD_DIR / "templates"
        output_dir.mkdir(exist_ok=True)

        try:
            result = generate_template(
                company_id=company_id,
                template_type=template_type,
                output_dir=str(output_dir),
                include_example_row=include_example_row,
                language=language
            )

            # Store template info for download
            template_info[template_id] = {
                "path": result["template_path"],
                "generated_at": result["generated_at"],
                "metadata": result["metadata"]
            }

            return {
                "status": "success",
                "template_id": template_id,
                "template_path": result["template_path"],
                "download_url": f"/api/template/download/{template_id}",
                "sheet_count": result["sheet_count"],
                "generated_at": result["generated_at"],
                "metadata": result["metadata"]
            }

        except Exception as e:
            raise HTTPException(500, f"Template generation failed: {str(e)}")
    ```

  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3.5.3 إضافة endpoint `/api/template/download/{template_id}`
  - **File**: `web_service.py`
  - **Add endpoint**:

    ```python
    from fastapi.responses import FileResponse

    # Global dict to store template info (في production استخدم database)
    template_info: Dict[str, Dict] = {}

    @app.get("/api/template/download/{template_id}")
    async def download_template(template_id: str, request: Request):
        """
        Download generated template by ID.
        """
        audit_log_access(f"/api/template/download/{template_id}", request)

        if template_id not in template_info:
            raise HTTPException(404, "Template not found")

        template_path = template_info[template_id]["path"]

        if not Path(template_path).exists():
            raise HTTPException(404, "Template file not found")

        return FileResponse(
            path=template_path,
            filename=f"employee_template_{template_id[:8]}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    ```

  - _Requirements: 2.1, 2.2, 2.3, 2.4_

---

### 3.6 Dashboard UI Enhancements

- [x] 3.6.1 إضافة Template Generation Section في Dashboard
  - **File**: Dashboard HTML (embedded في `web_service.py` أو ملف منفصل)
  - **Add section**:

    ```html
    <div class="template-section">
      <h3>📋 Generate Company-Specific Template</h3>
      <form id="templateForm">
        <div class="form-group">
          <label for="companySelect">Company:</label>
          <select id="companySelect" name="company_id" required>
            <option value="">Select Company...</option>
            <option value="1">Company A</option>
            <option value="2">Company B</option>
            <!-- Dynamically populated from API -->
          </select>
        </div>

        <div class="form-group">
          <label for="templateType">Template Type:</label>
          <select id="templateType" name="template_type">
            <option value="employee">Employee</option>
            <option value="contract">Contract</option>
          </select>
        </div>

        <div class="form-group">
          <label>
            <input
              type="checkbox"
              name="include_example_row"
              id="includeExample"
            />
            Include example row
          </label>
        </div>

        <div class="form-group">
          <label for="language">Language:</label>
          <select id="language" name="language">
            <option value="ar">العربية</option>
            <option value="en">English</option>
          </select>
        </div>

        <button type="submit" class="btn btn-primary">Generate Template</button>
      </form>

      <div id="templateResult" style="display:none; margin-top: 20px;">
        <div class="alert alert-success">
          <h4>✅ Template Generated Successfully</h4>
          <p>Sheet Count: <span id="sheetCount"></span></p>
          <p>Generated At: <span id="generatedAt"></span></p>
          <a id="downloadLink" href="#" class="btn btn-success" download>
            📥 Download Template
          </a>
        </div>
      </div>
    </div>
    ```

  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3.6.2 إضافة JavaScript لمعالجة Template Generation
  - **File**: Dashboard HTML (script section)
  - **Add JavaScript**:

    ```javascript
    document
      .getElementById("templateForm")
      .addEventListener("submit", async function (e) {
        e.preventDefault();

        const formData = new FormData(this);
        const resultDiv = document.getElementById("templateResult");

        try {
          const response = await fetch("/api/template/generate", {
            method: "POST",
            body: formData,
          });

          if (!response.ok) {
            throw new Error("Template generation failed");
          }

          const data = await response.json();

          // Display result
          document.getElementById("sheetCount").textContent = data.sheet_count;
          document.getElementById("generatedAt").textContent = new Date(
            data.generated_at,
          ).toLocaleString("ar-EG");
          document.getElementById("downloadLink").href = data.download_url;

          resultDiv.style.display = "block";
        } catch (error) {
          alert("Error generating template: " + error.message);
        }
      });
    ```

  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3.6.3 إضافة Rejection Details Table في Dashboard
  - **File**: Dashboard HTML
  - **Add section**:
    ```html
    <div id="rejectionDetails" style="display:none; margin-top: 20px;">
      <h4>⚠️ Rejected Rows Details</h4>
      <table class="table table-striped">
        <thead>
          <tr>
            <th>Row #</th>
            <th>Name</th>
            <th>Reason (Arabic)</th>
            <th>Field</th>
            <th>Value</th>
            <th>Suggested Fix</th>
            <th>Auto-Fix?</th>
          </tr>
        </thead>
        <tbody id="rejectionTableBody">
          <!-- Populated dynamically -->
        </tbody>
      </table>
    </div>
    ```
  - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [x] 3.6.4 إضافة JavaScript لعرض Rejection Details
  - **File**: Dashboard HTML (script section)
  - **Add JavaScript**:

    ```javascript
    function displayRejectionDetails(rejectedRows) {
      const tbody = document.getElementById("rejectionTableBody");
      tbody.innerHTML = "";

      if (rejectedRows && rejectedRows.length > 0) {
        rejectedRows.forEach((row) => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
                    <td>${row.row_number}</td>
                    <td>${row.name}</td>
                    <td>${row.reason_ar}</td>
                    <td><code>${row.field}</code></td>
                    <td>${row.value}</td>
                    <td>${row.suggestion}</td>
                    <td>${row.can_auto_fix ? "✅ Yes" : "❌ No"}</td>
                `;
          tbody.appendChild(tr);
        });

        document.getElementById("rejectionDetails").style.display = "block";
      } else {
        document.getElementById("rejectionDetails").style.display = "none";
      }
    }

    // Call this function when dry-run results arrive
    // Example: displayRejectionDetails(response.rejected_rows_details);
    ```

  - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [x] 3.6.5 إضافة Conditional Action Buttons في Dashboard
  - **File**: Dashboard HTML
  - **Add section**:

    ```html
    <div id="conditionalActions" style="display:none; margin-top: 20px;">
      <h4>Choose Action</h4>
      <div class="button-group">
        <button onclick="approveConditional('execute')" class="btn btn-success">
          ✅ Execute Accepted Only (<span id="acceptedCount"></span> rows)
        </button>
        <button onclick="approveConditional('fix')" class="btn btn-warning">
          🔧 Try Auto-Fix (Musleh)
        </button>
        <button onclick="approveConditional('cancel')" class="btn btn-danger">
          ❌ Cancel - Fix Manually
        </button>
      </div>
    </div>

    <div id="autoExecuteMessage" style="display:none; margin-top: 20px;">
      <div class="alert alert-success">
        <h4>✅ All Rows Accepted - Executing Now...</h4>
        <p>Total Rows: <span id="totalAcceptedRows"></span></p>
      </div>
    </div>
    ```

  - _Requirements: 2.9, 2.10, 2.11, 2.12_

- [x] 3.6.6 إضافة JavaScript لمعالجة Conditional Actions
  - **File**: Dashboard HTML (script section)
  - **Add JavaScript**:

    ```javascript
    let currentOperationId = null;

    function handleDryRunResults(response) {
      currentOperationId = response.operation_id;

      const acceptedCount = response.excel_validation_stats.accepted;
      const rejectedCount = response.excel_validation_stats.rejected;

      // Display rejection details if any
      if (response.rejected_rows_details) {
        displayRejectionDetails(response.rejected_rows_details);
      }

      // Show appropriate UI based on rejection count
      if (rejectedCount === 0 && acceptedCount > 0) {
        // Auto-execute scenario
        document.getElementById("totalAcceptedRows").textContent =
          acceptedCount;
        document.getElementById("autoExecuteMessage").style.display = "block";
        document.getElementById("conditionalActions").style.display = "none";
      } else if (rejectedCount > 0) {
        // Manual decision scenario
        document.getElementById("acceptedCount").textContent = acceptedCount;
        document.getElementById("conditionalActions").style.display = "block";
        document.getElementById("autoExecuteMessage").style.display = "none";
      }
    }

    async function approveConditional(choice) {
      if (!currentOperationId) {
        alert("No operation in progress");
        return;
      }

      const formData = new FormData();
      formData.append("operation_id", currentOperationId);
      formData.append("choice", choice);

      try {
        const response = await fetch("/api/approve-conditional", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error("Conditional approval failed");
        }

        const data = await response.json();
        alert(`Choice recorded: ${choice}. Next step: ${data.next_step}`);

        // Hide action buttons
        document.getElementById("conditionalActions").style.display = "none";

        // Start monitoring operation status
        monitorOperationStatus(currentOperationId);
      } catch (error) {
        alert("Error: " + error.message);
      }
    }
    ```

  - _Requirements: 2.9, 2.10, 2.11, 2.12_

- [x] 3.6.7 إضافة Agent Timeline Section في Dashboard
  - **File**: Dashboard HTML
  - **Add section**:

    ```html
    <div id="agentTimeline" style="display:none; margin-top: 20px;">
      <h3>🤖 Agent Timeline</h3>
      <div id="timelineContainer" class="timeline">
        <!-- Populated dynamically -->
      </div>
    </div>

    <style>
      .timeline {
        border-left: 2px solid #007bff;
        padding-left: 20px;
      }

      .timeline-event {
        margin-bottom: 15px;
        padding: 10px;
        background: #f8f9fa;
        border-radius: 5px;
        position: relative;
      }

      .timeline-event::before {
        content: "";
        position: absolute;
        left: -26px;
        top: 50%;
        transform: translateY(-50%);
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #007bff;
      }

      .timeline-event.success::before {
        background: #28a745;
      }

      .timeline-event.failed::before {
        background: #dc3545;
      }

      .timeline-event.in_progress::before {
        background: #ffc107;
        animation: pulse 1.5s infinite;
      }

      @keyframes pulse {
        0%,
        100% {
          opacity: 1;
        }
        50% {
          opacity: 0.5;
        }
      }

      .timestamp {
        font-size: 0.85em;
        color: #6c757d;
      }

      .agent {
        font-weight: bold;
        color: #007bff;
      }

      .action {
        color: #495057;
      }

      .tooltip {
        font-size: 0.9em;
        color: #6c757d;
        font-style: italic;
      }
    </style>
    ```

  - _Requirements: 2.13, 2.14, 2.15, 2.16_

- [x] 3.6.8 إضافة JavaScript لـ Agent Timeline Updates
  - **File**: Dashboard HTML (script section)
  - **Add JavaScript**:

    ```javascript
    let timelineUpdateInterval = null;

    function updateAgentTimeline(operationId) {
      fetch(`/api/agent-traces/${operationId}`)
        .then((res) => {
          if (!res.ok) {
            throw new Error("Failed to fetch agent traces");
          }
          return res.json();
        })
        .then((data) => {
          const container = document.getElementById("timelineContainer");
          container.innerHTML = "";

          if (data.events && data.events.length > 0) {
            data.events.forEach((event) => {
              const eventDiv = document.createElement("div");
              eventDiv.className = `timeline-event ${event.status}`;

              const statusIcon =
                event.status === "success"
                  ? "✅"
                  : event.status === "failed"
                    ? "❌"
                    : "⏳";

              eventDiv.innerHTML = `
                            <span class="timestamp">${new Date(event.timestamp).toLocaleTimeString("ar-EG")}</span> -
                            <span class="agent">${event.agent}</span> -
                            <span class="action">${event.action}</span>
                            ${statusIcon}
                            ${event.decision ? `<br><strong>Decision:</strong> ${event.decision}` : ""}
                            ${event.reasoning ? `<br><span class="tooltip">${event.reasoning}</span>` : ""}
                        `;

              container.appendChild(eventDiv);
            });

            document.getElementById("agentTimeline").style.display = "block";
          } else {
            container.innerHTML = "<p>No agent events yet...</p>";
          }
        })
        .catch((error) => {
          console.error("Error updating agent timeline:", error);
        });
    }

    function startTimelinePolling(operationId) {
      // Clear any existing interval
      if (timelineUpdateInterval) {
        clearInterval(timelineUpdateInterval);
      }

      // Initial update
      updateAgentTimeline(operationId);

      // Poll every 2 seconds
      timelineUpdateInterval = setInterval(() => {
        updateAgentTimeline(operationId);
      }, 2000);
    }

    function stopTimelinePolling() {
      if (timelineUpdateInterval) {
        clearInterval(timelineUpdateInterval);
        timelineUpdateInterval = null;
      }
    }

    // Call startTimelinePolling(operationId) when operation starts
    // Call stopTimelinePolling() when operation completes
    ```

  - _Requirements: 2.13, 2.14, 2.15, 2.16_

---

## Phase 4: Validation & Testing 🧪

### 4.1 Fix Checking - Verify Bug Fixes Work

- [x] 4.1.1 **Property 1: Expected Behavior** - Template Generation Works Test
  - **IMPORTANT**: إعادة تشغيل نفس اختبار task 1.1.1 - لا تكتب اختبار جديد
  - **Run Tests**:
    - `POST /api/template/generate` مع `{company_id: 1, template_type: "employee"}` → توقع **200 OK** مع download_url
    - فتح Dashboard → توقع **وجود** section "Generate Template"
    - استدعاء download endpoint → توقع **Excel file** مع company-specific data
  - **EXPECTED OUTCOME**: الاختبار **ينجح** (يُؤكد إصلاح المشكلة)
  - _Requirements: Expected Behavior Properties من التصميم (2.1, 2.2, 2.3, 2.4)_

- [x] 4.1.2 **Property 1: Expected Behavior** - Dry-Run Rejection Details Visible Test
  - **IMPORTANT**: إعادة تشغيل نفس اختبار task 1.1.2
  - **Run Tests**:
    - dry-run مع ملف يحتوي 5 أخطاء
    - فحص response → توقع **وجود** `rejected_rows_details` array
    - فحص Dashboard → توقع **جدول تفصيلي** بـ 5 صفوف
  - **EXPECTED OUTCOME**: الاختبار **ينجح**
  - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [x] 4.1.3 **Property 1: Expected Behavior** - Auto-Execute Active Test
  - **IMPORTANT**: إعادة تشغيل نفس اختبار task 1.1.3
  - **Run Tests**:
    - dry-run مع ملف نظيف → توقع `auto_execute: true` و **تنفيذ فوري**
    - dry-run مع أخطاء → توقع `auto_execute: false` و **action buttons**
  - **EXPECTED OUTCOME**: الاختبار **ينجح**
  - _Requirements: 2.9, 2.10, 2.11, 2.12_

- [x] 4.1.4 **Property 1: Expected Behavior** - Agent Timeline Displayed Test
  - **IMPORTANT**: إعادة تشغيل نفس اختبار task 1.1.4
  - **Run Tests**:
    - بدء operation
    - `GET /api/agent-traces/{operation_id}` → توقع **events array**
    - Dashboard → توقع **timeline section** مع agent events
  - **EXPECTED OUTCOME**: الاختبار **ينجح**
  - _Requirements: 2.13, 2.14, 2.15, 2.16_

- [x] 4.1.5 **Property 1: Expected Behavior** - State Fields Populated Test
  - **IMPORTANT**: إعادة تشغيل نفس اختبار task 1.1.5
  - **Run Tests**:
    - فحص `SerajState` → تأكيد **وجود** الحقول الثلاثة
    - بعد dry-run → تأكيد `rejected_rows_details` **populated**
    - بعد conditional check → تأكيد `auto_execute` **set**
  - **EXPECTED OUTCOME**: الاختبار **ينجح**
  - _Requirements: 2.17, 2.18, 2.19_

### 4.2 Preservation Checking - Verify No Regressions

- [x] 4.2.1 **Property 2: Preservation** - Verify Existing API Endpoints Still Work
  - **IMPORTANT**: إعادة تشغيل نفس اختبارات task 2.1.1
  - **Run Preservation Tests**:
    - جميع endpoints الموجودة (`/upload`, `/dry-run`, `/approve`, `/write`) تُرجع نفس JSON format
    - Telegram bot integration يعمل
    - CLI tools تعمل
  - **EXPECTED OUTCOME**: الاختبارات **تنجح** (لا regressions)
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 4.2.2 **Property 2: Preservation** - Verify Agent Logic Unchanged
  - **IMPORTANT**: إعادة تشغيل نفس اختبارات task 2.1.2
  - **Run Preservation Tests**:
    - Agent selection logic unchanged
    - Musleh healing يعمل
    - State fields الموجودة محفوظة
  - **EXPECTED OUTCOME**: الاختبارات **تنجح**
  - _Requirements: 3.4, 3.5, 3.6_

- [x] 4.2.3 **Property 2: Preservation** - Verify Security & Logging
  - **IMPORTANT**: إعادة تشغيل نفس اختبارات task 2.1.3
  - **Run Preservation Tests**:
    - Authentication يعمل
    - Audit logging يُسجل
    - Parser يعمل
    - Analytics endpoint يُرجع data
  - **EXPECTED OUTCOME**: الاختبارات **تنجح**
  - _Requirements: 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16_

- [x] 4.2.4 **Property 2: Preservation** - Verify Test Suite Coverage
  - **IMPORTANT**: إعادة تشغيل test suite الكامل
  - **Run all existing tests**: تأكيد >80% coverage و جميع الاختبارات تنجح
  - **Compare with baseline**: مقارنة results مع baseline من task 2.1.4
  - **EXPECTED OUTCOME**: جميع الاختبارات **تنجح** بدون regressions
  - _Requirements: جميع متطلبات Preservation_

---

## Phase 5: Integration Testing & Documentation 📚

### 5.1 End-to-End Testing

- [x] 5.1.1 E2E Test: Template Generation Flow
  - **Scenario**: مستخدم يُولّد قالب من Dashboard، يُحمّله، يُملؤه، يرفعه
  - **Steps**:
    1. فتح Dashboard → template section
    2. اختيار company، template type
    3. Generate → download
    4. ملء Excel بالبيانات
    5. رفع via `/upload`
    6. dry-run → عرض results
  - **Expected**: Flow كامل يعمل بسلاسة

- [x] 5.1.2 E2E Test: Conditional Execution Flow (Clean File)
  - **Scenario**: رفع ملف نظيف → auto-execute فوري
  - **Steps**:
    1. رفع ملف بدون أخطاء
    2. dry-run → `rejected: 0`
    3. توقع auto-execute فوري
    4. Dashboard يُظهر "✅ All rows accepted - Executing now..."
  - **Expected**: تنفيذ فوري بدون انتظار approval

- [x] 5.1.3 E2E Test: Conditional Execution Flow (With Errors)
  - **Scenario**: رفع ملف بأخطاء → manual decision
  - **Steps**:
    1. رفع ملف مع 5 أخطاء
    2. dry-run → `rejected: 5`
    3. Dashboard يُظهر rejection details table
    4. Dashboard يُظهر action buttons
    5. مستخدم يختار "Execute Accepted Only"
    6. تنفيذ الصفوف المقبولة فقط
  - **Expected**: User choice يتحكم في التنفيذ

- [x] 5.1.4 E2E Test: Agent Timeline Monitoring
  - **Scenario**: monitoring agent execution real-time
  - **Steps**:
    1. بدء operation
    2. Dashboard timeline يبدأ بالتحديث كل 2 ثانية
    3. عرض Seraj → Fahas → Mudaqqiq → Katib events
    4. عرض status icons (⏳/✅/❌)
    5. عرض reasoning tooltips
  - **Expected**: real-time visibility لـ agent execution

### 5.2 Documentation Updates

- [x] 5.2.1 تحديث API Documentation
  - **Add docs for new endpoints**:
    - `POST /api/template/generate`
    - `GET /api/template/download/{template_id}`
    - `POST /api/approve-conditional`
    - `GET /api/agent-traces/{operation_id}`
  - **Include**:
    - Parameters
    - Request/Response examples
    - Error codes
    - Authentication requirements

- [x] 5.2.2 تحديث Dashboard User Guide
  - **Add sections**:
    - How to generate templates
    - Understanding rejection details
    - Conditional execution workflow
    - Monitoring agent timeline
  - **Include screenshots** (إذا أمكن)

- [x] 5.2.3 تحديث Developer Documentation
  - **Add sections**:
    - LangGraph conditional execution node
    - Agent events service integration
    - State management expansion
    - Extending rejection detail formatting

- [x] 5.2.4 Update CHANGELOG
  - **Document all changes**:
    - New features
    - API additions
    - UI enhancements
    - Bug fixes
  - **Version bump** (if applicable)

---

## Phase 6: Checkpoint - Final Verification ✅

- [x] 6.1 Final Checkpoint - Ensure All Tests Pass
  - تشغيل جميع الاختبارات (bug condition, preservation, E2E)
  - التأكد من عدم وجود regressions
  - مراجعة coverage (>80%)
  - سؤال المستخدم إذا ظهرت أي مشاكل

- [x] 6.2 Code Review & Quality Check
  - مراجعة جميع التغييرات
  - التأكد من style consistency
  - التحقق من error handling
  - التأكد من logging كافي

- [x] 6.3 Performance Testing
  - اختبار template generation time
  - اختبار rejection details formatting performance
  - اختبار agent timeline update latency
  - التأكد من عدم تدهور في performance

- [x] 6.4 Security Review
  - مراجعة authentication على endpoints الجديدة
  - التحقق من input validation
  - التأكد من audit logging لجميع العمليات
  - فحص file upload security

- [x] 6.5 User Acceptance Testing
  - عرض التغييرات على stakeholders
  - جمع feedback
  - تطبيق تعديلات إذا لزم الأمر

---

## Summary

هذا المخطط التنفيذي يغطي:

- ✅ **Phase 1**: Bug Condition Exploration Tests (كشف المشاكل)
- ✅ **Phase 2**: Preservation Property Tests (حماية السلوك الموجود)
- 🔧 **Phase 3**: Implementation (تطبيق الإصلاحات الخمسة)
- 🧪 **Phase 4**: Validation (التحقق من نجاح الإصلاحات)
- 📚 **Phase 5**: Integration & Documentation (التكامل والتوثيق)
- ✅ **Phase 6**: Final Checkpoint (المراجعة النهائية)

**التبعيات الرئيسية**:

1. Phase 1 & 2 يجب أن تُكمل **قبل** Phase 3 (فهم المشاكل أولاً)
2. Task 3.1 (State Management) يجب أن تُكمل **قبل** Tasks 3.2-3.4 (تبعية state fields)
3. Task 3.4 (Agent Events Service) يجب أن تُكمل **قبل** Task 3.6.7-3.6.8 (Timeline UI يعتمد على service)
4. Phase 3 يجب أن تُكمل **قبل** Phase 4 (التحقق من الإصلاحات)

**الأولويات**:

- **عالية**: State Management (3.1) - تبعية لكل شيء
- **عالية**: Conditional Execution (3.3) - core functionality
- **متوسطة**: Template Generation (3.5) - user-facing feature
- **متوسطة**: Rejection Details (3.2) - user experience
- **متوسطة**: Agent Tracing (3.4) - monitoring
- **منخفضة**: Dashboard UI (3.6) - يعتمد على backend completion
