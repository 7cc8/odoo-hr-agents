# Graph Report - odoo-hr-agents-2  (2026-10-12)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4515 nodes · 9835 edges · 207 communities (176 shown, 31 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 505 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5696b76d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- OdooReadonlyRepository
- WriterTests
- test_saudi_labor_law_rules.py
- web_service.py
- MuwaffaqAgent
- SijilAgent
- Request
- AgentGoal
- AttendanceService
- AgentTracer
- OdooRecruitmentWriteGateway
- LetterService
- OdooAppraisalWriteGateway
- environment_policy.py
- writer.py
- SerajMetaAgent
- eos_service.py
- OdooGRWriteGateway
- WarningService
- FahasAgent
- OdooLoanWriteGateway
- OdooDisciplinaryWriteGateway
- AnalyticsService
- MonitoringDashboard
- dry_run_report.py
- TelegramBotTests
- SerajLLMService
- katib_service.py
- TestSeraj20Scenarios
- test_p2_seven_questions_deterministic.py
- LeaveService
- patch
- HaresAgent
- MetricsCollector
- BaseAgent
- AgentEventsService
- SerajState
- FilePersistentCheckpointer
- .get_repository
- generate_all_hr_templates.py
- parse_xlsx
- MuslehService
- rotate_api_key.py
- telegram_bot.py
- TelegramBotClient
- TranscriptionResult
- Validator
- TestMuslehService
- manage_retention.py
- MuslehAgent
- OdooContractWriteGateway
- parser.py
- KatibAgent
- test_observability.py
- TestEndToEndWorkflows
- manager.py
- MudaqqiqAgent
- VectorStore
- TemplateDetector
- get_events_service
- ToolRegistry
- test_katib_agent.py
- DocumentExpiryService
- test_mudaqqiq_agent.py
- DemoAgent
- generate_employee_template.py
- test_seraj_meta_integration.py
- MemoryManager
- mock_fahas_execute
- excel_template_validator.py
- agentic_nodes.py
- excel_nodes.py
- KatibAgent
- payroll_service.py
- build_graph
- MemoryEnabledAgent
- LearningSystem
- OdooLeaveWriteGateway
- DeploymentVerifier
- run_telegram_bot_polling
- LaborLawKnowledgeBase
- ExpenseService
- ingest_user_message
- ObservableAgent
- test_memory_advanced.py
- WebServiceTests
- verify_write_auth
- OdooExpenseWriteGateway
- ._load_ws
- PayrollService
- Any
- test_memory_system.py
- TestSevenQuestionsRealGraph
- TestSerajToolCalling
- ContractService
- OdooPayrollWriteGateway
- TestUnifiedAgentCockpitAcceptance
- test_web_service_phase24_25.py
- run.cjs
- calculate_gosi_contributions
- TestSijilPageAndExport
- TestAgentEventsServiceP3
- LLMProvider
- TestPerformanceBenchmarks
- classify_intent
- TestAgentTracer
- test_graph_memory.py
- get_active_odoo_config
- execute_writer_endpoint
- TestMonitoringDashboard
- test_generate_employee_template.py
- FailureCodesTests
- MemorySaver
- 01_test_create_employee.py
- test_p3_persistent_checkpointer.py
- test_integration.py
- test_graph_routing.py
- .get_operation_detail
- apply_appraisal_endpoint
- 04_test_safe_fields_extended.py
- ConversationSession
- log_telegram_audit
- Any
- create_deletion_plan
- MakeApprovalTests
- UserProfile
- AgentMetrics
- output_validator_check.py
- SijilAuditService
- FakeOdooRepository
- TestSerajControlledDeletion
- mudaqqiq_agent.py
- apply_ui_redesign.py
- detect_employee_nationality
- TestMetricsCollector
- TestFahasServiceAndSeparation
- apply_contract_endpoint
- apply_disciplinary_endpoint
- apply_eos_endpoint
- apply_leave_endpoint
- .plan
- TestLaborLawMudaqqiqRouting
- TestSecurityValidation
- test_comparison_old_vs_new.py
- MockWriteGateway
- TestPersistentCheckpointer
- TestEOSService
- ComplianceRule
- install.ps1
- determine_disciplinary_occurrence
- OdooReadonlyRepositoryError
- Any
- TestStressTesting
- TestHelpers
- apply_gr_endpoint
- TestSijilAuditService
- ._get_delete_gateway
- .scan_expiries
- ProductionMonitor
- handle_wizard_employee_selection
- handle_musleh_heal_callback
- MockDeleteGateway
- TestSerajAddEditWorkflow
- TelegramNotifierTests
- TestWebServiceSijilAndLaya
- .dry_run_expense
- langgraph.json
- test_chat_api.py
- TestEnableAgenticFahas
- TestFahasVerifyRecordStatus
- WorkingMemory
- .__init__
- 02_test_lookup_department_job.py
- get_gr_service_for_bot
- test_telegram_bot.py
- .get_recent_operations
- .search_operations
- live_telegram_scenario_runner.py
- .calculate_annual_leave
- .calculate_gosi
- .calculate_overtime
- .validate_disciplinary
- .validate_probation
- graph/__init__.py
- integration/__init__.py
- run_comprehensive_scenario_demonstration
- ValueError
- BaseModel
- get
- post
- Request
- Worksheet

## God Nodes (most connected - your core abstractions)
1. `OdooReadonlyRepository` - 186 edges
2. `audit_log_access()` - 106 edges
3. `TelegramBotClient` - 102 edges
4. `TelegramBotTests` - 95 edges
5. `run_telegram_bot_polling()` - 68 edges
6. `SerajLLMService` - 54 edges
7. `SerajState` - 54 edges
8. `handle_callback_dispatch()` - 54 edges
9. `KatibAgent` - 52 edges
10. `MudaqqiqAgent` - 51 edges

## Surprising Connections (you probably didn't know these)
- `AnalyticsService` --uses--> `OdooReadonlyRepository`  [INFERRED]
  analytics_service.py → odoo_readonly_repository.py
- `AppraisalService` --uses--> `OdooReadonlyRepository`  [INFERRED]
  appraisal_service.py → odoo_readonly_repository.py
- `AttendanceService` --uses--> `OdooReadonlyRepository`  [INFERRED]
  attendance_service.py → odoo_readonly_repository.py
- `ContractService` --uses--> `OdooReadonlyRepository`  [INFERRED]
  contract_service.py → odoo_readonly_repository.py
- `DisciplinaryService` --uses--> `OdooReadonlyRepository`  [INFERRED]
  disciplinary_service.py → odoo_readonly_repository.py

## Import Cycles
- None detected.

## Communities (207 total, 31 thin omitted)

### Community 0 - "OdooReadonlyRepository"
Cohesion: 0.06
Nodes (25): OdooReadonlyRepository, Any, جلب تفاصيل طلب موافقة أو خطاب محدد., جلب خطابات الإنذار والمساءلات من warning.letter., جلب أنواع الإنذارات من warning.type., جلب المصروفات من hr.expense., Searches employees comprehensively by name, email, identification ID, or…, Backwards-compatible alias for comprehensive employee candidate search. (+17 more)

### Community 1 - "WriterTests"
Cohesion: 0.07
Nodes (15): EnvironmentGuardError, OdooWriteGateway, Any, RuntimeError, WriteGatewayError, FakeCommon, FakeModels, make_gateway() (+7 more)

### Community 2 - "test_saudi_labor_law_rules.py"
Cohesion: 0.06
Nodes (67): التحقق من نوع العقد وفق المادة 37 (حظر العقود غير المحددة لغير السعودي), خدمة إدارة الإجازات ونظام العمل السعودي (Leave Service)…, calculate_annual_leave_entitlement(), calculate_article_77_compensation(), calculate_overtime_pay(), ContractType, get_occasion_leave_statutory_days(), NationalityType (+59 more)

### Community 3 - "web_service.py"
Cohesion: 0.05
Nodes (81): BaseModel, FastAPI, post, AgentApprovalApiRequest, AgentCancelApiRequest, apply_loan_endpoint(), apply_payslip_endpoint(), ApprovalRequest (+73 more)

### Community 4 - "MuwaffaqAgent"
Cohesion: 0.06
Nodes (50): get_muwaffaq_agent(), MatchCandidate, MatchDecision, MatchResult, MatchStrategy, MuwaffaqAgent, Any, Enum (+42 more)

### Community 5 - "SijilAgent"
Cohesion: 0.07
Nodes (50): AnomalyType, AuditAnomaly, AuditDecision, AuditScope, AuditSummary, get_sijil_agent(), Any, Enum (+42 more)

### Community 6 - "Request"
Cohesion: 0.05
Nodes (87): FileResponse, get, Request, audit_log_access(), download_template_endpoint(), get_agent_operation_endpoint(), get_agents_operations_endpoint(), get_agents_overview_endpoint() (+79 more)

### Community 7 - "AgentGoal"
Cohesion: 0.05
Nodes (39): AgentGoal, create_agent_goal(), مساعد لإنشاء هدف للوكيل, create_fahas_query_goal(), FahasAgent, AgentGoal, Any, Fahas Agent - وكيل الاستعلام والتحقق ======================================… (+31 more)

### Community 8 - "AttendanceService"
Cohesion: 0.05
Nodes (49): AttendanceDryRunResult, AttendanceExecutionResult, AttendanceService, AttendanceSummaryResult, DailyAttendanceDetail, Any, خدمة إدارة الحضور والعمل الإضافي ونظام العمل السعودي (Attendance & Overtime…, جلب وتلخيص سجلات حضور الموظف وحساب ساعات وأجر العمل الإضافي وفق المادتين 98 و… (+41 more)

### Community 9 - "AgentTracer"
Cohesion: 0.08
Nodes (19): AgentTracer, Any, Add a span to the trace, Get hierarchical span tree, Context for nested tracing, Agent Tracing System Provides comprehensive tracing for agent execution: -…, Initialize LangSmith integration, End the current trace (+11 more)

### Community 10 - "OdooRecruitmentWriteGateway"
Cohesion: 0.06
Nodes (31): OdooRecruitmentWriteGateway, Any, RuntimeError, إنشاء سجل مرشح/متقدم جديد لموديل hr.applicant في Odoo مع التزام التوطين السعودي., قراءة سجل المرشح من Odoo لأغراض التحقق المستقل (Readback Verification)., نقل المرشح إلى مرحلة تالية في خط أنابيب التوظيف (First Interview, Contract…, اعتماد حالة طلب التوظيف (draft, submitted, approved)., بوابة الكتابة الآمنة والمحصورة لإدارة التوظيف والمرشحين (hr.applicant). تلتزم… (+23 more)

### Community 11 - "LetterService"
Cohesion: 0.06
Nodes (43): LetterApplyResult, LetterDryRunResult, LetterSalaryDetails, LetterService, Any, خدمة إدارة وإصدار خطابات الموارد البشرية وشهادات الرواتب الرسمية (HR Official…, الخدمة الشاملة للخطابات وشهادات التعريف بالراتب مع حماية التحقق المزدوج…, قائمة أنواع الخطابات المدعومة إدارياً. (+35 more)

### Community 12 - "OdooAppraisalWriteGateway"
Cohesion: 0.06
Nodes (31): AppraisalDryRunResult, AppraisalExecutionResult, AppraisalService, AppraisalSummary, calculate_weighted_score(), determine_appraisal_rating(), خدمة إدارة وتدقيق تقييمات الأداء والموظفين (Employee Appraisals Service)…, خدمة إدارة وتدقيق تقييمات الأداء والموظفين في Odoo. تلتزم بضوابط المادة 53… (+23 more)

### Community 13 - "environment_policy.py"
Cohesion: 0.05
Nodes (28): CleanupInputError, emails_match(), load_created_records(), main(), process_cleanup(), Any, Path, Safely clean employees created by one specific writer results file. (+20 more)

### Community 14 - "writer.py"
Cohesion: 0.07
Nodes (34): Approval, ApprovalReportMismatchError, ApprovalSchemaError, Any, Exception, Path, Schema and validation for the writer's approval file. This module performs…, Raises ApprovalReportMismatchError unless the approval corresponds exactly to… (+26 more)

### Community 15 - "SerajMetaAgent"
Cohesion: 0.06
Nodes (33): AgentSelectionReasoning, AgentType, IntentType, InteractionLearning, Any, Enum, str, وكيل التنسيق الذكي الشامل: «سراج» (Seraj Meta-Agent)… (+25 more)

### Community 16 - "eos_service.py"
Cohesion: 0.06
Nodes (36): حساب مكافأة نهاية الخدمة بالريال وفق المواد 84 و 85 و 87, calculate_service_period_components(), EOSCalculationSummary, EOSDryRunResult, EOSExecutionResult, EOSService, خدمة إدارة مكافأة نهاية الخدمة والتسويات ونظام العمل السعودي (End of Service…, خدمة تسوية مكافأة نهاية الخدمة والتعويضات النظامية في Odoo. تطبق بدقة حاسمة… (+28 more)

### Community 17 - "OdooGRWriteGateway"
Cohesion: 0.06
Nodes (27): GRDryRunResult, GRExecutionResult, GRService, GRTransactionSummary, خدمة إدارة المعاملات الحكومية والجوازات والتأشيرات (Government Relations…, خدمة إدارة وتدقيق المعاملات الحكومية والجوازات في Odoo. تلتزم بضوابط المادة 40…, جلب وتلخيص المعاملات الحكومية المسجلة للموظف وتصنيفه (سعودي أم غير سعودي)., الفحص التجريبي الاستباقي للمعاملة الحكومية وتدقيق الضوابط النظامية للمادة 40. (+19 more)

### Community 18 - "WarningService"
Cohesion: 0.07
Nodes (36): OdooWarningWriteGateway, Any, Exception, بوابة الكتابة الآمنة لخطابات الإنذار والمساءلات التأديبية (Odoo Warning Write…, إنشاء خطاب إنذار في Odoo (warning.letter)., إنشاء نوع إنذار جديد في Odoo (warning.type)., قراءة خطاب إنذار محدد للتحقق بعد الكتابة (Readback Verification)., البحث واسترجاع خطابات الإنذار. (+28 more)

### Community 19 - "FahasAgent"
Cohesion: 0.07
Nodes (41): DeletionPolicyError, Exception, سياسة وضوابط الحذف والأرشفة المحكومة (Controlled Deletion & Archiving Policy)…, خطأ في سياسة الحذف أو الأرشفة أو الاسترجاع., تحديد النموذج والوصف العربي بناءً على الكلمات المفتاحية في الاستعلام., resolve_model_from_query(), FahasAgent, FahasSecurityError (+33 more)

### Community 20 - "OdooLoanWriteGateway"
Cohesion: 0.07
Nodes (22): LoanDryRunResult, LoanExecutionResult, LoanService, LoanSummary, خدمة إدارة وتدقيق سلف وقروض الموظفين (Employee Loans Service)…, الفحص والتدقيق التجريبي لطلب السلفة/القرض وفق المادة 92 من نظام العمل السعودي., اعتماد وتسجيل السلفة/القرض فعلياً في Odoo مع إلزامية التأكيد الكتابي الصريح., خدمة إدارة وتدقيق سلف وقروض الموظفين في Odoo. تلتزم بضوابط المادة 92 وسقف… (+14 more)

### Community 21 - "OdooDisciplinaryWriteGateway"
Cohesion: 0.07
Nodes (26): DisciplinaryActionSummary, DisciplinaryDryRunResult, DisciplinaryExecutionResult, DisciplinaryService, Any, خدمة إدارة الجزاءات والمخالفات التأديبية ونظام العمل السعودي (Disciplinary…, اعتماد وتسجيل الجزاء التأديبي فعلياً في Odoo مع إلزامية التأكيد الكتابي والتحقق…, DisciplinaryEnvironmentGuardError (+18 more)

### Community 22 - "AnalyticsService"
Cohesion: 0.08
Nodes (26): AnalyticsService, ComplianceKpis, detect_employee_nationality(), determine_nitaqat_band(), FinancialKpis, OperationsKpis, Any, خدمة التحليلات الشاملة ولوحة المؤشرات التنفيذية (HR Executive Analytics &… (+18 more)

### Community 23 - "MonitoringDashboard"
Cohesion: 0.07
Nodes (28): Observability & Monitoring System for Odoo HR Agents Provides tracing, metrics,…, Alert, AlertLevel, AlertRule, AlertType, MonitoringDashboard, Any, Enum (+20 more)

### Community 24 - "dry_run_report.py"
Cohesion: 0.09
Nodes (23): AST, build_full_report(), build_report_dict(), csv_formula_guard(), DryRunReportError, generate_dry_run_report(), _MiniXlsxEmitter, Any (+15 more)

### Community 26 - "SerajLLMService"
Cohesion: 0.07
Nodes (25): FahasAgent, KatibAgent, Any, محرك التفكير واللغة الطبيعية وتنسيق المهام لسراج عبر OpenRouter وتفويض…, حلقة تنسيق مهام الاستعلام: سراج يطلب المهمة المحددة -> يفوضها لوكيل فاحص في…, Returns True if Ollama is available with required model., واجهة التوافق الخلفي مع النظام: تستدعي دورة المحادثة الكاملة chat_turn., Call local LLM server (Ollama) compatible with OpenAI Chat Completions API.… (+17 more)

### Community 27 - "katib_service.py"
Cohesion: 0.08
Nodes (27): ApprovalPlan, ApprovalPlanError, Any, Exception, Path, مخطط خطط الاعتماد الموحد (Unified Approval Plan Schema)…, استهلاك الخطة (تنفيذ لمرة واحدة), فحص انتهاء صلاحية الخطة (+19 more)

### Community 28 - "TestSeraj20Scenarios"
Cohesion: 0.05
Nodes (23): سيناريو 5: التعويض عن الإنهاء غير المشروع (المادة 77) -> لا يقل عن أجر شهرين., سيناريو 6: حظر حسم أكثر من 5 أيام كجزاء في الشهر (المادة 70)., سيناريو 7: تقادم وسقوط المخالفة بعد مضي 30 يوماً على اكتشافها (المادة 72)., سيناريو 8: سقف قسط سلفة صاحب العمل لا يتجاوز 10% من الراتب (المادة 92 المعدلة)., سيناريو 9: فترة التجربة الأصلية 90 يوماً والتمديد إلى 180 مشروط باتفاق كتابي…, سيناريو 10: إجازات المناسبات بعد تعديل 1446هـ (المادة 113) -> الأبوة 3 أيام،…, سيناريو 11: إجازة الوضع للأم العاملة (تعديلات 1446هـ) -> 12 أسبوعاً بأجر كامل…, سيناريو 12: اشتراط العقد محدد المدة لغير السعودي وبطلان العقد غير المحدد… (+15 more)

### Community 29 - "test_p2_seven_questions_deterministic.py"
Cohesion: 0.06
Nodes (27): detect_company_references(), expand_query_phrases(), تصنيف النية - Classify Intent =============================== يصنف طلبات…, اكتشاف مراجع الشركات في النص يرجع قائمة بالمراجع مع نوع كل مرجع, توسيع العبارات الشائعة لتحسين الفهم, check_consistency(), فحص اتساق البيانات: مجموع عدد الشركات يجب أن يساوي الإجمالي دالة حتمية خارج…, اختبار P2: الطبقة الحتمية للأسئلة السبعة… (+19 more)

### Community 30 - "LeaveService"
Cohesion: 0.07
Nodes (33): EmployeeLeaveSummary, LeaveDryRunResult, LeaveExecutionResult, LeaveService, LeaveTypeInfo, Any, جلب جميع أنواع الإجازات المتاحة في أودو, جلب الملخص الشامل لإجازات الموظف مع حساب الاستحقاق النظامي وفق المادة 109. (+25 more)

### Community 32 - "HaresAgent"
Cohesion: 0.09
Nodes (24): AgentPlan, create_hares_security_goal(), Environment, HaresAgent, OperationType, AgentGoal, Any, Enum (+16 more)

### Community 33 - "MetricsCollector"
Cohesion: 0.05
Nodes (27): MetricPoint, MetricsCollector, MetricType, Any, Enum, str, Metrics Collection System Provides real-time metrics for agent performance…, Convert to dictionary (+19 more)

### Community 34 - "BaseAgent"
Cohesion: 0.08
Nodes (26): ABC, AgentMemory, AgentReflection, BaseAgent, Any, Base Agent Class - البنية الأساسية لكل الوكلاء…, نتيجة التأمل والمراجعة, الفئة الأساسية لكل الوكلاء الذكية (Agentic AI) كل وكيل يرث من هذه الفئة ويُطبق:… (+18 more)

### Community 35 - "AgentEventsService"
Cohesion: 0.10
Nodes (17): AgentEventsService, is_odoo_operation_event(), _mask_safe_ref(), Any, إزالة الأسرار وكلمات المرور والبيانات الحساسة من مراجع النتائج المعروضة., التحقق الصارم مما إذا كان الحدث يمثل عملية فعلية مؤثرة داخل Odoo تستوجب التوثيق…, محرك إدارة الأحداث والعمليات لمنظومة الوكلاء. Thread-safe، يحفظ السجلات في…, قراءة آخر أحداث مسجلة لتهيئة الحالة عند إعادة تشغيل الخادم. (+9 more)

### Community 36 - "SerajState"
Cohesion: 0.06
Nodes (52): build_session_context(), classify_intent(), collect_companies(), company_suffix(), fahas_tools(), fahas_verify(), finalize(), finalize_write() (+44 more)

### Community 37 - "FilePersistentCheckpointer"
Cohesion: 0.14
Nodes (12): Checkpoint, FilePersistentCheckpointer, Any, Path, تنظيف checkpoints قديمة Args: max_age_days: عدد الأيام للاحتفاظ بالـ checkpoints, File-based persistent checkpointer Extends MemorySaver but persists data to…, تحميل checkpoints المحفوظة من القرص, حفظ checkpoints الحالية إلى القرص (+4 more)

### Community 38 - ".get_repository"
Cohesion: 0.11
Nodes (22): enrich_records_with_aliases(), FahasExecutionError, Any, RuntimeError, تصحيح واستبدال أسماء الحقول الشائعة التي قد يطلبها النموذج بالخطأ إلى حقول Odoo…, إثراء السجلات بأسماء الحقول المقروءة لتسهيل استيعاب النموذج للنتائج., خطأ تنفيذي أثناء استعلام فاحص لبيانات Odoo., الحصول على مستودع Odoo المعتمد للقراءة المباشرة. (+14 more)

### Community 39 - "generate_all_hr_templates.py"
Cohesion: 0.13
Nodes (35): _apply_sheet_styling(), _build_instructions_sheet(), build_master_onboarding_workbook(), _build_reference_sheet(), build_standalone_template(), generate_all(), get_appraisals_spec(), get_attendance_spec() (+27 more)

### Community 40 - "parse_xlsx"
Cohesion: 0.23
Nodes (9): make_run_id(), parse_xlsx(), Any, Path, row_hash(), sha256_bytes(), _xlsx_has_formulas_or_merged_or_hidden(), build_xlsx() (+1 more)

### Community 41 - "MuslehService"
Cohesion: 0.11
Nodes (20): ActionableOption, MuslehDecisionResult, MuslehService, Any, القرار التنفيذي النهائي الصادر من وكيل مصلح., الواجهة التنفيذية لوكيل الإصلاح الذاتي وحل المشكلات: «مصلح» (Musleh Engine)., فحص الصف المعطوب واتخاذ القرار العلاجي المناسب. صمام الأمان: يتجاوز الصف فوراً…, استشارة الوكلاء الأربعة: فاحص، موفق، مدقق، ولايا. (+12 more)

### Community 42 - "rotate_api_key.py"
Cohesion: 0.07
Nodes (21): cmd_info(), cmd_verify(), _get_env(), _load_dotenv(), main(), _mask_key(), Verify current .env credentials against Odoo (read-only, changes nothing).…, Best-effort .env loading without requiring python-dotenv as a dependency. (+13 more)

### Community 43 - "telegram_bot.py"
Cohesion: 0.11
Nodes (33): execute_appraisal_via_service(), execute_contract_via_service(), execute_disciplinary_action_via_service(), execute_eos_settlement_via_service(), execute_loan_via_service(), execute_payslip_via_service(), get_appraisal_service_for_bot(), get_contract_service_for_bot() (+25 more)

### Community 44 - "TelegramBotClient"
Cohesion: 0.11
Nodes (32): get_analytics_service_for_bot(), get_expiry_service_for_bot(), handle_analytics_wizard_step(), handle_callback_dispatch(), handle_template_request(), Lightweight Telegram Bot API client using standard urllib., Displays Laya decision engine details and capabilities., Central router for all callback queries. (+24 more)

### Community 45 - "TranscriptionResult"
Cohesion: 0.11
Nodes (15): patch, اختبارات شاملة لمحرك تحويل الصوت إلى نص: «محرك الهمس» (Tests for…, TestWhisperSTTService, Any, Path, خدمة تحويل الصوت إلى نص: «محرك الهمس» (Whisper STT Service)…, Transcribes the given audio file using the best available backend. Args:…, Executes transcription via local faster-whisper model. (+7 more)

### Community 46 - "Validator"
Cohesion: 0.16
Nodes (5): FakeRepository, make_row(), ValidatorTests, safe_many2one_id(), Validator

### Community 47 - "TestMuslehService"
Cohesion: 0.07
Nodes (16): MockRepository, Any, اختبارات شاملة لوكيل الإصلاح الذاتي والتعافي: «مصلح» (Tests for MuslehService)…, تطبيق الإصلاح التلقائي الفوري عند تفعيل auto_repair وثقة >= 90%., الهويات والتكرار خط أحمر يحال حصراً للمسؤول البشري عبر سراج حتى مع auto_repair., عند طلب قسم جديد غير مضاف في Odoo ولا يوجد له بديل مقارب., معالجة دفعة: الصفوف السليمة والجاهزة للإصلاح تمر، والمعطوبة تُعزل., اختبار تحويل مختلف صيغ التواريخ المعطوبة إلى YYYY-MM-DD. (+8 more)

### Community 48 - "manage_retention.py"
Cohesion: 0.09
Nodes (17): clean_expired_reports(), get_folder_info(), is_writer_folder_or_audit(), main(), Any, datetime, Path, Check if the given folder contains or is an audit writer result. (+9 more)

### Community 49 - "MuslehAgent"
Cohesion: 0.14
Nodes (16): create_musleh_diagnostic_goal(), MuslehAgent, AgentGoal, Any, وضع خطة التشخيص والإصلاح الخطوات: 1. Assess - تقييم المشكلة 2. Consult -…, تحديد إذا كانت مشكلة هوية (خط أحمر), استشارة المراجع الحية, وكيل التشخيص والإصلاح - مُصلِّح يُشخّص المشاكل ويقترح الحلول (+8 more)

### Community 50 - "OdooContractWriteGateway"
Cohesion: 0.14
Nodes (15): ContractDryRunResult, ContractExecutionResult, ContractSummary, خدمة إدارة وتدقيق عقود العمل وهيكلة الأجور (Employment Contracts & Compensation…, ContractEnvironmentGuardError, ContractWriteGatewayError, OdooContractWriteGateway, Any (+7 more)

### Community 51 - "parser.py"
Cohesion: 0.10
Nodes (20): Single source of truth for Path A failure codes and their final status. Every…, خدمة وكيل الإصلاح الذاتي والتعافي: «مصلح» (Musleh Self-Healing & Diagnostic…, clean_value_text(), collapse_spaces(), email_match_key(), generic_match_key(), is_valid_email_format(), name_match_key() (+12 more)

### Community 52 - "KatibAgent"
Cohesion: 0.13
Nodes (15): KatibAgent, Any, الحصول على بوابة الكتابة مع فحص الأمان, المرحلة 1: الإدراك - تحليل طلب الكتابة وفهم السياق Args: action_request: طلب…, المرحلة 3: التنفيذ - تطبيق الخطة مع audit logging P5: التنفيذ الآن يتطلب فحص…, المرحلة 4: التأمل - تقييم النتائج والتعلم من التجربة Args: perception: نتائج…, تحليل الأمان للعملية المطلوبة, تحليل التأثير المتوقع للعملية (+7 more)

### Community 53 - "test_observability.py"
Cohesion: 0.14
Nodes (23): Observability System Demo Demonstrates full observability capabilities with…, Run complete observability demo, run_demo(), observable_phase(), observable_run(), Observability Integration with BaseAgent Provides seamless integration of…, Decorator for agent run method with full observability. Usage: @observable_run…, Decorator for agent phase methods with tracing. Usage:… (+15 more)

### Community 54 - "TestEndToEndWorkflows"
Cohesion: 0.10
Nodes (16): integration, Path, Test complete query workflow, Test complete write workflow, Test complete Excel processing workflow, Test error detection and healing workflow, Test employee matching workflow, Test complete audit workflow (+8 more)

### Community 55 - "manager.py"
Cohesion: 0.11
Nodes (18): enhance_agent_with_memory(), Agent Integration with Memory System ==================================== دمج…, Decorator لإضافة قدرات الذاكرة لأي agent class الاستخدام: ```python…, Memory System for Odoo HR Agents ================================= نظام ذاكرة…, Learning System - نظام التعلم الذكي =================================== يتعلم…, Memory Manager - مدير الذاكرة الموحد ==================================== يدير…, حفظ معرفة دلالية Returns: knowledge_id: معرف المعرفة, الحصول على معرفة بالمعرف (+10 more)

### Community 56 - "MudaqqiqAgent"
Cohesion: 0.12
Nodes (15): MudaqqiqAgent, Any, المرحلة 1: الإدراك - فهم السياق القانوني والمتطلبات Args: check_request: طلب…, المرحلة 2: التخطيط - بناء استراتيجية التحقق Args: perception: نتائج مرحلة…, المرحلة 3: التنفيذ - تطبيق القواعد والتحقق Args: plan: خطة التحقق من مرحلة…, المرحلة 4: التأمل - تفسير القرارات والتعلم Args: perception: نتائج الإدراك…, تحديد القواعد المطبقة على الحالة, تقييم المخاطر القانونية (+7 more)

### Community 57 - "VectorStore"
Cohesion: 0.09
Nodes (17): prepare_episode_text(), Any, Path, Vector Store Integration - Chroma DB ==================================== دمج…, البحث الدلالي في الحلقات Args: query: استعلام نصي filters: تصفية بـ metadata…, الحصول على حلقات مشابهة لحلقة معينة Args: episode_id: معرف الحلقة المرجعية…, إضافة معرفة إلى Vector DB Args: knowledge_id: معرف المعرفة text: النص للتضمين…, البحث الدلالي في المعرفة Args: query: استعلام نصي category: تصفية بالفئة limit:… (+9 more)

### Community 58 - "TemplateDetector"
Cohesion: 0.10
Nodes (18): main(), Graphify Pipeline Execution Script for odoo-hr-agents…, detect_template(), get_processing_plan(), Any, Template Detector - كاشف نوع Template تلقائياً…, معلومات عن sheet واحد, نتيجة فحص الـ Template (+10 more)

### Community 59 - "get_events_service"
Cohesion: 0.12
Nodes (11): get_events_service(), خدمة الأحداث وإدارة سير العمليات لمنظومة الوكلاء (Agent Events & Operations…, TestExcelDryRunWorkflow, اختبارات تكاملية وتحقق لوكيل التدقيق «مدقق» وتوجيه استشارات نظام العمل السعودي…, TestMainAcceptancePipeline, TestPollingResilienceAndTimeout, اختبارات القبول الشاملة للواجهة الموحدة لمنظومة الوكلاء Unified Multi-Agent…, get_agent_operation_events_endpoint() (+3 more)

### Community 60 - "ToolRegistry"
Cohesion: 0.11
Nodes (16): Any, Tool Registry - مدير الأدوات الموحد ==================================== يُدير…, تسجيل كل الأدوات المتاحة, تسجيل أدوات القراءة من Odoo, تسجيل أدوات الكتابة (تتطلب موافقة), # TODO: تسجيل أدوات الكتابة من katib_service, التحقق من صلاحية الوكيل لاستخدام الأداة, تحويل لصيغة OpenAI function schema (+8 more)

### Community 61 - "test_katib_agent.py"
Cohesion: 0.11
Nodes (25): get_katib_agent(), Enum, str, أنواع عمليات الكتابة المدعومة, استراتيجيات Rollback بعد حذف DELETE_CREATED (S2) Rollback يُنفذ عبر نموذج…, الحصول على كائن وكيل كاتب المفرد (Singleton), RollbackStrategy, WriteOperationType (+17 more)

### Community 62 - "DocumentExpiryService"
Cohesion: 0.13
Nodes (19): DocumentExpiryScanResult, DocumentExpiryService, خدمة الرصد الاستباقي لانتهاء الوثائق والتنبيهات المجدولة (Document Expiry…, الخدمة الشاملة للرصد الاستباقي لانتهاء الوثائق والتنبيهات المجدولة., تسجيل نتائج الفحص في سجل التدقيق., صياغة بطاقة تقرير فحص الوثائق التفاعلية لقناة وتطبيقات تيليقرام., توليد تقرير HTML تفاعلي فائق الجمال وفق معايير الهوية المؤسسية السعودية., توليد تقرير PDF رسمي لمخرجات فحص الصلاحيات باستخدام Playwright. (+11 more)

### Community 63 - "test_mudaqqiq_agent.py"
Cohesion: 0.14
Nodes (24): ComplianceCategory, اختبارات وكيل التدقيق والامتثال: مدقق (Mudaqqiq Agentic Compliance Agent Tests)…, اختبار مرحلة التأمل بعد فحص ناجح, اختبار الدورة الذكية الكاملة, اختبار مرحلة الإدراك لقواعد نظام العمل, اختبار الواجهة العامة verify_compliance, اختبار Singleton Factory, اختبار فحص متعدد الفئات (+16 more)

### Community 64 - "DemoAgent"
Cohesion: 0.19
Nodes (11): AgentGoal, DemoAgent, Any, Execute phase - run the plan, Reflect phase - evaluate results, Demo Agent with Full Observability Shows: - Automatic tracing (perceive -> plan…, Run full agentic loop with automatic tracing, Perceive phase - analyze the goal (+3 more)

### Community 65 - "generate_employee_template.py"
Cohesion: 0.20
Nodes (23): _add_dropdowns(), _build_employees_sheet(), _build_instructions_sheet(), _build_reference_sheet(), _first_active_company_name(), _first_active_dept_name(), _first_active_job_name(), generate_template() (+15 more)

### Community 66 - "test_seraj_meta_integration.py"
Cohesion: 0.13
Nodes (22): عقدة سراج Meta-Agent - التنسيق الذكي هذه العقدة تستخدم SerajMetaAgent لاتخاذ…, عقدة المراجعة الذكية - تحليل نتائج الوكلاء تُستدعى بعد تنفيذ الوكلاء لتحليل…, seraj_meta_orchestration(), seraj_meta_reflect(), اختبار دمج SerajMetaAgent مع LangGraph…, اختبار 3: عقدة المراجعة الذكية يجب أن تحلل النتائج وتتعلم من التفاعلات, اختبار 4: التعلم من التفاعلات يجب أن يتعلم Meta-Agent من النجاحات والفشل, اختبار 5: التكامل الكامل مع LangGraph يختبر المسار الكامل: classify_intent →… (+14 more)

### Community 67 - "MemoryManager"
Cohesion: 0.14
Nodes (13): MemoryManager, Any, datetime, حفظ حلقة تفاعل Returns: episode_id: معرف الحلقة, الحصول على حلقة بالمعرف, البحث في الحلقات السابقة Args: query: استعلام نصي (سيستخدم semantic search إذا…, الحصول على الحلقات الأخيرة, الحصول على الأنماط الناجحة لوكيل ونية معينة (+5 more)

### Community 68 - "mock_fahas_execute"
Cohesion: 0.15
Nodes (15): create_mock_llm_for_question(), mock_fahas_execute(), Any, اختبار الأسئلة السبعة على Graph مع Mock LLM…, Mock لتنفيذ أدوات Fahas بدون Odoo فعلي, إنشاء Mock LLM يرجع استدعاءات أدوات مسجلة لكل سؤال Args: messages: قائمة…, السؤال 1: "ما الشركات المتاحة لي؟" التحقق: - يرجع 4 شركات - company_id فارغة…, السؤال 2: "كم عدد الموظفين في شركة النخبة الذكية؟" التحقق: - يرجع 13 موظف -… (+7 more)

### Community 69 - "excel_template_validator.py"
Cohesion: 0.15
Nodes (22): _detect_header_and_data_rows(), identify_template_and_sheet(), make_run_id(), _map_columns_to_keys(), _match_employee_in_odoo(), _match_reference(), Any, Path (+14 more)

### Community 70 - "agentic_nodes.py"
Cohesion: 0.11
Nodes (17): hares_agentic_guard(), mudaqqiq_agentic_verify(), musleh_agentic_heal(), muwaffaq_agentic_match(), Any, Agentic Nodes - عقد LangGraph للوكلاء الذكية…, عقدة حارس الذكية - فحص الأمان قبل الكتابة يُستدعى قبل katib_execute للتحقق من…, عقدة مصلح الذكية - معالجة البيانات المُرفوضة يُستدعى عندما تكون هناك بيانات… (+9 more)

### Community 71 - "excel_nodes.py"
Cohesion: 0.11
Nodes (22): create_excel_approval(), generate_dry_run_report(), heal_excel_batch(), parse_excel_file(), Any, عقد معالجة Excel في الرسم (P4) ================================= تنفيذ مسار…, عقدة إصلاح الصفوف (بدون auto_repair). - تستخدم MuslehService لمعالجة الصفوف…, عقدة توليد تقرير dry-run. - تُنشئ تقرير تفصيلي بما سيُكتب - تحدد ما إذا كانت… (+14 more)

### Community 72 - "KatibAgent"
Cohesion: 0.16
Nodes (15): get_katib_agent(), KatibAgent, KatibExecutionError, KatibSecurityError, Any, Exception, توثيق العملية في سجل التدقيق (Append-Only JSONL)., توثيق عمليات الأرشفة والحذف في سجل مخصص دون تخزين أسرار أو نسخ بيانات شخصية غير… (+7 more)

### Community 73 - "payroll_service.py"
Cohesion: 0.18
Nodes (13): PayrollEnvironmentGuardError, PayrollWriteGatewayError, Exception, بوابة الكتابة الآمنة لمسيرات الرواتب (Odoo Payroll Write Gateway - Phase 19)…, خطأ يطلق عند محاولة الكتابة في قاعدة بيانات غير مصرح بها., خطأ يطلق عند فشل تنفيذ عملية الكتابة في Odoo., PayslipDryRunResult, PayslipExecutionResult (+5 more)

### Community 74 - "build_graph"
Cohesion: 0.09
Nodes (23): build_graph(), Graph assembly. read : ingest_user_message -> classify_intent -> seraj_think…, بناء رسم سراج الرئيسي Args: checkpointer: MemorySaver أو SQLite للحفظ المستمر…, Entry point for `langgraph dev` (the dev server supplies its own checkpointer)., مستودع Odoo مزيّف للاختبارات ================================ يحاكي Odoo XML-…, graph(), mock_odoo_connection(), fixture (+15 more)

### Community 75 - "MemoryEnabledAgent"
Cohesion: 0.12
Nodes (13): create_memory_aware_agent(), MemoryEnabledAgent, Any, الحصول على حلقات مشابهة من الذاكرة, الحصول على الأنماط الناجحة السابقة, التعلم من حلقة سابقة يمكن للوكيل تخصيص هذه الدالة حسب احتياجاته, تحويل وكيل موجود ليصبح memory-aware Args: agent_instance: نسخة من أي وكيل…, Mixin class لإضافة قدرات الذاكرة لأي وكيل الاستخدام: ```python class… (+5 more)

### Community 76 - "LearningSystem"
Cohesion: 0.15
Nodes (12): LearningSystem, Any, الحصول على أداء النظام ككل, اكتشاف الأنماط المتكررة Args: agent: الوكيل intent: النية min_occurrences: الحد…, نظام التعلم الذكي يوفر: 1. تتبع النجاحات والفشل 2. اكتشاف الأنماط 3. تحسين…, اقتراح أفضل استراتيجية بناءً على التعلم Args: agent: الوكيل intent: النية…, نقل المعرفة من وكيل إلى آخر Args: from_agent: الوكيل المصدر to_agent: الوكيل…, Args: memory_manager: مدير الذاكرة (+4 more)

### Community 77 - "OdooLeaveWriteGateway"
Cohesion: 0.18
Nodes (13): LeaveEnvironmentGuardError, LeaveWriteGatewayError, OdooLeaveWriteGateway, Any, RuntimeError, إنشاء رصيد إجازة (allocation) لموظف عند الحاجة وفق الضوابط النظامية., بوابة الكتابة الآمنة والمحصورة لموديل الإجازات (hr.leave) ومخصصات الإجازات…, إنشاء طلب إجازة في hr.leave مع التحقق المسبق من الحقول الإلزامية. (+5 more)

### Community 78 - "DeploymentVerifier"
Cohesion: 0.16
Nodes (11): DeploymentVerifier, main(), Check agent instantiation, Check configuration files, Check storage directories, Check external connections, Verifies deployment health, Print verification summary (+3 more)

### Community 79 - "run_telegram_bot_polling"
Cohesion: 0.13
Nodes (21): execute_applicant_via_service(), execute_letter_via_service(), get_allowed_users(), get_letter_service_for_bot(), get_main_menu_keyboard(), get_recruitment_service_for_bot(), handle_letter_wizard_step(), handle_recruitment_wizard_step() (+13 more)

### Community 80 - "LaborLawKnowledgeBase"
Cohesion: 0.13
Nodes (11): استشارة قانونية ونظامية من وكيل التدقيق «مدقق» استناداً إلى نصوص نظام العمل…, LaborLawArticle, LaborLawKnowledgeBase, Any, المعرفة النظامية لنظام العمل السعودي واللوائح التنفيذية (Saudi Labor Law…, قراءة وفهرسة المواد من saudi_labor_law.md., استخراج أي تعريفات وتفاصيل إضافية من page.html., إرجاع نص المادة برقمها. (+3 more)

### Community 81 - "ExpenseService"
Cohesion: 0.14
Nodes (14): ExpenseService, الخدمة الشاملة لإدارة ومطابقة مصروفات الموظفين وانتدابات العمل في Odoo., المرحلة الثانية من التحقق المزدوج: التأكد من رمز الموافقة والكلمة الإلزامية…, تحويل ملف HTML إلى PDF عبر Playwright., توليد سند صرف ومطالبة نفقات رسمية., mock_gateway(), mock_repo(), fixture (+6 more)

### Community 82 - "ingest_user_message"
Cohesion: 0.13
Nodes (17): ingest_user_message(), Returns (args, company_id). - explicit company_id in the tool call becomes the…, Appends the new user query to history and resets per-run scratch fields., resolve_company_args(), wants_all_companies(), Company-context tests for the LangGraph skeleton (no network, no Odoo)., test_company_suffix(), test_explicit_company_becomes_sticky() (+9 more)

### Community 83 - "ObservableAgent"
Cohesion: 0.10
Nodes (11): ObservableAgent, Trigger monitoring checks, Mixin for adding observability to agents. Usage: class MyAgent(ObservableAgent,…, Start tracking a phase, Record full run metrics, Test observability integration, Test ObservableAgent mixin, Test @observable_run decorator (+3 more)

### Community 84 - "test_memory_advanced.py"
Cohesion: 0.14
Nodes (19): اختبارات متقدمة لنظام الذاكرة ============================== يختبر: 1. Vector…, اختبار 3: البحث الدلالي في المعرفة, اختبار 4: تحليل الأداء, اختبار 5: اكتشاف الأنماط, اختبار 6: اقتراح الاستراتيجيات, اختبار 7: نقل المعرفة بين الوكلاء, اختبار 1: تهيئة Vector Store, اختبار 8: الأداء الإجمالي للنظام (+11 more)

### Community 85 - "WebServiceTests"
Cohesion: 0.15
Nodes (4): create_sample_xlsx(), patch, Path, WebServiceTests

### Community 86 - "verify_write_auth"
Cohesion: 0.12
Nodes (20): apply_attendance_endpoint(), AttendanceActionPayload, AttendanceApplyPayload, AttendanceDryRunPayload, check_in_endpoint(), check_out_endpoint(), dry_run_attendance_endpoint(), get_attendance_service_instance() (+12 more)

### Community 87 - "OdooExpenseWriteGateway"
Cohesion: 0.21
Nodes (11): ExpenseEnvironmentGuardError, ExpenseWriteGatewayError, OdooExpenseWriteGateway, Any, Exception, بوابة الكتابة الآمنة لمصروفات الموظفين والانتدابات (Odoo Expense Write Gateway…, إنشاء مطالبة مصروف جديد في Odoo (hr.expense)., قراءة مصروف محدد للتحقق بعد الكتابة (Readback Verification). (+3 more)

### Community 88 - "._load_ws"
Cohesion: 0.17
Nodes (3): TestEmployeesSheet, TestInstructionsSheet, TestReferenceSheet

### Community 89 - "PayrollService"
Cohesion: 0.13
Nodes (6): PayrollService, Any, خدمة إدارة مسيرات الرواتب وحساب الأجور ونظام حماية الأجور WPS., اعتماد وإنشاء قسيمة الراتب في Odoo بموجب مبدأ التحقق المزدوج Four-Eyes., توليد ملف نظام حماية الأجور (WPS SIF Format) المعتمد للبنك المركزي ومنصة مدد., TestPayrollService

### Community 90 - "Any"
Cohesion: 0.16
Nodes (11): execute_warning_via_service(), _finish_warning_dry_run(), get_templates_menu_keyboard(), get_warning_service_for_bot(), handle_excel_document(), Any, Path, Sends an Excel or PDF document directly to Telegram chat. (+3 more)

### Community 91 - "test_memory_system.py"
Cohesion: 0.16
Nodes (17): اختبارات نظام الذاكرة ==================== يختبر: 1. Working Memory 2. Episodic…, اختبار 3: Semantic Memory - المعرفة الدلالية, اختبار 4: Profile Memory - التفضيلات, اختبار 5: دمج الذاكرة مع الوكلاء, اختبار 1: Working Memory - ذاكرة قصيرة المدى, اختبار 6: استرجاع الأنماط الناجحة, اختبار 7: إحصائيات الذاكرة, تشغيل جميع الاختبارات (+9 more)

### Community 92 - "TestSevenQuestionsRealGraph"
Cohesion: 0.11
Nodes (10): اختبار الأسئلة السبعة على Graph الحقيقي…, السؤال 1: "ما الشركات المتاحة لي؟" التحقق: - يرجع 4 شركات - company_id فارغة…, السؤال 2: "كم عدد الموظفين في شركة النخبة الذكية؟" التحقق: - يرجع 13 موظف -…, السؤال 3: "كم عدد الموظفين؟" (بعد تحديد النخبة) التحقق: - يرجع 13 موظف…, السؤال 4: "والشركة الثانية؟" التحقق: - يرجع سؤال تأكيد (وليس رقماً) - لا يتجاوز…, السؤال 5: "كم عدد الموظفين في كل الشركات؟" التحقق: - يرجع 14 موظف - company_id…, السؤال 6: "كم عدد الموظفين في النظام ككل؟" التحقق: - يرجع 14 موظف, السؤال 7: "وزّع الموظفين على الشركات" التحقق: - مجموع التوزيع = 14 (1 + 13 + 0… (+2 more)

### Community 93 - "TestSerajToolCalling"
Cohesion: 0.19
Nodes (3): object, patch, TestSerajToolCalling

### Community 94 - "ContractService"
Cohesion: 0.13
Nodes (5): ContractService, Any, خدمة إدارة وتدقيق عقود العمل وهيكلة الأجور في Odoo., اعتماد وتحديث عقد عمل الموظف في Odoo بموجب مبدأ التحقق المزدوج Four-Eyes…, TestContractService

### Community 95 - "OdooPayrollWriteGateway"
Cohesion: 0.20
Nodes (7): OdooPayrollWriteGateway, Any, إنشاء قسيمة راتب (hr.payslip) جديدة لموظف في Odoo., تحديث حالة قسيمة الراتب (draft, verify, done, cancel)., قراءة سجل قسيمة الراتب من Odoo لأغراض التحقق المستقل (Readback Verification)., بوابة كتابة معزولة ومخصصة لمسيرات الرواتب في Odoo (hr.payslip)., TestOdooPayrollWriteGateway

### Community 97 - "test_web_service_phase24_25.py"
Cohesion: 0.17
Nodes (11): DocumentExpiryItem, ExpenseApplyResult, ExpenseDryRunResult, خدمة إدارة وتدقيق مصروفات الموظفين والانتدابات (Employee Expenses & Travel…, client(), fixture, اختبارات واجهات برمجة التطبيقات للمرحلتين 24 و 25 (Web Service API Endpoints…, test_expense_apply_endpoint_requires_confirmation() (+3 more)

### Community 98 - "run.cjs"
Cohesion: 0.23
Nodes (15): buildRunnerArgv(), { execFileSync }, formatAnalyzeCommand(), formatBunxCommand(), formatDocumentationDlxCommand(), formatPnpmAllowBuildArgs(), formatPnpmDlxCommand(), fs (+7 more)

### Community 99 - "calculate_gosi_contributions"
Cohesion: 0.12
Nodes (14): calculate_gosi_contributions(), GOSIContributionResult, تفصيل اشتراكات التأمينات الاجتماعية (GOSI), حساب اشتراكات التأمينات الاجتماعية (GOSI) للسعودي وغير السعودي بدقة تامة. الأجر…, اختبار حساب GOSI لموظف سعودي براتب قياسي (أساسي 10,000 + سكن 2,500 = 12,500), اختبار حساب GOSI لموظف غير سعودي: 2% أخطار مهنية لصاحب العمل، و0% استقطاع على…, اختبار تطبيق السقف الأعلى للاشتراك (45,000 ريال) لموظف سعودي براتب مرتفع, اختبار تطبيق الحد الأدنى للاشتراك (1,500 ريال) (+6 more)

### Community 100 - "TestSijilPageAndExport"
Cohesion: 0.12
Nodes (8): Test PDF export endpoint generates a valid A4 Arabic PDF report., Test recent operations list endpoint enforces authentication and serves data…, Test GET /sijil loads the complete Arabic RTL interface with no Odoo write…, Test searching by plan_id returns a direct match or candidate., Test searching with Arabic-Indic numerals like '١٤' normalizes to '14'., Test searching for an unknown ID returns not_found with Arabic message., Test operation detail endpoint returns complete audit contract., TestSijilPageAndExport

### Community 101 - "TestAgentEventsServiceP3"
Cohesion: 0.14
Nodes (8): P3: البحث في القرص عند عدم وجود العملية في الذاكرة, P3: تحسين تحميل آخر 200 سطر بدلاً من 100, اختبار تحسينات P3 في agent_events_service, إعداد نسخة جديدة من الخدمة لكل اختبار, P3: إزالة company_id الافتراضية المثبتة, P3: operation_id موجود في حالة الرسم, P3: العقد تستدعي emit_event مع operation_id, TestAgentEventsServiceP3

### Community 102 - "LLMProvider"
Cohesion: 0.20
Nodes (8): LLMProvider, Any, LLM Provider Manager - إدارة مزودي النماذج اللغوية…, Rule-based fallback عندما لا يتوفر LLM, تعيين مزود LLM يدوياً, الحصول على النموذج الافتراضي, استدعاء Ollama محلياً عبر Chat Completions API, set_llm_provider()

### Community 103 - "TestPerformanceBenchmarks"
Cohesion: 0.17
Nodes (9): benchmark, slow, Benchmark memory efficiency, Test caching effectiveness, Test performance under sustained load, Performance benchmark tests, Benchmark agent execution latency, Benchmark request throughput (+1 more)

### Community 104 - "classify_intent"
Cohesion: 0.17
Nodes (9): classify_intent(), تصنيف نية المستخدم بناءً على قواعد حتمية يرجع: {"intent":…, أسئلة العد حسب الشركة (السؤال 2، 7), سؤال قائمة الشركات (السؤال 1), عبارات آمنة لا تُصنّف كتعديل, كشف نوايا التعديل بوضوح, السؤال 1: ما الشركات المتاحة لي؟, أسئلة العد الإجمالي (السؤال 5 و 6) (+1 more)

### Community 105 - "TestAgentTracer"
Cohesion: 0.12
Nodes (7): Test trace context manager, Test span context manager, Test trace is saved to disk, Test trace summary generation, Test creating a trace, Test nested span hierarchy, TestAgentTracer

### Community 106 - "test_graph_memory.py"
Cohesion: 0.15
Nodes (15): Drop assistant tool_calls without full tool replies, and orphan tool messages., Last `limit` clean messages, always starting at a user message., sanitize_history(), trim_history(), append_messages(), Any, Shared state for the Seraj graph., Reducer: nodes return ONLY new messages; they are appended to the thread… (+7 more)

### Community 107 - "get_active_odoo_config"
Cohesion: 0.16
Nodes (14): get_active_odoo_config(), Any, Centralized Odoo Configuration and Multi-Database Connection Manager. Allows…, Saves verified credentials to config/odoo_connection.json and updates current…, Returns the currently active Odoo credentials (from json or env)., Tests XML-RPC authentication against a specified Odoo instance., save_active_odoo_config(), test_odoo_connection() (+6 more)

### Community 108 - "execute_writer_endpoint"
Cohesion: 0.18
Nodes (14): format_writer_notification(), is_telegram_configured(), Any, Telegram notification service for Odoo HR Agents. Sends alerts and execution…, Sends a text message to Telegram via Bot API sendMessage. Returns a dict with…, Formats an execution result from writer.py into an informative Arabic Telegram…, send_telegram_notification(), approve_and_execute_endpoint() (+6 more)

### Community 109 - "TestMonitoringDashboard"
Cohesion: 0.13
Nodes (7): Test MonitoringDashboard, Test creating alert rules, Test alert cooldown period, Test custom alert handlers, Test dashboard data generation, Test report generation, TestMonitoringDashboard

### Community 110 - "test_generate_employee_template.py"
Cohesion: 0.13
Nodes (6): _generate_to_bytes(), Tests for generate_employee_template.py (fully mocked, no network, no real…, Generate a template and return its raw bytes., TestMain, TestOutputFile, TestSheetNames

### Community 111 - "FailureCodesTests"
Cohesion: 0.22
Nodes (3): Returns the single allowed final_status for a given failure_code. Returns None…, status_for_failure_code(), FailureCodesTests

### Community 112 - "MemorySaver"
Cohesion: 0.16
Nodes (9): MemorySaver, اختبار التكامل مع LangGraph, test_integration_with_langgraph(), fixture, بناء Graph مع checkpointer, إعداد Thread واحد للمحادثة, اختبار استمرارية سياق الشركة عبر الأسئلة, اختبار تدفق سياق الشركة: 1. فارغة بعد السؤال 1 (قائمة الشركات) 2. = 15 بعد… (+1 more)

### Community 113 - "01_test_create_employee.py"
Cohesion: 0.27
Nodes (13): attempt_minimal_create(), check_env(), cleanup_test_record(), connect(), inspect_employee_fields(), inspect_module_exclusions(), log_event(), main() (+5 more)

### Community 114 - "test_p3_persistent_checkpointer.py"
Cohesion: 0.29
Nodes (8): cleanup_old_checkpoints(), get_checkpointer_for_environment(), get_persistent_checkpointer(), P3: Persistent Checkpointer Implementation…, إنشاء checkpointer دائم باستخدام ملف JSON P3 requirement: company_id و messages…, حصول على checkpointer مناسب للبيئة الحالية Returns: -…, تنظيف checkpoints قديمة للحفاظ على حجم الملفات Args: days_to_keep: عدد الأيام…, اختبار P3: Persistent Checkpointer =================================== يختبر أن…

### Community 115 - "test_integration.py"
Cohesion: 0.23
Nodes (12): get_llm_provider(), الحصول على مزود LLM المُكوّن, main(), اختبار 4: LangGraph Integration, اختبار 5: Full Pipeline (إن أمكن), اختبار 1: Tool Registry, اختبار 2: LLM Provider, test_fahas_agent() (+4 more)

### Community 116 - "test_graph_routing.py"
Cohesion: 0.27
Nodes (9): route_after_think(), Routing tests for the LangGraph skeleton (no network, no Odoo)., test_approval_requires_matching_plan_id_route(), test_error_short_circuits(), test_goes_to_tools_when_requested(), test_policy_failure_blocks_approval(), test_stops_when_no_tool_calls(), test_turn_cap_enforced() (+1 more)

### Community 117 - ".get_operation_detail"
Cohesion: 0.22
Nodes (5): Path, تجميع واستخراج ملف التوثيق الشامل للعملية المحددة: - ملخص العملية - الخط الزمني…, توليد تقرير توثيق رسمي بصيغة PDF: - حجم A4 عمودي - ورق وخلفية بيضاء (#ffffff)…, توليد ملف PDF عالي الجودة بحجم A4 وخلفية بيضاء: 1. تجربة Playwright إن كان…, حجب الرموز السرية ومفاتيح الـ API وكلمات المرور والبيانات الشخصية غير الضرورية.

### Community 118 - "apply_appraisal_endpoint"
Cohesion: 0.22
Nodes (9): apply_appraisal_endpoint(), AppraisalApplyPayload, AppraisalDryRunPayload, dry_run_appraisal_endpoint(), get_appraisal_service_instance(), get_appraisal_summary_endpoint(), Returns employee appraisal history and probation period status (Article 53)., Validates appraisal scores and weights, and checks Article 53 and Saudi… (+1 more)

### Community 119 - "04_test_safe_fields_extended.py"
Cohesion: 0.45
Nodes (12): check_env(), cleanup(), compare_payload(), connect(), create_employee(), duplicate_check(), fail(), log_event() (+4 more)

### Community 120 - "ConversationSession"
Cohesion: 0.15
Nodes (6): ConversationSession, Any, فحص هل هناك سؤال توضيحي معلق (مثل اختيار الشركة) ومعالجة رد المستخدم عليه.…, إضافة رسالة إلى تاريخ الجلسة مع الحفاظ على سقف أقصى 12 رسالة لمنع تضخم السياق., فحص صلاحية العملية المعلقة: استهلاك مسبق، انتهاء مهلة TTL، أو اختلاف الهوية., وسم العملية بأنها استهلكت لمنع إعادة التنفيذ.

### Community 121 - "log_telegram_audit"
Cohesion: 0.17
Nodes (13): execute_attendance_action_via_service(), execute_via_backend_api(), get_attendance_service_for_bot(), handle_approval_callback(), handle_attendance_wizard_step(), handle_voice_message(), log_telegram_audit(), Logs all Telegram interactions for compliance and audit trail (Section 5.2). (+5 more)

### Community 122 - "Any"
Cohesion: 0.09
Nodes (29): UploadFile, ApplicantApplyPayload, ApplicantDryRunPayload, apply_applicant_endpoint(), dry_run_applicant_endpoint(), get_applicant_detail_endpoint(), get_appraisal_ratings_guide_endpoint(), get_common_gr_transactions_endpoint() (+21 more)

### Community 123 - "create_deletion_plan"
Cohesion: 0.23
Nodes (5): create_deletion_plan(), DeletionPlan, Any, إنشاء خطة دقيقة للأرشفة أو الاسترجاع أو الحذف لسجل مفرد بعد التحقق من السياسة., TestDeletionPolicyUnit

### Community 125 - "UserProfile"
Cohesion: 0.21
Nodes (6): الحصول على ملف المستخدم, تحديث الملف بناءً على حلقة تفاعل, Any, ملف المستخدم (Profile Memory) تفضيلات وسلوك المستخدم أو الشركة, تحويل إلى dictionary للتخزين, UserProfile

### Community 126 - "AgentMetrics"
Cohesion: 0.17
Nodes (7): AgentMetrics, Metrics for a single agent, Calculate success rate, Calculate average duration, Calculate average confidence, Calculate average tokens per run, Get average duration for a specific phase

### Community 127 - "output_validator_check.py"
Cohesion: 0.26
Nodes (6): normalize_email_exact(), Any, safe_many2one_dict(), safe_many2one_id(), ValidationResult, Validator

### Community 128 - "SijilAuditService"
Cohesion: 0.28
Nodes (5): خدمة وكيل الرقابة والتدقيق غير القابل للتلاعب: «سجل» (Sijil Audit & Governance…, الخدمة المركزية لوكيل الرقابة والتدقيق (سجل)., SijilAuditService, Unit tests for SijilAuditService (Phase 21: Sijil Audit PDF Generator)., Unit and integration tests for Sijil Agent Web Interface, Unified Search,…

### Community 129 - "FakeOdooRepository"
Cohesion: 0.30
Nodes (6): FakeOdooRepository, Any, مستودع مزيّف يحتوي على بيانات ثابتة للاختبار, تصفية الأقسام بناءً على domain, محاكاة execute_kw (الواجهة الرئيسية), تصفية الموظفين بناءً على domain

### Community 131 - "mudaqqiq_agent.py"
Cohesion: 0.25
Nodes (10): ComplianceDecision, ComplianceStatus, ComplianceViolation, get_mudaqqiq_agent(), Enum, str, وكيل التدقيق والامتثال الذكي: «مدقق» (Mudaqqiq Agentic Compliance Agent)…, الحصول على كائن وكيل مدقق المفرد (Singleton) (+2 more)

### Community 132 - "apply_ui_redesign.py"
Cohesion: 0.27
Nodes (8): build_pipeline_block(), kind_of(), main(), patch_html(), Path, إعادة تصميم واجهات المشروع (dashboard / sijil / user_guide) بالبايثون…, مخطط خط السير: 5 عقد، موصّلات مستقيمة، منطقتان (قراءة فقط / كتابة محكومة).…, _stagger_css()

### Community 133 - "detect_employee_nationality"
Cohesion: 0.18
Nodes (7): جلب وتلخيص عقد العمل وهيكل الراتب والتأمينات للموظف., فحص وتدقيق هيكل عقد العمل تجريبياً (Dry-Run) والتحقق من المادة 37 والمادة 53…, detect_employee_nationality(), Any, التحقق الحتمي من جنسية الموظف (سعودي أم غير سعودي): 1. استخدام الإدخال الصريح…, جلب وتلخيص آخر قسيمة راتب أو بيانات مسير الراتب للموظف., تدقيق وفحص مسير وقسيمة الراتب تجريبياً (Dry-Run) والتحقق من سقف الاستقطاعات…

### Community 134 - "TestMetricsCollector"
Cohesion: 0.18
Nodes (4): Test MetricsCollector, Test system-wide metrics, Test health status calculation, TestMetricsCollector

### Community 136 - "apply_contract_endpoint"
Cohesion: 0.18
Nodes (11): apply_contract_endpoint(), ContractApplyPayload, ContractDryRunPayload, dry_run_contract_endpoint(), get_contract_service_instance(), get_contract_types_endpoint(), get_employee_contract_endpoint(), Returns available contract types from hr.contract.type. (+3 more)

### Community 137 - "apply_disciplinary_endpoint"
Cohesion: 0.18
Nodes (11): apply_disciplinary_endpoint(), DisciplinaryApplyPayload, DisciplinaryDryRunPayload, dry_run_disciplinary_endpoint(), get_disciplinary_categories_endpoint(), get_disciplinary_service_instance(), get_disciplinary_summary_endpoint(), Returns available violation/penalty categories from discipline.category. (+3 more)

### Community 138 - "apply_eos_endpoint"
Cohesion: 0.18
Nodes (11): apply_eos_endpoint(), dry_run_eos_endpoint(), EOSApplyPayload, EOSDryRunPayload, get_eos_reasons_endpoint(), get_eos_service_instance(), get_eos_summary_endpoint(), Returns available end of service reasons from hr.end.service.benefit.type. (+3 more)

### Community 139 - "apply_leave_endpoint"
Cohesion: 0.18
Nodes (11): apply_leave_endpoint(), dry_run_leave_endpoint(), get_employee_leave_summary_endpoint(), get_leave_service_instance(), get_leave_types_endpoint(), LeaveApplyPayload, LeaveDryRunPayload, Returns all active leave types defined in Odoo. (+3 more)

### Community 140 - ".plan"
Cohesion: 0.20
Nodes (5): المرحلة 2: التخطيط - بناء خطة تنفيذ مع rollback strategy P5: لم يعد كاتب يتخذ…, بناء خطوات التنفيذ التفصيلية, تحديد استراتيجية Rollback المناسبة, تحديد الضمانات الأمنية المطلوبة, تحديد المخاطر المحتملة

### Community 141 - "TestLaborLawMudaqqiqRouting"
Cohesion: 0.20
Nodes (3): is_labor_law_query(), يحدد ما إذا كان السؤال موجهاً لنظام العمل واللوائح العمالية., TestLaborLawMudaqqiqRouting

### Community 142 - "TestSecurityValidation"
Cohesion: 0.24
Nodes (6): security, Security-focused tests, Test SQL injection prevention, Test unauthorized access prevention, Test data validation and sanitization, TestSecurityValidation

### Community 143 - "test_comparison_old_vs_new.py"
Cohesion: 0.23
Nodes (6): ComparisonRunner, main(), Any, مقارنة فعلية: Service القديم vs Agent الجديد يشغل نفس الأسئلة على النظامين…, تشغيل المقارنة الكاملة, طباعة التقرير النهائي

### Community 144 - "MockWriteGateway"
Cohesion: 0.27
Nodes (5): MockWriteGateway, Any, بوابة كتابة وهمية للاختبار, اختبار مرحلة الإدراك لعملية إنشاء, test_katib_perceive_create_operation()

### Community 145 - "TestPersistentCheckpointer"
Cohesion: 0.25
Nodes (5): اختبار File-based checkpointer للحفظ المستمر, إنشاء file-based checkpointer بنجاح, اختيار checkpointer المناسب للبيئة, بناء graph مع persistent checkpointer, TestPersistentCheckpointer

### Community 147 - "ComplianceRule"
Cohesion: 0.22
Nodes (4): ComplianceRule, تحميل قاعدة قواعد الامتثال, تحديد طريقة الفحص للقاعدة, البحث عن قاعدة بالمعرف

### Community 148 - "install.ps1"
Cohesion: 0.56
Nodes (8): Find-InnoSetupInstall(), Invoke-Download(), Invoke-Install(), Invoke-Uninstall(), Test-Signature(), Update-SessionPath(), Write-Status(), Write-Step()

### Community 149 - "determine_disciplinary_occurrence"
Cohesion: 0.22
Nodes (7): جلب وتلخيص سجل الجزاءات والمخالفات للموظف واحتساب رصيد الخصومات المستهلك في…, الفحص التجريبي الاستباقي لطلب الجزاء التأديبي والتحقق الحتمي من: 1. المادة 70…, determine_disciplinary_occurrence(), date, تحديد درجة تكرار المخالفة (Occurrence: first, second, third, fourth) وفق المادة…, المادة 71: سقوط أثر تكرار المخالفة إذا انقضى عليها 180 يوماً, test_article_71_disciplinary_repetition_reset()

### Community 150 - "OdooReadonlyRepositoryError"
Cohesion: 0.25
Nodes (4): OdooReadonlyRepositoryError, Exception, call(), dump()

### Community 151 - "Any"
Cohesion: 0.31
Nodes (5): Any, توليد الإحصائيات والمؤشرات القيادية للحوكمة والرقابة., صياغة مستند HTML تنفيذي فاخر مبني على مواصفات: - DESIGN.md (Resend Black Velvet…, قراءة ودمج كافة سجلات التدقيق من ملفات logs., توليد التقرير الرقابي العام بصيغة PDF.

### Community 152 - "TestStressTesting"
Cohesion: 0.25
Nodes (6): stress, slow, Stress tests for high-volume scenarios, Test processing large Excel file (10,000 rows), Test multiple agents running concurrently, TestStressTesting

### Community 154 - "apply_gr_endpoint"
Cohesion: 0.22
Nodes (9): apply_gr_endpoint(), dry_run_gr_endpoint(), get_gr_service_instance(), get_gr_summary_endpoint(), GRApplyPayload, GRDryRunPayload, Returns employee GR transaction history and nationality status., Validates GR transaction against Article 40 and Saudi vs Non-Saudi nationality… (+1 more)

### Community 156 - "._get_delete_gateway"
Cohesion: 0.25
Nodes (6): KatibExecutionError, KatibSecurityError, Exception, الحصول على بوابة الحذف المعزولة, خطأ أمني عند محاولة تنفيذ عملية غير مصرح بها, خطأ تنفيذي أثناء الكتابة في Odoo

### Community 157 - ".scan_expiries"
Cohesion: 0.32
Nodes (5): Any, date, تحويل القيمة إلى كائن تاريخ صالح., تحديد مستوى الخطورة وفق عدد الأيام المتبقية., فحص شامل لكافة وثائق الموظفين وحساب الاستحقاقات ومستويات الخطورة.

### Community 158 - "ProductionMonitor"
Cohesion: 0.36
Nodes (4): main(), ProductionMonitor, Production monitoring and alerting, Start monitoring loop

### Community 159 - "handle_wizard_employee_selection"
Cohesion: 0.36
Nodes (8): execute_leave_via_service(), get_leave_service_for_bot(), handle_leave_wizard_step(), handle_wizard_employee_selection(), prompt_leave_type_selection(), Dispatches interactive employee selection from disambiguation button click., show_employee_leaves_balance(), show_leaves_menu()

### Community 160 - "handle_musleh_heal_callback"
Cohesion: 0.25
Nodes (8): handle_musleh_heal_callback(), is_autofix_enabled(), Returns True if auto-repair mode is enabled for this chat, False for review-…, Displays Musleh self-healing engine details, consultation workflow, and auto-…, Displays current Autofix mode (ON/OFF) with interactive toggle buttons., Executes Musleh consultation and healing on broken rows in dry-run report., show_autofix_status_card(), show_musleh_info_card()

### Community 161 - "MockDeleteGateway"
Cohesion: 0.25
Nodes (6): MockDeleteGateway, اختبار مرحلة الإدراك لعملية خطرة (حذف), اختبار مرحلة التخطيط لعملية خطرة, بوابة حذف وهمية للاختبار, test_katib_perceive_dangerous_operation(), test_katib_plan_dangerous_operation()

### Community 165 - ".dry_run_expense"
Cohesion: 0.29
Nodes (4): Any, قائمة تصنيفات المصروفات المدعومة., تحديد معرف الشركة والعملة (الافتراضي: 15 للشركة، والريال السعودي SAR)., المرحلة الأولى من التحقق المزدوج: فحص بيانات المصروف واحتساب الضريبة وإصدار…

### Community 166 - "langgraph.json"
Cohesion: 0.33
Nodes (5): dependencies, env, graphs, seraj, .

### Community 167 - "test_chat_api.py"
Cohesion: 0.33
Nodes (5): اختبار سريع لـ API الشات يتحقق من أن الـ endpoints تعمل بشكل صحيح, اختبار أساسي للشات API, اختبار تكامل الشات بدون LangGraph حقيقي, test_chat_api(), test_chat_integration_mock()

### Community 168 - "TestEnableAgenticFahas"
Cohesion: 0.33
Nodes (4): اختبار تتبع company_id عبر الأسئلة في Thread واحد التدفق: 1. None (قائمة…, اختبار ENABLE_AGENTIC_FAHAS على الأسئلة السبعة ملاحظة: بما أن…, اختبار الأسئلة السبعة على fahas_tools (المسار الحالي الوحيد) التحقق: - Q1:…, TestEnableAgenticFahas

### Community 170 - "WorkingMemory"
Cohesion: 0.40
Nodes (3): الحصول على ذاكرة العمل للجلسة, ذاكرة العمل (Working Memory) ذاكرة قصيرة المدى للجلسة الحالية فقط, WorkingMemory

### Community 171 - ".__init__"
Cohesion: 0.40
Nodes (3): Path, Args: storage_dir: مجلد التخزين (افتراضي: ./memory_store) use_vector_db: هل…, تهيئة Vector DB (Chroma)

### Community 172 - "02_test_lookup_department_job.py"
Cohesion: 0.80
Nodes (4): connect(), exact_lookup(), log_event(), main()

### Community 173 - "get_gr_service_for_bot"
Cohesion: 0.40
Nodes (5): execute_gr_transaction_via_service(), get_gr_service_for_bot(), handle_gr_wizard_step(), show_employee_gr_card(), show_gr_menu()

## Knowledge Gaps
- **11 isolated node(s):** `ComplianceViolation`, `MatchResult`, `TemplateType`, `env`, `seraj` (+6 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OdooReadonlyRepository` connect `OdooReadonlyRepository` to `WriterTests`, `test_saudi_labor_law_rules.py`, `web_service.py`, `Request`, `AttendanceService`, `apply_contract_endpoint`, `OdooRecruitmentWriteGateway`, `LetterService`, `OdooAppraisalWriteGateway`, `environment_policy.py`, `apply_disciplinary_endpoint`, `apply_eos_endpoint`, `eos_service.py`, `OdooGRWriteGateway`, `WarningService`, `FahasAgent`, `OdooLoanWriteGateway`, `OdooDisciplinaryWriteGateway`, `AnalyticsService`, `OdooReadonlyRepositoryError`, `dry_run_report.py`, `apply_gr_endpoint`, `TestSeraj20Scenarios`, `LeaveService`, `handle_wizard_employee_selection`, `handle_musleh_heal_callback`, `.get_repository`, `generate_all_hr_templates.py`, `telegram_bot.py`, `TelegramBotClient`, `get_gr_service_for_bot`, `OdooContractWriteGateway`, `parser.py`, `apply_leave_endpoint`, `DocumentExpiryService`, `generate_employee_template.py`, `excel_template_validator.py`, `writer.py`, `payroll_service.py`, `run_telegram_bot_polling`, `ExpenseService`, `verify_write_auth`, `PayrollService`, `Any`, `ContractService`, `test_web_service_phase24_25.py`, `get_active_odoo_config`, `execute_writer_endpoint`, `apply_appraisal_endpoint`, `log_telegram_audit`, `Any`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Why does `get_events_service()` connect `get_events_service` to `SijilAuditService`, `AgentEventsService`, `SerajState`, `TestAgentEventsServiceP3`, `agentic_nodes.py`, `web_service.py`, `Request`, `Any`, `TestLaborLawMudaqqiqRouting`, `.search_operations`, `ingest_user_message`, `FahasAgent`, `.get_operation_detail`, `dry_run_report.py`, `SerajLLMService`, `katib_service.py`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `MuwaffaqAgent` connect `MuwaffaqAgent` to `BaseAgent`, `agentic_nodes.py`, `AgentGoal`, `DeploymentVerifier`, `TestEndToEndWorkflows`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `OdooReadonlyRepository` (e.g. with `AnalyticsService` and `AppraisalService`) actually correct?**
  _`OdooReadonlyRepository` has 31 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ComplianceViolation`, `MatchResult`, `TemplateType` to the rest of the system?**
  _11 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `OdooReadonlyRepository` be split into smaller, more focused modules?**
  _Cohesion score 0.06471306471306472 - nodes in this community are weakly interconnected._
- **Should `WriterTests` be split into smaller, more focused modules?**
  _Cohesion score 0.06554621848739496 - nodes in this community are weakly interconnected._