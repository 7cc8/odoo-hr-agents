// =========================================================================
    // 1. AUTHENTICATION & SECURE API FETCH
    // =========================================================================
    function getApiToken() {
      try {
        return (
          sessionStorage.getItem("odoo_hr_api_token") ||
          localStorage.getItem("odoo_hr_api_token") ||
          ""
        );
      } catch (_) {
        return "";
      }
    }

    function setApiToken(token) {
      try {
        if (token) {
          sessionStorage.setItem("odoo_hr_api_token", token);
          localStorage.setItem("odoo_hr_api_token", token);
        } else {
          sessionStorage.removeItem("odoo_hr_api_token");
          localStorage.removeItem("odoo_hr_api_token");
        }
      } catch (_) { }
    }

    function syncSettingsTokenInput() {
      const input = document.getElementById("settingsOperatorTokenInput");
      const status = document.getElementById("settingsOperatorTokenStatus");
      const token = getApiToken();
      if (input) input.value = token;
      if (status) {
        if (token) {
          status.innerHTML =
            '<span style="color: var(--color-phosphor-green); font-weight: 600; display: inline-flex; align-items: center; gap: 5px;"><svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg> الرمز مفعّل في هذه الجلسة</span>';
        } else {
          status.innerHTML =
            '<span style="color: var(--color-smoke);">لم يتم تعيين رمز للمشغّل بعد.</span>';
        }
      }
    }

    function saveOperatorTokenFromSettings() {
      const input = document.getElementById("settingsOperatorTokenInput");
      const val = (input?.value || "").trim();
      if (!val) {
        alert("يرجى إدخال الرمز أولاً.");
        return;
      }
      setApiToken(val);
      syncSettingsTokenInput();
      alert("تم حفظ وتفعيل رمز المصادقة بنجاح.");
      if (
        document
          .getElementById("view-sijil")
          ?.classList.contains("is-visible")
      ) {
        loadRecentAuditMetrics();
      }
    }

    function clearOperatorTokenFromSettings() {
      setApiToken("");
      syncSettingsTokenInput();
      alert("تم مسح رمز المصادقة من الجلسة.");
    }

    function promptForApiToken() {
      const current = getApiToken();
      const entered = window.prompt(
        "أدخل رمز جلسة المشغّل المعتمد (X-API-Key):",
        current,
      );
      if (entered !== null) {
        const val = entered.trim();
        if (val) {
          setApiToken(val);
          alert("تم حفظ وتفعيل رمز المصادقة بنجاح.");
        } else {
          setApiToken("");
          alert("تم مسح رمز المصادقة.");
        }
        if (
          document
            .getElementById("view-sijil")
            ?.classList.contains("is-visible")
        ) {
          loadRecentAuditMetrics();
        }
        syncSettingsTokenInput();
      }
    }

    async function apiFetch(url, options = {}) {
      if (!options.signal)
        options.signal = AbortSignal.timeout(
          options.method === "POST" ? 120000 : 30000,
        );
      options.headers = options.headers || {};
      const storedToken = getApiToken();
      if (storedToken) {
        if (options.headers instanceof Headers)
          options.headers.set("X-API-Key", storedToken);
        else if (!options.headers["X-API-Key"])
          options.headers["X-API-Key"] = storedToken;
      }
      let response = await fetch(url, options);
      // When a mutation or user-initiated action receives 401 Unauthorized, prompt the user seamlessly
      if (
        response.status === 401 &&
        options.method &&
        options.method !== "GET" &&
        !options.silentAuth
      ) {
        const entered = window.prompt(
          "يتطلب هذا الإجراء مصادقة المشغّل (X-API-Key).\nيرجى إدخال رمز جلسة العمليات المعتمد:",
          getApiToken() || "",
        );
        if (entered !== null) {
          const val = entered.trim();
          if (val) {
            setApiToken(val);
            syncSettingsTokenInput();
            options.headers = options.headers || {};
            if (options.headers instanceof Headers)
              options.headers.set("X-API-Key", val);
            else options.headers["X-API-Key"] = val;
            response = await fetch(url, options);
          }
        }
      }
      return response;
    }


    function debounce(func, wait = 250) {
      let timeout;
      return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
      };
    }

    // =========================================================================
    // 2. GLOBAL STATE
    // =========================================================================
    let currentOperationId = null;
    let lastEventSequence = 0;
    let pollingInterval = null;
    let selectedCompanyId = null;
    let activeAgentsData = [];
    let streamConsecutiveErrors = 0;
    let currentChatId = `web_${crypto.randomUUID()}`;
    let currentOperationStatus = null;
    let chatRequestInFlight = false;
    let resumeRequestId = 0;

    // Sijil Server-Side Pagination State
    let sijilPage = 1;
    let sijilLimit = 10;
    let sijilTotal = 0;

    // Operations Server-Side Pagination State
    let opsPage = 1;
    let opsLimit = 10;
    let opsTotal = 0;

    const AGENTS_META = {
      seraj: {
        name_ar: "سراج",
        color: "var(--agent-seraj)",
        role: "المنسق العام",
        popover:
          "سراج: المنسق العام ومحاور المشغّل • انقر لإدراج أمره في الشات",
        icon: "sparkles",
        img: "/images/seraj.webp",
      },
      fahas: {
        name_ar: "فاحص",
        color: "var(--agent-fahas)",
        role: "استعلام Odoo",
        popover: "فاحص: قراءة واستعلام بيانات Odoo 19.0e الحية بأمان تام",
        icon: "search",
        img: "/images/svg/fahas.svg",
      },
      modaqeq: {
        name_ar: "مدقق",
        color: "var(--agent-modaqeq)",
        role: "نظام العمل",
        popover:
          "مدقق: مطابقة مواد ولوائح نظام العمل السعودي (40 مادة مفهرسة)",
        icon: "shield-check",
        img: "/images/svg/modaqeq.svg",
      },
      mowafaq: {
        name_ar: "موفق",
        color: "var(--agent-mowafaq)",
        role: "المطابقة الدلالية",
        popover: "موفق: مطابقة المسميات والأقسام بين ملفات Excel وسجلات Odoo",
        icon: "git-merge",
        img: "/images/svg/mowafaq.svg",
      },
      musleh: {
        name_ar: "مصلح",
        color: "var(--agent-musleh)",
        role: "التشخيص الذاتي",
        popover: "مصلح: كشف الأخطاء وإصلاح الشذوذ واقتراح الحلول التصحيحية",
        icon: "wrench",
        img: "/images/svg/musleh.svg",
      },
      hares: {
        name_ar: "حارس",
        color: "var(--agent-hares)",
        role: "حوكمة الأمان PII",
        popover:
          "حارس: حجب البيانات الحساسة وتفعيل بوابة موافقة المشغّل البشري",
        icon: "lock",
        img: "/images/svg/hares.svg",
      },
      katib: {
        name_ar: "كاتب",
        color: "var(--agent-katib)",
        role: "قيد Odoo",
        popover:
          "كاتب: تنفيذ عمليات الإنشاء والتعديل في Odoo بعد اعتماد حارس",
        icon: "pencil",
        img: "/images/svg/katib.svg",
      },
      sijil: {
        name_ar: "سجل",
        color: "var(--agent-sijil)",
        role: "الختم الرقمي",
        popover: "سجل: التوثيق الرقابي والختم اللاتراجعي بتشفير SHA-256",
        icon: "book-open",
        img: "/images/svg/sijil.svg",
      },
    };

    const STATUS_MAP_AR = {
      idle: "جاهز",
      ready: "جاهز",
      analyzing_request: "يحلل الطلب",
      querying_odoo: "يستعلم من Odoo",
      inspecting_data: "يفحص البيانات",
      matching_references: "يقارن المراجع",
      verifying_permissions: "يتحقق من الصلاحيات",
      waiting_user_clarification: "ينتظر توضيح المستخدم",
      waiting_clarification: "ينتظر توضيح المستخدم",
      waiting_approval: "ينتظر الاعتماد",
      executing_write: "ينفذ التعديل",
      verifying_result: "يتحقق من النتيجة",
      documenting_audit: "يوثق العملية",
      completed: "اكتمل",
      failed: "تعذر التنفيذ",
      cancelled: "أُلغيت",
      inconclusive: "النتيجة غير محسومة",
      disconnected: "انقطع اتصال متابعة الأحداث",
    };

    // =========================================================================
    // 3. INITIALIZATION
    // =========================================================================
    document.addEventListener("DOMContentLoaded", () => {
      loadHrReferenceOptions();
      renderAgentsStrip();
      loadSystemStatus();
      syncSettingsTokenInput();
      loadLlmSettings();
      populateTemplateCompanySelector();
      loadAgentsOverview();
      loadRecentAuditMetrics();
      loadOperationsList();
      checkSavedMotionPreference();
      initTimelineResize();
      try { if (localStorage.getItem('workflow_expanded_pref') === '1') toggleChatFocusWidth(); } catch (_) { }
      const urlParams = new URLSearchParams(window.location.search);
      const savedOperation = urlParams.get("operation");
      if (savedOperation) resumeOperationInCockpit(savedOperation);

      // Deep Linking & Path Resolution for Unified Single Page Application
      const path = (window.location.pathname || "").toLowerCase();
      let requestedView = urlParams.get("view");
      if (!requestedView) {
        if (path === "/sijil") requestedView = "sijil";
        else if (path === "/chat") requestedView = "chat";
        else if (path === "/diagram/companies") requestedView = "census";
      }

      if (requestedView) {
        const viewMap = {
          chat: "view-cockpit",
          copilot: "view-cockpit",
          cockpit: "view-cockpit",
          upload: "view-upload",
          excel: "view-upload",
          operations: "view-operations",
          agents: "view-agents",
          sijil: "view-sijil",
          audit: "view-sijil",
          settings: "view-settings",
          census: "view-sijil",
          diagram: "view-sijil",
        };
        const targetViewId =
          viewMap[requestedView.toLowerCase()] ||
          (document.getElementById(requestedView) ? requestedView : null);
        if (targetViewId) {
          switchView(targetViewId, false);
          if (
            requestedView.toLowerCase() === "census" ||
            requestedView.toLowerCase() === "diagram"
          ) {
            setTimeout(() => {
              const sec = document.getElementById("censusDiagramCard");
              if (sec) sec.scrollIntoView({ behavior: "smooth" });
            }, 350);
          }
        }
      }

      const ta = document.getElementById("chatInput");
      if (ta) ta.addEventListener("input", () => autoResizeTextarea(ta));
      setInterval(() => {
        if (!document.hidden) {
          loadAgentsOverview();
          loadSystemStatus();
          if (
            document
              .getElementById("view-operations")
              .classList.contains("is-visible")
          )
            loadOperationsList();
          if (
            document
              .getElementById("view-sijil")
              .classList.contains("is-visible")
          )
            loadRecentAuditMetrics();
        }
      }, 15000);
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          closeDetailsDrawer();
          closeOpDetailModal();
        }
      });
    });

    // =========================================================================
    // SYSTEM LOCKDOWN & VIEW MANAGEMENT (قفل كل شيء والسماح فقط بالإعدادات)
    // =========================================================================
    let isSystemLocked = false;

    function applySystemLockdown(lock) {
      isSystemLocked = lock;
      document.body.classList.toggle("is-locked-down", lock);

      const tabsToLock = [
        "view-cockpit",
        "view-operations",
        "view-agents",
        "view-sijil",
      ];
      tabsToLock.forEach((viewId) => {
        const btn = document.querySelector(
          `.nav-tab-btn[data-view="${viewId}"]`,
        );
        if (btn) {
          if (lock) {
            btn.classList.add("is-locked");
            btn.setAttribute("disabled", "true");
            btn.title =
              "مقفل: مسموح فقط بصفحة الإعدادات لربط قاعدة بيانات Odoo";
          } else {
            btn.classList.remove("is-locked");
            btn.removeAttribute("disabled");
            btn.title = "";
          }
        }
      });

      const settingsBtn = document.querySelector(
        `.nav-tab-btn[data-view="view-settings"]`,
      );
      if (settingsBtn) {
        if (lock) {
          settingsBtn.classList.add("lockdown-highlight");
        } else {
          settingsBtn.classList.remove("lockdown-highlight");
        }
      }

      const odooDisconnectedBanner = document.getElementById(
        "odooDisconnectedBanner",
      );
      const settingsAlert = document.getElementById(
        "settingsLockdownAlertBox",
      );
      if (odooDisconnectedBanner) {
        odooDisconnectedBanner.style.display = lock ? "flex" : "none";
      }
      if (settingsAlert) {
        settingsAlert.style.display = lock ? "block" : "none";
      }

      // Disable / enable Cockpit inputs
      const chatInput = document.getElementById("chatInput");
      const sendChatBtn = document.getElementById("chatSendBtn");
      const excelFileInput = document.getElementById("chatExcelFileInput");
      if (chatInput) {
        chatInput.disabled = lock;
        if (lock) {
          chatInput.placeholder =
            "النظام مقفل بالكامل — مسموح فقط بصفحة الإعدادات لربط قاعدة بيانات Odoo";
        } else {
          chatInput.placeholder =
            "تحدث مع سراج أو اسأل عن الموظفين أو اطلب تنفيذ مهام الموارد البشرية…";
        }
      }
      if (sendChatBtn) sendChatBtn.disabled = lock;
      if (excelFileInput) excelFileInput.disabled = lock;

      // Header status pill
      const odooBadge = document.getElementById("odooConnectionBadge");
      const odooDot = document.getElementById("odooStatusDot");
      const odooText = document.getElementById("odooStatusText");
      if (odooBadge && odooText) {
        if (lock) {
          odooBadge.className = "stream-status-pill is-disconnected";
          if (odooDot) odooDot.style.background = "var(--color-coral)";
          odooText.textContent = "مقفل: Odoo غير متصل";
        }
      }

      // If locked, automatically force view to settings!
      if (lock) {
        const currentVisible = document.querySelector(
          ".view-section.is-visible",
        );
        if (!currentVisible || currentVisible.id !== "view-settings") {
          switchView("view-settings");
        }
      }
    }

    // View Switching
    function switchView(viewId, updateUrl = true) {
      if (isSystemLocked && viewId !== "view-settings") {
        console.warn(
          "النظام في وضع القفل: مسموح فقط بصفحة الإعدادات لربط قاعدة بيانات Odoo.",
        );
        return;
      }

      document
        .querySelectorAll(".view-section")
        .forEach((el) => el.classList.remove("is-visible"));
      document.querySelectorAll(".nav-tab-btn").forEach((el) => {
        el.classList.remove("is-active");
        el.setAttribute("aria-selected", "false");
      });

      const target = document.getElementById(viewId);
      if (target) target.classList.add("is-visible");

      const btn = document.querySelector(
        `.nav-tab-btn[data-view="${viewId}"]`,
      );
      if (btn) {
        btn.classList.add("is-active");
        btn.setAttribute("aria-selected", "true");
      }

      if (viewId === "view-upload") {
        populateDedicatedCompanySelector();
        initDedicatedUploadEvents();
      }
      if (viewId === "view-operations") loadOperationsList();
      if (viewId === "view-agents") loadAgentsOverview();
      if (viewId === "view-sijil") loadRecentAuditMetrics();
      if (viewId === "view-settings") {
        syncSettingsTokenInput();
        loadSystemStatus();
        loadLlmSettings();
      }

      if (updateUrl) {
        try {
          const viewSlug = viewId.replace(/^view-/, "");
          const url = new URL(window.location.href);
          url.searchParams.set("view", viewSlug);
          window.history.replaceState({ view: viewSlug }, "", url.toString());
        } catch (_) { }
      }
    }

    function handleTabNavigation(event) {
      if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key))
        return;
      const tabs = [
        ...document.querySelectorAll(".nav-tab-btn:not(.is-locked)"),
      ];
      const currentIndex = tabs.indexOf(document.activeElement);
      if (currentIndex < 0) return;
      event.preventDefault();
      const nextIndex =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? tabs.length - 1
            : (currentIndex +
              (event.key === "ArrowRight" ? 1 : -1) +
              tabs.length) %
            tabs.length;
      const nextTab = tabs[nextIndex];
      nextTab.focus();
      switchView(nextTab.dataset.view);
    }

    // =========================================================================
    // 4. SYSTEM STATUS & CONNECTION (LIVE SOURCE)
    // =========================================================================
    let settingsFormInitialized = false;

    async function loadSystemStatus(forceFill = false) {
      try {
        const res = await apiFetch("/api/status");
        const data = await res.json();
        if (data.status === "online" || data.status === "success") {
          const connEl = document.getElementById("connectionScopePillText");
          if (connEl) {
            connEl.textContent =
              data.connection_name ||
              (data.odoo?.database
                ? `odoo (${data.odoo.database})`
                : "default");
          }

          const compSelect = document.getElementById("companySelector");
          if (compSelect && data.companies && data.companies.length > 0) {
            if (
              !selectedCompanyId ||
              !data.companies.some((c) => c.id === selectedCompanyId)
            ) {
              selectedCompanyId =
                data.default_company_id || data.companies[0].id;
            }
            compSelect.innerHTML = data.companies
              .map(
                (c) => `
              <option value="${c.id}" ${c.id === selectedCompanyId ? "selected" : ""}>
                ${escapeHtml(c.name)}
              </option>
            `,
              )
              .join("");
            compSelect.disabled = false;
          } else if (compSelect) {
            compSelect.innerHTML =
              '<option value="">لا توجد شركات متاحة</option>';
            compSelect.disabled = true;
          }

          // Populate inputs ONLY on first load (if empty) or if explicitly requested via forceFill
          if (!settingsFormInitialized || forceFill) {
            ["Url", "Db", "Username"].forEach((key, i) => {
              const el = document.getElementById(`settings${key}`);
              if (el && (!el.value || forceFill)) {
                el.value =
                  [data.odoo?.url, data.odoo?.database, data.odoo?.username][
                  i
                  ] || "";
              }
            });
            settingsFormInitialized = true;
          }

          document.getElementById("settingsConnectionMessage").textContent =
            data.connection_error ||
            (data.odoo?.connected
              ? `متصل بقاعدة ${data.odoo?.database || ""} · ${data.companies?.length || 0} شركة متاحة`
              : "غير متصل بخادم Odoo");
          document.getElementById("settingsSelectedCompany").textContent =
            `الشركة المختارة: ${compSelect?.selectedOptions[0]?.textContent.trim() || "غير محددة"}`;

          // Enforce lockdown or restore full access based on Odoo connection
          const isConnected = !!(data.odoo && data.odoo.connected);
          applySystemLockdown(!isConnected);

          const odooBadge = document.getElementById("odooConnectionBadge");
          const odooDot = document.getElementById("odooStatusDot");
          const odooText = document.getElementById("odooStatusText");
          const odooErrDetail = document.getElementById(
            "odooBannerErrorDetail",
          );

          if (!isConnected) {
            if (odooErrDetail) {
              odooErrDetail.textContent = data.connection_error
                ? `الخطأ الفني: ${data.connection_error}`
                : `(تعذر الاتصال بقاعدة Odoo: ${data.odoo?.url || "غير محدد"})`;
            }
          } else {
            if (odooBadge && odooText) {
              odooBadge.className = "stream-status-pill";
              if (odooDot)
                odooDot.style.background = "var(--color-phosphor-green)";
              odooText.textContent = `Odoo: متصل (${data.odoo.database || ""})`;
            }
          }

          const settingsBox = document.getElementById(
            "systemSettingsInfoBox",
          );
          if (settingsBox) {
            settingsBox.innerHTML = `
              • وضع التشغيل: <span class="badge badge-success">${escapeHtml(data.mode || "test_safe (آمن ومحمي)")}</span><br>
              • خادم Odoo: <span class="mono">${escapeHtml(data.odoo?.url || "غير محدد")} (${escapeHtml(data.odoo?.database || "غير محددة")})</span><br>
              • مفتاح التعديل في أودو: <span class="mono">Write Gateway Guard Active</span><br>
              • الفحص الرقابي المستقل: <span class="badge badge-success">تحقق راجع نشط («فاحص»)</span><br>
              • دفتر السجلات اللاتراجعي: <span class="badge badge-success">Append-Only Active (سجل)</span>
            `;
          }
        }
      } catch (err) {
        console.warn("System status error:", err);
      }
    }

    function handleCompanyChange(newCompanyId) {
      if (
        currentOperationId &&
        !["completed", "failed", "cancelled", "inconclusive"].includes(
          currentOperationStatus,
        )
      ) {
        const confirmChange = confirm(
          "تنبيه حوكمة:\nتوجد عملية جارية حالياً برقم (" +
          currentOperationId +
          ").\n" +
          "تغيير الشركة الآن لن يغير نطاق العملية الجارية بصمت.\n" +
          "هل ترغب بتغيير نطاق العمليات الجديدة فقط؟",
        );
        if (!confirmChange) {
          document.getElementById("companySelector").value =
            selectedCompanyId;
          return;
        }
      }
      selectedCompanyId = parseInt(newCompanyId, 10);
      document.getElementById("settingsSelectedCompany").textContent =
        `الشركة المختارة: ${document.getElementById("companySelector").selectedOptions[0]?.textContent.trim()}`;
      // New requests use the selected scope; never transplant an existing plan.
      currentOperationId = null;
      currentOperationStatus = null;
      currentChatId = `web_${crypto.randomUUID()}`;
    }

    // =========================================================================
    // TEMPLATE GENERATION FUNCTIONS
    // =========================================================================
    async function generateTemplate() {
      const companySelector = document.getElementById(
        "companySelect",
      );
      const statusEl = document.getElementById("templateGenerationStatus");
      const downloadSection = document.getElementById(
        "templateDownloadSection",
      );
      const generateBtn = document.getElementById("generateTemplateBtn");

      const companyId = companySelector.value
        ? parseInt(companySelector.value, 10)
        : null;

      try {
        generateBtn.disabled = true;
        statusEl.textContent = "جاري إنشاء القالب...";
        statusEl.style.color = "var(--color-amber)";
        downloadSection.style.display = "none";

        const res = await apiFetch("/api/template/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ company_id: companyId }),
        });

        const data = await res.json();

        if (data.status === "success") {
          statusEl.textContent = data.message_ar || "تم إنشاء القالب بنجاح";
          statusEl.style.color = "var(--color-phosphor-green)";

          // Show download section
          const downloadLink = document.getElementById(
            "templateDownloadLink",
          );
          const fileNameEl = document.getElementById("templateFileName");

          downloadLink.href = data.download_url;
          fileNameEl.textContent = `الشركة: ${data.company_name}`;
          downloadSection.style.display = "block";
        } else {
          throw new Error(data.detail || "فشل في إنشاء القالب");
        }
      } catch (err) {
        statusEl.textContent = `خطأ: ${err.message}`;
        statusEl.style.color = "var(--color-coral)";
      } finally {
        generateBtn.disabled = false;
      }
    }

    // Populate template company selector when system status loads
    async function populateTemplateCompanySelector() {
      const selector = document.getElementById("companySelect");
      if (selector && selector.children && selector.children.length > 1) {
        return; // Already populated without redundant fetch
      }
      try {
        const res = await apiFetch("/api/status");
        const data = await res.json();

        if (data.companies && data.companies.length > 0) {
          const selector = document.getElementById("companySelect");
          if (selector) {
            const options =
              '<option value="">الشركة الافتراضية</option>' +
              data.companies
                .map(
                  (c) =>
                    `<option value="${c.id}">${escapeHtml(c.name)}</option>`,
                )
                .join("");
            selector.innerHTML = options;
          }
        }
      } catch (err) {
        console.warn("Failed to populate template company selector:", err);
      }
    }

    // =========================================================================
    // REJECTION DETAILS & CONDITIONAL EXECUTION FUNCTIONS
    // =========================================================================
    function displayRejectionDetails(rejectedDetails, containerElement) {
      if (!rejectedDetails || rejectedDetails.length === 0) {
        return;
      }

      const sectionHtml = `
        <div class="rejection-details-section">
          <div class="rejection-details-header">
            <div class="rejection-details-title">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-coral)" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <span>تفاصيل الصفوف المرفوضة (${rejectedDetails.length})</span>
            </div>
            <span class="badge badge-error">${rejectedDetails.length} خطأ</span>
          </div>

          <table class="rejection-details-table">
            <thead>
              <tr>
                <th>رقم الصف</th>
                <th>اسم الموظف</th>
                <th>الحقل</th>
                <th>القيمة</th>
                <th>السبب</th>
                <th>الاقتراح</th>
                <th>إصلاح تلقائي</th>
              </tr>
            </thead>
            <tbody>
              ${rejectedDetails
          .map(
            (detail) => `
                <tr>
                  <td><span class="rejection-row-number">${detail.row_number}</span></td>
                  <td>${escapeHtml(detail.name)}</td>
                  <td><span class="rejection-field">${escapeHtml(detail.field)}</span></td>
                  <td class="mono">${escapeHtml(detail.value)}</td>
                  <td>${escapeHtml(detail.reason_ar)}</td>
                  <td><span class="rejection-suggestion">${escapeHtml(detail.suggestion)}</span></td>
                  <td>${detail.can_auto_fix ? '<span class="rejection-autofix-badge">ممكن</span>' : "—"}</td>
                </tr>
              `,
          )
          .join("")}
            </tbody>
          </table>
        </div>
      `;

      if (containerElement) {
        containerElement.innerHTML = sectionHtml;
      } else {
        // Insert into chat messages
        const chatContainer = document.getElementById("chatMessages");
        if (chatContainer) {
          const tempDiv = document.createElement("div");
          tempDiv.innerHTML = sectionHtml;
          chatContainer.appendChild(tempDiv.firstChild);
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
      }
    }

    function displayConditionalExecutionCard(
      operationId,
      acceptedCount,
      rejectedCount,
    ) {
      const cardHtml = `
        <div class="conditional-execution-card" id="conditionalExecutionCard">
          <div class="conditional-execution-header">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-iris-violet)" stroke-width="2">
              <path d="M10 2v7.527a2 2 0 0 1-.211.896L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45l-5.069-10.127A2 2 0 0 1 14 9.527V2"></path>
              <path d="M8.5 2h7"></path>
              <path d="M7 16h10"></path>
            </svg>
            <div class="conditional-execution-title">اختر الإجراء المطلوب</div>
          </div>

          <div class="conditional-execution-message">
            تم فحص الملف:<br>
            • <strong style="color: var(--color-phosphor-green);">${acceptedCount} صف مقبول</strong> - جاهز للتنفيذ<br>
            • <strong style="color: var(--color-coral);">${rejectedCount} صف مرفوض</strong> - يحتوي على أخطاء<br><br>
            يرجى اختيار أحد الخيارات التالية:
          </div>

          <div class="conditional-execution-buttons">
            <button class="conditional-btn conditional-btn-execute" 
                    onclick="handleConditionalChoice('execute', '${operationId}')"
                    id="btnConditionalExecute">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <span>تنفيذ المقبول فقط (${acceptedCount} صف)</span>
            </button>

            <button class="conditional-btn conditional-btn-fix" 
                    onclick="handleConditionalChoice('fix', '${operationId}')"
                    id="btnConditionalFix">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
              </svg>
              <span>إرسال إلى مصلح للإصلاح</span>
            </button>

            <button class="conditional-btn conditional-btn-cancel" 
                    onclick="handleConditionalChoice('cancel', '${operationId}')"
                    id="btnConditionalCancel">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
              <span>إلغاء العملية</span>
            </button>
          </div>
        </div>
      `;

      // Insert into chat messages
      const chatContainer = document.getElementById("chatMessages");
      if (chatContainer) {
        const tempDiv = document.createElement("div");
        tempDiv.innerHTML = cardHtml;
        chatContainer.appendChild(tempDiv.firstChild);
        chatContainer.scrollTop = chatContainer.scrollHeight;
      }
    }

    async function handleConditionalChoice(choice, operationId) {
      const buttons = [
        document.getElementById("btnConditionalExecute"),
        document.getElementById("btnConditionalFix"),
        document.getElementById("btnConditionalCancel"),
      ];

      // Disable all buttons
      buttons.forEach((btn) => {
        if (btn) btn.disabled = true;
      });

      const choiceLabels = {
        execute: "تنفيذ الصفوف المقبولة فقط",
        fix: "إرسال إلى مصلح للإصلاح التلقائي",
        cancel: "إلغاء العملية",
      };

      appendUserMessage(choiceLabels[choice] || choice);
      showTypingIndicator();

      try {
        const res = await apiFetch("/api/approve-conditional", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            operation_id: operationId,
            chat_id: currentChatId,
            user_choice: choice,
            approved_by: "Dashboard User",
          }),
        });

        const data = await res.json();

        if (data.status === "success") {
          appendSerajMessage(data.message_ar + "\n\n" + data.next_step);

          // Remove conditional execution card
          const card = document.getElementById("conditionalExecutionCard");
          if (card) card.remove();

          // If execute or fix, continue monitoring
          if (choice === "execute" || choice === "fix") {
            startLiveEventPolling(operationId);
          }
        } else {
          throw new Error(data.detail || "فشل في تسجيل الاختيار");
        }
      } catch (err) {
        appendSerajMessage(`خطأ: ${err.message}`, null, null, null, null);
        // Re-enable buttons on error
        buttons.forEach((btn) => {
          if (btn) btn.disabled = false;
        });
      } finally {
        hideTypingIndicator();
      }
    }

    function normalizeInputUrl(inputEl) {
      if (!inputEl) return "";
      let u = (inputEl.value || "").trim();
      if (!u) return "";
      if (!u.startsWith("http://") && !u.startsWith("https://"))
        u = "https://" + u;
      try {
        const parsed = new URL(u);
        inputEl.value = parsed.origin;
        return parsed.origin;
      } catch (err) {
        const clean = u
          .replace(/\/odoo.*$/, "")
          .replace(/\/web.*$/, "")
          .replace(/\/+$/, "");
        inputEl.value = clean;
        return clean;
      }
    }

    async function saveConnectionSettings(e) {
      e.preventDefault();
      const button = document.getElementById("saveConnectionBtn");
      const message = document.getElementById("settingsConnectionMessage");
      const urlInput = document.getElementById("settingsUrl");
      const cleanUrl = normalizeInputUrl(urlInput);

      if (
        !confirm(
          "سيغيّر حفظ الاتصال قاعدة البيانات المستخدمة للطلبات الجديدة في المنظومة. هل تريد المتابعة؟",
        )
      )
        return;
      button.disabled = true;
      message.textContent = "جاري التحقق من الاتصال…";
      try {
        const res = await apiFetch("/api/settings/connection", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: cleanUrl || urlInput.value.trim(),
            db: document.getElementById("settingsDb").value.trim(),
            username: document
              .getElementById("settingsUsername")
              .value.trim(),
            api_key: document.getElementById("settingsApiKey").value || null,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "تعذر حفظ الاتصال");
        document.getElementById("settingsApiKey").value = "";
        currentOperationId = null;
        currentChatId = `web_${crypto.randomUUID()}`;
        await loadSystemStatus();
        message.innerHTML =
          '<span style="color: var(--color-phosphor-green); font-weight: bold; font-size: 14px;">تم حفظ الاتصال والتحقق منه بنجاح تم إلغاء قفل كافة أقسام المنظومة.</span>';
      } catch (err) {
        message.innerHTML = `<div style="background: rgba(var(--bad-rgb),0.15); border: 1px solid var(--color-coral); border-radius: 8px; padding: 12px; margin-top: 10px; color: var(--bad); font-size: 13px; line-height: 1.6;">
          <div style="font-weight: 700; display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
            <span>خطأ في التحقق من الاتصال:</span>
          </div>
          <div>${escapeHtml(err.message)}</div>
          <div style="margin-top: 8px; font-size: 12px; color: var(--color-silver-mist); border-top: 1px solid rgba(var(--ink-rgb),0.08); padding-top: 6px;">
            <strong>تأكد من الآتي:</strong><br>
            1. <strong>اسم المستخدم:</strong> اكتب <strong>البريد الإلكتروني</strong> المسجل به في Odoo (وليس الاسم الظاهر).<br>
            2. <strong>مفتاح API:</strong> تم إنشاؤه من (Odoo 🡰 صورة الملف الشخصي 🡰 تفضيلي / أمان الحساب 🡰 مفاتيح API).
          </div>
        </div>`;
      } finally {
        button.disabled = false;
      }
    }

    async function clearAndResetConnection() {
      if (
        !confirm(
          "هل أنت متأكد من رغبتك في حذف بيانات الاتصال القديمة ومسح الحقول للبدء من جديد؟",
        )
      )
        return;
      const message = document.getElementById("settingsConnectionMessage");

      // 1. Immediately wipe the form input values in the browser
      document.getElementById("settingsUrl").value = "";
      document.getElementById("settingsDb").value = "";
      document.getElementById("settingsUsername").value = "";
      document.getElementById("settingsApiKey").value = "";
      settingsFormInitialized = true; // prevent automatic re-fill

      message.innerHTML =
        '<span style="color: var(--color-silver-mist);">جاري مسح بيانات الاتصال القديمة من النظام…</span>';

      try {
        const res = await apiFetch("/api/settings/connection/reset", {
          method: "POST",
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "تعذر مسح الاتصال");
        message.innerHTML =
          '<span style="color: var(--color-phosphor-green); font-weight: bold; font-size: 14px;">تم مسح وحذف بيانات الاتصال القديمة بالكامل. أصبحت الحقول فارغة ويمكنك الآن إدخال بيانات القاعدة الجديدة.</span>';
        await loadSystemStatus();
      } catch (err) {
        message.textContent = "تم تفريغ الحقول محلياً: " + err.message;
      }
    }

    // =========================================================================
    // 4.1 LLM ENGINE & PROVIDERS CONFIGURATION
    // =========================================================================
    const CLOUD_PRESETS = {
      gemini: {
        name: "Google Gemini (رسمي)",
        base_url: "https://generativelanguage.googleapis.com/v1beta/openai",
        model: "gemini-3.5-flash",
        models: [
          { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash (مستقر وفائق السرعة - موصى به)", badge: "موصى به" },
          { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash Lite (أقصى سرعة استجابة)", badge: "فائق السرعة" },
          { id: "gemini-3.6-flash", label: "Gemini 3.6 Flash (أحدث إصدار)", badge: "حديث" },
          { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash (معاينة تجريبية)", badge: "معاينة" },
          { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro (الاستدلال المتقدم)", badge: "الرائد" },
        ],
        placeholder_key: "AIzaSy...",
        key_url: "https://aistudio.google.com/app/apikey",
      },
      claude: {
        name: "Anthropic Claude",
        base_url: "https://openrouter.ai/api/v1",
        model: "anthropic/claude-3.7-sonnet",
        models: [
          { id: "anthropic/claude-3.7-sonnet", label: "Claude 3.7 Sonnet (استدلال هجين وبرمجة)", badge: "الأقوى" },
          { id: "anthropic/claude-3.5-sonnet", label: "Claude 3.5 Sonnet (أداء فائق الدقة)", badge: "دقيق جداً" },
          { id: "anthropic/claude-3.5-haiku", label: "Claude 3.5 Haiku (خفيف وفوري)", badge: "سريع" },
        ],
        placeholder_key: "sk-ant-... أو sk-or-...",
        key_url: "https://console.anthropic.com/settings/keys",
      },
      openrouter: {
        name: "OpenRouter (شامل - كافة النماذج)",
        base_url: "https://openrouter.ai/api/v1",
        model: "anthropic/claude-3.7-sonnet",
        models: [
          { id: "anthropic/claude-3.7-sonnet", label: "Claude 3.7 Sonnet", badge: "الأقوى" },
          { id: "google/gemini-2.5-pro", label: "Gemini 2.5 Pro", badge: "استدلال متقدم" },
          { id: "openai/gpt-4o", label: "GPT-4o", badge: "رائد" },
          { id: "deepseek/deepseek-r1", label: "DeepSeek R1", badge: "تفكير عميق" },
          { id: "meta-llama/llama-3.3-70b-instruct", label: "Llama 3.3 70B", badge: "مفتوح المصدر" },
        ],
        placeholder_key: "sk-or-v1-...",
        key_url: "https://openrouter.ai/keys",
      },
      openai: {
        name: "OpenAI (رسمي)",
        base_url: "https://api.openai.com/v1",
        model: "gpt-4o",
        models: [
          { id: "gpt-4o", label: "GPT-4o (النموذج الرائد الشامل)", badge: "الأقوى" },
          { id: "o3-mini", label: "o3-mini (استدلال وتفكير عميق)", badge: "تفكير عميق" },
          { id: "o1", label: "o1 (تفكير منطقي معقد)", badge: "استدلال" },
          { id: "gpt-4.5-preview", label: "GPT-4.5 Preview", badge: "أحدث" },
          { id: "gpt-4o-mini", label: "GPT-4o-mini (سريع واقتصادي)", badge: "اقتصادي" },
        ],
        placeholder_key: "sk-proj-...",
        key_url: "https://platform.openai.com/api-keys",
      },
      deepseek: {
        name: "DeepSeek (رسمي)",
        base_url: "https://api.deepseek.com/v1",
        model: "deepseek-reasoner",
        models: [
          { id: "deepseek-reasoner", label: "DeepSeek R1 (نموذج التفكير والاستدلال الأقوى)", badge: "الأقوى" },
          { id: "deepseek-chat", label: "DeepSeek V3 (متعدد الأغراض فائق السرعة)", badge: "سريع" },
        ],
        placeholder_key: "sk-...",
        key_url: "https://platform.deepseek.com/api_keys",
      },
      groq: {
        name: "Groq (سرعة فائقة)",
        base_url: "https://api.groq.com/openai/v1",
        model: "llama-3.3-70b-versatile",
        models: [
          { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B Versatile", badge: "الأقوى" },
          { id: "deepseek-r1-distill-llama-70b", label: "DeepSeek R1 Distill 70B", badge: "تفكير واستدلال" },
          { id: "qwen-2.5-32b", label: "Qwen 2.5 32B", badge: "لغات متعددة" },
        ],
        placeholder_key: "gsk_...",
        key_url: "https://console.groq.com/keys",
      },
      mistral: {
        name: "Mistral AI (رسمي)",
        base_url: "https://api.mistral.ai/v1",
        model: "mistral-large-latest",
        models: [
          { id: "mistral-large-latest", label: "Mistral Large (الأقوى)", badge: "الأقوى" },
          { id: "codestral-latest", label: "Codestral (برمجة وأتمتة)", badge: "أتمتة" },
        ],
        placeholder_key: "...",
        key_url: "https://console.mistral.ai/api-keys",
      },
      together: {
        name: "Together AI (نماذج مفتوحة)",
        base_url: "https://api.together.xyz/v1",
        model: "deepseek-ai/DeepSeek-R1",
        models: [
          { id: "deepseek-ai/DeepSeek-R1", label: "DeepSeek R1", badge: "الأقوى" },
          { id: "meta-llama/Llama-3.3-70B-Instruct-Turbo", label: "Llama 3.3 70B", badge: "سريع" },
        ],
        placeholder_key: "...",
        key_url: "https://api.together.ai/settings/api-keys",
      },
      perplexity: {
        name: "Perplexity AI",
        base_url: "https://api.perplexity.ai",
        model: "sonar-pro",
        models: [
          { id: "sonar-pro", label: "Sonar Pro (بحث واستدلال)", badge: "الأقوى" },
          { id: "sonar-reasoning", label: "Sonar Reasoning", badge: "تفكير" },
        ],
        placeholder_key: "pplx-...",
        key_url: "https://www.perplexity.ai/settings/api",
      },
      custom: {
        name: "مشغل مخصص / أي طرف ثالث",
        base_url: "",
        model: "",
        models: [],
        placeholder_key: "Bearer token أو API key أو اتركه فارغاً للبروكسي المحلي",
        key_url: null,
      },
    };

    let llmSavedHasCloudKey = false;

    function renderModelSuggestions(preset) {
      const datalist = document.getElementById("cloudModelDatalist");
      const pillsContainer = document.getElementById("cloudModelQuickPills");
      if (datalist) {
        datalist.innerHTML = (preset.models || [])
          .map((m) => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.label)}</option>`)
          .join("");
      }
      if (pillsContainer) {
        if (!preset.models || preset.models.length === 0) {
          pillsContainer.innerHTML = "";
          return;
        }
        pillsContainer.innerHTML = preset.models
          .map(
            (m) => `
              <button
                type="button"
                class="chip-btn"
                onclick="selectQuickModel('${escapeHtml(m.id)}')"
                style="font-size: 11.5px; padding: 4px 10px; border-radius: 999px; background: var(--paper-3); border: 1px solid var(--rule); color: var(--ink-2); cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 120ms ease;"
                title="انقر لاعتماد هذا النموذج مباشرة"
              >
                <span>${escapeHtml(m.id)}</span>
                <span style="font-size: 10px; padding: 1px 5px; border-radius: 999px; background: color-mix(in oklab, var(--accent) 15%, transparent); color: var(--accent); font-weight: 600;">${escapeHtml(m.badge || "مقترح")}</span>
              </button>
            `,
          )
          .join("");
      }
    }

    function selectQuickModel(modelId) {
      const modelInput = document.getElementById("cloudModelInput");
      if (modelInput) {
        modelInput.value = modelId;
        modelInput.focus();
      }
    }

    function handleCloudPresetChange(presetKey) {
      const preset = CLOUD_PRESETS[presetKey] || CLOUD_PRESETS.custom;
      if (!preset) return;
      const baseUrlInput = document.getElementById("cloudBaseUrlInput");
      const modelInput = document.getElementById("cloudModelInput");
      const keyInput = document.getElementById("cloudApiKeyInput");
      const helpLink = document.getElementById("getApiKeyHelpLink");

      if (helpLink) {
        if (preset.key_url) {
          helpLink.style.display = "inline";
          helpLink.href = preset.key_url;
          helpLink.textContent = `احصل على مفتاح ${preset.name} ↗`;
        } else {
          helpLink.style.display = "none";
        }
      }

      if (presetKey !== "custom") {
        if (baseUrlInput) baseUrlInput.value = preset.base_url;
        // إذا كان حقل النموذج فارغاً أو كان يحتوي على افتراضي قديم، نضع النموذج الأقوى تلقائياً
        const allKnownDefaults = Object.values(CLOUD_PRESETS).flatMap((p) => [
          p.model,
          ...(p.models || []).map((m) => m.id),
        ]);
        if (
          modelInput &&
          (!modelInput.value || allKnownDefaults.includes(modelInput.value))
        ) {
          modelInput.value = preset.model;
        }
      }

      renderModelSuggestions(preset);

      if (keyInput && preset.placeholder_key) {
        if (!llmSavedHasCloudKey) {
          keyInput.placeholder = `ألصق مفتاح الـ API (${preset.placeholder_key})`;
        }
      }
    }

    function handleLlmModeChange(mode) {
      const autoCard = document.getElementById("modeAutoCard");
      const manualCard = document.getElementById("modeManualCard");

      if (mode === "auto") {
        if (autoCard) {
          autoCard.style.borderColor = "var(--color-phosphor-green)";
          autoCard.style.borderWidth = "2px";
        }
        if (manualCard) {
          manualCard.style.borderColor = "var(--color-charcoal)";
          manualCard.style.borderWidth = "1px";
        }
      } else {
        if (manualCard) {
          manualCard.style.borderColor = "var(--color-phosphor-green)";
          manualCard.style.borderWidth = "2px";
        }
        if (autoCard) {
          autoCard.style.borderColor = "var(--color-charcoal)";
          autoCard.style.borderWidth = "1px";
        }
      }
      setActiveProvider(
        document.getElementById("llmActiveProvider")?.value || "local",
      );
    }

    function setActiveProvider(prov) {
      const hiddenInput = document.getElementById("llmActiveProvider");
      if (hiddenInput) hiddenInput.value = prov;
      const btnLocal = document.getElementById("btnSelectLocal");
      const btnCloud = document.getElementById("btnSelectCloud");
      const cloudSec = document.getElementById("cloudSettingsSection");
      const localSec = document.getElementById("localSettingsSection");
      const hint = document.getElementById("activeProviderHint");
      const isAuto =
        document.querySelector('input[name="llm_mode"]:checked')?.value !==
        "manual";

      if (prov === "cloud") {
        if (btnCloud) {
          btnCloud.style.borderColor = "var(--color-phosphor-green)";
          btnCloud.style.borderWidth = "1.5px";
          btnCloud.style.background = "rgba(var(--ok-rgb),0.1)";
          btnCloud.style.color = "var(--color-snow)";
        }
        if (btnLocal) {
          btnLocal.style.borderColor = "var(--color-charcoal)";
          btnLocal.style.borderWidth = "1px";
          btnLocal.style.background = "var(--color-ash)";
          btnLocal.style.color = "var(--color-silver-mist)";
        }
        // عرض إعدادات المشغل السحابي فقط وإخفاء المحلي
        if (cloudSec) cloudSec.style.display = "block";
        if (localSec) localSec.style.display = "none";
        if (hint) {
          hint.textContent = isAuto
            ? "في وضع Auto: يتم تشغيل المشغل السحابي، وإذا لم يستجب يتحول تلقائياً إلى المحرك المحلي لضمان عدم توقف الوكلاء."
            : "في وضع Manual: يتم الاعتماد على المشغل السحابي حصراً دون أي تبديل.";
        }
      } else {
        if (btnLocal) {
          btnLocal.style.borderColor = "var(--color-phosphor-green)";
          btnLocal.style.borderWidth = "1.5px";
          btnLocal.style.background = "rgba(var(--ok-rgb),0.1)";
          btnLocal.style.color = "var(--color-snow)";
        }
        if (btnCloud) {
          btnCloud.style.borderColor = "var(--color-charcoal)";
          btnCloud.style.borderWidth = "1px";
          btnCloud.style.background = "var(--color-ash)";
          btnCloud.style.color = "var(--color-silver-mist)";
        }
        // عرض إعدادات المحرك المحلي فقط وإخفاء السحابي
        if (localSec) localSec.style.display = "block";
        if (cloudSec) cloudSec.style.display = "none";
        if (hint) {
          hint.textContent = isAuto
            ? "في وضع Auto: يتم تشغيل المحرك المحلي كأولوية مع التبديل التلقائي إذا تعثر."
            : "في وضع Manual: يتم الاعتماد على المحرك المحلي حصراً دون أي تبديل.";
        }
      }
    }

    function toggleApiKeyVisibility() {
      const input = document.getElementById("cloudApiKeyInput");
      if (!input) return;
      input.type = input.type === "password" ? "text" : "password";
    }

    async function loadLlmSettings() {
      try {
        const res = await apiFetch("/api/settings/llm");
        const data = await res.json();
        if (data.status !== "success" || !data.config) return;

        const cfg = data.config;
        const health = data.health || {};

        // 1. Mode radio buttons
        const modeRadios = document.querySelectorAll(
          'input[name="llm_mode"]',
        );
        modeRadios.forEach((r) => {
          r.checked = r.value === (cfg.mode || "auto");
        });
        handleLlmModeChange(cfg.mode || "auto");

        // 2. Active provider
        setActiveProvider(cfg.active_provider || "local");

        // 3. Cloud Provider
        const cloud = cfg.cloud || {};
        const presetSelect = document.getElementById("cloudPresetSelector");
        if (presetSelect && cloud.provider) {
          presetSelect.value = cloud.provider;
        }
        const cloudBaseUrl = document.getElementById("cloudBaseUrlInput");
        if (cloudBaseUrl)
          cloudBaseUrl.value =
            cloud.base_url || "https://openrouter.ai/api/v1";
        const cloudModel = document.getElementById("cloudModelInput");
        if (cloudModel) cloudModel.value = cloud.model || "openrouter/auto";

        const activePresetKey =
          presetSelect && presetSelect.value
            ? presetSelect.value
            : cloud.provider || "openrouter";
        const activePreset =
          CLOUD_PRESETS[activePresetKey] || CLOUD_PRESETS.custom;
        if (typeof renderModelSuggestions === "function") {
          renderModelSuggestions(activePreset);
        }

        llmSavedHasCloudKey = !!(cloud.has_api_key || cloud.has_key);
        const keyIndicator = document.getElementById(
          "cloudKeySavedIndicator",
        );
        const keyInput = document.getElementById("cloudApiKeyInput");
        if (keyIndicator) {
          keyIndicator.style.display =
            cloud.has_api_key || cloud.has_key ? "inline" : "none";
        }
        if (keyInput) {
          const masked = cloud.api_key_masked || cloud.api_key;
          if ((cloud.has_api_key || cloud.has_key) && masked) {
            keyInput.placeholder = `المفتاح الحالي: ${masked} (اتركه فارغاً للإبقاء عليه)`;
          } else {
            keyInput.placeholder =
              "ألصق مفتاح الـ API Key هنا (مثل sk-or-v1-...)";
          }
        }

        // 4. Local Provider
        const local = cfg.local || {};
        const localBaseUrl = document.getElementById("localBaseUrlInput");
        if (localBaseUrl)
          localBaseUrl.value = local.base_url || "http://localhost:11434/v1";
        const localModel = document.getElementById("localModelInput");
        if (localModel) localModel.value = local.model || "qwen3.5:9b";

        // 5. Status Badges
        const effBadge = document.getElementById("llmEffectiveBadge");
        if (effBadge) {
          effBadge.textContent = health.effective_engine
            ? `المحرك الفعال: ${health.effective_engine}`
            : "جاهز";
          effBadge.className =
            health.effective_engine &&
              health.effective_engine.includes("fallback")
              ? "badge badge-warning"
              : "badge badge-success";
        }

        const localBadge = document.getElementById("localStatusBadge");
        if (localBadge) {
          if (health.local && health.local.available) {
            localBadge.innerHTML = `<span style="color: var(--color-phosphor-green);">متصل (${health.local.latency_ms || 0}ms)</span>`;
          } else {
            localBadge.innerHTML = `<span style="color: var(--color-smoke);">غير متصل</span>`;
          }
        }

        const cloudBadge = document.getElementById("cloudStatusBadge");
        if (cloudBadge) {
          if (health.cloud && health.cloud.available) {
            cloudBadge.innerHTML = `<span style="color: var(--color-phosphor-green);">متصل (${health.cloud.latency_ms || 0}ms)</span>`;
          } else if (cloud.has_api_key || cloud.has_key) {
            cloudBadge.innerHTML = `<span style="color: var(--color-amber);">مهيأ (بانتظار طلب)</span>`;
          } else {
            cloudBadge.innerHTML = `<span style="color: var(--color-smoke);">غير مهيأ (بدون مفتاح)</span>`;
          }
        }

        // تحديث شارة محرك الذكاء الاصطناعي في الشريط العلوي (Top Nav)
        const topBadge = document.getElementById("aiEngineStatusBadge");
        const topDot = document.getElementById("aiEngineStatusDot");
        const topText = document.getElementById("aiEngineStatusText");

        if (topBadge && topDot && topText) {
          const mode = cfg.mode || "auto";
          const active = cfg.active_provider || "local";
          const hasKey = !!(cloud.has_api_key || cloud.has_key);
          const provName = cloud.provider
            ? cloud.provider.toUpperCase()
            : "CLOUD";
          const provModel = cloud.model || "";
          const locModel = local.model || "qwen3.5:9b";

          const serajSub = document.getElementById("serajEngineSubtitle");
          if (active === "cloud" && hasKey) {
            topDot.style.background = "var(--ink)";
            topDot.style.boxShadow = "none";
            topText.textContent =
              mode === "auto"
                ? `AI: سحابي 🡰 محلي (${provName})`
                : `AI: سحابي (${provName})`;
            topBadge.title = `الذكاء السحابي نشط (${provModel}) - وضع: ${mode} - انقر لتغيير الإعدادات`;
            if (serajSub) {
              serajSub.textContent = `تشغيل سحابي معتمد عبر ${provName} (${provModel || 'Gemini'}) • حوكمة Odoo Stage`;
            }
          } else if (active === "cloud" && !hasKey) {
            topDot.style.background = "var(--color-coral)";
            topDot.style.boxShadow = "none";
            topText.textContent = `AI: سحابي (مفقود API Key)`;
            topBadge.title = `المشغل السحابي يحتاج مفتاح API Key - انقر لتهيئته`;
            if (serajSub) {
              serajSub.textContent = `مشغل سحابي غير مهيأ (بانتظار API Key) • حوكمة Odoo Stage`;
            }
          } else {
            topDot.style.background = "var(--color-phosphor-green)";
            topDot.style.boxShadow = "none";
            topText.textContent =
              mode === "auto"
                ? "AI: محلي 🡰 سحابي (Ollama)"
                : "AI: محلي (Ollama)";
            topBadge.title = `المحرك المحلي نشط (${locModel}) - وضع: ${mode} - انقر لتغيير الإعدادات`;
            if (serajSub) {
              serajSub.textContent = `تشغيل محلي محكوم عبر Ollama (${locModel}) • حوكمة Odoo Stage`;
            }
          }
        }
      } catch (err) {
        console.warn("Failed to load LLM settings:", err);
      }
    }

    async function testLlmConnection(target) {
      const resultBox = document.getElementById("llmTestResultBox");
      const btn =
        target === "cloud"
          ? document.getElementById("btnTestCloud")
          : document.getElementById("btnTestLocal");
      const origText = btn ? btn.textContent : "";

      if (btn) {
        btn.disabled = true;
        btn.textContent = "جاري الفحص...";
      }

      if (resultBox) {
        resultBox.style.display = "block";
        resultBox.style.background = "rgba(var(--ink-rgb),0.05)";
        resultBox.style.border = "1px solid var(--color-charcoal)";
        resultBox.style.color = "var(--color-silver-mist)";
        resultBox.textContent = `جاري فحص الاتصال بـ ${target === "cloud" ? "المشغل السحابي" : "المحرك المحلي"}...`;
      }

      try {
        const payload = { target: target };
        if (target === "cloud") {
          payload.provider =
            document.getElementById("cloudPresetSelector")?.value ||
            "openrouter";
          payload.base_url =
            document.getElementById("cloudBaseUrlInput")?.value?.trim() ||
            null;
          payload.model =
            document.getElementById("cloudModelInput")?.value?.trim() || null;
          const keyVal = document
            .getElementById("cloudApiKeyInput")
            ?.value?.trim();
          payload.api_key = keyVal ? keyVal : null;
        } else {
          payload.base_url =
            document.getElementById("localBaseUrlInput")?.value?.trim() ||
            null;
          payload.model =
            document.getElementById("localModelInput")?.value?.trim() || null;
        }

        const res = await apiFetch("/api/settings/llm/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(
            data.detail || data.message || `خطأ في الخادم (${res.status})`,
          );
        }
        const isSuccess =
          data.available === true ||
          data.status === "online" ||
          data.success === true;

        if (resultBox) {
          if (isSuccess) {
            resultBox.style.background = "rgba(var(--ok-rgb),0.12)";
            resultBox.style.border = "1px solid var(--color-phosphor-green)";
            resultBox.style.color = "var(--color-snow)";
            resultBox.innerHTML = `<strong>نجح الاتصال بنجاح</strong><br>
              المشغل: <span class="mono">${escapeHtml(data.provider || target)}</span> · 
              زمن الاستجابة: <span class="mono">${data.latency_ms || 0}ms</span> · 
              النموذج: <span class="mono">${escapeHtml(data.model || payload.model || (data.models && data.models[0]) || "افتراضي")}</span><br>
              <span style="font-size: 12.5px; color: var(--color-phosphor-green);">${escapeHtml(data.message || "")}</span>`;
          } else {
            resultBox.style.background = "rgba(var(--bad-rgb),0.15)";
            resultBox.style.border = "1px solid var(--color-coral)";
            resultBox.style.color = "var(--bad)";

            let hintHtml = "";
            if (
              data.status === "invalid_key" ||
              (data.message && data.message.includes("401"))
            ) {
              const currentProvider = payload.provider || "openrouter";
              const keyUrl =
                CLOUD_PRESETS[currentProvider]?.key_url ||
                "https://openrouter.ai/keys";
              hintHtml = `
                <div style="margin-top: 8px; padding: 8px 12px; background: rgba(var(--warn-rgb),0.12); border: 1px solid rgba(var(--warn-rgb),0.3); border-radius: 8px; color: var(--warn); font-size: 12px; line-height: 1.6;">
                  <strong>سبب الخطأ 401:</strong> المفتاح المدخل غير مصرح به أو ليس بالصيغة المخصصة لهذا المشغل.<br>
                  • مفاتيح OpenRouter تبدأ بـ: <span class="mono" style="background: rgba(0,0,0,0.3); padding: 1px 4px; border-radius: 4px;">sk-or-v1-...</span><br>
                  • يمكنك إنشاء مفتاح صالح ومجاني بدقيقة واحدة عبر: <a href="${keyUrl}" target="_blank" rel="noopener noreferrer" style="color: var(--ink); text-decoration: underline; font-weight: 700;">صفحة مفاتيح ${escapeHtml(CLOUD_PRESETS[currentProvider]?.name || "المشغل")} ↗</a>
                </div>`;
            }

            const adviceText =
              target === "local"
                ? "تأكد من تشغيل تطبيق Ollama محلياً أو اضغط على زر «تشغيل خادم Ollama» أعلاه."
                : "تأكد من صحة الرابط ومفتاح API واتصالك بالإنترنت.";

            resultBox.innerHTML = `<strong>فشل الاتصال:</strong> ${escapeHtml(data.message || "تعذر الوصول إلى الخادم.")}<br>
              <span style="font-size: 12.5px; color: var(--color-silver-mist);">${adviceText}</span>
              ${hintHtml}`;
          }
        }
      } catch (err) {
        if (resultBox) {
          resultBox.style.background = "rgba(var(--bad-rgb),0.15)";
          resultBox.style.border = "1px solid var(--color-coral)";
          resultBox.style.color = "var(--bad)";
          resultBox.textContent = `حدث خطأ أثناء الفحص: ${err.message}`;
        }
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = origText;
        }
      }
    }

    async function startLocalOllamaService() {
      const btn = document.getElementById("btnStartLocalOllama");
      const resultBox = document.getElementById("llmTestResultBox");
      const origBtnText = btn ? btn.textContent : "";

      if (btn) {
        btn.disabled = true;
        btn.textContent = "جاري تشغيل خادم Ollama...";
      }

      if (resultBox) {
        resultBox.style.display = "block";
        resultBox.style.background = "rgba(var(--ink-rgb),0.04)";
        resultBox.style.border = "1px solid var(--color-charcoal)";
        resultBox.style.color = "var(--color-silver-mist)";
        resultBox.innerHTML =
          "جاري إطلاق خادم Ollama المحلي في الخلفية وربطه بالنماذج المرفقة...";
      }

      try {
        const res = await apiFetch("/api/settings/llm/start-local", {
          method: "POST",
        });
        const data = await res.json();
        if (resultBox) {
          if (data.status === "success") {
            const h = data.health || {};
            resultBox.style.background = "rgba(var(--ok-rgb),0.12)";
            resultBox.style.border = "1px solid var(--color-phosphor-green)";
            resultBox.style.color = "var(--color-snow)";
            const count =
              h.models && h.models.length
                ? `· النماذج المتاحة: <span class="mono">${h.models.join(", ")}</span>`
                : "";
            resultBox.innerHTML = `<strong>${escapeHtml(data.message)}</strong><br>${count}`;
          } else {
            resultBox.style.background = "rgba(var(--bad-rgb),0.15)";
            resultBox.style.border = "1px solid var(--color-coral)";
            resultBox.style.color = "var(--bad)";
            resultBox.innerHTML = `<strong>${escapeHtml(data.message || "تعذر تشغيل الخادم المحلي.")}</strong>`;
          }
        }
        await loadLlmSettings();
      } catch (err) {
        if (resultBox) {
          resultBox.style.background = "rgba(var(--bad-rgb),0.15)";
          resultBox.style.border = "1px solid var(--color-coral)";
          resultBox.style.color = "var(--bad)";
          resultBox.innerHTML = `<strong>خطأ أثناء طلب تشغيل الخادم:</strong> ${escapeHtml(err.message)}`;
        }
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = origBtnText;
        }
      }
    }

    async function saveLlmSettings(e) {
      if (e) e.preventDefault();
      const saveBtn = document.getElementById("saveLlmBtn");
      const statusMsg = document.getElementById("llmSaveStatusMsg");
      const origBtnText = saveBtn ? saveBtn.textContent : "";

      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = "جاري الحفظ والتطبيق...";
      }
      if (statusMsg) {
        statusMsg.innerHTML =
          '<span style="color: var(--color-silver-mist);">جاري إرسال الإعدادات وحفظها...</span>';
      }

      try {
        const selectedModeEl = document.querySelector(
          'input[name="llm_mode"]:checked',
        );
        const mode = selectedModeEl ? selectedModeEl.value : "auto";
        const activeProvider =
          document.getElementById("llmActiveProvider")?.value || "local";
        const cloudPreset =
          document.getElementById("cloudPresetSelector")?.value ||
          "openrouter";
        const cloudBaseUrl =
          document.getElementById("cloudBaseUrlInput")?.value?.trim() || "";
        const cloudModel =
          document.getElementById("cloudModelInput")?.value?.trim() || "";
        const rawApiKey = document
          .getElementById("cloudApiKeyInput")
          ?.value?.trim();
        const localBaseUrl =
          document.getElementById("localBaseUrlInput")?.value?.trim() || "";
        const localModel =
          document.getElementById("localModelInput")?.value?.trim() || "";

        const payload = {
          mode: mode,
          active_provider: activeProvider,
          fallback_enabled: mode === "auto",
          local_base_url: localBaseUrl || undefined,
          local_model: localModel || undefined,
          cloud_provider: cloudPreset || undefined,
          cloud_base_url: cloudBaseUrl || undefined,
          cloud_model: cloudModel || undefined,
          cloud_api_key: rawApiKey ? rawApiKey : null,
        };

        const res = await apiFetch("/api/settings/llm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok || data.status !== "success") {
          throw new Error(
            data.detail ||
            data.message ||
            "تعذر حفظ إعدادات الذكاء الاصطناعي",
          );
        }

        if (statusMsg) {
          statusMsg.innerHTML =
            '<span style="color: var(--color-phosphor-green); font-weight: bold; font-size: 13.5px;">تم حفظ وتطبيق إعدادات الذكاء الاصطناعي بنجاح</span>';
        }

        // Clear password field to avoid keeping plaintext in DOM
        const keyInput = document.getElementById("cloudApiKeyInput");
        if (keyInput) keyInput.value = "";

        await loadLlmSettings();
      } catch (err) {
        if (statusMsg) {
          statusMsg.innerHTML = `<span style="color: var(--bad); font-weight: bold;">خطأ في الحفظ: ${escapeHtml(err.message)}</span>`;
        }
      } finally {
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.textContent = origBtnText;
        }
      }
    }

    // =========================================================================
    // 5. AGENTS STRIP & CHARACTERS (PROPER TERMINATION)
    // =========================================================================
    function resetAllAgentsToIdle() {
      document.querySelectorAll(".agent-character-card").forEach((c) => {
        c.classList.remove("is-active");
      });
      document.querySelectorAll("[id^='agentStatusBubble_']").forEach((b) => {
        b.textContent = "جاهز";
      });
      document.querySelectorAll("[id^='agentStatusDot_']").forEach((d) => {
        d.style.background = "var(--color-phosphor-green)";
        d.style.boxShadow = "none";
      });
    }

    function renderAgentsStrip() {
      const container = document.getElementById("agentsStrip");
      if (!container) return;
      container.innerHTML = "";

      Object.entries(AGENTS_META).forEach(([key, meta]) => {
        const card = document.createElement("div");
        card.className = "agent-character-card t-avatar";
        card.id = `agentCard_${key}`;
        card.style.setProperty("--agent-color", meta.color);
        card.onclick = () => openAgentDetails(key);

        card.innerHTML = `
          <div class="agent-avatar-wrap">
            ${meta.img ? `<img src="${meta.img}" alt="${escapeHtml(meta.name_ar)}" class="agent-avatar-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />` : ""}
            <div class="agent-avatar-svg-fallback" style="${meta.img ? "display:none;" : "display:flex;"} width:100%; height:100%; align-items:center; justify-content:center;">
              ${getAgentSvg(meta.icon)}
            </div>
          </div>
          <div class="agent-tile-info">
            <div class="agent-tile-header">
              <span class="agent-name">${meta.name_ar}</span>
              <span class="agent-tile-status-dot" id="agentStatusDot_${key}"></span>
              <span class="agent-status-bubble" id="agentStatusBubble_${key}" style="display:none;">جاهز</span>
            </div>
            <div class="agent-role-short">${meta.role}</div>
          </div>
          <div class="agent-popover">${escapeHtml(meta.popover || meta.name_ar + ": " + meta.role)}</div>
        `;
        container.appendChild(card);
      });

      setupAgentRibbonTransitions();
    }

    function setupAgentRibbonTransitions() {
      const root = document.getElementById("agentsStrip");
      if (!root) return;
      const cards = Array.from(
        root.querySelectorAll(".agent-character-card"),
      );
      if (cards.length === 0) return;

      const cs = getComputedStyle(document.documentElement);
      const num = (name, fb) => {
        const v = parseFloat(cs.getPropertyValue(name));
        return Number.isFinite(v) ? v : fb;
      };
      const ease = (name, fb) => cs.getPropertyValue(name).trim() || fb;

      function setShifts(activeIdx, phase) {
        const lift = num("--avatar-lift", -3.5);
        const falloff = num("--avatar-falloff", 0.45);
        const scale = num("--avatar-scale", 1.025);
        const tf =
          phase === "out"
            ? ease("--avatar-ease-out", "cubic-bezier(0.34, 1.6, 0.64, 1)")
            : ease("--avatar-ease-in", "cubic-bezier(0.22, 1, 0.36, 1)");

        cards.forEach((el, i) => {
          el.style.transitionTimingFunction = tf;
          if (activeIdx == null) {
            el.style.setProperty("--shift", "0px");
            el.style.setProperty("--scale-active", "1");
            return;
          }
          const d = Math.abs(i - activeIdx);
          el.style.setProperty(
            "--shift",
            (lift * Math.pow(falloff, d)).toFixed(3) + "px",
          );
          el.style.setProperty(
            "--scale-active",
            i === activeIdx ? String(scale) : "1",
          );
        });
      }

      cards.forEach((el, i) => {
        el.onmouseenter = () => setShifts(i, "in");
      });
      root.onmouseleave = () => setShifts(null, "out");
    }

    function getAgentSvg(iconName) {
      switch (iconName) {
        case "sparkles":
          return `<svg viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`;
        case "search":
          return `<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>`;
        case "shield-check":
          return `<svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>`;
        case "git-merge":
          return `<svg viewBox="0 0 24 24"><circle cx="18" cy="18" r="3"></circle><circle cx="6" cy="6" r="3"></circle><path d="M6 21V9a9 9 0 0 0 9 9"></path></svg>`;
        case "lock":
          return `<svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>`;
        case "wrench":
          return `<svg viewBox="0 0 24 24"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>`;
        case "pencil":
          return `<svg viewBox="0 0 24 24"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>`;
        case "book-open":
          return `<svg viewBox="0 0 24 24"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>`;
        case "cpu":
          return `<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>`;
        default:
          return `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"></circle></svg>`;
      }
    }

    async function loadAgentsOverview() {
      try {
        const res = await apiFetch("/api/agents/overview");
        const data = await res.json();
        if (data.status === "success") {
          activeAgentsData = data.agents;
          updateAgentsStripDisplay(data.agents);
          renderAgentsFullGrid(data.agents);
        }
      } catch (err) {
        console.warn("Agents overview load:", err);
      }
    }

    function updateAgentsStripDisplay(agents) {
      agents.forEach((a) => {
        const bubble = document.getElementById(`agentStatusBubble_${a.id}`);
        const card = document.getElementById(`agentCard_${a.id}`);
        if (bubble)
          bubble.textContent =
            a.status_label || STATUS_MAP_AR[a.status_code] || "جاهز";
        if (card) {
          if (
            a.status_code !== "ready" &&
            a.status_code !== "completed" &&
            a.status_code !== "failed"
          ) {
            card.classList.add("is-active");
          } else {
            card.classList.remove("is-active");
          }
        }
      });
    }

    function directInquiryToAgent(agentId, event) {
      if (event) {
        event.stopPropagation();
        event.preventDefault();
      }
      switchView("view-cockpit");
      const meta = AGENTS_META[agentId] || {};
      const defaultPrompts = {
        seraj: "مرحباً سراج، أحتاج مساعدتك في تنسيق ومتابعة عمليات الموارد البشرية عبر الوكلاء.",
        fahas: "أهلاً فاحص، أحتاج الاستعلام والتحقق من سجلات Odoo الحية للموظفين والعقود.",
        modaqeq: "أهلاً مدقق، أرجو مطابقة بيانات الرواتب وساعات العمل مع مواد نظام العمل السعودي.",
        mowafaq: "أهلاً موفق، أحتاج مطابقة وتوفيق مسميات الوظائف والأقسام غير المتطابقة مع Odoo.",
        musleh: "أهلاً مصلح، أرجو فحص الأخطاء وتشخيص السجلات المرفوضة وتقديم مقترحات التصحيح.",
        hares: "أهلاً حارس، أحتاج فحص سرية البيانات وحماية المعلومات الحساسة ومراجعة حدود الصلاحيات.",
        katib: "أهلاً كاتب، أحتاج مراجعة جاهزية خطة القيد والإنشاء قبل الترحيل إلى Odoo.",
        sijil: "أهلاً سجل، أرجو استعراض سجلات التدقيق اللاتراجعي وشهادات التحقق الراجع (Readback)."
      };
      const promptText = defaultPrompts[agentId] || `أهلاً ${meta.name_ar || agentId}، أحتاج استشارتك في مهام الموارد البشرية.`;

      setTimeout(() => {
        const input = document.getElementById("chatInput");
        if (input) {
          input.value = promptText;
          if (typeof autoResizeTextarea === "function") autoResizeTextarea(input);
          input.focus();
          try {
            input.setSelectionRange(input.value.length, input.value.length);
          } catch (_) { }
        }
      }, 50);
    }
    window.directInquiryToAgent = directInquiryToAgent;

    function renderAgentsFullGrid(agents) {
      const grid = document.getElementById("agentsFullGrid");
      if (!grid) return;
      grid.innerHTML = "";

      agents.forEach((a) => {
        const meta = AGENTS_META[a.id] || {
          color: "var(--color-phosphor-green)",
          icon: "sparkles",
        };
        const card = document.createElement("div");
        card.className = "agent-full-card";
        card.onclick = () => openAgentDetails(a.id);
        card.style.cursor = "pointer";

        // Map status code to appropriate badge and icon
        let badgeClass = "badge-neutral";
        let statusDot = "🟢";
        if (a.status_code === "ready" || a.status_code === "idle") {
          badgeClass = "badge-success";
          statusDot = "🟢";
        } else if (a.status_code === "processing" || a.status_code === "busy" || a.status_code === "analyzing_request") {
          badgeClass = "badge-warning";
          statusDot = "⚙️";
        } else if (a.status_code === "online") {
          badgeClass = "badge-success";
          statusDot = "⚡";
        } else if (a.status_code === "failed") {
          badgeClass = "badge-danger";
          statusDot = "⚠️";
        }
        const statusLabel = a.status_label || STATUS_MAP_AR[a.status_code] || "جاهز";

        card.innerHTML = `
          <div class="agent-full-card-header">
            <div class="agent-avatar-wrap" style="border-color: ${meta.color}; width: 48px; height: 48px;">
              ${meta.img ? `<img src="${meta.img}" alt="${escapeHtml(a.name_ar)}" class="agent-avatar-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />` : ""}
              <div class="agent-avatar-svg-fallback" style="${meta.img ? "display:none;" : "display:flex;"} width:100%; height:100%; align-items:center; justify-content:center;">
                ${getAgentSvg(meta.icon)}
              </div>
            </div>
            <div>
              <div style="font-size: 16px; font-weight: 700; color: var(--color-snow);">${escapeHtml(a.name_ar)}</div>
              <div style="font-size: 12px; color: var(--color-silver-mist);">${escapeHtml(a.title_ar || meta.role)}</div>
            </div>
            <span class="badge ${badgeClass}" style="margin-right: auto; display: inline-flex; align-items: center; gap: 4px;">
              <span>${statusLabel}</span>
              <span aria-hidden="true">${statusDot}</span>
            </span>
          </div>
          <div style="font-size: 12.5px; color: var(--color-silver-mist); line-height: 1.5;">${escapeHtml(a.description_short || meta.role)}</div>
          <ul class="agent-capabilities">${(a.capabilities || []).map((c) => `<li>${escapeHtml(c)}</li>`).join("")}</ul>
          <div class="agent-stats">
            <span><strong class="tabular-nums font-mono">${a.operation_count || 0}</strong> عملية</span>
            <span><strong class="tabular-nums font-mono">${a.event_count || 0}</strong> حدث</span>
            <span>آخر نشاط: <strong class="tabular-nums">${escapeHtml(a.last_active_at?.slice(0, 19).replace("T", " ") || "لا يوجد")}</strong></span>
          </div>
          <div style="font-size: 12.5px; background: var(--paper-2); padding: 8px 12px; border-radius: 8px; border: 1px solid var(--color-charcoal);">
            <span style="color: var(--color-smoke);">آخر مهمة:</span>
            <span style="color: var(--color-snow); font-weight: 500;"> ${escapeHtml(a.last_task || "في انتظار المهام")}</span>
          </div>
          <div class="agent-card-actions" style="margin-top: 14px; display: flex; gap: 8px;">
            <button type="button" class="btn btn-sm btn-outline-primary agent-inquiry-btn" style="flex: 1; justify-content: center; font-size: 12px; padding: 7px 12px;" onclick="directInquiryToAgent('${a.id}', event)" title="بدء محادثة فورية وتوجيه استفسار لسراج والوكيل">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="13" height="13" style="margin-left: 4px;">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              <span>توجيه استفسار مباشر 💬</span>
            </button>
            <button type="button" class="btn btn-sm btn-subtle" style="padding: 7px 12px; font-size: 12px;" onclick="openAgentDetails('${a.id}'); event.stopPropagation();" title="عرض بطاقة الصلاحيات والمهام">
              <span>التفاصيل</span>
            </button>
          </div>
        `;
        grid.appendChild(card);
      });
    }

    // =========================================================================
    // 6. CHAT & CONVERSATION HANDLERS
    // =========================================================================
    function handleTextareaKeyDown(e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleChatSubmit(e);
      }
    }

    function sendQuickPrompt(promptText) {
      const input = document.getElementById("chatInput");
      input.value = promptText;
      handleChatSubmit(new Event("submit"));
    }

    function fillPrompt(promptText) {
      const input = document.getElementById("chatInput");
      if (input) {
        input.value = promptText;
        autoResizeTextarea(input);
        input.focus();
      }
    }

    function toggleReasoning(el) {
      const drawer = el.closest(".reasoning-drawer");
      if (!drawer) return;
      const body = drawer.querySelector(".reasoning-body");
      if (!body) return;
      const isHidden = body.style.display === "none";
      body.style.display = isHidden ? "block" : "none";
      const icon = el.querySelector("span");
      if (icon) {
        icon.textContent = isHidden
          ? "▼ تفكير سراج: استدعاء الوكيل «مدقق» لفحص نصوص اللائحة"
          : "▶ تفكير سراج (انقر للتوسيع)";
      }
    }

    function switchScenario(scene, btn) {
      if (btn) {
        document
          .querySelectorAll(".btn-sim-trigger")
          .forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
      }

      const badge = document.getElementById("dockGlobalStatusBadge");
      const badgeText = document.getElementById("dockGlobalStatusText");
      const approvalCard = document.getElementById("hitlApprovalGateBanner");
      const routeTarget = document.getElementById("route-step-target");
      const chatBox = document.getElementById("chatMessages");
      const timelineBox = document.getElementById("timelineContainer");

      if (scene === "standby") {
        resetAllAgentsToIdle();
        if (badge) {
          badge.style.borderColor = "rgba(var(--ok-rgb),0.25)";
          badge.style.color = "var(--color-phosphor-green)";
        }
        if (badgeText) badgeText.textContent = "8 وكلاء في حالة جاهزية كاملة";
        hideHitlGate();
        if (routeTarget) {
          routeTarget.textContent = "الوكيل المختص";
          routeTarget.classList.remove("active");
        }
        if (typeof renderAgentTimeline === "function") {
          renderAgentTimeline([], "idle");
        }
      } else if (scene === "law") {
        resetAllAgentsToIdle();
        const modaqeqCard = document.getElementById("agentCard_modaqeq");
        if (modaqeqCard) modaqeqCard.classList.add("is-active");
        const modaqeqDot = document.getElementById("agentStatusDot_modaqeq");
        if (modaqeqDot) {
          modaqeqDot.style.background = "var(--agent-modaqeq)";
          modaqeqDot.style.boxShadow = "0 0 8px var(--agent-modaqeq)";
        }
        if (badge) {
          badge.style.borderColor = "rgba(var(--ink-rgb),0.45)";
          badge.style.color = "var(--ink)";
        }
        if (badgeText)
          badgeText.textContent = "مدقق: تم استرجاع ومطابقة المادة 77 بنجاح";
        hideHitlGate();
        if (routeTarget) {
          routeTarget.textContent = "مدقق (نظام العمل)";
          routeTarget.classList.add("active");
        }

        if (chatBox) {
          chatBox.innerHTML = `
            <div class="msg-bubble msg-user">
              <div class="msg-avatar"><svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg></div>
              <div class="msg-content-wrapper">
                <div class="msg-meta"><span>المشغّل</span> • <span class="mono">الآن</span></div>
                <div class="msg-card">ما هي ضوابط إنهاء العقد لسبب غير مشروع بموجب المادة 77 من نظام العمل السعودي؟</div>
              </div>
            </div>
            <div class="msg-bubble msg-assistant">
              <div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">
                <img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/images/svg/seraj.svg';">
              </div>
              <div class="msg-content-wrapper">
                <div class="msg-meta"><span>سراج</span> • <span class="mono">الآن</span></div>
                <div class="msg-card">
                  <div class="reasoning-drawer">
                    <div class="reasoning-trigger" onclick="toggleReasoning(this)">
                      <span>▼ تفكير سراج: استدعاء الوكيل «مدقق» لفحص نصوص اللائحة</span>
                    </div>
                    <div class="reasoning-body">
                      -&gt; query: labor_law_ksa.match(article=77)<br>
                      -&gt; modaqeq_agent returned: compensation rules for indefinite and fixed-term contracts.<br>
                      -&gt; synthesizing legal opinion for HR operator.
                    </div>
                  </div>

                  <div class="tool-call-badge">
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                    <span>مدقق: تم التحقق من المادة 77 • نظام العمل السعودي 1446هـ</span>
                  </div>
                  <br>
                  أفاد الوكيل <strong>«مدقق»</strong> بالضوابط القانونية المعتمدة طبقاً لنص <strong>المادة 77</strong>:<br>
                  إذا أُنهي العقد لسبب غير مشروع، يستحق الطرف المتضرر تعويضاً على النحو التالي (ما لم يتضمن العقد تعويضاً محدداً ينص عليه صراحة):
                  <br><br>
                  1. <strong>أجر خمسة عشر يوماً</strong> عن كل سنة من سنوات خدمة العامل إذا كان العقد <strong>غير محدد المدة</strong>.<br>
                  2. <strong>أجر المدة الباقية من العقد</strong> إذا كان العقد <strong>محدد المدة</strong>.<br>
                  3. وفي جميع الأحوال، يجب ألا يقل التعويض المشار إليه في الفقرتين السابقتين عن <strong>أجر العامل لمدة شهرين</strong>.
                </div>
              </div>
            </div>
          `;
          chatBox.scrollTop = chatBox.scrollHeight;
        }

        if (timelineBox) {
          timelineBox.innerHTML = `
            <div class="timeline-track-list">
              <div class="timeline-entry">
                <div class="timeline-marker-avatar" style="--marker-color: var(--agent-modaqeq);">
                  <img src="/images/modaqeq.webp" onerror="this.src='/images/svg/modaqeq.svg'">
                </div>
                <div class="timeline-entry-content">
                  <div class="timeline-entry-heading">
                    <strong>استشارة نظام العمل:</strong> استرجع «مدقق» نصوص المادة 77 بطلب من «سراج» وقدم الصياغة القانونية.
                  </div>
                  <div class="timeline-entry-meta">
                    <span>الآن • وكيل: مدقق</span>
                    <span class="timeline-seal-badge">SEAL: 91a4c82e</span>
                  </div>
                </div>
              </div>
            </div>
          `;
        }
      } else if (scene === "hitl") {
        document
          .querySelectorAll(".agent-character-card")
          .forEach((t) => t.classList.add("is-active"));
        if (badge) {
          badge.style.borderColor = "rgba(var(--warn-rgb),0.45)";
          badge.style.color = "var(--color-amber)";
        }
        if (badgeText)
          badgeText.textContent =
            "بانتظار توقيعك البشري: تدقيق ملف رواتب عبر حارس";
        if (approvalCard) approvalCard.style.display = "block";
        if (routeTarget) {
          routeTarget.textContent = "حارس 🡰 توقيع المشغّل";
          routeTarget.classList.add("active");
        }
        startHitlCountdown(299);

        if (chatBox) {
          chatBox.innerHTML = `
            <div class="msg-bubble msg-user">
              <div class="msg-avatar"><svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg></div>
              <div class="msg-content-wrapper">
                <div class="msg-meta"><span>المشغّل</span> • <span class="mono">الآن</span></div>
                <div class="msg-card">تم إرفاق ملف كشف تعديل الرواتب: <code>hr_batch_modifications_october.xlsx</code></div>
              </div>
            </div>
            <div class="msg-bubble msg-assistant">
              <div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">
                <img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/images/svg/seraj.svg';">
              </div>
              <div class="msg-content-wrapper">
                <div class="msg-meta"><span>سراج</span> • <span class="mono">الآن</span></div>
                <div class="msg-card">
                  <div class="tool-call-badge" style="background: rgba(var(--ink-rgb),0.15); border-color: rgba(var(--ink-rgb),0.35); color: var(--ink);">
                    <span>فاحص: قراءة 14 سجلاً ومطابقتها مع Odoo Stage بنجاح</span>
                  </div>
                  <br>
                  اكتمل فحص الملف دلالياً ونظامياً عبر <strong>«فاحص»</strong> و<strong>«مدقق»</strong> و<strong>«موفق»</strong>.
                  <br><br>
                  <strong>إشعار حوكمة الأمان:</strong> رصد الوكيل <strong>«حارس»</strong> وجود تعديلات مالية تتطلب <strong>توقيعك البشري الصريح</strong> قبل السماح لوكيل «كاتب» بقيد التعديلات في قاعدة بيانات Odoo.
                  <br>
                  يرجى مراجعة الجدول في <strong>بوابة الاعتماد البشري (HITL)</strong> على اليسار والضغط على «اعتماد» أو «رفض».
                </div>
              </div>
            </div>
          `;
          chatBox.scrollTop = chatBox.scrollHeight;
        }

        if (timelineBox) {
          timelineBox.innerHTML = `
            <div class="timeline-track-list">
              <div class="timeline-entry">
                <div class="timeline-marker-avatar" style="--marker-color: var(--agent-hares);">
                  <img src="/images/hares.webp" onerror="this.src='/images/svg/hares.svg'">
                </div>
                <div class="timeline-entry-content">
                  <div class="timeline-entry-heading">
                    <strong>حظر تلقائي للكتابة (HITL):</strong> علّق «حارس» أمر القيد وأصدر تصريح موافقة بانتظار المشغّل.
                  </div>
                  <div class="timeline-entry-meta">
                    <span>الآن • وكيل: حارس</span>
                    <span class="timeline-seal-badge">SEAL: 77a1bc8f</span>
                  </div>
                </div>
              </div>
            </div>
          `;
        }
      }
    }

    async function handleChatSubmit(e) {
      if (e) e.preventDefault();
      const input = document.getElementById("chatInput");
      const text = input.value.trim();
      if (!text || chatRequestInFlight) return;
      if (
        ["completed", "failed", "cancelled", "inconclusive"].includes(
          currentOperationStatus,
        )
      ) {
        currentOperationId = null;
        currentChatId = `web_${crypto.randomUUID()}`;
        lastEventSequence = 0;
      }

      input.value = "";
      autoResizeTextarea(input);
      appendUserMessage(text);
      showTypingIndicator();
      setSerajBusy("سراج يعالج الطلب…");

      try {
        const payload = {
          message: text,
          chat_id: currentChatId,
          operation_id: currentOperationId,
          company_id: selectedCompanyId,
        };

        const res = await apiFetch("/api/seraj/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (data.status === "success") {
          currentOperationId = data.operation_id;
          currentOperationStatus = data.operation?.status;
          document.getElementById("activeOpIdBadge").textContent =
            currentOperationId;

          appendSerajMessage(
            data.response,
            data.pending_action,
            data.pending_clarification,
            data.operation,
            data.rejected_rows_details,
            data.llm_meta,
          );
          if (data.operation) {
            updateProcessStepper(data.operation.events || []);
            updateOperationBadges(data.operation);
          }
          if (
            ![
              "completed",
              "failed",
              "cancelled",
              "inconclusive",
              "waiting_approval",
              "waiting_user_clarification",
            ].includes(currentOperationStatus)
          )
            startLiveEventPolling(currentOperationId);
        } else {
          appendSerajMessage(
            "عذراً، واجه سراج صعوبة في معالجة طلبك: " +
            (data.detail || "خطأ غير معروف"),
          );
        }
      } catch (err) {
        appendSerajMessage("تعذر الاتصال بخادم المنظومة: " + err.message);
      } finally {
        hideTypingIndicator();
        setSerajIdle();
        loadAgentsOverview();
      }
    }

    async function handleApprovePlan() {
      hideHitlGate();
      if (!currentOperationId) return;
      appendUserMessage("تأكيد");
      showTypingIndicator();
      setSerajBusy("جاري تنفيذ العملية المعتمدة عبر «كاتب»…");

      try {
        const res = await apiFetch("/api/agents/approve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: currentChatId,
            operation_id: currentOperationId,
          }),
        });
        const data = await res.json();
        appendSerajMessage(
          data.response,
          null,
          null,
          data.operation,
          data.rejected_rows_details,
        );
        if (data.operation) {
          updateProcessStepper(data.operation.events || []);
          updateOperationBadges(data.operation);
        }
      } catch (err) {
        appendSerajMessage("تعذر إتمام الاعتماد: " + err.message);
      } finally {
        hideTypingIndicator();
        setSerajIdle();
        loadAgentsOverview();
      }
    }

    async function handleCancelPlan() {
      hideHitlGate();
      if (!currentOperationId) return;
      appendUserMessage("إلغاء");
      showTypingIndicator();
      setSerajBusy("جاري إلغاء العملية…");

      try {
        const res = await apiFetch("/api/agents/cancel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: currentChatId,
            operation_id: currentOperationId,
          }),
        });
        const data = await res.json();
        appendSerajMessage(
          data.response,
          null,
          null,
          data.operation,
          data.rejected_rows_details,
        );
        if (data.operation) {
          updateProcessStepper(data.operation.events || []);
          updateOperationBadges(data.operation);
        }
        resetAllAgentsToIdle();
      } catch (err) {
        appendSerajMessage("تعذر إلغاء العملية: " + err.message);
      } finally {
        hideTypingIndicator();
        setSerajIdle();
        loadAgentsOverview();
      }
    }

    // =========================================================================
    // 7. EXCEL UPLOAD & CONTROLLED DRY-RUN INSPECTION
    // =========================================================================
    async function handleFileUpload(input) {
      if (!input.files || !input.files[0]) return;
      const file = input.files[0];
      const formData = new FormData();
      formData.append("file", file);
      if (chatRequestInFlight) return;
      currentChatId = `web_${crypto.randomUUID()}`;
      formData.append("chat_id", currentChatId);
      formData.append("company_id", selectedCompanyId);

      appendUserMessage(
        `تم إرفاق الملف: «${file.name}» (${Math.round(file.size / 1024)} KB)`,
      );
      showTypingIndicator();
      setSerajBusy("سراج وفاحص يستلمان الملف ويفحصان محتواه…");

      try {
        const res = await apiFetch("/api/agents/upload", {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (data.status === "success") {
          currentOperationId = data.operation_id;
          currentOperationStatus = data.operation?.status;
          document.getElementById("activeOpIdBadge").textContent =
            currentOperationId;

          if (data.dry_run_report) {
            if (data.dry_run_report.summary) {
              const r = data.dry_run_report;
              const tmplTitle =
                r.template_title || r.summary?.template_title || "";
              const tmplLine = tmplTitle
                ? `• نوع القالب المكتشف: **${tmplTitle}**\n`
                : "";
              const repMsg =
                `${data.message}\n\n` +
                `**تقرير الفحص الأولي المحكوم (Dry-Run)** لملف «${data.filename}»:\n` +
                tmplLine +
                `• إجمالي الصفوف المفحوصة: ${r.total_rows}\n` +
                `• الصفوف المقبولة والمطابقة: ${r.accepted_count}\n` +
                `• الصفوف المرفوضة أو غير المطابقة: ${r.rejected_count}\n` +
                `جرى الفحص بصورة جافة وآمنة دون إجراء أي كتابة أو تعديل غير معتمد في Odoo.`;
              appendSerajMessage(repMsg);
              if (r.report_url) appendDryRunReportLink(r.report_url);
            } else if (data.dry_run_report.error) {
              appendSerajMessage(
                `تعذر استكمال فحص ملف الإكسل «${data.filename}»:\n${data.dry_run_report.error}`,
              );
            }
          } else {
            appendSerajMessage(
              data.message || "لم يصل تقرير فحص. أعد رفع الملف.",
            );
          }
          if (data.operation) {
            updateProcessStepper(data.operation.events || []);
            updateOperationBadges(data.operation);
          }
        } else {
          if (data.operation) {
            currentOperationId = data.operation_id;
            updateOperationBadges(data.operation);
            updateProcessStepper(data.operation.events || []);
          }
          appendSerajMessage(
            data.message ||
            data.detail ||
            "تعذر فحص الملف. أعد رفع ملف Excel صحيح.",
          );
        }
      } catch (err) {
        appendSerajMessage("تعذر رفع الملف: " + err.message);
      } finally {
        hideTypingIndicator();
        setSerajIdle();
        input.value = "";
        loadAgentsOverview();
      }
    }

    function appendDryRunReportLink(url) {
      const button = document.createElement("button");
      button.className = "btn btn-sm btn-secondary";
      button.textContent = "عرض تقرير الصفوف وأسباب الرفض";
      button.onclick = async () => {
        const overlay = document.getElementById("detailsDrawerOverlay");
        const sheet = overlay ? overlay.querySelector(".drawer-sheet") : null;
        const body = document.getElementById("drawerBody");
        if (sheet) sheet.classList.add("is-wide");
        document.getElementById("drawerTitle").textContent =
          "نتيجة فحص Excel — تقرير التدقيق";
        const subTitle = document.getElementById("drawerSubtitle");
        if (subTitle) subTitle.textContent = "توثيق الحدث وأدلة التدقيق";
        body.innerHTML = `
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px 20px; gap: 12px; color: var(--color-silver-mist);">
            <div class="spinner" style="width: 24px; height: 24px; border: 2px solid var(--color-charcoal); border-top-color: var(--color-phosphor-green); border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
            <span>جاري تحميل تقرير الفحص وأدلة التدقيق…</span>
          </div>
        `;
        overlay.classList.add("is-open");
        try {
          const res = await apiFetch(url);
          const data = await res.json();
          if (!res.ok)
            throw new Error(data.detail || "تعذر العثور على التقرير");
          renderDryRunReportDrawer(data, "فحص ملف Excel");
        } catch (err) {
          body.innerHTML = `
            <div style="padding: 24px; border: 1px solid var(--color-charcoal); border-radius: 12px; background: var(--paper-2); color: var(--color-coral); text-align: center;">
              <div style="font-weight: 600; margin-bottom: 6px;">تعذر تحميل تقرير الفحص</div>
              <div style="font-size: 12px; color: var(--color-silver-mist);">${escapeHtml(err.message)}</div>
            </div>
          `;
        }
      };
      document.getElementById("chatMessages").appendChild(button);
    }

    // =========================================================================
    // 8. CHAT DOM HELPERS
    // =========================================================================
    function appendUserMessage(text) {
      const container = document.getElementById("chatMessages");
      const msg = document.createElement("div");
      msg.className = "msg-bubble msg-user";
      msg.innerHTML = `
        <div class="msg-avatar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
        </div>
        <div class="msg-content-wrapper">
          <div class="msg-meta"><span>أنت</span> • <span class="mono">${getTimeStr()}</span></div>
          <div class="msg-card">${escapeHtml(text)}</div>
        </div>
      `;
      container.appendChild(msg);
      container.scrollTop = container.scrollHeight;
    }

    function appendSerajMessage(
      text,
      pendingAction,
      pendingClarification,
      opData,
      rejectionDetails,
      llmMeta,
    ) {
      hideTypingIndicator();
      setSerajIdle();

      const container = document.getElementById("chatMessages");
      const msg = document.createElement("div");
      msg.className = "msg-bubble msg-assistant";

      let llmBadgeHtml = "";
      if (llmMeta && llmMeta.provider) {
        if (llmMeta.provider === "cloud") {
          llmBadgeHtml = `<span class="badge" title="تمت المعالجة عبر الذكاء السحابي (${escapeHtml(llmMeta.model || "")})" style="font-size: 12px; padding: 2px 8px; background: rgba(var(--ink-rgb),0.12); color: var(--ink); border: 1px solid rgba(var(--ink-rgb),0.3); border-radius: 9999px; margin-right: 6px;">ذكاء سحابي (${escapeHtml(llmMeta.provider_name || "Cloud")}: ${escapeHtml(llmMeta.model || "")})</span>`;
        } else if (
          llmMeta.provider === "ollama" ||
          llmMeta.provider === "local"
        ) {
          llmBadgeHtml = `<span class="badge" title="تمت المعالجة محلياً عبر خادم Ollama (${escapeHtml(llmMeta.model || "")})" style="font-size: 12px; padding: 2px 8px; background: rgba(var(--ok-rgb),0.12); color: var(--color-phosphor-green); border: 1px solid rgba(var(--ok-rgb),0.3); border-radius: 9999px; margin-right: 6px;">محرك محلي (Ollama: ${escapeHtml(llmMeta.model || "")})</span>`;
        } else if (llmMeta.provider === "fallback") {
          llmBadgeHtml = `<span class="badge" title="تمت المعالجة عبر محرك الحوكمة والقواعد الاحترازية" style="font-size: 12px; padding: 2px 8px; background: rgba(var(--warn-rgb),0.12); color: var(--color-amber); border: 1px solid rgba(var(--warn-rgb),0.3); border-radius: 9999px; margin-right: 6px;">قواعد احترازية</span>`;
        }
      }

      let actionCardHtml = "";

      if (
        pendingClarification &&
        pendingClarification.type === "clarify_delete_or_archive"
      ) {
        const target = pendingClarification.target || "السجل";
        actionCardHtml = `
          <div class="chat-action-card">
            <div class="action-card-header">
              <span class="action-card-title">تحديد نوع الإجراء المطلوب نظاماً</span>
            </div>
            <div style="font-size: 12.5px; color: var(--color-silver-mist); margin-bottom: 10px;">
              يرجى اختيار أحد الإجراءين المعتمدين بخصوص «${escapeHtml(target)}»:
            </div>
            <div class="action-buttons-group">
              <button class="btn btn-sm btn-primary" onclick="handleClarificationChoice('أرشفة')">أرشفة آمنة (المسار الموصى به)</button>
              <button class="btn btn-sm btn-danger" onclick="handleClarificationChoice('حذف نهائي')">حذف نهائي محكوم</button>
            </div>
          </div>
        `;
      } else if (pendingAction || (opData && (opData.pending_action || opData.plan) && opData.status === "waiting_approval")) {
        const act = pendingAction || opData.pending_action || opData.plan;
        window.currentHitlPendingAction = act;
        window.currentHitlPendingValues = {};
        actionCardHtml = `
          <div class="chat-action-card card-approval">
            <div class="action-card-header">
              <span class="action-card-title">يتطلب اعتماد بشري قبل التنفيذ</span>
              <span class="badge badge-warning">بانتظار الاعتماد</span>
            </div>
            <div class="action-card-grid">
              <div><span class="label">الإجراء:</span><span class="val">${escapeHtml(act.action || "تعديل سجل")}</span></div>
              <div><span class="label">المستهدف:</span><span class="val">${escapeHtml(act.name || act.record_name || act.target || "Odoo")}</span></div>
              <div><span class="label">المنفذ:</span><span class="val">كاتب (بإشراف حارس)</span></div>
              <div><span class="label">رمز الخطة:</span><span class="val mono">${escapeHtml(act.plan_id || "خطة رسمية")}</span></div>
            </div>
            <div class="action-buttons-group">
              <button class="btn btn-sm btn-success" onclick="executeHitlApproval()">اعتماد وقيد في Odoo 🡰</button>
              <button class="btn btn-sm btn-secondary" onclick="executeHitlCancel()">إلغاء الأمر</button>
            </div>
          </div>
        `;
        renderHitlDiffTable(act);
        showHitlGate(currentOperationId || act.operation_id, 1, 0);
      }

      msg.innerHTML = `
        <div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">
          <img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/images/svg/seraj.svg';">
        </div>
        <div class="msg-content-wrapper">
          <div class="msg-meta" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
            <span style="color: var(--agent-seraj); font-weight: 600;">سراج</span>
            <span>•</span>
            <span class="mono">${getTimeStr()}</span>
            ${llmBadgeHtml}
          </div>
          <div class="msg-card">${formatMarkdownText(text)} ${actionCardHtml}</div>
        </div>
      `;
      container.appendChild(msg);
      container.scrollTop = container.scrollHeight;
    }

    function handleClarificationChoice(choice) {
      appendUserMessage(choice);
      showTypingIndicator();
      setSerajBusy("سراج يوجه الإجراء المحدد…");
      apiFetch("/api/seraj/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: choice,
          chat_id: currentChatId,
          operation_id: currentOperationId,
          company_id: selectedCompanyId,
        }),
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.operation_id) currentOperationId = data.operation_id;
          if (data.operation && data.operation.status) currentOperationStatus = data.operation.status;
          appendSerajMessage(
            data.response,
            data.pending_action,
            data.pending_clarification,
            data.operation,
            data.rejected_rows_details,
            data.llm_meta,
          );
          if (data.operation) {
            updateProcessStepper(data.operation.events || []);
            updateOperationBadges(data.operation);
          }
          startLiveEventPolling(currentOperationId);
        })
        .catch((err) =>
          appendSerajMessage(
            "تعذر التوجيه: " + err.message,
            null,
            null,
            null,
            null,
          ),
        )
        .finally(() => {
          hideTypingIndicator();
          setSerajIdle();
        });
    }

    function setSerajBusy(text) {
      chatRequestInFlight = true;
      const sendBtn = document.getElementById("chatSendBtn");
      if (sendBtn) sendBtn.disabled = true;
      const cfBusy = document.getElementById("chatFileInput");
      if (cfBusy) cfBusy.disabled = true;
      const cfExcel = document.getElementById("chatExcelFileInput");
      if (cfExcel) cfExcel.disabled = true;
      const bubble = document.getElementById("agentStatusBubble_seraj");
      if (bubble) bubble.textContent = text || "يعمل الآن…";
      const card = document.getElementById("agentCard_seraj");
      if (card) card.classList.add("is-active");
      const serajBadge = document.getElementById("serajStateBadge");
      if (serajBadge) {
        serajBadge.textContent = "سراج يعالج…";
        serajBadge.className = "badge badge-warning";
      }
    }

    function setSerajIdle() {
      chatRequestInFlight = false;
      const sendBtn = document.getElementById("chatSendBtn");
      if (sendBtn) sendBtn.disabled = false;
      const cfIdle = document.getElementById("chatFileInput");
      if (cfIdle) cfIdle.disabled = false;
      const cfExcel = document.getElementById("chatExcelFileInput");
      if (cfExcel) cfExcel.disabled = false;
      const bubble = document.getElementById("agentStatusBubble_seraj");
      if (bubble) bubble.textContent = "جاهز";
      const card = document.getElementById("agentCard_seraj");
      if (card) card.classList.remove("is-active");
      const serajBadge = document.getElementById("serajStateBadge");
      if (serajBadge) {
        serajBadge.textContent = "جاهز";
        serajBadge.className = "badge badge-neutral";
      }
    }

    // =========================================================================
    // FLOATING ISLAND COMPOSER & CHAT ENHANCEMENTS
    // =========================================================================
    function triggerChatExcelUpload() {
      const fileInput = document.getElementById("chatExcelFileInput");
      if (fileInput) fileInput.click();
    }

    function handleChatExcelSelected(input) {
      if (input.files && input.files.length > 0) {
        handleFileUpload(input);
        input.value = "";
      }
    }

    function handleChatDragOver(e) {
      e.preventDefault();
      e.stopPropagation();
      const composer = document.getElementById("chatForm");
      if (composer) composer.classList.add("is-drag-over");
    }

    function handleChatDragLeave(e) {
      e.preventDefault();
      e.stopPropagation();
      const composer = document.getElementById("chatForm");
      if (composer) composer.classList.remove("is-drag-over");
    }

    function handleChatDrop(e) {
      e.preventDefault();
      e.stopPropagation();
      const composer = document.getElementById("chatForm");
      if (composer) composer.classList.remove("is-drag-over");

      if (
        e.dataTransfer &&
        e.dataTransfer.files &&
        e.dataTransfer.files.length > 0
      ) {
        const file = e.dataTransfer.files[0];
        const name = file.name.toLowerCase();
        if (name.endsWith(".xlsx") || name.endsWith(".xls")) {
          const dummyInput = { files: [file] };
          handleFileUpload(dummyInput);
        } else {
          appendSerajMessage(
            "تنبيه: يدعم مركز المعالجة ملفات Excel (.xlsx, .xls) فقط للفحص والتدقيق المحكوم.",
          );
        }
      }
    }

    function startNewChatSession() {
      if (chatRequestInFlight) return;
      hideHitlGate();
      currentOperationId = null;
      currentChatId = `web_${crypto.randomUUID()}`;
      currentOperationStatus = null;
      lastEventSequence = 0;

      const chatMessages = document.getElementById("chatMessages");
      if (chatMessages) {
        chatMessages.innerHTML = `
          <div class="msg-bubble msg-assistant">
            <div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">
              <img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/images/svg/seraj.svg';">
            </div>
            <div class="msg-content-wrapper">
              <div class="msg-meta">
                <span>سراج</span> • <span class="mono">جلسة جديدة</span>
              </div>
              <div class="msg-card">
                جلسة جديدة. أنا «سراج» المنسق والمحاور لمنظومة وكلاء Odoo HR.<br>
                يمكنك كتابة استفسارك أو أمر العمل، أو إرفاق ملف Excel عبر زر «إرفاق Excel» لبدء فحص جاف محكوم فوراً.
              </div>
            </div>
          </div>
          <div id="typingIndicator" class="typing-indicator msg-bubble msg-assistant" role="status" aria-label="سراج يكتب الرد" aria-live="polite">
            <div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">
              <img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/images/svg/seraj.svg';">
            </div>
            <div class="typing-dots">
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
            </div>
          </div>
        `;
      }

      const activeBadge = document.getElementById("activeOpIdBadge");
      if (activeBadge) activeBadge.textContent = "—";
      const activeStatus = document.getElementById("activeOpStatusBadge");
      if (activeStatus) {
        activeStatus.textContent = "جاهز";
        activeStatus.className = "badge badge-neutral";
      }
      const serajBadge = document.getElementById("serajStateBadge");
      if (serajBadge) {
        serajBadge.textContent = "جاهز";
        serajBadge.className = "badge badge-neutral";
      }

      resetAllAgentsToIdle();
      const input = document.getElementById("chatInput");
      if (input) {
        input.value = "";
        autoResizeTextarea(input);
        input.focus();
      }
    }


    function toggleChatFocusWidth() {
      const grid = document.querySelector(".cockpit-grid");
      if (!grid) return;
      const isExp = grid.classList.toggle("is-workflow-expanded");
      if (isExp) grid.classList.remove("is-chat-expanded");
      const texts = document.querySelectorAll(".btn-toggle-wf-text");
      texts.forEach(t => {
        t.textContent = isExp ? "استعادة العرض ⤡" : "توسيع المساحة ⤢";
      });
      const chatBtn = document.getElementById("btnToggleChatWidth");
      if (chatBtn && isExp) chatBtn.classList.remove("is-active");
      try { localStorage.setItem("workflow_expanded_pref", isExp ? "1" : "0"); } catch (_) { }
    }

    function initTimelineResize() {
      const tl = document.getElementById("timelineContainer");
      const card = document.getElementById("agentTimeline");
      if (!tl || !card || card.querySelector(".timeline-resize-handle")) return;

      const handle = document.createElement("div");
      handle.className = "timeline-resize-handle";
      handle.title = "اسحب للأسفل لتمديد سجل التتبع الزمني • انقر مرتين لإعادة الضبط";
      handle.setAttribute("role", "separator");
      handle.setAttribute("aria-orientation", "horizontal");
      handle.setAttribute("aria-label", "مقبض تغيير ارتفاع سجل التتبع الزمني");
      handle.innerHTML = '<div class="timeline-resize-grip"></div>';
      card.appendChild(handle);

      const savedH = localStorage.getItem("agent_timeline_height");
      if (savedH && !isNaN(savedH)) {
        tl.style.setProperty("max-height", savedH + "px", "important");
        tl.style.setProperty("height", savedH + "px");
      }

      let startPageY = 0, startH = 0, isDragging = false;

      function getPageY(e) {
        if (e.touches && e.touches.length > 0) {
          return (typeof e.touches[0].pageY !== 'undefined') ? e.touches[0].pageY : (e.touches[0].clientY + window.scrollY);
        }
        return (typeof e.pageY !== 'undefined') ? e.pageY : (e.clientY + window.scrollY);
      }

      function onStart(e) {
        isDragging = true;
        startPageY = getPageY(e);
        startH = tl.getBoundingClientRect().height;
        tl.classList.add("is-resizing");
        document.body.style.cursor = "ns-resize";
        document.body.style.userSelect = "none";
        handle.classList.add("is-active");

        window.addEventListener("mousemove", onMove, { passive: false });
        window.addEventListener("mouseup", onEnd);
        window.addEventListener("touchmove", onMove, { passive: false });
        window.addEventListener("touchend", onEnd);
        e.preventDefault();
      }

      function onMove(e) {
        if (!isDragging) return;
        const delta = getPageY(e) - startPageY;
        const newH = Math.max(380, Math.min(1800, Math.round(startH + delta)));
        tl.style.setProperty("max-height", newH + "px", "important");
        tl.style.setProperty("height", newH + "px");
        e.preventDefault();
      }

      function onEnd() {
        if (!isDragging) return;
        isDragging = false;
        tl.classList.remove("is-resizing");
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        handle.classList.remove("is-active");

        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onEnd);
        window.removeEventListener("touchmove", onMove);
        window.removeEventListener("touchend", onEnd);

        const finalH = Math.round(tl.getBoundingClientRect().height);
        try { localStorage.setItem("agent_timeline_height", finalH); } catch (_) { }
      }

      handle.addEventListener("mousedown", onStart);
      handle.addEventListener("touchstart", onStart, { passive: false });
      handle.addEventListener("dblclick", function () {
        try { localStorage.removeItem("agent_timeline_height"); } catch (_) { }
        tl.style.removeProperty("max-height");
        tl.style.removeProperty("height");
      });
    }

    function toggleChatFocusWidth() {
      const cockpitGrid = document.querySelector(".cockpit-grid");
      const btn = document.getElementById("btnToggleChatWidth");
      if (!cockpitGrid) return;
      const isExpanded = cockpitGrid.classList.toggle("is-chat-expanded");
      if (btn) {
        btn.classList.toggle("is-active", isExpanded);
        btn.setAttribute(
          "title",
          isExpanded ? "استعادة العرض الافتراضي" : "توسيع مساحة المحادثة",
        );
        btn.setAttribute(
          "aria-label",
          isExpanded ? "استعادة العرض الافتراضي" : "توسيع مساحة المحادثة",
        );
      }
    }

    function toggleQuickPromptsModal(show) {
      const overlay = document.getElementById("quickPromptsModalOverlay");
      if (!overlay) return;
      if (show === undefined) {
        show = overlay.style.display === "none";
      }
      overlay.style.display = show ? "flex" : "none";
    }

    function insertQuickPromptText(text) {
      toggleQuickPromptsModal(false);
      const input = document.getElementById("chatInput");
      if (input) {
        input.value = text;
        autoResizeTextarea(input);
        input.focus();
      }
    }

    function showTypingIndicator() {
      hideTypingIndicator();
      const el = document.createElement("div");
      el.id = "typingIndicator";
      el.className = "typing-indicator msg-bubble msg-assistant is-visible";
      el.setAttribute("role", "status");
      el.setAttribute("aria-label", "سراج يكتب الرد");
      el.setAttribute("aria-live", "polite");
      el.innerHTML =
        '<div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);"><img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src=\'/images/svg/seraj.svg\';"></div>' +
        '<div class="msg-content-wrapper"><div class="msg-card" style="padding: 10px 14px;"><div class="typing-dots"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div></div>';
      const container = document.getElementById("chatMessages");
      if (container) {
        container.appendChild(el);
        container.scrollTop = container.scrollHeight;
      }
    }

    function hideTypingIndicator() {
      const container = document.getElementById("chatMessages");
      if (container) {
        const indicators = container.querySelectorAll("#typingIndicator, .typing-indicator, .typing-dots");
        indicators.forEach((el) => {
          const bubble = el.closest(".typing-indicator, .msg-bubble.is-visible");
          if (bubble && bubble.parentNode) {
            bubble.parentNode.removeChild(bubble);
          } else if (el.parentNode && el.id === "typingIndicator") {
            el.parentNode.removeChild(el);
          }
        });
      }
      document.querySelectorAll("#typingIndicator, .typing-indicator, .typing-dots").forEach((el) => {
        el.classList.remove("is-visible");
        el.style.setProperty("display", "none", "important");
        if (el.parentNode && (el.id === "typingIndicator" || el.classList.contains("typing-indicator"))) {
          el.parentNode.removeChild(el);
        }
      });
      setSerajIdle();
    }

    function autoResizeTextarea(el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 140) + "px";
    }

    // =========================================================================
    // 9. REAL-TIME EVENT STREAMING & ROBUST POLLING (NO ARBITRARY 30S TIMEOUT)
    // =========================================================================
    function startLiveEventPolling(opId) {
      if (!opId) return;
      if (pollingInterval) clearInterval(pollingInterval);
      lastEventSequence = 0;
      streamConsecutiveErrors = 0;
      setStreamConnected(true, "المتابعة نشطة ومستمرة");

      let snapshotCycleCounter = 0;

      pollingInterval = setInterval(async () => {
        if (opId !== currentOperationId) return;
        try {
          // A. Fetch incremental events since last sequence
          const res = await apiFetch(
            `/api/agents/operations/${opId}/events?after=${lastEventSequence}`,
          );
          if (res.status === 404) {
            clearInterval(pollingInterval);
            pollingInterval = null;
            resetAllAgentsToIdle();
            setStreamConnected(false, "انتهت العملية أو تم تحديث الخادم");
            hideTypingIndicator();
            return;
          }
          const data = await res.json();
          if (opId !== currentOperationId) return;
          let op = null;

          if (data.status === "success") {
            streamConsecutiveErrors = 0;

            if (data.events && data.events.length > 0) {
              data.events.forEach((evt) => {
                lastEventSequence = Math.max(
                  lastEventSequence,
                  evt.sequence || 0,
                );
              });
              const opRes = await apiFetch(`/api/agents/operations/${opId}`);
              if (opRes.status === 404) {
                clearInterval(pollingInterval);
                pollingInterval = null;
                resetAllAgentsToIdle();
                setStreamConnected(false, "انتهت العملية أو تم تحديث الخادم");
                hideTypingIndicator();
                return;
              }
              const opData = await opRes.json();
              if (opId !== currentOperationId) return;
              if (opData.status === "success" && opData.operation) {
                op = opData.operation;
                updateProcessStepper(op.events || []);
                updateOperationBadges(op);
              }
            } else {
              // Periodic snapshot verification every 4 cycles (~6s) to ensure ground truth
              snapshotCycleCounter++;
              if (snapshotCycleCounter % 4 === 0) {
                const opRes = await apiFetch(
                  `/api/agents/operations/${opId}`,
                );
                if (opRes.status === 404) {
                  clearInterval(pollingInterval);
                  pollingInterval = null;
                  resetAllAgentsToIdle();
                  setStreamConnected(
                    false,
                    "انتهت العملية أو تم تحديث الخادم",
                  );
                  hideTypingIndicator();
                  return;
                }
                const opData = await opRes.json();
                if (opId !== currentOperationId) return;
                if (opData.status === "success" && opData.operation) {
                  op = opData.operation;
                  updateOperationBadges(op);
                }
              }
            }

            // B. Strictly terminate ONLY when reaching a confirmed terminal state
            const terminalStatuses = [
              "completed",
              "failed",
              "cancelled",
              "inconclusive",
            ];
            if (op) currentOperationStatus = op.status;
            const isTerminal =
              (op && terminalStatuses.includes(op.status)) ||
              data.is_active === false;

            if (isTerminal) {
              clearInterval(pollingInterval);
              pollingInterval = null;
              resetAllAgentsToIdle();

              if (!op) {
                try {
                  const finalOpRes = await apiFetch(
                    `/api/agents/operations/${opId}`,
                  );
                  const finalOpData = await finalOpRes.json();
                  if (
                    finalOpData.status === "success" &&
                    finalOpData.operation
                  ) {
                    op = finalOpData.operation;
                  }
                } catch (e) {
                  console.warn("Could not fetch final op snapshot", e);
                }
              }

              if (op) {
                updateProcessStepper(op.events || []);
                updateOperationBadges(op);
              }
              setStreamConnected(true, "اكتملت العملية");
              hideTypingIndicator();
              return;
            }

            // NOTE: If no events arrive for 30s or longer, do NOT declare completion!
            // The operation is still tracked until confirmed terminal state.
            setStreamConnected(true, "المتابعة نشطة ومستمرة");
          } else {
            throw new Error(data.detail || "تعذر استلام بيانات المتابعة");
          }
        } catch (err) {
          streamConsecutiveErrors++;
          hideTypingIndicator();
          setStreamConnected(
            false,
            `انقطع الاتصال بالمتابعة (${err.message})`,
          );
          if (streamConsecutiveErrors >= 8) {
            clearInterval(pollingInterval);
            pollingInterval = null;
            showStreamRecoveryOption(opId);
          }
        }
      }, 1500);
    }

    function setStreamConnected(isConnected, customText) {
      const badge = document.getElementById("liveStreamBadge");
      const text = document.getElementById("streamStatusText");
      if (!badge || !text) return;
      if (isConnected) {
        badge.className = "stream-status-pill";
        text.textContent = customText || "البث متصل";
      } else {
        badge.className = "stream-status-pill is-disconnected";
        text.textContent = customText || "تعذر تحديث الحالة";
      }
    }

    function showStreamRecoveryOption(opId) {
      const badge = document.getElementById("liveStreamBadge");
      const text = document.getElementById("streamStatusText");
      if (badge && text) {
        badge.className = "stream-status-pill is-disconnected";
        text.innerHTML = `انقطع الاتصال بالمتابعة • <a href="javascript:void(0)" onclick="resumeLiveEventPolling('${opId}')" style="color:var(--color-amber);text-decoration:underline;font-weight:700;">استئناف المتابعة</a>`;
      }
    }

    function resumeLiveEventPolling(opId) {
      streamConsecutiveErrors = 0;
      setStreamConnected(true, "جاري استئناف المتابعة…");
      startLiveEventPolling(opId || currentOperationId);
    }

    let hitlCountdownTimer = null;
    let hitlRemainingSeconds = 300; // 5-minute Approval TTL

    function updateCockpitTelemetry(events, activeAgent, op) {
      const evtList = events || [];
      const loopCount = Math.min(
        5,
        Math.max(1, Math.ceil(evtList.length / 2)),
      );
      const loopEl = document.getElementById("cockpitLoopCounter");
      if (loopEl)
        loopEl.textContent = `${evtList.length > 0 ? loopCount : 0} / 5`;

      const estimatedTokens = Math.min(8192, 1200 + evtList.length * 340);
      const tokenEl = document.getElementById("cockpitContextTokens");
      if (tokenEl)
        tokenEl.textContent = `${estimatedTokens.toLocaleString("en-US")} / 8,192 Tokens`;
      const tokenBar = document.getElementById("pillarContextBar");
      if (tokenBar)
        tokenBar.style.width = `${Math.min(100, Math.round((estimatedTokens / 8192) * 100))}%`;

      // Update Agent Cognitive Status in 21st.dev Dock Header
      const thoughtStrip = document.getElementById("agentThoughtStreamStrip");
      if (thoughtStrip) {
        thoughtStrip.style.display = "none"; // Cleanly hidden to prevent unstyled text spill
      }
      const dockStatusText =
        document.getElementById("dockGlobalStatusText") ||
        document.getElementById("dockStatusText");
      const routeTarget = document.getElementById("route-step-target");
      if (
        evtList.length > 0 &&
        op &&
        op.status !== "completed" &&
        op.status !== "failed" &&
        op.status !== "cancelled"
      ) {
        const latest = evtList[evtList.length - 1];
        const agentKey = latest.agent || activeAgent || "seraj";
        const meta = AGENTS_META[agentKey] || {
          name_ar: agentKey,
          color: "var(--color-phosphor-green)",
        };
        if (dockStatusText) {
          dockStatusText.textContent = `${meta.name_ar}: ${latest.action || latest.status_label || "يعالج الطلب..."}`;
        }
        if (routeTarget) {
          routeTarget.textContent = meta.name_ar;
          routeTarget.classList.add("active");
        }
        // Highlight active agent card and status dot
        document
          .querySelectorAll(".agent-character-card")
          .forEach((c) => c.classList.remove("is-active"));
        const activeCard = document.getElementById(`agentCard_${agentKey}`);
        if (activeCard) activeCard.classList.add("is-active");
        const activeDot = document.getElementById(
          `agentStatusDot_${agentKey}`,
        );
        if (activeDot) {
          activeDot.style.background = meta.color;
          activeDot.style.boxShadow = `0 0 8px ${meta.color}`;
        }
      } else {
        if (dockStatusText) {
          dockStatusText.textContent =
            op && op.status === "completed"
              ? "اكتملت العملية بنجاح"
              : "متصل وجاهز للتشغيل";
        }
        if (routeTarget) {
          routeTarget.textContent = "الوكيل المختص";
          routeTarget.classList.remove("active");
        }
        if (
          op &&
          (op.status === "completed" ||
            op.status === "failed" ||
            op.status === "cancelled")
        ) {
          hideHitlGate();
        }
      }
    }

    function showHitlGate(opId, acceptedCount, rejectedCount) {
      if (!window.hrReferenceOptions || !window.hrReferenceOptions.departments || window.hrReferenceOptions.departments.length === 0) {
        loadHrReferenceOptions();
      }
      const banner = document.getElementById("hitlApprovalGateBanner");
      if (!banner) return;
      const accEl = document.getElementById("hitlAcceptedCount");
      const rejEl = document.getElementById("hitlRejectedCount");
      const refEl = document.getElementById("hitlOpIdRef");
      if (accEl) accEl.textContent = acceptedCount || 0;
      if (rejEl) rejEl.textContent = rejectedCount || 0;
      if (refEl) refEl.textContent = opId || currentOperationId || "OP-REQ";
      const addBtn = document.getElementById("btnHitlAddField");
      if (addBtn) addBtn.style.display = "inline-flex";
      const subTitle = document.getElementById("hitlGateSubtitle");
      if (subTitle) {
        subTitle.textContent = "اكتمل تدقيق وفحص البيانات. تقتضي سياسة الأمان توقيعك البشري الصريح قبل سماح «حارس» لـ «كاتب» بتعديل قاعدة Odoo:";
      }
      const confirmBtn = banner.querySelector(".btn-approval-confirm");
      const denyBtn = banner.querySelector(".btn-approval-deny");
      if (confirmBtn) {
        confirmBtn.style.opacity = "1";
        confirmBtn.style.pointerEvents = "auto";
      }
      if (denyBtn) {
        denyBtn.style.opacity = "1";
        denyBtn.style.pointerEvents = "auto";
      }
      banner.style.setProperty("display", "block", "important");
      banner.style.visibility = "visible";
      banner.style.opacity = "1";
      banner.classList.add("is-visible");
      startHitlCountdown(300); // 5-minute Approval TTL
    }

    function hideHitlGate() {
      const banner = document.getElementById("hitlApprovalGateBanner");
      if (banner) {
        banner.style.setProperty("display", "none", "important");
        banner.classList.remove("is-visible");
      }
      if (hitlCountdownTimer) {
        clearInterval(hitlCountdownTimer);
        hitlCountdownTimer = null;
      }
      const timerEl = document.getElementById("hitlTtlCountdown");
      if (timerEl) {
        timerEl.textContent = "05:00";
        timerEl.style.color = "var(--color-silver-mist)";
      }
      const tbody = document.getElementById("hitlDiffTableBody");
      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--color-smoke); text-align: center; padding: 14px;">لا توجد تعديلات معلقة</td></tr>';
      }
      const addBtn = document.getElementById("btnHitlAddField");
      if (addBtn) addBtn.style.display = "none";
      const planCodeBadge = document.getElementById("hitlPlanCodeBadge");
      if (planCodeBadge) planCodeBadge.textContent = "";

      window.currentHitlPendingAction = null;
      window.currentHitlPendingValues = {};
    }

    function startHitlCountdown(durationSec) {
      if (hitlCountdownTimer) clearInterval(hitlCountdownTimer);
      hitlRemainingSeconds = durationSec;
      const timerEl = document.getElementById("hitlTtlCountdown");

      function tick() {
        const m = Math.floor(hitlRemainingSeconds / 60);
        const s = hitlRemainingSeconds % 60;
        const fmt = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
        if (timerEl) {
          timerEl.textContent = fmt;
          if (hitlRemainingSeconds <= 60) {
            timerEl.style.color = "var(--color-coral)";
          } else {
            timerEl.style.color = "var(--color-amber)";
          }
        }
        if (hitlRemainingSeconds <= 0) {
          clearInterval(hitlCountdownTimer);
          hitlCountdownTimer = null;
          if (timerEl) timerEl.textContent = "00:00 (انتهت الصلاحية)";
          alert(
            "انتهت صلاحية إذن الاعتماد (5 دقائق TTL). يرجى إعادة فحص وتدقيق العملية.",
          );
          hideHitlGate();
        }
        hitlRemainingSeconds--;
      }

      tick();
      hitlCountdownTimer = setInterval(tick, 1000);
    }

    // =========================================================================
    // =========================================================================
    // HITL INTERACTIVE GATE & LIVE PARAMETER DIFF TABLE (WITH LIVE ODOO OPTIONS)
    // =========================================================================
    window.currentHitlPendingAction = null;
    window.currentHitlPendingValues = {};
    window.hrReferenceOptions = {
      departments: [],
      jobs: [],
      genders: [{ id: "male", name: "ذكر" }, { id: "female", name: "أنثى" }],
      marital_statuses: [
        { id: "single", name: "أعزب / عزباء" },
        { id: "married", name: "متزوج / متزوجة" },
        { id: "divorced", name: "مطلق / مطلقة" },
        { id: "widower", name: "أرمل / أرملة" }
      ]
    };

    const HR_FIELD_METADATA = {
      name: { label: "اسم الموظف الكامل", type: "text", placeholder: "الاسم الكامل للموظف" },
      department_id: { label: "القسم / الإدارة", type: "select_department", placeholder: "اختر القسم المعتمد في Odoo..." },
      job_title: { label: "المسمى الوظيفي", type: "datalist_job", placeholder: "اختر أو اكتب المسمى الوظيفي..." },
      work_email: { label: "البريد الإلكتروني للعمل", type: "email", placeholder: "name@company.com" },
      work_phone: { label: "رقم الهاتف / الجوال", type: "tel", placeholder: "05xxxxxxxx" },
      gender: { label: "الجنس", type: "select_gender", placeholder: "اختر الجنس..." },
      marital: { label: "الحالة الاجتماعية", type: "select_marital", placeholder: "اختر الحالة الاجتماعية..." },
      work_permit_no: { label: "رقم الهوية الوطنية / الإقامة", type: "text", placeholder: "10 أرقام (هوية أو إقامة)" },
      birthday: { label: "تاريخ الميلاد", type: "date", placeholder: "YYYY-MM-DD" },
      notes: { label: "ملاحظات إدارية", type: "text", placeholder: "أي ملاحظات إدارية إضافية..." }
    };

    const HR_AVAILABLE_ADDABLE_FIELDS = [
      { key: "department_id", label: "القسم / الإدارة", icon: "🏢", desc: "تنسيب الموظف لإدارة معتمدة في Odoo" },
      { key: "job_title", label: "المسمى الوظيفي", icon: "💼", desc: "المسمى الوظيفي الرسمي للموظف" },
      { key: "work_email", label: "البريد الإلكتروني للعمل", icon: "📧", desc: "البريد الرسمي للموظف" },
      { key: "work_phone", label: "رقم الهاتف / الجوال", icon: "📱", desc: "رقم الاتصال المعتمد" },
      { key: "gender", label: "الجنس (ذكر / أنثى)", icon: "⚧", desc: "تحديد الجنس في ملف الموظف" },
      { key: "marital", label: "الحالة الاجتماعية", icon: "💍", desc: "أعزب، متزوج، مطلق، أرمل" },
      { key: "work_permit_no", label: "الهوية الوطنية / الإقامة", icon: "🆔", desc: "رقم السجل المدني أو هوية مقيم" },
      { key: "birthday", label: "تاريخ الميلاد", icon: "📅", desc: "تاريخ الميلاد الرسمي للموظف" },
      { key: "notes", label: "ملاحظات إدارية", icon: "📝", desc: "ملاحظات إضافية على ملف الموظف" }
    ];

    async function loadHrReferenceOptions() {
      try {
        const res = await apiFetch("/api/reference/hr-options");
        const data = await res.json();
        if (data.status === "success") {
          window.hrReferenceOptions = data;
          if (window.currentHitlPendingAction) {
            renderHitlDiffTable(window.currentHitlPendingAction);
          }
        }
      } catch (err) {
        console.warn("Could not load HR reference options:", err);
      }
    }

    function renderHitlInputField(key, val, meta) {
      if (key === "department_id") {
        const deps = window.hrReferenceOptions?.departments || [];
        return `
          <select class="form-control hitl-live-select" 
                  onchange="handleHitlValueChange('department_id', this.value)" 
                  style="height: 34px; font-size: 12.5px; padding: 4px 8px; width: 100%; background: var(--paper-2); border: 1px solid var(--rule); border-radius: 4px; color: var(--text);">
            <option value="">-- اختر القسم المعتمد في Odoo (${deps.length} متاح) --</option>
            ${deps.map(d => `
              <option value="${d.id}" ${String(val) === String(d.id) ? 'selected' : ''}>
                ${escapeHtml(d.name)} ${d.company_name ? `— [${escapeHtml(d.company_name)}]` : ''}
              </option>
            `).join('')}
          </select>
        `;
      }

      if (key === "gender") {
        const genders = window.hrReferenceOptions?.genders || [
          { id: "male", name: "ذكر" },
          { id: "female", name: "أنثى" }
        ];
        return `
          <select class="form-control hitl-live-select" 
                  onchange="handleHitlValueChange('gender', this.value)" 
                  style="height: 34px; font-size: 12.5px; padding: 4px 8px; width: 100%; background: var(--paper-2); border: 1px solid var(--rule); border-radius: 4px; color: var(--text);">
            <option value="">-- اختر الجنس --</option>
            ${genders.map(g => `<option value="${g.id}" ${String(val) === String(g.id) ? 'selected' : ''}>${escapeHtml(g.name)}</option>`).join('')}
          </select>
        `;
      }

      if (key === "marital") {
        const statuses = window.hrReferenceOptions?.marital_statuses || [
          { id: "single", name: "أعزب / عزباء" },
          { id: "married", name: "متزوج / متزوجة" },
          { id: "divorced", name: "مطلق / مطلقة" },
          { id: "widower", name: "أرمل / أرملة" }
        ];
        return `
          <select class="form-control hitl-live-select" 
                  onchange="handleHitlValueChange('marital', this.value)" 
                  style="height: 34px; font-size: 12.5px; padding: 4px 8px; width: 100%; background: var(--paper-2); border: 1px solid var(--rule); border-radius: 4px; color: var(--text);">
            <option value="">-- اختر الحالة الاجتماعية --</option>
            ${statuses.map(s => `<option value="${s.id}" ${String(val) === String(s.id) ? 'selected' : ''}>${escapeHtml(s.name)}</option>`).join('')}
          </select>
        `;
      }

      if (key === "job_title") {
        const jobs = window.hrReferenceOptions?.jobs || [];
        return `
          <div style="position: relative; width: 100%;">
            <input type="text" list="hitlJobsDatalist" class="form-control hitl-live-input" 
                   value="${escapeHtml(val)}" 
                   placeholder="اختر من وظائف Odoo أو اكتب مسمى جديد..." 
                   oninput="handleHitlValueChange('job_title', this.value)" 
                   style="height: 34px; font-size: 12.5px; padding: 4px 8px; width: 100%; background: var(--paper-2); border: 1px solid var(--rule); border-radius: 4px; color: var(--text);">
            <datalist id="hitlJobsDatalist">
              ${jobs.map(j => `<option value="${escapeHtml(j.name)}"></option>`).join('')}
            </datalist>
          </div>
        `;
      }

      if (key === "birthday") {
        return `
          <input type="date" class="form-control hitl-live-input" 
                 value="${escapeHtml(val)}" 
                 onchange="handleHitlValueChange('birthday', this.value)" 
                 style="height: 34px; font-size: 12.5px; padding: 4px 8px; width: 100%; background: var(--paper-2); border: 1px solid var(--rule); border-radius: 4px; color: var(--text);">
        `;
      }

      const inputType = key === "work_email" ? "email" : (key === "work_phone" ? "tel" : "text");
      return `
        <input type="${inputType}" class="form-control hitl-live-input" 
               value="${escapeHtml(val)}" 
               placeholder="${escapeHtml(meta.placeholder || `أدخل ${meta.label || key}...`)}" 
               oninput="handleHitlValueChange('${escapeHtml(key)}', this.value)" 
               style="height: 34px; font-size: 12.5px; padding: 4px 8px; width: 100%; background: var(--paper-2); border: 1px solid var(--rule); border-radius: 4px; color: var(--text);">
      `;
    }

    function renderHitlDiffTable(pendingAction) {
      const tbody = document.getElementById("hitlDiffTableBody");
      const planCodeBadge = document.getElementById("hitlPlanCodeBadge");
      const addBtn = document.getElementById("btnHitlAddField");
      if (!tbody) return;

      window.currentHitlPendingAction = pendingAction;

      if (!pendingAction) {
        hideHitlGate();
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--color-smoke); text-align: center; padding: 12px;">لا توجد تعديلات معلقة</td></tr>';
        if (planCodeBadge) planCodeBadge.textContent = "";
        if (addBtn) addBtn.style.display = "none";
        return;
      }

      if (addBtn) addBtn.style.display = "inline-flex";

      if (planCodeBadge && pendingAction.plan_id) {
        planCodeBadge.textContent = `خطة: ${pendingAction.plan_id}`;
      }

      // Purge any stray dummy custom_field keys
      if (window.currentHitlPendingValues) {
        Object.keys(window.currentHitlPendingValues).forEach(k => {
          if (k.startsWith("custom_field_")) {
            delete window.currentHitlPendingValues[k];
          }
        });
      }
      if (pendingAction.values) {
        Object.keys(pendingAction.values).forEach(k => {
          if (k.startsWith("custom_field_")) {
            delete pendingAction.values[k];
          }
        });
      }

      const type = pendingAction.action_type || pendingAction.type || "create";
      const empName = pendingAction.employee_name || pendingAction.record_name || pendingAction.name || "موظف جديد";

      let rowsHtml = "";

      if (type === "create") {
        const vals = pendingAction.values || {};
        if (!window.currentHitlPendingValues || Object.keys(window.currentHitlPendingValues).length === 0) {
          window.currentHitlPendingValues = {
            name: pendingAction.name || vals.name || "",
            department_id: vals.department_id || "",
            job_title: vals.job_title || "",
            work_email: vals.work_email || "",
            work_phone: vals.work_phone || ""
          };
        }

        const keys = Object.keys(window.currentHitlPendingValues);
        if (keys.length === 0) {
          window.currentHitlPendingValues.name = empName;
          keys.push("name");
        }

        keys.forEach(k => {
          const val = window.currentHitlPendingValues[k] || "";
          const meta = HR_FIELD_METADATA[k] || { label: k, placeholder: `أدخل ${k}...` };
          rowsHtml += `
            <tr data-field="${escapeHtml(k)}">
              <td class="hitl-cell-emp" style="font-weight: 600; color: var(--text);">${escapeHtml(window.currentHitlPendingValues.name || empName)}</td>
              <td style="color: var(--color-silver-mist); font-size: 12px; font-weight: 500;">${escapeHtml(meta.label)}</td>
              <td style="color: var(--color-smoke); font-size: 12px;">— (حقل جديد)</td>
              <td>
                ${renderHitlInputField(k, val, meta)}
              </td>
              <td style="text-align: center;">
                ${k !== 'name' ? `<button type="button" class="btn btn-sm" onclick="deleteHitlField('${escapeHtml(k)}')" title="حذف هذا الحقل" style="background: transparent; border: none; color: var(--color-coral); cursor: pointer; padding: 2px 6px; font-size: 13px;">✕</button>` : ''}
              </td>
            </tr>
          `;
        });
      } else if (type === "update") {
        const fieldKey = pendingAction.field || "job_title";
        const meta = HR_FIELD_METADATA[fieldKey] || { label: pendingAction.field_label || fieldKey };
        const oldVal = pendingAction.old_value || "—";
        const newVal = pendingAction.new_value || (pendingAction.values ? pendingAction.values[fieldKey] : "");

        if (!window.currentHitlPendingValues || Object.keys(window.currentHitlPendingValues).length === 0) {
          window.currentHitlPendingValues = {
            [fieldKey]: newVal
          };
        }

        const keys = Object.keys(window.currentHitlPendingValues);
        keys.forEach(k => {
          const val = window.currentHitlPendingValues[k] || "";
          const isPrimary = (k === fieldKey);
          const fMeta = HR_FIELD_METADATA[k] || { label: k, placeholder: `أدخل ${k}...` };
          rowsHtml += `
            <tr data-field="${escapeHtml(k)}">
              <td class="hitl-cell-emp" style="font-weight: 600; color: var(--text);">${escapeHtml(empName)}</td>
              <td style="color: var(--color-silver-mist); font-size: 12px; font-weight: 500;">${escapeHtml(fMeta.label)}</td>
              <td style="color: var(--color-smoke); font-size: 12px;">${isPrimary ? `<del>${escapeHtml(oldVal)}</del>` : '—'}</td>
              <td>
                ${renderHitlInputField(k, val, fMeta)}
              </td>
              <td style="text-align: center;">
                ${!isPrimary ? `<button type="button" class="btn btn-sm" onclick="deleteHitlField('${escapeHtml(k)}')" title="حذف الحقل" style="background: transparent; border: none; color: var(--color-coral); cursor: pointer; padding: 2px 6px; font-size: 13px;">✕</button>` : ''}
              </td>
            </tr>
          `;
        });
      } else if (type === "delete" || type === "archive" || type === "unarchive") {
        const actTitle = type === "archive" ? "أرشفة آمنة" : (type === "unarchive" ? "إلغاء أرشفة" : "حذف نهائي محكوم");
        const oldState = type === "unarchive" ? "مؤرشف (غير نشط)" : "نشط (active=True)";
        const newState = type === "archive" ? "مؤرشف (active=False)" : (type === "unarchive" ? "نشط (active=True)" : "حذف كلي لا يمكن التراجع عنه");

        rowsHtml = `
          <tr>
            <td style="font-weight: 600; color: var(--text);">${escapeHtml(empName)} (ID: ${escapeHtml(pendingAction.record_id || pendingAction.employee_id || '')})</td>
            <td style="color: var(--color-silver-mist); font-size: 12px;">حالة السجل (${actTitle})</td>
            <td style="color: var(--color-smoke); font-size: 12px;">${escapeHtml(oldState)}</td>
            <td style="color: var(--warn); font-weight: 600; font-size: 12.5px;">${escapeHtml(newState)}</td>
            <td></td>
          </tr>
        `;
      }

      if (!rowsHtml || !rowsHtml.trim()) {
        hideHitlGate();
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--color-smoke); text-align: center; padding: 12px;">لا توجد تعديلات معلقة</td></tr>';
        return;
      }

      tbody.innerHTML = rowsHtml;
    }

    function handleHitlValueChange(fieldKey, value) {
      if (!window.currentHitlPendingValues) window.currentHitlPendingValues = {};
      window.currentHitlPendingValues[fieldKey] = value;
      if (window.currentHitlPendingAction) {
        if (!window.currentHitlPendingAction.values) window.currentHitlPendingAction.values = {};
        window.currentHitlPendingAction.values[fieldKey] = value;
        if (fieldKey === "name") {
          window.currentHitlPendingAction.name = value;
          window.currentHitlPendingAction.record_name = value;
          window.currentHitlPendingAction.employee_name = value;
          document.querySelectorAll(".hitl-cell-emp").forEach(el => el.textContent = value || "موظف جديد");
        }
        if (fieldKey === "job_title" && window.currentHitlPendingAction.type === "update") {
          window.currentHitlPendingAction.new_value = value;
        }
      }
    }

    
    document.addEventListener("click", function(e) {
      const menu = document.getElementById("hitlFieldPickerMenu");
      const btn = document.getElementById("btnHitlAddField");
      if (menu && menu.style.display === "block") {
        if (!menu.contains(e.target) && (!btn || !btn.contains(e.target))) {
          menu.style.display = "none";
        }
      }
    });

    function toggleHitlFieldPicker() {
      const menu = document.getElementById("hitlFieldPickerMenu");
      if (!menu) return;
      if (menu.style.display === "block") {
        menu.style.display = "none";
        return;
      }

      const existingKeys = Object.keys(window.currentHitlPendingValues || {});
      const available = HR_AVAILABLE_ADDABLE_FIELDS.filter(f => !existingKeys.includes(f.key));

      if (available.length === 0) {
        menu.innerHTML = '<div style="padding: 10px; font-size: 12px; color: var(--color-silver-mist); text-align: center;">جميع الحقول المعتمدة مضافة بالفعل في الجدول.</div>';
      } else {
        menu.innerHTML = `
          <div style="font-size: 11px; font-weight: 700; color: var(--color-gold); padding: 6px 10px 8px; border-bottom: 1px solid var(--rule); margin-bottom: 4px;">
            اختر الحقل المراد إضافته إلى بيانات الموظف:
          </div>
          ${available.map(f => `
            <button type="button" onclick="addSpecificHitlField('${escapeHtml(f.key)}')" 
                    style="width: 100%; text-align: right; display: flex; align-items: center; gap: 8px; padding: 7px 8px; background: transparent; border: none; border-radius: 6px; color: var(--color-snow); cursor: pointer; font-size: 12px;" 
                    onmouseenter="this.style.background='var(--paper-3)'" 
                    onmouseleave="this.style.background='transparent'">
              <span style="font-size: 14px;">${f.icon}</span>
              <div style="flex: 1;">
                <div style="font-weight: 600;">${escapeHtml(f.label)}</div>
                <div style="font-size: 10.5px; color: var(--color-silver-mist);">${escapeHtml(f.desc)}</div>
              </div>
            </button>
          `).join('')}
        `;
      }
      menu.style.display = "block";
    }

    function addSpecificHitlField(fieldKey) {
      const menu = document.getElementById("hitlFieldPickerMenu");
      if (menu) menu.style.display = "none";

      if (!window.currentHitlPendingValues) window.currentHitlPendingValues = {};
      window.currentHitlPendingValues[fieldKey] = "";

      if (window.currentHitlPendingAction) {
        if (!window.currentHitlPendingAction.values) window.currentHitlPendingAction.values = {};
        window.currentHitlPendingAction.values[fieldKey] = "";
      }
      renderHitlDiffTable(window.currentHitlPendingAction);
    }

    function addHitlFieldRow() {
      toggleHitlFieldPicker();
    }

    function deleteHitlField(fieldKey) {
      if (window.currentHitlPendingValues) {
        delete window.currentHitlPendingValues[fieldKey];
      }
      if (window.currentHitlPendingAction && window.currentHitlPendingAction.values) {
        delete window.currentHitlPendingAction.values[fieldKey];
      }
      renderHitlDiffTable(window.currentHitlPendingAction);
    }

    async function executeHitlApproval() {
      // 1. Single Action HITL Approval (Employee Create / Update / Delete / Archive)
      if (window.currentHitlPendingAction) {
        const act = window.currentHitlPendingAction;
        const opId = currentOperationId || act.operation_id;
        const planId = act.plan_id;
        const modifiedPayload = Object.assign({}, window.currentHitlPendingValues || {});

        hideHitlGate();
        appendUserMessage("اعتماد التعديلات وقيدها في Odoo");
        showTypingIndicator();
        setSerajBusy("سراج ينفذ الأمر المعتمد عبر «كاتب»...");

        try {
          const res = await apiFetch("/api/agents/approve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: currentChatId,
              operation_id: opId,
              plan_id: planId,
              modified_payload: modifiedPayload
            }),
          });
          const data = await res.json();
          if (data.status === "success") {
            appendSerajMessage(data.response, data.pending_action, null, null, null, data.llm_meta);
            if (data.operation) {
              updateOperationBadges(data.operation);
              startTimelinePolling(opId);
            }
          } else {
            appendSerajMessage("❌ فشل تنفيذ العملية عبر «كاتب»: " + (data.detail || data.error || "خطأ غير متوقع"));
          }
        } catch (err) {
          appendSerajMessage("❌ تعذر إرسال إذن الاعتماد: " + err.message);
        } finally {
          hideTypingIndicator();
          setSerajIdle();
          window.currentHitlPendingAction = null;
          window.currentHitlPendingValues = {};
        }
        return;
      }

      // 2. Batch Conditional Execution Approval (Only when conditional batch actions card is actually active)
      const condActions = document.getElementById("conditionalActions");
      const hasBatchConditional = condActions && condActions.style.display !== "none";
      if (hasBatchConditional && typeof approveConditional === "function") {
        hideHitlGate();
        try {
          await approveConditional("execute");
        } finally {
          hideTypingIndicator();
          setSerajIdle();
        }
        return;
      }

      // 3. Fallback: No active pending plan to approve
      appendSerajMessage("ℹ️ لا توجد عملية أو تعديلات معلقة تتطلب اعتماداً حالياً. المنظومة في وضع الاستعداد.");
      hideHitlGate();
      hideTypingIndicator();
      setSerajIdle();
    }

    async function executeHitlAutoFix() {
      hideHitlGate();
      if (typeof approveConditional === "function") {
        await approveConditional("fix");
      }
    }

    async function executeHitlCancel() {
      hideHitlGate();
      if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
      }
      currentOperationStatus = "cancelled";

      if (window.currentHitlPendingAction) {
        const act = window.currentHitlPendingAction;
        const opId = currentOperationId || act.operation_id;

        appendUserMessage("إلغاء الأمر");
        showTypingIndicator();
        setSerajBusy("سراج يوثق إلغاء العملية...");

        try {
          const res = await apiFetch("/api/agents/cancel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: currentChatId,
              operation_id: opId
            }),
          });
          const data = await res.json();
          appendSerajMessage(data.response || "🚫 تم إلغاء العملية بناءً على طلبك، ولم يتم إجراء أي تعديل أو كتابة في Odoo.");
          if (data.operation) {
            updateOperationBadges(data.operation);
            updateProcessStepper(data.operation.events || [], data.operation);
          }
        } catch (err) {
          appendSerajMessage("🚫 تم إلغاء الأمر محلياً.");
        } finally {
          hideTypingIndicator();
          setSerajIdle();
          window.currentHitlPendingAction = null;
          window.currentHitlPendingValues = {};
          if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
          }
          currentOperationStatus = "cancelled";
        }
        return;
      }

      const condActions = document.getElementById("conditionalActions");
      const hasBatchConditional = condActions && condActions.style.display !== "none";
      if (hasBatchConditional && typeof approveConditional === "function") {
        try {
          await approveConditional("cancel");
        } finally {
          hideTypingIndicator();
          setSerajIdle();
        }
        return;
      }

      appendSerajMessage("ℹ️ لا توجد عملية نشطة لإلغائها.");
      hideTypingIndicator();
      setSerajIdle();
    }

    function togglePillarsExpansion() {
      const grid = document.getElementById("pillarsGridContainer");
      const text = document.getElementById("togglePillarsText");
      if (!grid) return;
      const isHidden = grid.style.display === "none" || !grid.style.display;
      if (isHidden) {
        grid.style.display = "grid";
        if (text) text.textContent = "طي البطاقات ▴";
      } else {
        grid.style.display = "none";
        if (text) text.textContent = "توسيع البطاقات ▾";
      }
    }

    function openPillarDetails(pillarKey) {
      const overlay = document.getElementById("detailsDrawerOverlay");
      const title = document.getElementById("drawerTitle");
      const subtitle = document.getElementById("drawerSubtitle");
      const body = document.getElementById("drawerBody");
      const sheet = overlay ? overlay.querySelector(".drawer-sheet") : null;
      if (!overlay || !body) return;
      if (sheet) sheet.classList.add("is-wide");

      if (pillarKey === "prompt") {
        title.textContent =
          "الركيزة 01: Prompt Engineering — هندسة الأوامر وتخصيص هوية الوكلاء";
        subtitle.textContent = "System Prompts & Strict Agent Boundaries";
        body.innerHTML = `
          <div style="background: var(--paper-2); padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
            <div style="font-size: 14px; font-weight: 700; color: var(--color-snow); margin-bottom: 8px;">هندسة وتوجيه هوية الوكلاء الـ 8 المستقلين</div>
            <p style="color: var(--color-silver-mist); line-height: 1.6; margin: 0;">
              لكل وكيل في المنظومة موجه نظام صارم (System Prompt) يحدد دوره واختصاصه ويمنع التداخل أو تجاوز الصلاحيات المعمارية. لا يوجد وكيل واحد يقوم بكل شيء.
            </p>
          </div>
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px;">
            <div style="background: var(--paper-2); padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
              <div style="font-weight: 700; color: var(--agent-seraj); margin-bottom: 4px;">«سراج» — المنسق والمحاور العام</div>
              <div style="font-size: 12px; color: var(--color-silver-mist);">إدارة الحوار مع المستخدم، تفكيك الطلبات، توجيه الأوامر للوكلاء، وشرح النتائج بلغة طبيعية. يُحظر عليه الكتابة المباشرة في Odoo.</div>
            </div>
            <div style="background: var(--paper-2); padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
              <div style="font-weight: 700; color: var(--agent-fahas); margin-bottom: 4px;">«فاحص» — التدقيق والاستعلام المسبق</div>
              <div style="font-size: 12px; color: var(--color-silver-mist);">فحص قوالب Excel، قراءة بيانات Odoo الحالية فقط (Read-Only)، واكتشاف التكرارات قبل أي خطوة تنفيذ.</div>
            </div>
            <div style="background: var(--paper-2); padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
              <div style="font-weight: 700; color: var(--agent-modaqeq); margin-bottom: 4px;">«مدقق» — حارس الامتثال لنظام العمل</div>
              <div style="font-size: 12px; color: var(--color-silver-mist);">تدقيق البيانات ضد مواد نظام العمل السعودي (ساعات رمضان المادة 98، نسب التوطين المادة 36، الأجور والبدلات).</div>
            </div>
            <div style="background: var(--paper-2); padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
              <div style="font-weight: 700; color: var(--agent-katib); margin-bottom: 4px;">«كاتب» — المنفذ الحصري في Odoo</div>
              <div style="font-size: 12px; color: var(--color-silver-mist);">الوكيل الوحيد المخول بالكتابة في قاعدة البيانات. لا يعمل إلا بعد اجتياز التدقيق المسبق وتوقيع بوابة الاعتماد البشري (HITL).</div>
            </div>
          </div>
        `;
      } else if (pillarKey === "context") {
        title.textContent =
          "الركيزة 02: Context Engineering — هندسة السياق وحقن المعرفة (RAG)";
        subtitle.textContent =
          "Dynamic Context Window & Saudi Labor Law Injection";
        body.innerHTML = `
          <div style="background: var(--paper-2); padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <span style="font-size: 14px; font-weight: 700; color: var(--color-snow);">استهلاك نافذة السياق (Context Window)</span>
              <span class="mono" style="color: var(--color-phosphor-green); font-weight: 700;">1,420 / 8,192 Tokens</span>
            </div>
            <div style="height: 8px; background: var(--color-ash); border-radius: 9999px; overflow: hidden; margin-bottom: 10px;">
              <div style="width: 17%; height: 100%; background: var(--color-phosphor-green);"></div>
            </div>
            <p style="font-size: 12.5px; color: var(--color-silver-mist); margin: 0;">
              تتم إدارة السياق عبر ضغط واسترجاع ذكي لمنع الهلوسة ولضمان بقاء النموذج داخل نافذة الاستدلال الدقيقة دون إهدار الموارد.
            </p>
          </div>
          <div style="background: var(--paper-2); padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
            <div style="font-size: 14px; font-weight: 700; color: var(--color-snow); margin-bottom: 10px;">مواد نظام العمل السعودي المحقونة تلقائياً في RAG</div>
            <ul style="list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; font-size: 12.5px; color: var(--color-silver-mist);">
              <li style="padding: 8px 12px; background: var(--paper-2); border-radius: 6px; border-right: 3px solid var(--color-phosphor-green);">
                <strong style="color: var(--color-snow);">المادة 98:</strong> تخفيض ساعات العمل الفعلية في شهر رمضان المبارك للمسلمين إلى (6) ساعات يومياً أو (36) ساعة أسبوعياً.
              </li>
              <li style="padding: 8px 12px; background: var(--paper-2); border-radius: 6px; border-right: 3px solid var(--color-phosphor-green);">
                <strong style="color: var(--color-snow);">المادة 36:</strong> حظر تشغيل غير السعوديين في المهن المقصورة حصرياً على المواطنين (التوطين).
              </li>
              <li style="padding: 8px 12px; background: var(--paper-2); border-radius: 6px; border-right: 3px solid var(--color-phosphor-green);">
                <strong style="color: var(--color-snow);">المادة 77:</strong> ضوابط التعويض في حال إنهاء العقد من أحد الطرفين لسبب غير مشروع.
              </li>
            </ul>
          </div>
        `;
      } else if (pillarKey === "loop") {
        title.textContent =
          "الركيزة 03: Loop Engineering — الحلقات المستقلة وكابح الأمان";
        subtitle.textContent = "Autonomous ReAct Cycles & Safety Loop Brake";
        body.innerHTML = `
          <div style="background: var(--paper-2); padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
            <div style="font-size: 14px; font-weight: 700; color: var(--color-snow); margin-bottom: 8px;">دورة التفكير والتصحيح الذاتي (Perception → Plan → Act → Reflect)</div>
            <p style="color: var(--color-silver-mist); line-height: 1.6; margin: 0 0 12px 0;">
              يعمل الوكلاء ضمن حلقة تفكير ذاتية؛ عند وجود خطأ في ملف الموظفين يقوم «مصلح» باقتراح تصحيح آلي واختباره، وإذا لم ينجح يعود للتفكير والتصحيح مجدداً.
            </p>
            <div style="background: var(--paper-2); padding: 12px; border-radius: 8px; font-family: var(--font-mono); font-size: 12px; color: var(--color-amber); text-align: center;">
              إدراك (Perceive) 🡰 تخطيط (Plan) 🡰 تدقيق (Verify) 🡰 تنفيذ (Execute) 🡰 انعكاس (Reflect)
            </div>
          </div>
          <div style="background: var(--paper-2); padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
            <div style="font-size: 14px; font-weight: 700; color: var(--color-amber); margin-bottom: 6px;">كابح الأمان (Safety Loop Brake — Max 5 Loops)</div>
            <p style="font-size: 12.5px; color: var(--color-silver-mist); line-height: 1.5; margin: 0;">
              لحماية المنظومة من الحلقات اللانهائية وهدر الاستهلاك، يتم تطبيق حد أقصى صارم (5 دورات). إذا لم تكتمل العملية خلالها يتم إيقافها فوراً وتصعيدها للمشغّل البشري مع تقرير تفصيلي.
            </p>
          </div>
        `;
      } else if (pillarKey === "harness") {
        title.textContent =
          "الركيزة 04: Harness Engineering — بيئة التحكم وبوابة الاعتماد وسجل التدقيق";
        subtitle.textContent =
          "EnvironmentGuard, 5-Minute HITL TTL Gate & Forensic Sijil Ledger";
        body.innerHTML = `
          <div style="background: var(--paper-2); padding: 16px; border-radius: 12px; border: 1px solid var(--agent-hares); margin-bottom: 8px;">بوابة الاعتماد البشري بصلاحية 5 دقائق (5-Minute Approval TTL)</div>
            <p style="color: var(--color-silver-mist); line-height: 1.6; margin: 0;">
              تم تفعيل سياسة الحوكمة الصارمة: أي اعتماد كتابة يتم توليده يكون صالحاً لمدة 300 ثانية فقط لمنع ثغرات Time-of-Check to Time-of-Use (TOCTOU). بعد انتهاء المهلة يرفض «كاتب» التنفيذ تلقائياً.
            </p>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <div style="background: var(--paper-2); padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
              <div style="font-weight: 700; color: var(--color-snow); margin-bottom: 6px;">عزل الصلاحيات ورمز المشغل</div>
              <div style="font-size: 12px; color: var(--color-silver-mist); line-height: 1.5;">حظر الرموز الافتراضية غير الآمنة (رفض فوري برمز HTTP 503)، والتأكد من تطابق X-API-Key مع صلاحيات الشركة المحددة.</div>
            </div>
            <div style="background: var(--paper-2); padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
              <div style="font-weight: 700; color: var(--agent-sijil); margin-bottom: 6px;">دفتر «سجل» اللاتراجعي</div>
              <div style="font-size: 12px; color: var(--color-silver-mist); line-height: 1.5;">تسجيل كل قرار وحركة وكيل وبصمة SHA-256 في ملف agent_operations_log.jsonl مع استحالة التعديل أو التراجع اليدوي.</div>
            </div>
          </div>
        `;
      }
      overlay.classList.add("is-open");
    }

    function updateOperationBadges(op) {
      if (!op) return;
      currentOperationStatus = op.status || op.final_status_code;
      window.currentOperationObj = op;
      window.currentActiveAgent = op.active_agent;
      if (currentOperationId) {
        const url = new URL(window.location.href);
        url.searchParams.set("operation", currentOperationId);
        window.history.replaceState(null, "", url);
      }
      const stBadge = document.getElementById("activeOpStatusBadge");
      const agBadge = document.getElementById("activeOpAgentBadge");
      if (stBadge) {
        stBadge.textContent =
          op.status_label || STATUS_MAP_AR[op.status] || op.status;
        const isOpDone = (op.status === "completed" || op.status === "approved" || op.status === "success");
        const isOpFail = (op.status === "failed" || op.status === "error");
        stBadge.className = `badge ${isOpDone ? "badge-success" : isOpFail ? "badge-error" : "badge-warning"}`;
      }
      if (agBadge) agBadge.textContent = op.active_agent || "سراج";

      document
        .querySelectorAll(".agent-character-card")
        .forEach((c) => c.classList.remove("is-active"));
      if (
        op.active_agent &&
        op.status !== "completed" &&
        op.status !== "failed"
      ) {
        const card = document.getElementById(`agentCard_${op.active_agent}`);
        if (card) card.classList.add("is-active");
      }

      // Update 21st.dev Routing Pipeline Strip & Global Dock Status
      const targetStep = document.getElementById("route-step-target");
      const globalText = document.getElementById("dockGlobalStatusText");
      if (targetStep) {
        if (
          op.active_agent &&
          op.active_agent !== "seraj" &&
          op.status !== "completed" &&
          op.status !== "failed"
        ) {
          const meta = AGENTS_META[op.active_agent];
          targetStep.textContent = meta ? meta.name_ar : op.active_agent;
          targetStep.classList.add("active");
        } else {
          targetStep.textContent = "الوكيل المختص";
          targetStep.classList.remove("active");
        }
      }
      if (globalText) {
        if (op.status === "in_progress" || op.status === "running") {
          globalText.textContent = "جاري تنفيذ مهمة تشغيلية...";
        } else if (op.status === "waiting_approval") {
          globalText.textContent = "بانتظار توقيع المشغّل...";
        } else {
          globalText.textContent = "متصل وجاهز للتشغيل";
        }
      }

      updateCockpitTelemetry(op.events || [], op.active_agent, op);

      if (op.status === "waiting_approval") {
        const pAct = op.pending_action || op.plan || window.currentHitlPendingAction;
        if (pAct) {
          window.currentHitlPendingAction = pAct;
          renderHitlDiffTable(pAct);
          showHitlGate(op.operation_id || currentOperationId, 1, 0);
        }
      } else if (["completed", "failed", "cancelled", "inconclusive"].includes(op.status)) {
        hideHitlGate();
      }
    }

    function updateProcessStepper(events, opOverride) {
      const stepper = document.getElementById("processStepper");
      const countEl = document.getElementById("processStepCount");
      const subtitleEl = document.getElementById("stepperSubtitle");
      const stepperCard = document.getElementById("processStepperCard");
      if (!stepper) return;

      const evtList = Array.isArray(events) ? events : [];
      const op = opOverride || window.currentOperationObj || {};
      const opStatus =
        op.status || (evtList.length > 0 ? "in_progress" : "idle");
      const activeAgent =
        op.active_agent || window.currentActiveAgent || "seraj";

      if (evtList.length === 0 && (!op || !op.operation_id)) {
        if (stepperCard) stepperCard.style.display = "block";
        stepper.innerHTML = `
          <div class="stepper-idle-banner" style="padding: 20px 22px; background: var(--paper-2); border: 1px dashed var(--rule); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;">
            <div style="display: flex; align-items: center; gap: 14px;">
              <div style="width: 44px; height: 44px; border-radius: 6px; background: rgba(var(--ok-rgb), 0.1); border: 1px solid rgba(var(--ok-rgb), 0.3); display: flex; align-items: center; justify-content: center; color: var(--ok); font-size: 20px; flex-shrink: 0;">
                ⚡
              </div>
              <div>
                <div style="font-size: 14.5px; font-weight: 600; color: var(--ink);">خط سير العملية المباشر جاهز للتتبع اللحظي</div>
                <div style="font-size: 12.5px; color: var(--muted); margin-top: 3px; line-height: 1.5;">
                  أرسل طلباً في محادثة سراج أو ارفع ملف بيانات لبدء التتبع التلقائي لمراحل المعالجة والاستدلال عبر منظومة الوكلاء.
                </div>
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); background: var(--paper-hi); padding: 6px 14px; border-radius: 999px; border: 1px solid var(--rule);">
              <span class="live-dot" style="width: 7px; height: 7px; border-radius: 50%; background: var(--ok); display: inline-block;"></span>
              <span style="font-weight: 500; color: var(--ink-2);">8 وكلاء متصلين في وضع الاستعداد</span>
            </div>
          </div>
        `;
        if (countEl) countEl.textContent = "جاهز وفي الانتظار";
        if (subtitleEl)
          subtitleEl.textContent =
            "المسار التكيفي لمنظومة الوكلاء المعتمدين: سراج 🡰 فاحص 🡰 مدقق 🡰 موفق 🡰 مصلح 🡰 حارس 🡰 كاتب 🡰 سجل";
        updateCockpitTelemetry([], "seraj", op);
        if (typeof renderAgentTimeline === "function") {
          renderAgentTimeline([], opStatus);
        }
        return;
      }

      if (stepperCard) stepperCard.style.display = "block";

      // 1. Contextual Routing & Category Determination
      const isBatch =
        op.operation_type === "excel_import" ||
        op.operation_type === "file_upload" ||
        op.operation_type === "batch_import" ||
        op.operation_type === "recruitment" ||
        evtList.some(
          (e) =>
            e.event_type === "batch_import" ||
            e.agent === "mowafaq" ||
            e.agent === "musleh",
        );
      const hasWriteOrApproval =
        evtList.some((e) =>
          [
            "write_started",
            "write_completed",
            "action_approved",
            "plan_prepared",
          ].includes(e.event_type),
        ) || isBatch;
      const isLaborLaw =
        op.operation_type === "labor_law_consultation" ||
        (evtList.some(
          (e) =>
            e.event_type === "labor_law_consultation" ||
            (e.action && e.action.includes("legal")) ||
            (e.description_ar && e.description_ar.includes("نظام العمل")),
        ) &&
          !hasWriteOrApproval);
      const isSimpleQuery =
        op.operation_type === "odoo_query" ||
        op.operation_type === "query" ||
        (evtList.some(
          (e) =>
            e.event_type === "odoo_query" || e.event_type === "inspection",
        ) &&
          !hasWriteOrApproval &&
          !isLaborLaw);
      const isDirectAction =
        !isBatch &&
        !isLaborLaw &&
        !isSimpleQuery &&
        (hasWriteOrApproval ||
          op.operation_type === "update" ||
          op.operation_type === "unarchive" ||
          op.operation_type === "create" ||
          evtList.some(
            (e) =>
              e.event_type === "plan_prepared" ||
              e.event_type === "record_inspection",
          ));

      let journeyType = "full_enterprise";
      if (isLaborLaw) journeyType = "labor_law";
      else if (isSimpleQuery) journeyType = "odoo_query";
      else if (isDirectAction) journeyType = "direct_action";
      else journeyType = "full_enterprise";

      // Common state evaluation
      const hasSeraj =
        evtList.some(
          (e) =>
            e.agent === "seraj" &&
            (e.status === "completed" || e.status === "success"),
        ) || evtList.length > 0;
      const hasFahes =
        evtList.some(
          (e) =>
            (e.agent === "fahes" || e.agent === "fahas") &&
            (e.status === "completed" || e.status === "success"),
        ) ||
        evtList.some((e) =>
          [
            "modaqeq",
            "mowafaq",
            "musleh",
            "hares",
            "katib",
            "kateb",
            "sijil",
          ].includes(e.agent),
        );
      const hasModaqeq =
        evtList.some(
          (e) =>
            e.agent === "modaqeq" &&
            (e.status === "completed" || e.status === "success"),
        ) ||
        evtList.some((e) =>
          ["mowafaq", "musleh", "hares", "katib", "kateb", "sijil"].includes(
            e.agent,
          ),
        );
      const hasMowafaq = evtList.some(
        (e) =>
          e.agent === "mowafaq" &&
          (e.status === "completed" || e.status === "success"),
      );
      const hasMusleh = evtList.some(
        (e) =>
          e.agent === "musleh" &&
          (e.status === "completed" || e.status === "success"),
      );
      const isWaitingHITL =
        opStatus === "waiting_approval" ||
        opStatus === "waiting_clarification" ||
        evtList.some(
          (e) =>
            e.status === "waiting_approval" ||
            e.status === "waiting_clarification",
        );
      const hasHares =
        (evtList.some(
          (e) =>
            e.agent === "hares" &&
            (e.status === "completed" ||
              e.status === "approved" ||
              e.status === "success"),
        ) ||
          evtList.some((e) =>
            ["katib", "kateb", "sijil"].includes(e.agent),
          ) ||
          opStatus === "completed") &&
        !isWaitingHITL;
      const isCompleted =
        opStatus === "completed" ||
        evtList.some(
          (e) =>
            (e.agent === "sijil" ||
              e.agent === "katib" ||
              e.agent === "kateb" ||
              e.event_type === "task_completed") &&
            (e.status === "completed" || e.status === "success"),
        );
      const isFailed = opStatus === "failed";

      let PIPELINE_MILESTONES = [];

      if (journeyType === "labor_law") {
        if (subtitleEl)
          subtitleEl.textContent =
            "مسار الاستشارة والامتثال التشريعي المعتمد: سراج 🡰 مدقق 🡰 سراج";
        PIPELINE_MILESTONES = [
          {
            num: 1,
            id: "m_intent",
            agent: "seraj",
            name: "01. استقبال وتحليل الاستفسار التشريعي",
            desc: "تفكيك عناصر السؤال، استخلاص نية الاستشارة القانونية وتوجيه المسار لمستشار الامتثال",
            state: "completed",
            stateLabel: "منجز ومحلل",
            summary:
              "تم تفكيك عناصر السؤال واستخلاص المسألة النظامية الحاكمة",
            badgeColor: "var(--agent-seraj)",
          },
          {
            num: 2,
            id: "m_compliance",
            agent: "modaqeq",
            name: "02. استقراء وتدقيق مواد نظام العمل واللوائح",
            desc: "مراجعة المواد واللوائح التنفيذية وقرارات وزارة الموارد البشرية وتحديد الضوابط والاستثناءات",
            state:
              hasModaqeq || isCompleted
                ? "completed"
                : activeAgent === "modaqeq"
                  ? "active"
                  : "waiting",
            stateLabel:
              hasModaqeq || isCompleted
                ? "مطابق ومعتمد نظامياً"
                : activeAgent === "modaqeq"
                  ? "جاري التدقيق"
                  : "المحطة التالية",
            summary:
              "تمت مراجعة مواد نظام العمل والتأكد من الضوابط المعتمدة رسمياً",
            badgeColor: "var(--agent-modaqeq)",
          },
          {
            num: 3,
            id: "m_advisory",
            agent: "seraj",
            name: "03. صياغة الاستشارة النظامية والتوثيق المرجعي",
            desc: "عرض النتيجة بلغة عربية رسمية مع السند النظامي ورقم المرسوم وقيد المسألة في السجل المعرفي",
            state: isCompleted
              ? "completed"
              : activeAgent === "seraj"
                ? "active"
                : "waiting",
            stateLabel: isCompleted ? "معتمد ومكتمل" : "جاري صياغة الرد",
            summary: isCompleted
              ? "تم تقديم الاستشارة النظامية المعتمدة للمشغّل بنجاح واكتمال الدورة"
              : "في انتظار اكتمال التدقيق النظامي",
            badgeColor: "var(--agent-seraj)",
          },
        ];
      } else if (journeyType === "odoo_query") {
        if (subtitleEl)
          subtitleEl.textContent =
            "مسار الاستعلام وقراءة البيانات الحية: سراج 🡰 فاحص 🡰 سراج";
        PIPELINE_MILESTONES = [
          {
            num: 1,
            id: "m_query_intent",
            agent: "seraj",
            name: "01. استقبال وفك تشفير معايير الاستعلام",
            desc: "تحليل طلب الاستعلام واستخراج معايير الفلترة ونطاق المنشأة والصلاحيات",
            state: "completed",
            stateLabel: "منجز ومحلل",
            summary: "تم تفكيك معايير الاستعلام وتحديد نطاق البحث المأذون",
            badgeColor: "var(--agent-seraj)",
          },
          {
            num: 2,
            id: "m_odoo_read",
            agent: "fahas",
            name: "02. الاستعلام المباشر من Odoo HR",
            desc: "استدعاء واجهة Odoo API الآمنة والبحث في النماذج المأذونة واسترجاع الحقول الحية",
            state:
              hasFahes || isCompleted
                ? "completed"
                : activeAgent === "fahes" || activeAgent === "fahas"
                  ? "active"
                  : "waiting",
            stateLabel:
              hasFahes || isCompleted
                ? "تم الفحص والاسترجاع"
                : "جاري الاستعلام",
            summary: "تم استرجاع السجلات الحية من قاعدة بيانات Odoo بنجاح",
            badgeColor: "var(--agent-fahas)",
          },
          {
            num: 3,
            id: "m_query_result",
            agent: "seraj",
            name: "03. تلخيص البيانات وعرض التقرير النهائي",
            desc: "تنظيم وعرض السجلات المسترجعة وإتاحة تصديرها وشرح النتائج للمستخدم",
            state: isCompleted
              ? "completed"
              : activeAgent === "seraj"
                ? "active"
                : "waiting",
            stateLabel: isCompleted ? "مكتمل ومعروض" : "جاري تجهيز العرض",
            summary: isCompleted
              ? "تم عرض تقرير الاستعلام النهائي للمشغّل بنجاح"
              : "في انتظار اكتمال قراءة السجلات",
            badgeColor: "var(--agent-seraj)",
          },
        ];
      } else if (journeyType === "direct_action") {
        if (subtitleEl)
          subtitleEl.textContent =
            "مسار الإجراءات المباشرة والحوكمة المشروطة: سراج 🡰 فاحص 🡰 مدقق 🡰 حارس 🡰 كاتب 🡰 سجل";
        PIPELINE_MILESTONES = [
          {
            num: 1,
            id: "m_action_intent",
            agent: "seraj",
            name: "01. استقبال وتفكيك طلب الإجراء",
            desc: "تحليل طلب التعديل أو إلغاء الأرشفة واستخراج الكيانات المرجعية",
            state: "completed",
            stateLabel: "منجز ومحلل",
            summary: "تم استخلاص نية الإجراء وتحديد نطاق العملية",
            badgeColor: "var(--agent-seraj)",
          },
          {
            num: 2,
            id: "m_action_inspect",
            agent: "fahas",
            name: "02. استعلام السجل وفحصه في Odoo",
            desc: "التحقق من حالة السجل وأهليته للتعديل ومطابقة المعرفات",
            state: hasFahes ? "completed" : "active",
            stateLabel: hasFahes ? "مطابق ومفحوص" : "جاري الفحص",
            summary: "تم التأكد من تواجد السجل وصحة بياناته المرجعية",
            badgeColor: "var(--agent-fahas)",
          },
          {
            num: 3,
            id: "m_action_rules",
            agent: "modaqeq",
            name: "03. تدقيق شروط التعديل والامتثال",
            desc: "تدقيق سياسات إعادة الخدمة وشروط التعديل والامتثال النظامي",
            state: hasModaqeq
              ? "completed"
              : activeAgent === "modaqeq"
                ? "active"
                : "waiting",
            stateLabel: hasModaqeq ? "معتمد نظامياً" : "جاري التدقيق",
            summary: "مطابق لضوابط الموارد البشرية واللوائح المعتمدة",
            badgeColor: "var(--agent-modaqeq)",
          },
          {
            num: 4,
            id: "m_action_guard",
            agent: "hares",
            name: "04. حوكمة الصلاحيات وإصدار خطة الاعتماد (HITL)",
            desc: "إصدار خطة الاعتماد الرسمية واشتراط موافقة المشغّل البشري",
            state: isWaitingHITL
              ? "waiting"
              : hasHares
                ? "completed"
                : "active",
            stateLabel: isWaitingHITL
              ? "بانتظار موافقة المسؤول"
              : hasHares
                ? "معتمد وموثق"
                : "فحص الصلاحيات",
            summary: isWaitingHITL
              ? "معلق لحين مراجعة وتوقيع المسؤول"
              : hasHares
                ? "تم استيفاء التوقيع ومنح ترخيص التنفيذ"
                : "جاري استكمال الحوكمة",
            badgeColor: "var(--agent-hares)",
          },
          {
            num: 5,
            id: "m_action_write",
            agent: "katib",
            name: "05. التنفيذ الفعلي والكتابة في Odoo",
            desc: "تنفيذ التعديل أو إلغاء الأرشفة في Odoo بعد التحقق من ترخيص حارس",
            state: isWaitingHITL
              ? "future"
              : isCompleted
                ? "completed"
                : isFailed
                  ? "failed"
                  : activeAgent === "katib" || activeAgent === "kateb"
                    ? "active"
                    : "future",
            stateLabel: isWaitingHITL
              ? "في الانتظار"
              : isCompleted
                ? "منفذ في Odoo"
                : isFailed
                  ? "تعثر التنفيذ"
                  : "في الانتظار",
            summary: isWaitingHITL
              ? "في انتظار اعتماد المشغّل"
              : isCompleted
                ? "تم قيد التعديل في Odoo بنجاح تام"
                : "في انتظار ترخيص حارس",
            badgeColor: "var(--agent-katib)",
          },
          {
            num: 6,
            id: "m_action_seal",
            agent: "sijil",
            name: "06. التوثيق والختم الرقمي اللاتراجعي",
            desc: "توثيق البصمة الرقمية المشفرة في الدفتر اللاتراجعي وإصدار السند",
            state: isWaitingHITL
              ? "future"
              : isCompleted
                ? "completed"
                : "future",
            stateLabel: isWaitingHITL || !isCompleted
              ? "في الانتظار"
              : "مختوم وموثق",
            summary: isCompleted
              ? "تم توثيق البصمة المشفرة في سجل لحماية المعاملة من التلاعب"
              : "جاهز للختم فور اكتمال القيد",
            badgeColor: "var(--agent-sijil)",
          },
        ];
      } else {
        // Full Enterprise 8-Agent Journey
        if (subtitleEl)
          subtitleEl.textContent =
            "المسار الشامل لمنظومة الوكلاء المعتمدين: سراج 🡰 فاحص 🡰 مدقق 🡰 موفق 🡰 مصلح 🡰 حارس 🡰 كاتب 🡰 سجل";
        PIPELINE_MILESTONES = [
          {
            num: 1,
            id: "m_all_seraj",
            agent: "seraj",
            name: "01. استقبال وتفكيك الملف وتوجيه المهام",
            desc: "استلام طلب المشغّل، تفكيك عناصر البيانات وتوزيع مسار العمليات بين الوكلاء",
            state: hasSeraj
              ? "completed"
              : activeAgent === "seraj"
                ? "active"
                : "future",
            stateLabel: hasSeraj ? "منجز ومحلل" : "جاري التحليل",
            summary: hasSeraj
              ? "تم تفكيك عناصر الدفعة واستخراج الكيانات المرجعية"
              : "في انتظار استلام الطلب",
            badgeColor: "var(--agent-seraj)",
          },
          {
            num: 2,
            id: "m_all_fahas",
            agent: "fahas",
            name: "02. فحص سجلات Odoo ومنع الازدواجية",
            desc: "الاستعلام المباشر في Odoo للتحقق من عدم تكرار السجلات ومطابقة المعرفات والشواغر",
            state: hasFahes
              ? "completed"
              : activeAgent === "fahes" || activeAgent === "fahas"
                ? "active"
                : hasSeraj
                  ? "waiting"
                  : "future",
            stateLabel: hasFahes
              ? "مطابق ومفحوص"
              : activeAgent === "fahes" || activeAgent === "fahas"
                ? "جاري الفحص"
                : "المحطة التالية",
            summary: hasFahes
              ? "تم التحقق من قاعدة بيانات Odoo والتأكد من عدم تكرار المعرفات"
              : "جاهز للاستعلام في Odoo",
            badgeColor: "var(--agent-fahas)",
          },
          {
            num: 3,
            id: "m_all_modaqeq",
            agent: "modaqeq",
            name: "03. تدقيق الامتثال والأنظمة ونظام العمل",
            desc: "التحقق من توافق الإجراء مع مواد نظام العمل واللوائح التنفيذية والحدود المعتمدة",
            state: hasModaqeq
              ? "completed"
              : activeAgent === "modaqeq"
                ? "active"
                : hasFahes
                  ? "waiting"
                  : "future",
            stateLabel: hasModaqeq
              ? "معتمد نظامياً"
              : activeAgent === "modaqeq"
                ? "جاري التدقيق"
                : "المحطة التالية",
            summary: hasModaqeq
              ? "مطابق لسياسات نظام العمل والتأمينات الاجتماعية ولا توجد موانع"
              : "في انتظار اكتمال الفحص",
            badgeColor: "var(--agent-modaqeq)",
          },
          {
            num: 4,
            id: "m_all_mowafaq",
            agent: "mowafaq",
            name: "04. المطابقة الذكية للمسميات والشواغر",
            desc: "المطابقة الدلالية للمسميات الوظيفية والأقسام عند تباين الصياغة وفك الالتباس المعجمي",
            state: hasMowafaq
              ? "completed"
              : activeAgent === "mowafaq"
                ? "active"
                : hasModaqeq
                  ? "completed"
                  : "future",
            stateLabel: hasMowafaq
              ? "تمت المطابقة الذكية"
              : hasModaqeq
                ? "تطابق تلقائي سليم"
                : "في الانتظار",
            summary: hasMowafaq
              ? "تمت معالجة الالتباس والمطابقة الدلالية للشواغر"
              : hasModaqeq
                ? "المسميات متطابقة بنسبة 100% مع الهيكل المعتمد"
                : "في انتظار التدقيق",
            badgeColor: "var(--agent-mowafaq)",
          },
          {
            num: 5,
            id: "m_all_musleh",
            agent: "musleh",
            name: "05. المعالجة الذاتية وتصحيح الأخطاء",
            desc: "تشخيص الأخطاء الشاذة واقتراح التصحيح التلقائي وتطبيق سياسات العزل والحجر الصحي",
            state: hasMusleh
              ? "completed"
              : activeAgent === "musleh"
                ? "active"
                : hasModaqeq
                  ? "completed"
                  : "future",
            stateLabel: hasMusleh
              ? "تمت المعالجة الذاتية"
              : hasModaqeq
                ? "خالٍ من الأخطاء"
                : "في الانتظار",
            summary: hasMusleh
              ? "تم تصحيح الأخطاء وتحديث الحقول المعتمدة"
              : hasModaqeq
                ? "كافة السجلات سليمة ولم تتطلب تدخلاً استثنائياً للعزل"
                : "في انتظار التدقيق",
            badgeColor: "var(--agent-musleh)",
          },
            {
              num: 6,
              id: "m_all_hares",
              agent: "hares",
              name: "06. حوكمة الصلاحيات والاعتماد البشري (HITL)",
              desc: "فحص مصفوفة الصلاحيات، طلب التوثيق، وإصدار رمز الاعتماد المشروط للمسؤول",
              state: hasHares
                ? "completed"
                : isWaitingHITL
                  ? "waiting"
                  : activeAgent === "hares"
                    ? "active"
                    : "future",
              stateLabel: hasHares
                ? "معتمد وموثق"
                : isWaitingHITL
                  ? "بانتظار موافقة المسؤول"
                  : activeAgent === "hares"
                    ? "فحص الصلاحيات"
                    : "في الانتظار",
              summary: hasHares
                ? "تم استيفاء شروط الحوكمة واعتماد رمز الصلاحية للتنفيذ"
                : isWaitingHITL
                  ? "معلق لحين مراجعة واعتماد المسؤول البشري (HITL)"
                  : "في انتظار اكتمال التدقيق",
              badgeColor: "var(--agent-hares)",
            },
            {
              num: 7,
              id: "m_all_katib",
              agent: "katib",
              name: "07. التنفيذ الفعلي والكتابة في Odoo",
              desc: "المنفذ الحصري لعمليات الكتابة والإنشاء والتعديل المباشر في Odoo عبر واجهة API",
              state: isCompleted
                ? "completed"
                : isFailed
                  ? "failed"
                  : activeAgent === "katib" ||
                      activeAgent === "kateb" ||
                      hasHares
                    ? "active"
                    : "future",
              stateLabel: isCompleted
                ? "منفذ ومرحّل"
                : isFailed
                  ? "تعثر التنفيذ"
                  : activeAgent === "katib" || hasHares
                    ? "جاري القيد والتنفيذ"
                    : "في الانتظار",
              summary: isCompleted
                ? "تم ترحيل وقيد السجلات المعتمدة في Odoo بنجاح تام"
                : isFailed
                  ? "حدث خطأ أثناء التنفيذ يتطلب مراجعة السجلات"
                  : "جاهز للتنفيذ فور اكتمال الاعتماد",
              badgeColor: "var(--agent-katib)",
            },
            {
              num: 8,
              id: "m_all_sijil",
              agent: "sijil",
              name: "08. التوثيق والختم الرقمي اللاتراجعي",
              desc: "توثيق البصمة الرقمية المشفرة (SHA-256) وسند الاعتماد غير القابل للتراجع في دفتر التدقيق",
              state: isCompleted ? "completed" : "future",
              stateLabel: isCompleted ? "مختوم وموثق رقمياً" : "في الانتظار",
              summary: isCompleted
                ? "تم توثيق البصمة المشفرة في دفتر التدقيق اللاتراجعي بنجاح"
                : "جاهز لإصدار البصمة المشفرة فور انتهاء التنفيذ",
              badgeColor: "var(--agent-sijil)",
            },
          ];
        }

        // Calculate completed count and percent
        const totalStages = PIPELINE_MILESTONES.length;
        const completedCount = PIPELINE_MILESTONES.filter(
          (m) => m.state === "completed",
        ).length;
        const percentDone = Math.round((completedCount / totalStages) * 100);
        if (countEl) {
          countEl.textContent = `${completedCount} من ${totalStages} مراحل منجزة (${percentDone}%)`;
        }

        stepper.innerHTML = "";
        PIPELINE_MILESTONES.forEach((m) => {
          const meta = AGENTS_META[m.agent] || {
            name_ar: m.agent,
            color: m.badgeColor,
          };
          const node = document.createElement("div");
          node.className = `step-node is-${m.state}`;
          node.style.cursor = "default";

          const stateColor =
            m.state === "completed"
              ? "var(--color-phosphor-green)"
              : m.state === "active"
                ? "#38bdf8"
                : m.state === "waiting"
                  ? "var(--color-amber)"
                  : m.state === "failed"
                    ? "var(--color-coral)"
                    : "var(--color-smoke)";

          let iconBg = "var(--paper-2)";
          let iconBorder = "var(--color-charcoal)";
          let iconColor = stateColor;

          if (m.state === "completed") {
            iconBg = "rgba(62, 207, 142, 0.12)";
            iconBorder = "var(--color-phosphor-green, #3ecf8e)";
            iconColor = "var(--color-phosphor-green, #3ecf8e)";
          } else if (m.state === "active") {
            iconBg = meta.color || "var(--agent-seraj, #38bdf8)";
            iconBorder = meta.color || "var(--agent-seraj, #38bdf8)";
            iconColor = "#04111d"; // Bold deep black/obsidian for maximum AAA contrast on bright background
          } else if (m.state === "waiting") {
            iconBg = "rgba(234, 179, 8, 0.16)";
            iconBorder = "var(--color-amber, #eab308)";
            iconColor = "#ffca16";
          } else if (m.state === "failed") {
            iconBg = "rgba(239, 68, 68, 0.16)";
            iconBorder = "var(--color-coral, #ef4444)";
            iconColor = "#ff6465";
          } else {
            iconBg = "transparent";
            iconBorder = "var(--rule-strong, #393939)";
            iconColor = "var(--color-smoke, #9e9e9e)";
          }

          node.innerHTML = `
          <div class="step-icon-box" style="background: ${iconBg} !important; border-color: ${iconBorder} !important; color: ${iconColor} !important; font-weight: 800; font-size: 15px;">
            ${m.state === "completed" ? "✓" : m.num}
          </div>
          <div class="step-content">
            <div class="step-header-line">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="step-desc" style="font-size: 13.5px; font-weight: 700; color: var(--color-snow);">${m.name}</span>
                <span class="step-agent-badge" style="color: ${meta.color}; border: 1px solid ${meta.color}; font-size: 11px; padding: 1px 7px; border-radius: 4px; background: rgba(0,0,0,0.25);">
                  ${meta.name_ar}
                </span>
              </div>
              <span class="step-status-tag" style="font-size: 11.5px; font-weight: 600; color: ${stateColor};">
                ${m.stateLabel}
              </span>
            </div>
            <div style="font-size: 12px; color: var(--color-smoke); margin-top: 3px; line-height: 1.4;">${m.desc}</div>
            <div style="font-size: 12px; color: ${m.state === "completed" ? "var(--color-phosphor-green)" : "var(--color-silver-mist)"}; margin-top: 4px; font-weight: 500; display: flex; align-items: center; gap: 5px;">
              <span style="opacity: 0.6;">↳</span> ${m.summary}
            </div>
          </div>
        `;
          stepper.appendChild(node);
        });

        updateCockpitTelemetry(evtList, activeAgent, op);
        if (typeof renderAgentTimeline === "function") {
          renderAgentTimeline(evtList, opStatus);
        }

        if (isWaitingHITL && opStatus === "waiting_approval") {
          const pAct = op.pending_action || op.plan || window.currentHitlPendingAction;
          if (pAct) {
            window.currentHitlPendingAction = pAct;
            renderHitlDiffTable(pAct);
            showHitlGate(op.operation_id || currentOperationId, 1, 0);
          }
        } else if (["completed", "failed", "cancelled", "inconclusive"].includes(opStatus)) {
          hideHitlGate();
        }
      }

      function openEventDetails(evt) {
        const overlay = document.getElementById("detailsDrawerOverlay");
        const title = document.getElementById("drawerTitle");
        const body = document.getElementById("drawerBody");
        if (!overlay || !body || !evt) return;

        const meta = resolveAgentMeta(evt.agent);
        const actionText = evt.action || evt.event_type || "معالجة";
        const reasoningText =
          typeof resolveAgentReasoning === "function"
            ? resolveAgentReasoning(evt)
            : evt.reasoning || evt.decision || "—";

        let timeStr = "";
        if (evt.timestamp) {
          try {
            timeStr = evt.timestamp.includes("T")
              ? evt.timestamp.substring(11, 19)
              : new Date(evt.timestamp).toLocaleTimeString("ar-EG");
          } catch (_) {
            timeStr = evt.timestamp;
          }
        }

        title.textContent = `سجل تتبع وأثر الحدث: «${evt.description_ar || actionText}»`;
        body.innerHTML = `
        <div style="display: flex; gap: 12px; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 200px; background: #141414; padding: 14px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
            <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 4px;">الوكيل المنفذ</div>
            <div style="font-size: 15px; font-weight: 700; color: ${meta.color || "var(--color-snow)"};">${meta.name_ar || evt.agent}</div>
          </div>
          <div style="flex: 1; min-width: 200px; background: #141414; padding: 14px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
            <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 4px;">نوع الإجراء والتوقيت</div>
            <div class="mono" style="font-size: 13px; color: var(--color-silver-mist);">[إجراء: ${escapeHtml(actionText)}] | ⏱ ${timeStr}</div>
          </div>
        </div>

        <div style="background: rgba(0, 0, 0, 0.4); padding: 14px; border-radius: 10px; border-right: 3px solid ${meta.color || "var(--color-slate)"}; margin-top: 10px;">
          <div style="font-size: 11.5px; font-weight: 700; color: ${meta.color || "var(--color-silver-mist)"}; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
            التعليل المنطقي والقرار (Cognitive Reasoning):
          </div>
          <div style="font-size: 13px; color: var(--color-snow); line-height: 1.55;">
            ${escapeHtml(reasoningText)}
          </div>
          ${
            evt.decision
              ? `
            <div style="margin-top: 8px; padding-top: 6px; border-top: 1px dashed rgba(255,255,255,0.1); font-size: 12.5px; color: var(--color-silver-mist);">
              <span style="font-weight: 700; color: ${meta.color || "var(--color-smoke)"};">القرار:</span>
              <span style="color: var(--color-snow);">${escapeHtml(evt.decision)}</span>
            </div>
          `
              : ""
          }
        </div>

        <div style="background: #141414; padding: 14px; border-radius: 12px; border: 1px solid var(--color-charcoal); margin-top: 10px;">
          <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 6px;">البيانات الفنية وأدلة التحقق (Metadata)</div>
          <pre style="margin: 0; font-size: 12px; color: var(--color-snow); max-height: 180px; overflow-y: auto; font-family: var(--font-mono);">${escapeHtml(JSON.stringify(evt.metadata || {}, null, 2))}</pre>
        </div>
      `;
        overlay.classList.add("is-open");
      }

      // =========================================================================
      // 10. AGENT DRAWER DETAILS (CENTERED MODAL)
      // =========================================================================
      function openAgentDetails(agentKey) {
        const meta = AGENTS_META[agentKey] || {};
        const agentData = activeAgentsData.find((a) => a.id === agentKey) || {};
        const overlay = document.getElementById("detailsDrawerOverlay");
        const title = document.getElementById("drawerTitle");
        const body = document.getElementById("drawerBody");
        if (!overlay || !body) return;

        title.textContent = `بطاقة الوكيل: «${meta.name_ar}»`;

        body.innerHTML = `
        <div style="display: flex; align-items: center; gap: 14px; background: #141414; padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
          <div class="agent-avatar-wrap" style="border-color: ${meta.color}; width: 50px; height: 50px; margin: 0;">
            ${meta.img ? `<img src="${meta.img}" alt="${escapeHtml(meta.name_ar)}" class="agent-avatar-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />` : ""}
            <div class="agent-avatar-svg-fallback" style="${meta.img ? "display:none;" : "display:flex;"} width:100%; height:100%; align-items:center; justify-content:center;">
              ${getAgentSvg(meta.icon)}
            </div>
          </div>
          <div>
            <div style="font-size: 17px; font-weight: 700; color: var(--color-snow);">${meta.name_ar}</div>
            <div style="font-size: 12px; color: var(--color-silver-mist);">${meta.role}</div>
          </div>
        </div>

        <div style="background: #141414; padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
          <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 4px;">الحالة التشغيلية الآن</div>
          <span class="badge ${agentData.status_code === "ready" ? "badge-neutral" : "badge-success"}">
            ${agentData.status_label || STATUS_MAP_AR[agentData.status_code] || "جاهز"}
          </span>
        </div>

        <div style="background: #141414; padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
          <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 4px;">المهمة الحالية / الأخيرة</div>
          <div style="font-size: 13.5px; color: var(--color-snow); line-height: 1.5;">${escapeHtml(agentData.last_task || "في انتظار استلام المهام")}</div>
        </div>

        <div style="background: #141414; padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
          <div class="settings-section-title">ماذا يفعل هذا الوكيل؟</div>
          <ul class="agent-capabilities">${(agentData.capabilities || []).map((c) => `<li>${escapeHtml(c)}</li>`).join("")}</ul>
          <div class="agent-stats">${agentData.operation_count || 0} عملية · ${agentData.event_count || 0} حدث مسجل</div>
        </div>
        <div class="agent-history">
          <div class="settings-section-title">آخر الأنشطة الفعلية</div>
          ${(agentData.recent_tasks || []).map((t) => `<div class="agent-history-item"><span class="mono">${escapeHtml(t.timestamp?.slice(0, 19).replace("T", " ") || "")}</span><p>${escapeHtml(t.description_ar)}</p><button class="btn btn-sm btn-secondary" onclick="closeDetailsDrawer();resumeOperationInCockpit('${escapeHtml(t.operation_id)}')">فتح العملية</button></div>`).join("") || "لا توجد أنشطة مسجلة لهذا الوكيل بعد."}
        </div>
        <div style="background: #141414; padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
          <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 4px;">الصلاحيات والحدود المعمارية</div>
          <div style="font-size: 12.5px; color: var(--color-silver-mist); line-height: 1.6;">
            ${agentKey === "fahas" ? "• قراءة واستعلام فقط (Read-Only) في Odoo.<br>• التحقق المستقل بعد التنفيذ (التحقق المستقل بعد التنفيذ).<br>• لا يملك أي صلاحيات كتابة أو تعديل." : ""}
            ${agentKey === "katib" ? "• المنفذ الحصري لعمليات الكتابة في Odoo.<br>• لا يُنفذ أي أمر إلا بعد التحقق المزدوج واعتماد الخطة.<br>• يُحظر الحذف الكلي غير المحكوم حماية للبيانات." : ""}
            ${agentKey === "seraj" ? "• واجهة المحادثة والتنسيق العام بين كافة الوكلاء.<br>• استلام الطلبات وشرح النتائج بلغة طبيعية.<br>• لا يقرأ أو يكتب في Odoo مباشرة دون الوكلاء المختصين." : ""}
            ${agentKey === "sijil" ? "• الرقابة والتدقيق غير القابل للتلاعب (Append-only).<br>• توثيق البصمات الرقمية وتوليد تقارير PDF الرسمية.<br>• قياس مؤشرات الحوكمة ونسب المطابقة." : ""}
            ${!["fahas", "katib", "seraj", "sijil"].includes(agentKey) ? "• يعمل ضمن منظومة التحقق والحوكمة المعتمدة.<br>• لا يتدخل في المحادثة المباشرة مع المستخدم بل يفوض الرد لسراج." : ""}
          </div>
        </div>
      `;

        overlay.classList.add("is-open");
      }

      function closeDetailsDrawer(e) {
        const overlay = document.getElementById("detailsDrawerOverlay");
        if (overlay) {
          overlay.classList.remove("is-open");
          const sheet = overlay.querySelector(".drawer-sheet");
          if (sheet) sheet.classList.remove("is-wide");
        }
      }

      // =========================================================================
      // 11. OPERATIONS DIRECTORY & "متابعة" ACTION
      // =========================================================================
      async function loadOperationsList() {
        const tbody = document.getElementById("operationsTableBody");
        if (!tbody) return;

        try {
          const res = await apiFetch("/api/agents/operations");
          const data = await res.json();
          if (data.status === "success" && data.operations) {
            if (data.operations.length === 0) {
              tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--color-smoke); padding: 30px;">لا توجد عمليات مسجلة حتى الآن.</td></tr>`;
              return;
            }
            tbody.innerHTML = data.operations
              .map(
                (op) => `
            <tr>
              <td class="mono" style="font-weight: 600; color: var(--color-snow);">${escapeHtml(op.operation_id)}</td>
              <td>${escapeHtml(op.operation_type || "محادثة")}</td>
              <td>${escapeHtml(op.requester || "المستخدم")}</td>
              <td>${escapeHtml(op.company_name || (op.company_id ? "شركة " + op.company_id : "الشركة المحددة"))}</td>
              <td><span style="color: ${AGENTS_META[op.active_agent]?.color || "var(--color-silver-mist)"}; font-weight: 600;">${AGENTS_META[op.active_agent]?.name_ar || op.active_agent}</span></td>
              <td><span class="badge ${op.status === "completed" ? "badge-success" : op.status === "failed" ? "badge-error" : "badge-warning"}">${op.status_label || STATUS_MAP_AR[op.status] || op.status}</span></td>
              <td class="mono" style="font-size: 12px;">${op.created_at ? (typeof formatLocalDateTime === "function" ? formatLocalDateTime(op.created_at) : op.created_at.substring(0, 19).replace("T", " ")) : "—"}</td>
              <td>
                <div style="display: flex; gap: 6px;">
                  <button class="btn btn-sm btn-secondary" onclick="resumeOperationInCockpit('${op.operation_id}')">متابعة</button>
                  <button class="btn btn-sm btn-iris" onclick="openOperationInSijil('${op.operation_id}')">سجل</button>
                  <button class="btn btn-sm btn-secondary" onclick="exportSingleOpPdf('${op.operation_id}')">PDF</button>
                </div>
              </td>
            </tr>
          `,
              )
              .join("");

            if (!currentOperationId && data.operations.length > 0) {
              const firstOp = data.operations[0];
              if (firstOp && typeof updateAgentTimeline === "function") {
                updateAgentTimeline(firstOp.operation_id);
              }
            }
          }
        } catch (err) {
          tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--color-coral); padding: 20px;">تعذر تحميل العمليات: ${err.message}</td></tr>`;
        }
      }

      async function resumeOperationInCockpit(opId) {
        if (!opId) return;
        if (chatRequestInFlight) return;
        const requestId = ++resumeRequestId;
        if (pollingInterval) clearInterval(pollingInterval);
        pollingInterval = null;
        lastEventSequence = 0;
        hideTypingIndicator();
        currentOperationId = opId;
        document.getElementById("activeOpIdBadge").textContent = opId;
        switchView("view-cockpit");

        try {
          const res = await apiFetch(`/api/agents/operations/${opId}`);
          const data = await res.json();
          if (requestId !== resumeRequestId) return;
          if (data.status === "success" && data.operation) {
            const op = data.operation;
            currentOperationId = op.operation_id || opId;
            currentChatId = op.chat_id || `read_only_${opId}`;
            currentOperationStatus = op.status || op.final_status_code;

            // A. Restore conversation messages
            const chatContainer = document.getElementById("chatMessages");
            if (chatContainer) {
              chatContainer.innerHTML = "";
              const messages = op.messages || op.conversation?.messages || [];
              if (messages.length) {
                messages.forEach((m, i) => {
                  if (m.role === "user") appendUserMessage(m.content);
                  else if (m.role === "assistant")
                    appendSerajMessage(
                      m.content,
                      i === messages.length - 1 ? op.pending_action : null,
                      i === messages.length - 1
                        ? op.pending_clarification
                        : null,
                      op,
                    );
                });
              } else if (op.user_query) appendUserMessage(op.user_query);

              let events = (op.events || []).slice().sort((a, b) => (b.sequence || 0) - (a.sequence || 0) || (new Date(b.timestamp || 0) - new Date(a.timestamp || 0)));
              let lastDesc = null;
              events.forEach((evt) => {
                if (evt.description_ar && evt.event_type !== "start") {
                  lastDesc = evt.description_ar;
                }
              });

              if (!messages.length && op.status === "completed") {
                appendSerajMessage(
                  lastDesc ||
                    `تم إنجاز العملية «${op.user_query}» ومطابقتها رقابياً بنجاح.`,
                  null,
                  null,
                  op,
                );
              } else if (!messages.length) {
                appendSerajMessage(
                  lastDesc ||
                    `جاري متابعة معالجة العملية «${op.user_query}» في مركز العمليات.`,
                  null,
                  null,
                  op,
                );
              }
            }

            // B. Update stepper & badges
            const pAct = op.pending_action || op.plan || (op.events && op.events.find(e => e.plan)?.plan) || null;
            if (pAct && op.status === "waiting_approval") {
              window.currentHitlPendingAction = pAct;
              renderHitlDiffTable(pAct);
              showHitlGate(op.operation_id || opId, 1, 0);
            }
            updateProcessStepper(op.events || [], op);
            updateOperationBadges(op);

            // C. Handle active or terminal state
            const terminalStatuses = [
              "completed",
              "failed",
              "cancelled",
              "inconclusive",
              "waiting_approval",
              "waiting_user_clarification",
              "waiting_clarification",
            ];
            if (terminalStatuses.includes(op.status)) {
              resetAllAgentsToIdle();
              setStreamConnected(true, "العملية مكتملة");
            } else {
              startLiveEventPolling(opId);
            }
          }
        } catch (err) {
          console.warn("Resume operation error:", err);
        }
      }

      // =========================================================================
      // 12. SIJIL AUDIT LEDGER, PAGINATION & PDF EXPORT
      // =========================================================================
      async function loadRecentAuditMetrics() {
        const tbody = document.getElementById("sijilRecentTableBody");
        if (!tbody) return;

        try {
          const offset = (sijilPage - 1) * sijilLimit;
          const res = await apiFetch(
            `/api/sijil/recent?limit=${sijilLimit}&offset=${offset}`,
          );
          const data = await res.json();
          if (!res.ok)
            throw new Error(data.detail || "تعذر تحميل سجلات التدقيق");

          const records = data.operations || data.records || [];
          sijilTotal = data.total || records.length;

          if (data.status === "success" && records.length > 0) {
            tbody.innerHTML = records
              .map((r) => {
                const ident =
                  r.identifier ||
                  r.record_id ||
                  r.operation_id ||
                  r.plan_id ||
                  "—";
                const typeLabel =
                  r.type || r.domain_ar || r.domain || "عملية موثقة";
                const statusOk =
                  r.status_raw === "success" || r.readback_verified;
                let ts = "—";
                if (r.timestamp) {
                  const raw = String(r.timestamp);
                  if (raw.includes("-")) {
                    ts = raw.substring(0, 19).replace("T", " ");
                  } else if (raw.length >= 15) {
                    ts = `${raw.substring(0, 4)}-${raw.substring(4, 6)}-${raw.substring(6, 8)} ${raw.substring(9, 11)}:${raw.substring(11, 13)}:${raw.substring(13, 15)}`;
                  } else {
                    ts = raw;
                  }
                }
                return `
            <tr>
              <td class="mono" style="font-size: 12.5px; color: var(--color-iris-glow);">${escapeHtml(ident)}</td>
              <td><span class="badge badge-neutral">${escapeHtml(typeLabel)}</span></td>
              <td>${escapeHtml(r.action || r.operation_type || "قيد نظامي")}</td>
              <td>${escapeHtml(r.target || r.user_query || "—")}</td>
              <td><span class="badge ${statusOk ? "badge-success" : "badge-warning"}">${escapeHtml(r.status || (statusOk ? "ناجحة" : "قيد المراجعة"))}</span></td>
              <td class="mono" style="font-size: 12px;">${ts}</td>
              <td>
                <div style="display: flex; gap: 6px;">
                  <button class="btn btn-sm btn-iris" onclick="openOperationInSijil('${ident}')">سجل</button>
                  <button class="btn btn-sm btn-secondary" onclick="exportSingleOpPdf('${ident}')">PDF</button>
                </div>
              </td>
            </tr>
          `;
              })
              .join("");
          } else if (data.status === "success") {
            tbody.innerHTML =
              '<tr><td colspan="7" style="text-align:center; color: var(--color-smoke); padding: 20px;">لا توجد عمليات موثقة بعد.</td></tr>';
          } else {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--color-coral); padding: 20px;">خطأ: ${escapeHtml(data.detail || "تعذر تحميل سجلات التدقيق")}</td></tr>`;
          }

          // Update pagination controls
          const totalPages = Math.max(1, Math.ceil(sijilTotal / sijilLimit));
          const infoEl = document.getElementById("sijilPaginationInfo");
          const pageBadge = document.getElementById("sijilPageBadge");
          const prevBtn = document.getElementById("sijilPrevBtn");
          const nextBtn = document.getElementById("sijilNextBtn");

          if (infoEl)
            infoEl.textContent = `الصفحة ${sijilPage} من ${totalPages} (إجمالي ${sijilTotal} سجل)`;
          if (pageBadge) pageBadge.textContent = sijilPage;
          if (prevBtn) prevBtn.disabled = sijilPage <= 1;
          if (nextBtn) nextBtn.disabled = sijilPage >= totalPages;
          renderSijilNumberedPages(totalPages);

          // Load summary metrics
          const sRes = await apiFetch("/api/sijil/summary");
          const sData = await sRes.json();
          if (sData.status === "success") {
            const el = document.getElementById("metricBlockedDeletions");
            if (el) el.textContent = sData.summary.blocked_actions || 0;
            document.getElementById("metricReadbackRate").textContent = sData
              .summary.readback_eligible_count
              ? `${sData.summary.readback_rate}%`
              : "غير مقاس";
            document.getElementById("metricApprovals").textContent =
              sData.summary.four_eyes_tokens_count || 0;
          }
        } catch (err) {
          console.warn("Sijil metrics error:", err);
          const isAuthError =
            err.message &&
            (err.message.includes("X-API-Key") ||
              err.message.includes("401") ||
              err.message.includes("غير مصرّح"));
          if (isAuthError) {
            tbody.innerHTML = `<tr><td colspan="7" role="alert" style="padding: 28px 20px; text-align: center;">
            <div style="font-size: 14px; font-weight: 700; color: var(--color-amber); margin-bottom: 8px;">
              يتطلب عرض سجلات التدقيق توفير رمز مصادقة المشغّل (X-API-Key)
            </div>
            <div style="font-size: 12.5px; color: var(--color-silver-mist); max-width: 520px; margin: 0 auto 16px; line-height: 1.6;">
              سجلات التدقيق الكاملة محمية ضمن حوكمة المنظومة لضمان سرية القيود. يرجى إدخال رمز جلسة المشغّل المعتمد للمتابعة.
            </div>
            <div style="display: flex; gap: 10px; justify-content: center; align-items: center; flex-wrap: wrap;">
              <button class="btn btn-sm btn-primary" onclick="promptForApiToken()">إدخال رمز المصادقة (X-API-Key)</button>
              <button class="btn btn-sm btn-secondary" onclick="loadRecentAuditMetrics()">إعادة المحاولة</button>
            </div>
          </td></tr>`;
          } else {
            tbody.innerHTML = `<tr><td colspan="7" role="alert" style="padding:20px;text-align:center">${escapeHtml(err.message)} <button class="btn btn-sm btn-secondary" onclick="loadRecentAuditMetrics()">إعادة المحاولة</button></td></tr>`;
          }
        }
      }

      function renderSijilNumberedPages(totalPages) {
        const nav = document.getElementById("sijilNumberedPages");
        const pages = new Set([
          1,
          totalPages,
          sijilPage - 1,
          sijilPage,
          sijilPage + 1,
        ]);
        nav.replaceChildren();
        let previous = 0;
        [...pages]
          .filter((p) => p > 0 && p <= totalPages)
          .sort((a, b) => a - b)
          .forEach((p) => {
            if (previous && p - previous > 1) {
              const dots = document.createElement("span");
              dots.textContent = "…";
              nav.appendChild(dots);
            }
            const button = document.createElement("button");
            button.className = `page-number ${p === sijilPage ? "is-current" : ""}`;
            if (p === sijilPage) button.setAttribute("aria-current", "page");
            button.textContent = p;
            button.onclick = () => {
              sijilPage = p;
              loadRecentAuditMetrics();
            };
            nav.appendChild(button);
            previous = p;
          });
      }

      function changeSijilPage(delta) {
        const totalPages = Math.max(1, Math.ceil(sijilTotal / sijilLimit));
        const newPage = sijilPage + delta;
        if (newPage >= 1 && newPage <= totalPages) {
          sijilPage = newPage;
          loadRecentAuditMetrics();
        }
      }

      async function executeSijilSearch() {
        const q = document.getElementById("sijilSearchInput").value.trim();
        const resultBox = document.getElementById("sijilSearchResultBox");
        if (!q || !resultBox) return;

        resultBox.style.display = "block";
        resultBox.innerHTML = `<div style="text-align: center; color: var(--color-smoke); padding: 20px;">جاري استعلام الدفتر اللاتراجعي...</div>`;

        try {
          const res = await apiFetch(
            `/api/sijil/search?q=${encodeURIComponent(q)}`,
          );
          const data = await res.json();
          if (
            data.status === "success" &&
            data.match_type === "single" &&
            data.operation
          ) {
            const op = data.operation;
            resultBox.innerHTML = `
            <div style="background: #181818; border: 1px solid var(--color-charcoal); border-radius: 12px; padding: 18px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div style="font-size: 15px; font-weight: 700; color: var(--color-snow);">نتيجة المطابقة: ${escapeHtml(op.operation_type || "عملية موثقة")}</div>
                <div style="display: flex; gap: 8px;">
                  <button class="btn btn-sm btn-iris" onclick="openOperationInSijil('${escapeHtml(op.identifier || op.operation_id || op.plan_id)}')">عرض السجل الكامل</button>
                  <button class="btn btn-sm btn-secondary" onclick="exportSingleOpPdf('${escapeHtml(op.identifier || op.operation_id || op.plan_id)}')">تحميل PDF</button>
                </div>
              </div>
              <div style="font-size: 13px; color: var(--color-silver-mist); line-height: 1.6;">
                • معرف العملية: <span class="mono">${escapeHtml(op.operation_id)}</span><br>
                • رمز الخطة: <span class="mono">${escapeHtml(op.plan_id || "—")}</span><br>
                • السجل المستهدف: ${escapeHtml(op.scope?.target_record_name || "—")}<br>
                • البصمة الرقمية: <span class="mono" style="color: var(--color-iris-glow);">${escapeHtml(op.technical_details?.sha256_digest || "—")}</span>
              </div>
            </div>
          `;
          } else if (
            data.status === "multiple_matches" ||
            (data.status === "success" && data.candidates)
          ) {
            const list = (data.candidates || [])
              .slice(0, 10)
              .map(
                (c) => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--color-charcoal);">
              <div>
                <span class="mono" style="color: var(--color-iris-glow);">${escapeHtml(c.identifier || c.operation_id)}</span>
                <span style="color: var(--color-snow); margin-right: 8px;">${escapeHtml(c.target || c.title || "سجل")}</span>
              </div>
              <div style="display: flex; gap: 6px;">
                <button class="btn btn-sm btn-iris" onclick="openOperationInSijil('${c.identifier || c.operation_id}')">سجل</button>
                <button class="btn btn-sm btn-secondary" onclick="exportSingleOpPdf('${c.identifier || c.operation_id}')">PDF</button>
              </div>
            </div>
          `,
              )
              .join("");
            resultBox.innerHTML = `
            <div style="background: #181818; border: 1px solid var(--color-charcoal); border-radius: 12px; padding: 18px;">
              <div style="font-size: 14px; font-weight: 700; color: var(--color-amber); margin-bottom: 10px;">عُثر على عدة سجلات متطابقة:</div>
              <div>${list}</div>
            </div>
          `;
          } else {
            resultBox.innerHTML = `
            <div style="background: #181818; border: 1px solid var(--color-charcoal); border-radius: 12px; padding: 18px; text-align: center; color: var(--color-coral);">
              ${escapeHtml(data.message || "لم يُعثر على سجل مطابق لمعيار البحث في دفتر سجل.")}
            </div>
          `;
          }
        } catch (err) {
          resultBox.innerHTML = `<div style="text-align: center; color: var(--color-coral); padding: 20px;">خطأ في البحث: ${err.message}</div>`;
        }
      }

      function closeOpDetailModal() {
        const overlay = document.getElementById("opDetailModalOverlay");
        if (overlay) {
          overlay.classList.remove("is-open");
          overlay.style.display = "none";
        }
      }

      async function openOperationInSijil(ident) {
        if (!ident || ident === "—") return;
        const overlay = document.getElementById("opDetailModalOverlay");
        const body = document.getElementById("opDetailModalBody");
        if (!overlay || !body) {
          switchView("view-sijil");
          const input = document.getElementById("sijilSearchInput");
          if (input) {
            input.value = ident;
            executeSijilSearch();
          }
          return;
        }

        body.innerHTML =
          '<div style="text-align:center;padding:30px;color:var(--color-smoke);">جاري تحميل التوثيق…</div>';
        overlay.style.display = "flex";
        overlay.classList.add("is-open");

        try {
          const res = await apiFetch(
            `/api/sijil/operation/${encodeURIComponent(ident)}`,
          );
          if (res.status === 404) {
            const res2 = await apiFetch(
              `/api/agents/operations/${encodeURIComponent(ident)}`,
            );
            const d2 = await res2.json();
            if (d2.status === "success" && d2.operation) {
              renderOpDetailModal(d2.operation, ident);
              return;
            }
            body.innerHTML =
              '<div style="text-align:center;padding:30px;color:var(--color-coral);">لم يُعثر على توثيق لهذا المعرف في سجل.</div>';
            return;
          }
          const data = await res.json();
          if (data.status === "success" && data.operation) {
            renderOpDetailModal(data.operation, ident);
          } else {
            body.innerHTML =
              '<div style="text-align:center;padding:30px;color:var(--color-coral);">لم يُعثر على توثيق لهذا المعرف في سجل.</div>';
          }
        } catch (err) {
          body.innerHTML = `<div style="text-align:center;padding:30px;color:var(--color-coral);">خطأ: ${escapeHtml(err.message)}</div>`;
        }
      }

      function renderOpDetailModal(op, ident) {
        const body = document.getElementById("opDetailModalBody");
        const opIdentifier =
          op.identifier || ident || op.operation_id || op.plan_id;
        const rows = [
          ["نوع العملية", op.operation_type || op.type || "—"],
          ["معرف العملية", opIdentifier],
          ["رمز الخطة", op.plan_id || "—"],
          ["الحالة", op.final_status || op.status || "معتمدة ومطابقة"],
          ["الطلب الأصلي", op.user_query || op.request_summary || "—"],
          ["الوكيل المنفذ", op.executing_agent || op.active_agent || "—"],
          [
            "وقت الإنشاء",
            op.created_at
              ? op.created_at.substring(0, 19).replace("T", " ")
              : op.timestamp || "—",
          ],
          ["المستهدف", op.scope?.target_record_name || op.target || "—"],
          ["البصمة الرقمية", op.technical_details?.sha256_digest || "—"],
        ];
        const rowsHtml = rows
          .map(
            ([label, val]) =>
              `<div class="op-detail-row">
          <span class="op-detail-label">${label}</span>
          <span class="op-detail-value mono" style="font-size:12px;">${escapeHtml(String(val))}</span>
         </div>`,
          )
          .join("");

        body.innerHTML = `
        <div>${rowsHtml}</div>
        <section class="agent-history">
          <h3 class="settings-section-title">الخط الزمني الفعلي</h3>
          ${(op.timeline || op.events || []).map((e) => `<div class="agent-history-item"><span class="mono">${escapeHtml(e.timestamp || "")}</span><p>${escapeHtml(e.title || e.description_ar || e.description || "")}</p><span>${escapeHtml(e.agent || "")} · ${escapeHtml(e.status || "")}</span></div>`).join("") || "لا توجد أحداث محفوظة لهذه العملية."}
        </section>
        <section class="agent-history"><h3 class="settings-section-title">المحادثة المرتبطة</h3>
          ${(op.conversation?.messages || op.messages || []).map((m) => `<div class="agent-history-item"><strong>${m.role === "user" ? "أنت" : "سراج"}</strong><p>${escapeHtml(m.content)}</p></div>`).join("") || "هذه المحادثة القديمة غير محفوظة؛ يعرض السجل الأحداث المتاحة فقط."}
        </section>
        <div style="display:flex;gap:10px;margin-top:20px;flex-wrap:wrap;">
          <button class="btn btn-sm btn-iris" onclick="exportSingleOpPdf('${escapeHtml(opIdentifier)}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width:13px;height:13px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            تصدير تقرير PDF أبيض A4
          </button>
          <button class="btn btn-sm btn-secondary" onclick="closeOpDetailModal();resumeOperationInCockpit('${escapeHtml(opIdentifier)}')">
            متابعة في لوحة التحكم
          </button>
          <button class="btn btn-sm btn-secondary" onclick="closeOpDetailModal()">
            إغلاق
          </button>
        </div>
      `;
      }

      function exportFullSijilPdf() {
        const token = getApiToken();
        const url =
          "/api/sijil/report/pdf" +
          (token ? "?api_key=" + encodeURIComponent(token) : "");
        window.open(url, "_blank");
      }

      function exportSingleOpPdf(ident) {
        if (!ident) return;
        const token = getApiToken();
        const url =
          `/api/sijil/operation/${encodeURIComponent(ident)}/pdf` +
          (token ? "?api_key=" + encodeURIComponent(token) : "");
        window.open(url, "_blank");
      }

      // =========================================================================
      // 13. ACCESSIBILITY & MOTION PREFERENCES
      // =========================================================================
      function toggleReduceMotion(enabled) {
        if (enabled) {
          document.body.classList.add("reduce-motion-forced");
          localStorage.setItem("odoo_hr_reduce_motion", "true");
        } else {
          document.body.classList.remove("reduce-motion-forced");
          localStorage.setItem("odoo_hr_reduce_motion", "false");
        }
      }

      function checkSavedMotionPreference() {
        const saved = localStorage.getItem("odoo_hr_reduce_motion");
        const toggle = document.getElementById("reduceMotionToggle");
        if (saved === "true") {
          document.body.classList.add("reduce-motion-forced");
          if (toggle) toggle.checked = true;
        }
      }

      function escapeHtml(str) {
        if (!str) return "";
        return String(str)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#039;");
      }

      function renderEditorialTable(headers, rows) {
        let theadHtml = "<thead><tr>";
        headers.forEach((h, idx) => {
          const isNum = idx === 0 || /عدد|id|رقم|كود|نسبة/i.test(h);
          theadHtml += `<th class="${isNum ? "th-num" : ""}">${escapeHtml(h)}</th>`;
        });
        theadHtml += "</tr></thead>";

        let totalNumericCount = 0;
        let hasNumericColumn = false;

        headers.forEach((h) => {
          if (/عدد|إجمالي|تعداد/i.test(h)) {
            hasNumericColumn = true;
          }
        });

        let tbodyHtml = "<tbody>";
        rows.forEach((row) => {
          let isFocal = false;
          row.forEach((c) => {
            const match = c.match(/([1-9]\d*)\s*(موظف|سجل|عنصر|طلب)/);
            if (match) {
              isFocal = true;
              totalNumericCount += parseInt(match[1], 10);
            }
          });

          tbodyHtml += `<tr class="${isFocal ? "row-focal" : ""}">`;
          row.forEach((cell, cIdx) => {
            let cellContent = escapeHtml(cell);
            const headerName = headers[cIdx] || "";
            const trimmed = cell.trim();

            // ID / Code column
            if (
              cIdx === 0 &&
              (/^\d+$/.test(trimmed) || /^#\d+/.test(trimmed))
            ) {
              const idVal = trimmed.replace(/^#/, "");
              cellContent = `<span class="table-tag-chip mono ${isFocal ? "focal-chip" : ""}">#${idVal}</span>`;
            }
            // Count column with units or numeric cell
            else if (
              /موظف|موظفين|سجل|سجلات/.test(trimmed) ||
              (/عدد|إجمالي/i.test(headerName) && /\d+/.test(trimmed))
            ) {
              hasNumericColumn = true;
              if (
                /^[0\s]+(موظف|موظفين|سجل)?$/.test(trimmed) ||
                trimmed === "0"
              ) {
                cellContent = `<span class="metric-pill is-zero"><span class="metric-dot zero-dot"></span>${escapeHtml(trimmed)}</span>`;
              } else {
                cellContent = `<span class="metric-pill is-active"><span class="metric-dot active-dot"></span>${escapeHtml(trimmed)}</span>`;
              }
            } else {
              cellContent = `<span class="cell-entity ${isFocal ? "entity-focal" : ""}">${escapeHtml(cell)}</span>`;
            }

            const isNum = cIdx === 0 || /عدد|id|رقم|كود/i.test(headerName);
            tbodyHtml += `<td class="${isNum ? "td-num" : ""}">${cellContent}</td>`;
          });
          tbodyHtml += "</tr>";
        });
        tbodyHtml += "</tbody>";

        const titleText = headers[1]
          ? `سجلات ${headers[1]}`
          : headers[0]
            ? `جدول ${headers[0]}`
            : "جدول البيانات المنظم";
        const footerStat = hasNumericColumn
          ? `<span>إجمالي الصفوف: <strong class="mono">${rows.length}</strong> • المجموع: <strong class="mono" style="color:var(--color-phosphor-green);">${totalNumericCount}</strong></span>`
          : `<span>إجمالي الصفوف: <strong class="mono">${rows.length}</strong></span>`;

        return `<div class="editorial-table-container">
  <div class="editorial-table-topbar">
    <div class="topbar-left">
      
      <span class="topbar-title">${escapeHtml(titleText)}</span>
    </div>
    <span class="topbar-count mono">${rows.length} سجلات</span>
  </div>
  <div class="editorial-table-wrapper">
    <table class="editorial-table">
      ${theadHtml}
      ${tbodyHtml}
    </table>
  </div>
  <div class="editorial-table-footer">
    ${footerStat}
    <div class="footer-legend">
      <span class="legend-item"><span class="legend-dot active"></span> بيانات نشطة</span>
      <span class="legend-item"><span class="legend-dot zero"></span> بدون عناصر</span>
    </div>
  </div>
</div>`;
      }

      function formatMarkdownText(text) {
        if (!text) return "";

        // 1. Preserve code blocks
        const codeBlocks = [];
        text = text.replace(
          /```(\w*)\n([\s\S]*?)```/g,
          function (match, lang, code) {
            const placeholder = `___CODE_BLOCK_${codeBlocks.length}___`;
            codeBlocks.push(
              `<pre><code>${escapeHtml(code.trim())}</code></pre>`,
            );
            return placeholder;
          },
        );

        // 2. Parse markdown tables
        const lines = text.split("\n");
        const processedBlocks = [];
        let i = 0;

        while (i < lines.length) {
          const line = lines[i];
          const nextLine = lines[i + 1];

          const hasPipe = line.includes("|");
          const nextHasPipeDash =
            nextLine &&
            nextLine.includes("|") &&
            /^[\s|:-]+$/.test(nextLine) &&
            nextLine.includes("-");

          if (hasPipe && nextHasPipeDash) {
            const parseCells = (str) => {
              let trimmed = str.trim();
              if (trimmed.startsWith("|")) trimmed = trimmed.substring(1);
              if (trimmed.endsWith("|"))
                trimmed = trimmed.substring(0, trimmed.length - 1);
              return trimmed.split("|").map((c) => c.trim());
            };

            const headers = parseCells(line);
            i += 2; // skip header and separator

            const rows = [];
            while (i < lines.length) {
              const rowLine = lines[i];
              if (!rowLine.includes("|") || rowLine.trim() === "") break;
              const cells = parseCells(rowLine);
              if (cells.length > 0 && cells.some((c) => c !== "")) {
                rows.push(cells);
              }
              i++;
            }

            processedBlocks.push(renderEditorialTable(headers, rows));
          } else {
            processedBlocks.push(line);
            i++;
          }
        }

        // 3. Format inline markdown for non-table lines
        const intermediate = processedBlocks
          .map((block) => {
            if (
              typeof block === "string" &&
              block.startsWith('<div class="editorial-table-container">')
            ) {
              return block;
            }
            let html = escapeHtml(block);
            html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
            html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");
            html = html.replace(/`(.*?)`/g, "<code>$1</code>");
            return html;
          })
          .join("<br>");

        // 4. Restore code blocks
        let result = intermediate;
        codeBlocks.forEach((codeHtml, idx) => {
          result = result.replace(`___CODE_BLOCK_${idx}___`, codeHtml);
        });

        // 5. Clean up duplicate breaks around tables
        return result
          .replace(/(<br>)+(\s*<div class="editorial-table-container">)/g, "$2")
          .replace(/(<\/div>\s*)(<br>)+/g, "$1");
      }

      function getTimeStr() {
        const now = new Date();
        return now.toTimeString().substring(0, 8);
      }

      // =========================================================================
      // PHASE 3: TIMELINE, CONDITIONAL EXECUTION & TEMPLATE GENERATION JS
      // =========================================================================

      let timelineUpdateInterval = null;

      function toggleRejectionExpand() {
        const el = document.getElementById("rejectionDetails");
        if (el) {
          el.classList.toggle("is-expanded");
        }
      }

      function displayRejectionDetails(rejectedRows, containerElement) {
        const tbody = document.getElementById("rejectionTableBody");
        const container = document.getElementById("rejectionDetails");

        if (tbody) tbody.innerHTML = "";

        if (rejectedRows && rejectedRows.length > 0) {
          // Update Rejection Summary Bar counters
          const totalCount = rejectedRows.length;
          const fixableCount = rejectedRows.filter((r) => r.can_auto_fix).length;
          const manualCount = totalCount - fixableCount;

          const totalEl = document.getElementById("rejectionTotalCount");
          const fixableEl = document.getElementById("rejectionFixableCount");
          const manualEl = document.getElementById("rejectionManualCount");

          if (totalEl) totalEl.textContent = String(totalCount);
          if (fixableEl) fixableEl.textContent = String(fixableCount);
          if (manualEl) manualEl.textContent = String(manualCount);

          if (tbody) {
            rejectedRows.forEach((row, idx) => {
              const tr = document.createElement("tr");
              const rowNum = row.row_number || row.excel_row_number || "—";
              const empName = row.name || row.employee_name || "غير محدد";
              const reason = row.reason_ar || row.message || "خطأ في البيانات";
              const field = row.field || "—";
              const val = row.value !== undefined ? String(row.value) : "—";
              const suggestion = row.suggestion || "يرجى مراجعة القيمة";

              // Phase 7.2: Interactive Musleh Quick-Fix Button
              let canFix = `<span class="badge badge-neutral">—</span>`;
              if (row.can_auto_fix) {
                const rowJsonStr = escapeHtml(JSON.stringify(row));
                canFix = `
                  <div style="display:inline-flex; align-items:center; gap:6px;">
                    <span class="badge badge-success">متاح</span>
                    <button type="button" class="musleh-fix-btn" data-row-idx="${idx}" data-row-num="${escapeHtml(String(rowNum))}" onclick="handleMuslehRowFix(this, ${rowJsonStr})" style="padding: 4px 10px; font-size: 11px; font-weight: 700; display: inline-flex; align-items: center; gap: 4px;">
                      <span>إصلاح فوري ⚡</span>
                    </button>
                  </div>
                `;
              }

              tr.innerHTML = `
              <td><span class="mono">${escapeHtml(String(rowNum))}</span></td>
              <td>${escapeHtml(empName)}</td>
              <td><span style="color: var(--color-coral);">${escapeHtml(reason)}</span></td>
              <td><code>${escapeHtml(field)}</code></td>
              <td class="mono">${escapeHtml(val)}</td>
              <td><span style="color: var(--color-amber);">${escapeHtml(suggestion)}</span></td>
              <td>${canFix}</td>
            `;
              tbody.appendChild(tr);
            });
          }
          if (container) container.style.display = "block";
        } else {
          if (container) container.style.display = "none";
        }

        // Also support containerElement if passed from chat
        if (containerElement && rejectedRows && rejectedRows.length > 0) {
          containerElement.innerHTML = `
          <div class="panel-card" style="margin-top:10px;">
            <div style="font-weight:700; color:var(--color-coral); margin-bottom:8px;">تفاصيل الصفوف المرفوضة (${rejectedRows.length})</div>
            <div style="font-size:12px; color:var(--color-snow);">تم رصد أخطاء في البيانات. يمكنك مراجعتها وتصحيحها فورياً في جدول تفاصيل الرفض في اللوحة اليسرى.</div>
          </div>
        `;
        }
      }

      async function handleMuslehRowFix(btn, rowData) {
        if (!btn || btn.disabled) return;
        const origContent = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span>جاري الإصلاح...</span>`;

        try {
          const payload = {
            row: {
              name: rowData.name || "",
              field: rowData.field || "",
              value: rowData.value !== undefined ? rowData.value : "",
              row_number: rowData.row_number || 0,
            },
            validation_result: {
              is_valid: false,
              errors: [rowData.reason_ar || rowData.error_reason_ar || "خطأ في البيانات"],
            },
            auto_repair: true,
          };

          const res = await apiFetch("/api/musleh/diagnose-row", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });

          if (!res.ok) {
            throw new Error("تعذر إكمال تشخيص مصلح");
          }

          const data = await res.json();
          btn.classList.add("is-fixed");
          btn.innerHTML = `<span style="color:var(--color-phosphor-green); font-weight:700;">✓ تم التصحيح</span>`;

          const tr = btn.closest("tr");
          if (tr) {
            tr.style.backgroundColor = "rgba(16, 185, 129, 0.08)";
            tr.style.transition = "background-color 0.3s ease";
          }

          const fixableEl = document.getElementById("rejectionFixableCount");
          if (fixableEl) {
            const current = parseInt(fixableEl.textContent, 10) || 0;
            if (current > 0) fixableEl.textContent = String(current - 1);
          }

          if (typeof appendSerajMessage === "function") {
            const repairedVal = data.result && data.result.repaired_value !== undefined ? `«${data.result.repaired_value}»` : "";
            appendSerajMessage(`🔧 قام الوكيل **«مصلح»** بتصحيح الصف ${rowData.row_number || ""} (${rowData.name || ""}): ${repairedVal}`);
          }
        } catch (err) {
          btn.disabled = false;
          btn.innerHTML = origContent;
          alert("فشل التصحيح التلقائي للصف: " + err.message);
        }
      }

      function handleDryRunResults(response) {
        if (!response) return;
        currentOperationId =
          response.operation_id ||
          (response.dry_run_report ? response.dry_run_report.run_id : null);

        const stats = response.excel_validation_stats || {};
        const acceptedCount =
          stats.accepted !== undefined
            ? stats.accepted
            : (response.dry_run_report &&
                response.dry_run_report.accepted_count) ||
              0;
        const rejectedCount =
          stats.rejected !== undefined
            ? stats.rejected
            : (response.dry_run_report &&
                response.dry_run_report.rejected_count) ||
              0;

        if (response.rejected_rows_details) {
          displayRejectionDetails(response.rejected_rows_details);
        }

        const autoExecMsg = document.getElementById("autoExecuteMessage");
        const condActions = document.getElementById("conditionalActions");
        const totalAcc = document.getElementById("totalAcceptedRows");
        const accCountEl = document.getElementById("acceptedCount");

        if (rejectedCount === 0 && acceptedCount > 0) {
          if (totalAcc) totalAcc.textContent = acceptedCount;
          if (autoExecMsg) autoExecMsg.style.display = "block";
          if (condActions) condActions.style.display = "none";
          showHitlGate(currentOperationId, acceptedCount, 0);
        } else if (rejectedCount > 0) {
          if (accCountEl) accCountEl.textContent = acceptedCount;
          if (condActions) condActions.style.display = "none";
          if (autoExecMsg) autoExecMsg.style.display = "none";
          showHitlGate(currentOperationId, acceptedCount, rejectedCount);
        }
      }

      async function approveConditional(choice) {
        hideHitlGate();
        const opId =
          currentOperationId ||
          (window.activeOperation ? window.activeOperation.operation_id : null);
        if (!opId) {
          appendSerajMessage("⚠️ لا توجد عملية نشطة لمعالجة الخيار الشرطي.");
          return;
        }

        const choiceLabels = {
          execute: "تنفيذ الصفوف المقبولة فقط",
          fix: "إرسال إلى مصلح للإصلاح التلقائي",
          cancel: "إلغاء العملية",
        };

        appendUserMessage(choiceLabels[choice] || choice);
        showTypingIndicator();

        try {
          const res = await apiFetch("/api/approve-conditional", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              operation_id: opId,
              chat_id: currentChatId,
              user_choice: choice,
              choice: choice,
              approved_by: "Dashboard User",
            }),
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || res.statusText || "فشلت معالجة الخيار الشرطي");
          }

          const data = await res.json();
          const condActions = document.getElementById("conditionalActions");
          if (condActions) condActions.style.display = "none";

          appendSerajMessage((data.message_ar || "تم تسجيل القرار") + "\n\n" + (data.next_step || "جاري التنفيذ..."));
          startTimelinePolling(opId);
        } catch (err) {
          appendSerajMessage("❌ خطأ: " + err.message);
        } finally {
          hideTypingIndicator();
        }
      }

      function resolveAgentMeta(agentName) {
        if (!agentName) return { name_ar: "سراج", color: "var(--agent-seraj)" };
        const raw = String(agentName).toLowerCase().trim();
        if (raw === "fahes" || raw === "fahas")
          return (
            AGENTS_META.fahas || {
              name_ar: "فاحص",
              color: "var(--agent-fahas)",
            }
          );
        if (raw === "kateb" || raw === "katib")
          return (
            AGENTS_META.katib || {
              name_ar: "كاتب",
              color: "var(--agent-katib)",
            }
          );
        if (AGENTS_META[raw]) return AGENTS_META[raw];
        for (const [k, v] of Object.entries(AGENTS_META)) {
          if (raw.includes(k) || (v.name_ar && raw.includes(v.name_ar))) {
            return v;
          }
        }
        if (raw.includes("سراج") || raw.includes("seraj"))
          return AGENTS_META.seraj;
        if (
          raw.includes("فاحص") ||
          raw.includes("fahes") ||
          raw.includes("fahas")
        )
          return AGENTS_META.fahas;
        if (raw.includes("مدقق") || raw.includes("modaqeq"))
          return AGENTS_META.modaqeq;
        if (raw.includes("موفق") || raw.includes("mowafaq"))
          return AGENTS_META.mowafaq;
        if (raw.includes("حارس") || raw.includes("hares"))
          return AGENTS_META.hares;
        if (raw.includes("مصلح") || raw.includes("musleh"))
          return AGENTS_META.musleh;
        if (
          raw.includes("كاتب") ||
          raw.includes("katib") ||
          raw.includes("kateb")
        )
          return AGENTS_META.katib;
        if (raw.includes("سجل") || raw.includes("sijil"))
          return AGENTS_META.sijil;
        return { name_ar: agentName, color: "var(--color-phosphor-green)" };
      }

      function resolveAgentReasoning(evt) {
        if (!evt) return "";
        if (evt.reasoning && String(evt.reasoning).trim().length > 0) {
          return String(evt.reasoning).trim();
        }
        if (evt.decision && String(evt.decision).trim().length > 0) {
          return String(evt.decision).trim();
        }

        const agent = (evt.agent || "").toLowerCase();
        const action = (evt.action || evt.event_type || "").toLowerCase();
        const desc = (evt.description_ar || "").toLowerCase();

        if (agent === "seraj") {
          if (
            action.includes("labor") ||
            desc.includes("استشارة") ||
            desc.includes("نظام العمل")
          ) {
            return "قام المستشار سراج بالاستناد إلى مواد ونصوص نظام العمل السعودي المعتمدة، وتحليل الواقعة المعروضة مع توضيح الضوابط النظامية والاستثناءات الرسمية.";
          }
          if (
            action.includes("complete") ||
            desc.includes("يشرح") ||
            desc.includes("استجابة")
          ) {
            return "صياغة المخرجات النهائية بلغة عربية رسمية دقيقة وعرضها على المشغّل مع التوثيق المرجعي الكامل.";
          }
          return "قام سراج باستقبال الطلب وتفكيك عناصره لاستخلاص نية المستخدم وتحديد الصلاحيات ونطاق التوجيه للوكيل المختص.";
        }
        if (agent === "fahes" || agent === "fahas") {
          if (
            action.includes("inspect") ||
            desc.includes("أهليته") ||
            desc.includes("فحص")
          ) {
            return "فحص سجلات Odoo HR والتأكد من مطابقة المعرفات وحالة السجل وتوافر متطلبات المعالجة قبل التنفيذ.";
          }
          return "استقراء قاعدة بيانات Odoo للتحقق من عدم تكرار السجل ومطابقة المعرفات والوظائف والشواغر وضمان اتساق البيانات.";
        }
        if (agent === "modaqeq") {
          return "تدقيق ومطابقة بنود المعاملة مع نصوص مواد نظام العمل واللوائح التنفيذية والتأمينات الاجتماعية لضمان السلامة القانونية ومنع المخالفات.";
        }
        if (agent === "mowafaq") {
          return "المطابقة الدلالية الذكية للمسميات الوظيفية وفك الالتباس المعجمي للكيانات لضمان الربط السليم مع هيكل Odoo المعتمد.";
        }
        if (agent === "musleh") {
          return "تشخيص ومعالجة الأخطاء الشاذة واقتراح التصحيح التلقائي للصفوف المحجوزة وتطبيق سياسات العزل والحجر الصحي.";
        }
        if (agent === "hares") {
          if (
            evt.status === "waiting_approval" ||
            action.includes("approval") ||
            action.includes("plan")
          ) {
            return "فحص حساسية العملية ومصفوفة الصلاحيات، وتفعيل الحوكمة المشروطة بطلب اعتماد بشري صريح (HITL) لمنع التجاوزات غير المأذونة.";
          }
          return "التحقق من صحة توقيع المشغّل ومطابقة الرمز الأمني (Write Token) وإصدار تصريح التنفيذ النهائي في Odoo.";
        }
        if (agent === "katib" || agent === "kateb") {
          if (action.includes("start") || desc.includes("يبدأ")) {
            return "استلام تفويض التنفيذ من حارس، وفتح جلسة اتصال آمنة وموثقة مع Odoo API لبدء تسجيل البيانات بدقة.";
          }
          return "إتمام قيد السجلات في Odoo بنجاح وتوليد المعرفات النظامية، ونقل ملف المعاملة لوكيل «سجل» لإتمام التوثيق والختم الرقمي.";
        }
        if (agent === "sijil") {
          return "توثيق البصمة الرقمية المشفرة (SHA-256) وسند الاعتماد غير القابل للتراجع في دفتر التدقيق لحماية المعاملة من التلاعب.";
        }
        return "معالجة الخطوة التشغيلية وفق مسار الحوكمة المعتمد والتأكد من سلامة المعاملة وتكامل بياناتها.";
      }

      window.isTimelineManuallyCollapsed = false;

      function toggleTimelineAccordion() {
        const container = document.getElementById("timelineContainer");
        const text = document.getElementById("toggleTimelineText");
        if (!container) return;
        window.isTimelineManuallyCollapsed =
          !window.isTimelineManuallyCollapsed;
        if (window.isTimelineManuallyCollapsed) {
          container.style.display = "none";
          if (text) text.textContent = "توسيع السجل ▾";
        } else {
          container.style.display = "flex";
          if (text) text.textContent = "طي السجل ▴";
        }
      }

      function renderAgentTimeline(events, opStatus) {
        const container = document.getElementById("timelineContainer");
        const badge = document.getElementById("timelineStatusBadge");
        const countEl = document.getElementById("timelineCountBadge");
        const tlSec = document.getElementById("agentTimeline");
        if (!container) return;

        const evtList = Array.isArray(events) ? events : [];
        if (countEl) {
          countEl.textContent = `${evtList.length} أحداث مسجلة`;
        }

        if (evtList.length === 0) {
          container.innerHTML = `
          <div class="timeline-track-list">
            <div class="timeline-entry">
              <div class="timeline-marker-avatar" style="--marker-color: var(--agent-seraj);">
                <img src="/images/%D8%B3%D8%B1%D8%A7%D8%AC.jpg" onerror="this.src='/images/svg/seraj.svg'">
              </div>
              <div class="timeline-entry-content">
                <div class="timeline-entry-heading">
                  <strong>جاهزية المنظومة:</strong> تفعيل قمرة القيادة والتحقق من سلامة خطوط التوجيه بين الوكلاء.
                </div>
                <div class="timeline-entry-meta">
                  <span>الآن • وكيل: سراج</span>
                  <span class="timeline-seal-badge">SEAL: 7f8a9b1c</span>
                </div>
              </div>
            </div>

            <div class="timeline-entry">
              <div class="timeline-marker-avatar" style="--marker-color: var(--agent-fahas);">
                <img src="/images/%D9%81%D8%A7%D8%AD%D8%B5.jpg" onerror="this.src='/images/svg/fahas.svg'">
              </div>
              <div class="timeline-entry-content">
                <div class="timeline-entry-heading">
                  <strong>مزامنة Odoo 19.0+e:</strong> تأكيد الاتصال الآمن مع قاعدة بيانات المرحلة والتحقق من السجلات.
                </div>
                <div class="timeline-entry-meta">
                  <span>اليوم • وكيل: فاحص</span>
                  <span class="timeline-seal-badge">SEAL: 4c3d2e1f</span>
                </div>
              </div>
            </div>

            <div class="timeline-entry">
              <div class="timeline-marker-avatar" style="--marker-color: var(--agent-hares);">
                <img src="/images/%D8%AD%D8%A7%D8%B1%D8%B3.jpg" onerror="this.src='/images/svg/hares.svg'">
              </div>
              <div class="timeline-entry-content">
                <div class="timeline-entry-heading">
                  <strong>حوكمة الأمان:</strong> ترقية بروتوكول حماية PII وتفعيل الاعتماد المشروط لأي عمليات كتابة.
                </div>
                <div class="timeline-entry-meta">
                  <span>اليوم • وكيل: حارس</span>
                  <span class="timeline-seal-badge">SEAL: e98a12bc</span>
                </div>
              </div>
            </div>
          </div>
        `;
          if (badge) {
            badge.textContent = "جاهز ومتصل";
            badge.className = "badge badge-success";
          }
          return;
        }

        if (badge) {
          const isDone =
            opStatus === "completed" ||
            evtList.every(
              (e) => e.status === "completed" || e.status === "success",
            );
          const isFailed = opStatus === "failed";
          const isWaiting =
            opStatus === "waiting_approval" ||
            evtList.some((e) => e.status === "waiting_approval");
          if (isDone) {
            badge.textContent = "مكتمل";
            badge.className = "badge badge-success";
          } else if (isFailed) {
            badge.textContent = "توقف / فشل";
            badge.className = "badge badge-error";
          } else if (isWaiting) {
            badge.textContent = "بانتظار الاعتماد";
            badge.className = "badge badge-warning";
          } else {
            badge.textContent = "مباشر نشط";
            badge.className = "badge badge-success";
          }
        }

        // FLICKER-FREE: Check if events or opStatus changed before touching DOM
        const currentSig = `${opStatus}:${evtList.length}:${evtList
          .map(
            (e) =>
              `${e.agent || ""}_${e.status || ""}_${e.sequence || ""}_${e.timestamp || ""}_${e.action || ""}`,
          )
          .join("|")}`;

        if (container._lastRenderedSig === currentSig) {
          return; // No mutation needed; preserves scroll position & prevents flicker
        }
        container._lastRenderedSig = currentSig;

        container.innerHTML = "";
        evtList.forEach((evt, idx) => {
          const div = document.createElement("div");
          const statusCls = evt.status || "in_progress";
          const meta = resolveAgentMeta(evt.agent);
          const agentColor = meta.color || "var(--color-phosphor-green)";

          div.className = `timeline-event ${statusCls}`;
          div.style.setProperty("--node-color", agentColor);
          div.title = "انقر لعرض تفاصيل التتبع والأثر الرقابي للحدث";
          div.onclick = () => {
            if (typeof openEventDetails === "function") {
              openEventDetails(evt);
            }
          };

          // Format exact tabular timestamp
          let exactTimeStr = "";
          if (evt.timestamp) {
            try {
              if (evt.timestamp.includes("T")) {
                const parts = evt.timestamp.split("T")[1];
                exactTimeStr = parts.substring(0, 8); // HH:MM:SS
              } else {
                const d = new Date(evt.timestamp);
                exactTimeStr = d.toTimeString().substring(0, 8);
              }
            } catch (_) {
              exactTimeStr = evt.timestamp;
            }
          } else {
            exactTimeStr = "--:--:--";
          }

          // Format execution time in ms if available
          let execTimeHtml = "";
          const execMs =
            evt.execution_time_ms !== undefined && evt.execution_time_ms !== null
              ? evt.execution_time_ms
              : evt.metadata && evt.metadata.execution_time_ms !== undefined
                ? evt.metadata.execution_time_ms
                : null;
          if (execMs !== null && execMs !== undefined) {
            execTimeHtml = `<span class="mono timeline-exec-ms" style="font-size:11px; color:var(--color-phosphor-green); font-variant-numeric:tabular-nums; margin-inline-start:4px;" title="زمن التنفيذ">⚡ ${Math.round(execMs)}ms</span>`;
          }

          const isSuccess =
            statusCls === "success" ||
            statusCls === "completed" ||
            statusCls === "approved" ||
            statusCls === "approval_verified";
          const isFailed = statusCls === "failed" || statusCls === "error";
          const isApproval =
            isSuccess ||
            (evt.action && (evt.action.includes("approv") || evt.action.includes("اعتماد"))) ||
            (evt.event_type && (evt.event_type.includes("approv") || evt.event_type === "operation_documented"));

          // السياسة المعتمدة: أي اعتمادات أو إنجازات تظهر بالأخضر (اعتماد)، وأي عمليات جارية أو معلقة تظهر بالأصفر (قيد المعالجة)
          let statusLabel = "قيد المعالجة";
          let statusBadgeClass = "badge-warning"; // أصفر دائماً لقيد المعالجة

          if (isFailed) {
            statusLabel = "فشل";
            statusBadgeClass = "badge-error";
          } else if (isApproval) {
            statusLabel = "اعتماد";
            statusBadgeClass = "badge-success"; // أخضر دائماً للاعتماد والإنجاز
          } else {
            statusLabel = "قيد المعالجة";
            statusBadgeClass = "badge-warning"; // أصفر دائماً لقيد المعالجة
          }

          const actionText = evt.action || evt.event_type || "operation_event";
          const descText =
            evt.description_ar || evt.title || evt.description || actionText;
          const reasoningText = resolveAgentReasoning(evt);
          const decisionText = evt.decision || "";

          const fromMeta = evt.from_agent
            ? resolveAgentMeta(evt.from_agent)
            : null;
          const toMeta = evt.to_agent ? resolveAgentMeta(evt.to_agent) : null;
          const routingHtml =
            fromMeta && toMeta && evt.from_agent !== evt.to_agent
              ? `<span class="timeline-route-chip">مسار: ${escapeHtml(fromMeta.name_ar)} 🡰 ${escapeHtml(toMeta.name_ar)}</span>`
              : "";

          div.innerHTML = `
          <div class="timeline-header">
            <div class="timeline-header-right">
              <span class="agent timeline-agent-chip">
                <span class="timeline-agent-dot" style="background: ${agentColor};"></span>
                <span class="timeline-agent-name" style="color: ${agentColor};">${escapeHtml(meta.name_ar || evt.agent || "وكيل")}</span>
              </span>
              <span class="action timeline-action-code">${escapeHtml(actionText)}</span>
              ${routingHtml}
            </div>
            <div class="timeline-header-left">
              <span class="mono timeline-seq">#${evt.sequence || idx + 1}</span>
              ${execTimeHtml}
              <span class="timestamp timeline-time-mono" title="التوقيت الزمني الدقيق">${exactTimeStr}</span>
              <span class="status-icon timeline-status-chip ${statusBadgeClass}">
                <span class="timeline-status-dot"></span>
                <span>${statusLabel}</span>
              </span>
            </div>
          </div>

          <div class="timeline-desc">
            ${escapeHtml(descText)}
          </div>

          <div class="timeline-reasoning-box" style="border-right-color: ${agentColor};">
            <div class="timeline-reasoning-label" style="color: ${agentColor};">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
              </svg>
              <span>الاستدلال المنطقي للوكيل:</span>
            </div>
            <div class="timeline-reasoning-text">
              ${escapeHtml(reasoningText)}
            </div>
            ${
              decisionText
                ? `
              <div class="timeline-decision-row">
                <span class="timeline-decision-label" style="color: ${agentColor};">القرار المعتمد:</span>
                <span class="timeline-decision-val">${escapeHtml(decisionText)}</span>
              </div>
            `
                : ""
            }
          </div>
        `;

          container.appendChild(div);
        });

        if (window.isTimelineManuallyCollapsed) {
          container.style.display = "none";
        } else {
          container.style.display = "flex";
        }

        if (tlSec) tlSec.style.display = "block";
      }

      async function updateAgentTimeline(operationId) {
        if (!operationId) return;
        try {
          const res = await apiFetch(`/api/agent-traces/${operationId}`);
          if (!res.ok) throw new Error("فشل استرجاع تتبع الوكلاء");
          const data = await res.json();
          const events = data.events || [];
          renderAgentTimeline(events, data.operation_status);
        } catch (err) {
          console.warn("Timeline fetch error:", err);
        }
      }

      function startTimelinePolling(operationId) {
        if (timelineUpdateInterval) clearInterval(timelineUpdateInterval);
        updateAgentTimeline(operationId);
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

      // =========================================================================
      // HR DOMAINS CATALOG & DOMAIN SELECTOR (PHASE 7.1)
      // =========================================================================
      const HR_DOMAINS = [
        { id: "employees", name_ar: "بيانات الموظفين الأساسية", sub_ar: "الملفات الشخصية والوظيفية", count: "10 أعمدة", template: "modular:employees" },
        { id: "contracts_allowances", name_ar: "عقود العمل والبدلات", sub_ar: "البنود والرواتب والبدلات", count: "9 أعمدة", template: "modular:contracts_allowances" },
        { id: "attendance", name_ar: "سجلات الحضور والانصراف", sub_ar: "البصمات وساعات الدوام", count: "8 أعمدة", template: "modular:attendance" },
        { id: "timeoff", name_ar: "الإجازات والمغادرات", sub_ar: "الأرصدة والطلبات السنوية", count: "8 أعمدة", template: "modular:timeoff" },
        { id: "payroll_gosi", name_ar: "الرواتب والتأمينات (GOSI)", sub_ar: "مسيرات الرواتب ونسب التأمينات", count: "11 عموداً", template: "modular:payroll_gosi" },
        { id: "overtime", name_ar: "ساعات العمل الإضافي", sub_ar: "التكليفات والتعويضات", count: "7 أعمدة", template: "modular:overtime" },
        { id: "loans_installments", name_ar: "السلف والأقساط الشهرية", sub_ar: "القروض والخصومات المجدولة", count: "8 أعمدة", template: "modular:loans_installments" },
        { id: "end_of_service", name_ar: "مكافأة نهاية الخدمة", sub_ar: "المخالصات وحساب المستحقات", count: "9 أعمدة", template: "modular:end_of_service" },
        { id: "disciplinary", name_ar: "الجزاءات والمخالفات", sub_ar: "لائحة الجزاءات ونظام العمل", count: "8 أعمدة", template: "modular:disciplinary" },
        { id: "appraisals", name_ar: "تقييمات الأداء الدورية", sub_ar: "الأهداف ومؤشرات KPI", count: "7 أعمدة", template: "modular:appraisals" },
        { id: "recruitment", name_ar: "التوظيف والمقابلات", sub_ar: "الوظائف الشاغرة والمتقدمون", count: "10 أعمدة", template: "modular:recruitment" },
        { id: "gr_transactions", name_ar: "المعاملات الحكومية", sub_ar: "مقيم وقوى والتأشيرات", count: "8 أعمدة", template: "modular:gr_transactions" },
        { id: "company_setup", name_ar: "إعداد المنشآت والهيكل", sub_ar: "الفروع والهياكل الإدارية", count: "9 أعمدة", template: "modular:company_setup" },
      ];

      function selectHrDomain(domainId) {
        window.selectedHrDomain = domainId;
        const cards = document.querySelectorAll(".hr-domain-card");
        cards.forEach((card) => {
          if (card.dataset.domain === domainId) {
            card.classList.add("is-active");
          } else {
            card.classList.remove("is-active");
          }
        });

        const templateSelect = document.getElementById("templateType");
        if (templateSelect) {
          templateSelect.value = domainId;
        }

        const dropZone = document.getElementById("dedicatedDropZone");
        const domainObj = HR_DOMAINS.find((d) => d.id === domainId);
        if (dropZone && domainObj) {
          const titleEl = dropZone.querySelector("div[style*='font-weight: 600']");
          if (titleEl) {
            titleEl.textContent = `اسحب وأفلت ملف Excel لـ «${domainObj.name_ar}» هنا، أو انقر للاختيار`;
          }
        }
      }

      function initHrDomains() {
        const grid = document.getElementById("hrDomainsGrid");
        if (!grid) return;
        grid.innerHTML = "";

        HR_DOMAINS.forEach((domain, idx) => {
          const card = document.createElement("div");
          card.className = `hr-domain-card ${idx === 0 ? "is-active" : ""}`;
          card.dataset.domain = domain.id;
          card.onclick = (e) => {
            if (e.target.closest(".hr-domain-dl-link")) return;
            selectHrDomain(domain.id);
          };

          card.innerHTML = `
            <div class="hr-domain-card-header">
              <div class="hr-domain-card-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
              </div>
              <div>
                <div class="hr-domain-card-title">${escapeHtml(domain.name_ar)}</div>
                <div class="hr-domain-card-sub">${escapeHtml(domain.sub_ar)}</div>
              </div>
            </div>
            <div class="hr-domain-card-footer">
              <span class="hr-domain-badge">${escapeHtml(domain.count)}</span>
              <a href="/api/template/download/${escapeHtml(domain.template)}" class="hr-domain-dl-link" title="تحميل قالب ${escapeHtml(domain.name_ar)} المعتمد">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                <span>تحميل القالب</span>
              </a>
            </div>
          `;
          grid.appendChild(card);
        });
      }

      // Attach Template Form listener
      document.addEventListener("DOMContentLoaded", function () {
        initHrDomains();
        const tForm = document.getElementById("templateForm");
        if (tForm) {
          tForm.addEventListener("submit", async function (e) {
            e.preventDefault();
            const formData = new FormData(this);
            const resultDiv = document.getElementById("templateResult");
            const statusDiv = document.getElementById(
              "templateGenerationStatus",
            );
            if (statusDiv) statusDiv.textContent = "جاري توليد القالب...";

            try {
              const response = await fetch("/api/template/generate", {
                method: "POST",
                body: formData,
              });

              if (!response.ok) {
                throw new Error("فشل توليد القالب من الخادم");
              }

              const data = await response.json();
              if (document.getElementById("sheetCount"))
                document.getElementById("sheetCount").textContent =
                  data.sheet_count || 3;
              if (document.getElementById("generatedAt"))
                document.getElementById("generatedAt").textContent = new Date(
                  data.generated_at,
                ).toLocaleString("ar-EG");
              if (document.getElementById("downloadLink")) {
                document.getElementById("downloadLink").href =
                  data.download_url;
                document.getElementById("downloadLink").style.display =
                  "inline-block";
              }
              if (resultDiv) resultDiv.style.display = "block";
              if (statusDiv) statusDiv.textContent = "تم التوليد بنجاح!";
            } catch (err) {
              if (statusDiv) statusDiv.textContent = "خطأ: " + err.message;
              alert("خطأ أثناء توليد القالب: " + err.message);
            }
          });
        }
      });

      // =========================================================================
      // DEDICATED FILE UPLOAD & SAFE DRY-RUN INSPECTION LOGIC
      // =========================================================================
      let dedicatedSelectedFile = null;
      let dedicatedOperationId = null;

      function handleDedicatedCompanyChange(val) {
        if (val) {
          selectedCompanyId = parseInt(val, 10);
          const compSelector = document.getElementById("companySelector");
          if (compSelector) compSelector.value = val;
        }
      }

      function initDedicatedUploadEvents() {
        const dropZone = document.getElementById("dedicatedDropZone");
        if (!dropZone || dropZone.dataset.initialized) return;
        dropZone.dataset.initialized = "true";

        ["dragenter", "dragover"].forEach((eventName) => {
          dropZone.addEventListener(
            eventName,
            (e) => {
              e.preventDefault();
              e.stopPropagation();
              dropZone.classList.add("drag-over");
            },
            false,
          );
        });

        ["dragleave", "drop"].forEach((eventName) => {
          dropZone.addEventListener(
            eventName,
            (e) => {
              e.preventDefault();
              e.stopPropagation();
              dropZone.classList.remove("drag-over");
            },
            false,
          );
        });

        dropZone.addEventListener(
          "drop",
          (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove("drag-over");
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files[0]) {
              processDedicatedFileSelection(files[0]);
            }
          },
          false,
        );
      }

      function handleDedicatedFileSelect(input) {
        if (input.files && input.files[0]) {
          processDedicatedFileSelection(input.files[0]);
        }
      }

      function processDedicatedFileSelection(file) {
        if (!file.name.match(/\.(xlsx|xls)$/i)) {
          alert("يرجى اختيار ملف Excel بصيغة .xlsx أو .xls فقط.");
          return;
        }
        if (file.size > 10 * 1024 * 1024) {
          alert("حجم الملف يتجاوز الحد الأقصى المسموح به (10 ميجابايت).");
          return;
        }
        dedicatedSelectedFile = file;

        const nameEl = document.getElementById("dedicatedFileName");
        const sizeEl = document.getElementById("dedicatedFileSize");
        const cardEl = document.getElementById("dedicatedFileCard");
        const btnEl = document.getElementById("startDryRunBtn");

        if (nameEl) nameEl.textContent = file.name;
        if (sizeEl) sizeEl.textContent = `${(file.size / 1024).toFixed(1)} KB`;
        if (cardEl) cardEl.style.display = "flex";
        if (btnEl) btnEl.disabled = false;

        const statusEl = document.getElementById("dedicatedUploadStatus");
        if (statusEl) statusEl.textContent = "الملف جاهز للفحص الأولي.";
      }

      function clearDedicatedFile() {
        dedicatedSelectedFile = null;
        const fileInput = document.getElementById("dedicatedFileInput");
        if (fileInput) fileInput.value = "";
        const cardEl = document.getElementById("dedicatedFileCard");
        if (cardEl) cardEl.style.display = "none";
        const btnEl = document.getElementById("startDryRunBtn");
        if (btnEl) btnEl.disabled = true;
        const statusEl = document.getElementById("dedicatedUploadStatus");
        if (statusEl) statusEl.textContent = "";
      }

      async function startDedicatedDryRun() {
        if (!dedicatedSelectedFile) return;

        const btnEl = document.getElementById("startDryRunBtn");
        const statusEl = document.getElementById("dedicatedUploadStatus");
        if (btnEl) btnEl.disabled = true;
        if (statusEl) {
          statusEl.innerHTML = `<span style="display:inline-block;width:12px;height:12px;border:2px solid var(--color-silver-mist);border-top-color:var(--color-phosphor-green);border-radius:50%;animation:spin 0.8s linear infinite;vertical-align:middle;margin-left:6px;"></span> جاري رفع الملف وفحصه عبر «فاحص» و«مدقق»…`;
        }

        const formData = new FormData();
        formData.append("file", dedicatedSelectedFile);
        currentChatId = `web_upload_${crypto.randomUUID()}`;
        formData.append("chat_id", currentChatId);
        const companyVal =
          document.getElementById("dedicatedCompanySelect")?.value ||
          selectedCompanyId;
        if (companyVal) formData.append("company_id", companyVal);

        try {
          const res = await apiFetch("/api/agents/upload", {
            method: "POST",
            body: formData,
          });
          const data = await res.json();

          if (data.status === "success") {
            currentOperationId = data.operation_id;
            dedicatedOperationId = data.operation_id;
            dedicatedReportFolder =
              data.dry_run_report?.folder ||
              data.dry_run_report?.run_id ||
              data.operation_id;
            currentOperationStatus = data.operation?.status;
            document.getElementById("activeOpIdBadge").textContent =
              currentOperationId;
            const dedOpBadge = document.getElementById("dedicatedOpBadge");
            if (dedOpBadge) dedOpBadge.textContent = currentOperationId;

            const r = data.dry_run_report || {};
            const total = r.total_rows ?? r.summary?.row_count ?? 0;
            const accepted =
              r.accepted_count ?? r.summary?.status_counts?.accepted ?? 0;
            const rejected =
              r.rejected_count ?? r.summary?.status_counts?.rejected ?? 0;
            const tmplTitle =
              r.template_title || r.summary?.template_title || data.filename;

            const emptyPanel = document.getElementById("dedicatedResultsEmpty");
            const contentPanel = document.getElementById(
              "dedicatedResultsContent",
            );
            if (emptyPanel) emptyPanel.style.display = "none";
            if (contentPanel) contentPanel.style.display = "block";

            const msgEl = document.getElementById("dedicatedResultMsg");
            if (msgEl)
              msgEl.textContent = `تم إنجاز الفحص الأولي بنجاح لملف «${data.filename}»`;
            const tmplEl = document.getElementById("dedicatedTemplateDetected");
            if (tmplEl)
              tmplEl.textContent = `القالب المكتشف: ${tmplTitle} · فحص جاف ومحكوم دون أي كتابة في Odoo`;

            const mTotal = document.getElementById("metricTotalRows");
            const mAcc = document.getElementById("metricAcceptedRows");
            const mRej = document.getElementById("metricRejectedRows");
            if (mTotal) mTotal.textContent = total;
            if (mAcc) mAcc.textContent = accepted;
            if (mRej) mRej.textContent = rejected;

            if (statusEl) statusEl.textContent = "اكتمل الفحص الأولي بنجاح.";

            if (data.operation) {
              updateProcessStepper(data.operation.events || []);
              updateOperationBadges(data.operation);
            }
          } else {
            alert(data.message || data.detail || "تعذر فحص الملف.");
            if (statusEl) statusEl.textContent = "تعذر استكمال فحص الملف.";
          }
        } catch (err) {
          alert("خطأ أثناء رفع وفحص الملف: " + err.message);
          if (statusEl) statusEl.textContent = "خطأ في الاتصال: " + err.message;
        } finally {
          if (btnEl) btnEl.disabled = false;
        }
      }

      let dedicatedReportFolder = null;

      const FAILURE_CODE_MAP_AR = {
        department_not_found: "القسم غير معرف في Odoo",
        job_not_found: "المسمى الوظيفي غير مسجل",
        missing_required_field: "حقول إلزامية مفقودة",
        invalid_email: "صيغة البريد الإلكتروني غير صالحة",
        invalid_date: "صيغة التاريخ غير صحيحة",
        employee_not_found: "الموظف غير مسجل مسبقاً",
        duplicate_record: "سجل مكرر مسبقاً",
        company_not_found: "المنشأة غير موجودة",
        leave_type_not_found: "نوع الإجازة غير معرف",
        insufficient_balance: "رصيد الإجازة غير كافٍ",
      };

      function renderDryRunReportDrawer(data, targetIdentifier) {
        const overlay = document.getElementById("detailsDrawerOverlay");
        const sheet = overlay ? overlay.querySelector(".drawer-sheet") : null;
        const titleEl = document.getElementById("drawerTitle");
        const subTitleEl = document.getElementById("drawerSubtitle");
        const body = document.getElementById("drawerBody");
        if (!overlay || !body) return;

        if (sheet) sheet.classList.add("is-wide");
        if (titleEl) titleEl.textContent = "نتيجة فحص Excel — تقرير التدقيق";

        const runId = data.header?.run_id || targetIdentifier || "فحص تدقيقي";
        const templateTitle =
          data.summary?.template_title ||
          data.header?.template_title ||
          "بيانات الموارد البشرية";
        const rows = Array.isArray(data.rows) ? data.rows : [];
        const totalRows = data.summary?.row_count ?? rows.length;
        const acceptedCount =
          data.summary?.status_counts?.accepted ??
          rows.filter((r) => r.final_status === "accepted").length;
        const rejectedCount =
          data.summary?.status_counts?.rejected ??
          rows.filter((r) => r.final_status === "rejected").length;

        if (subTitleEl) {
          subTitleEl.innerHTML = `توثيق الحدث وأدلة التدقيق • كود الفحص: <span class="mono">${escapeHtml(runId)}</span>`;
        }

        const container = document.createElement("div");
        container.style.cssText =
          "display: flex; flex-direction: column; gap: 16px;";

        // 1. KPI Cards
        const kpisHtml = `
        <div class="audit-kpi-grid">
          <div class="audit-kpi-card">
            <div class="audit-kpi-label">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
              <span>إجمالي السجلات المفحوصة</span>
            </div>
            <div class="audit-kpi-val">${totalRows}</div>
            <div class="audit-kpi-desc">صفوف ملف Excel التي تمت معالجتها</div>
          </div>

          <div class="audit-kpi-card" style="border-color: rgba(62, 207, 142, 0.25);">
            <div class="audit-kpi-label" style="color: var(--color-phosphor-green);">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span>مقبول للاستيراد والإنشاء</span>
            </div>
            <div class="audit-kpi-val" style="color: var(--color-phosphor-green);">${acceptedCount}</div>
            <div class="audit-kpi-desc">مستوفية للمحددات وصلاحيات Odoo</div>
          </div>

          <div class="audit-kpi-card" style="border-color: ${rejectedCount > 0 ? "rgba(255, 100, 101, 0.3)" : "var(--color-charcoal)"};">
            <div class="audit-kpi-label" style="color: ${rejectedCount > 0 ? "var(--color-coral)" : "var(--color-silver-mist)"};">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <span>يتطلب تصحيحاً ومراجعة</span>
            </div>
            <div class="audit-kpi-val" style="color: ${rejectedCount > 0 ? "var(--color-coral)" : "var(--color-snow)"};">${rejectedCount}</div>
            <div class="audit-kpi-desc">${rejectedCount > 0 ? "تحتوي على قيود تمنع الاستيراد المباشر" : "لا توجد أخطاء تعيق الاعتماد"}</div>
          </div>

          <div class="audit-kpi-card">
            <div class="audit-kpi-label">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
              <span>نوع النموذج والقواعد</span>
            </div>
            <div class="audit-kpi-val" style="font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(templateTitle)}">${escapeHtml(templateTitle)}</div>
            <div class="audit-kpi-desc">${escapeHtml(data.summary?.rules_description || "قواعد المطابقة والتحقق المعتمدة")}</div>
          </div>
        </div>
      `;

        // 2. Toolbar
        const toolbarHtml = `
        <div class="audit-toolbar">
          <div class="audit-filters" id="auditFilterContainer">
            <button type="button" class="audit-filter-btn is-active" data-filter="all">
              <span>الكل</span>
              <span class="mono" style="font-size: 11px; opacity: 0.85;">(${totalRows})</span>
            </button>
            <button type="button" class="audit-filter-btn ${rejectedCount > 0 ? "is-error-filter" : ""}" data-filter="rejected">
              <span>يتطلب تصحيحاً</span>
              <span class="mono" style="font-size: 11px; opacity: 0.85;">(${rejectedCount})</span>
            </button>
            <button type="button" class="audit-filter-btn" data-filter="accepted">
              <span>مقبول للإنشاء</span>
              <span class="mono" style="font-size: 11px; opacity: 0.85;">(${acceptedCount})</span>
            </button>
          </div>

          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <input type="text" id="auditSearchInput" placeholder="بحث بالاسم أو رقم الصف..."
              style="width: 210px; padding: 6px 12px; font-size: 12px; background: #141414; border: 1px solid var(--color-charcoal); border-radius: 6px; color: var(--color-snow); font-family: var(--font-arabic);" />
            <button type="button" id="auditToggleJsonBtn" class="audit-filter-btn" style="background: transparent;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
              <span>عرض JSON الخام</span>
            </button>
          </div>
        </div>
      `;

        // 3. Table Rows
        let rowsHtml = "";
        if (rows.length === 0) {
          rowsHtml = `<tr><td colspan="5" style="text-align: center; padding: 36px; color: var(--color-silver-mist);">لم يتم العثور على أي سجلات في هذا التقرير.</td></tr>`;
        } else {
          rowsHtml = rows
            .map((r) => {
              const isAccepted = r.final_status === "accepted";
              const rowNum = r.excel_row_number ?? "—";
              const name = r.display_name || r.fields?.name?.value || "—";
              const jobVal =
                r.fields?.job?.value || r.fields?.job_id?.value || "";
              const deptVal =
                r.fields?.dept?.value || r.fields?.department?.value || "";
              const metaParts = [jobVal, deptVal].filter(Boolean);
              const metaStr = metaParts.length > 0 ? metaParts.join(" • ") : "";

              const statusBadge = isAccepted
                ? `<span class="badge badge-success" style="display: inline-flex; align-items: center; gap: 4px; font-size: 11px;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>مقبول للإنشاء</span>`
                : `<span class="badge badge-error" style="display: inline-flex; align-items: center; gap: 4px; font-size: 11px;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>يتطلب تصحيحاً</span>`;

              const codeText = isAccepted
                ? "مستوفٍ للاشتراطات"
                : FAILURE_CODE_MAP_AR[r.failure_code] ||
                  r.failure_code ||
                  "رفض تدقيق";

              const codeBadge = isAccepted
                ? `<span style="font-size: 11px; color: var(--color-silver-mist); background: #1a1a1a; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.06);">${escapeHtml(codeText)}</span>`
                : `<span style="font-size: 11px; color: var(--color-coral); background: rgba(255,100,101,0.08); padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(255,100,101,0.25);">${escapeHtml(codeText)}</span>`;

              const reasonsArr =
                Array.isArray(r.reasons) && r.reasons.length > 0
                  ? r.reasons
                  : isAccepted
                    ? [
                        "سجل البيانات مكتمل ومستوفٍ للحقول الإلزامية والضوابط المعتمدة.",
                      ]
                    : ["يوجد خطأ في مطابقة البيانات يمنع الاعتماد المباشر."];

              const reasonsList = `
            <ul class="audit-evidence-list">
              ${reasonsArr
                .map(
                  (reason) => `
                <li class="audit-evidence-item ${isAccepted ? "is-accepted" : "is-rejected"}">
                  <span style="color: ${isAccepted ? "var(--color-phosphor-green)" : "var(--color-coral)"}; font-weight: bold; line-height: 1;">${isAccepted ? "✓" : "✕"}</span>
                  <span>${escapeHtml(reason)}</span>
                </li>
              `,
                )
                .join("")}
            </ul>
          `;

              const searchCorpus =
                `${rowNum} ${name} ${metaStr} ${r.failure_code || ""} ${reasonsArr.join(" ")}`.toLowerCase();

              return `
            <tr class="audit-table-row" data-status="${isAccepted ? "accepted" : "rejected"}" data-search="${escapeHtml(searchCorpus)}">
              <td style="width: 70px; text-align: center;">
                <span class="audit-row-num">#${escapeHtml(String(rowNum))}</span>
              </td>
              <td style="min-width: 170px;">
                <div style="font-weight: 600; color: var(--color-snow); font-size: 13px;">${escapeHtml(name)}</div>
                ${metaStr ? `<div style="font-size: 11px; color: var(--color-silver-mist); margin-top: 2px;">${escapeHtml(metaStr)}</div>` : ""}
              </td>
              <td style="width: 130px; white-space: nowrap;">
                ${statusBadge}
              </td>
              <td style="width: 175px; white-space: nowrap;">
                ${codeBadge}
              </td>
              <td style="min-width: 260px;">
                ${reasonsList}
              </td>
            </tr>
          `;
            })
            .join("");
        }

        const tableHtml = `
        <div class="audit-table-wrap">
          <table class="audit-table">
            <thead>
              <tr>
                <th style="width: 70px; text-align: center;"># الصف</th>
                <th style="min-width: 170px;">الاسم / السجل</th>
                <th style="width: 130px;">حالة الفحص</th>
                <th style="width: 175px;">رمز التدقيق</th>
                <th style="min-width: 260px;">أدلة التدقيق وتوثيق الحدث</th>
              </tr>
            </thead>
            <tbody id="auditTableBody">
              ${rowsHtml}
            </tbody>
          </table>
        </div>
      `;

        // 4. Raw JSON Wrap
        const rawJsonHtml = `
        <div id="auditRawJsonWrap" class="audit-raw-json-wrap">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid var(--color-charcoal); padding-bottom: 6px;">
            <span style="font-size: 11px; color: var(--color-silver-mist);">البيانات التقنية الكاملة (JSON Payload)</span>
            <button type="button" id="auditCopyJsonBtn" class="btn btn-sm btn-ghost" style="font-size: 11px;">نسخ الكل</button>
          </div>
          <code>${escapeHtml(JSON.stringify(data, null, 2))}</code>
        </div>
      `;

        container.innerHTML = kpisHtml + toolbarHtml + tableHtml + rawJsonHtml;
        body.replaceChildren(container);

        // Event Wiring
        let activeFilter = "all";
        let searchQuery = "";

        function applyFilters() {
          const trs = container.querySelectorAll(".audit-table-row");
          trs.forEach((tr) => {
            const rowStatus = tr.getAttribute("data-status");
            const rowSearch = tr.getAttribute("data-search") || "";
            const matchFilter =
              activeFilter === "all" || rowStatus === activeFilter;
            const matchSearch = !searchQuery || rowSearch.includes(searchQuery);
            tr.style.display = matchFilter && matchSearch ? "" : "none";
          });
        }

        const filterBtns = container.querySelectorAll(
          "#auditFilterContainer .audit-filter-btn",
        );
        filterBtns.forEach((btn) => {
          btn.addEventListener("click", () => {
            filterBtns.forEach((b) => b.classList.remove("is-active"));
            btn.classList.add("is-active");
            activeFilter = btn.getAttribute("data-filter") || "all";
            applyFilters();
          });
        });

        const searchInput = container.querySelector("#auditSearchInput");
        if (searchInput) {
          searchInput.addEventListener("input", (e) => {
            searchQuery = e.target.value.trim().toLowerCase();
            applyFilters();
          });
        }

        const toggleJsonBtn = container.querySelector("#auditToggleJsonBtn");
        const rawJsonWrap = container.querySelector("#auditRawJsonWrap");
        if (toggleJsonBtn && rawJsonWrap) {
          toggleJsonBtn.addEventListener("click", () => {
            const isHidden =
              rawJsonWrap.style.display === "none" ||
              !rawJsonWrap.style.display;
            rawJsonWrap.style.display = isHidden ? "block" : "none";
            toggleJsonBtn.classList.toggle("is-active", isHidden);
            toggleJsonBtn.querySelector("span").textContent = isHidden
              ? "إخفاء كود JSON"
              : "عرض JSON الخام";
          });
        }

        const copyBtn = container.querySelector("#auditCopyJsonBtn");
        if (copyBtn) {
          copyBtn.addEventListener("click", () => {
            navigator.clipboard
              .writeText(JSON.stringify(data, null, 2))
              .then(() => {
                alert("تم نسخ بيانات JSON إلى الحافظة بنجاح!");
              });
          });
        }
      }

      function openDedicatedRejectionDrawer() {
        const targetIdentifier = dedicatedReportFolder || currentOperationId;
        if (targetIdentifier) {
          const overlay = document.getElementById("detailsDrawerOverlay");
          const sheet = overlay ? overlay.querySelector(".drawer-sheet") : null;
          const body = document.getElementById("drawerBody");
          if (sheet) sheet.classList.add("is-wide");
          document.getElementById("drawerTitle").textContent =
            "نتيجة فحص Excel — تقرير التدقيق";
          const subTitle = document.getElementById("drawerSubtitle");
          if (subTitle) subTitle.textContent = "توثيق الحدث وأدلة التدقيق";
          body.innerHTML = `
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px 20px; gap: 12px; color: var(--color-silver-mist);">
            <div class="spinner" style="width: 24px; height: 24px; border: 2px solid var(--color-charcoal); border-top-color: var(--color-phosphor-green); border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
            <span>جاري تحميل تقرير الفحص وأدلة التدقيق…</span>
          </div>
        `;
          overlay.classList.add("is-open");
          apiFetch(
            `/api/reports/dry-run/${encodeURIComponent(targetIdentifier)}`,
          )
            .then(async (res) => {
              const data = await res.json();
              if (!res.ok)
                throw new Error(data.detail || "تعذر العثور على التقرير");
              renderDryRunReportDrawer(data, targetIdentifier);
            })
            .catch((err) => {
              body.innerHTML = `
            <div style="padding: 24px; border: 1px solid var(--color-charcoal); border-radius: 12px; background: #141414; color: var(--color-coral); text-align: center;">
              <div style="font-weight: 600; margin-bottom: 6px;">تعذر تحميل تقرير الفحص</div>
              <div style="font-size: 12px; color: var(--color-silver-mist);">${escapeHtml(err.message)}</div>
            </div>
          `;
            });
        } else {
          alert("لم يتم تحديد عملية فحص نشطة بعد.");
        }
      }

      async function handleDedicatedApprove() {
        if (!currentOperationId) {
          const statusEl = document.getElementById("dedicatedUploadStatus");
          if (statusEl)
            statusEl.innerHTML =
              '<span style="color:var(--color-coral);">يرجى فحص ملف أولاً قبل طلب الاعتماد.</span>';
          return;
        }

        const approveBtn = document.getElementById("dedicatedApproveBtn");
        const cancelBtn = document.getElementById("dedicatedCancelBtn");
        const statusEl = document.getElementById("dedicatedUploadStatus");
        const resultWrap = document.getElementById("dedicatedExecutionResult");

        if (approveBtn) {
          approveBtn.disabled = true;
          approveBtn.innerHTML =
            '<span style="display:inline-block;width:14px;height:14px;border:2px solid var(--color-obsidian);border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;margin-left:6px;vertical-align:middle;"></span> جاري الاعتماد والتنفيذ…';
        }
        if (cancelBtn) cancelBtn.disabled = true;
        if (statusEl) {
          statusEl.innerHTML =
            '<span style="color:var(--color-phosphor-green);"><span style="display:inline-block;width:12px;height:12px;border:2px solid var(--color-silver-mist);border-top-color:var(--color-phosphor-green);border-radius:50%;animation:spin 0.8s linear infinite;margin-left:6px;vertical-align:middle;"></span> جاري اعتماد وتنفيذ السجلات المقبولة في Odoo عبر الوكيل «كاتب»…</span>';
        }
        if (resultWrap) resultWrap.style.display = "none";

        try {
          const res = await apiFetch("/api/agents/approve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: currentChatId,
              operation_id: currentOperationId,
              report_folder: dedicatedReportFolder || currentOperationId,
              approved_by: "مشغّل النظام",
            }),
          });
          const data = await res.json();

          if (data.status === "success") {
            if (statusEl) {
              statusEl.innerHTML = `<span style="color: var(--color-phosphor-green); font-weight: 600;">✓ ${escapeHtml(data.response || "تم الاعتماد والتنفيذ بنجاح في Odoo.")}</span>`;
            }
            if (approveBtn) {
              approveBtn.innerHTML = "تم الاعتماد والتنفيذ بنجاح ✓";
              approveBtn.style.background = "var(--color-forest-depth)";
              approveBtn.style.color = "var(--color-phosphor-green)";
              approveBtn.disabled = true;
            }
            if (cancelBtn) cancelBtn.style.display = "none";

            if (resultWrap) {
              const odooBaseUrl = (
                document.getElementById("settingsUrl")?.value ||
                "https://edu-training1555.odoo.com"
              ).replace(/\/+$/, "");
              const respText = data.response || "";
              const isRecruitment =
                respText.includes("التوظيف") ||
                respText.includes("Recruitment");
              const odooDirectLink = isRecruitment
                ? `${odooBaseUrl}/odoo/recruitment`
                : `${odooBaseUrl}/odoo/employees`;
              const odooDirectLabel = isRecruitment
                ? "فتح شاشة التوظيف في Odoo ↗"
                : "فتح شاشة الموظفين في Odoo ↗";

              resultWrap.style.display = "block";
              resultWrap.innerHTML = `
              <div style="padding: 16px; border-radius: 12px; background: rgba(62, 207, 142, 0.08); border: 1px solid rgba(62, 207, 142, 0.3); margin-top: 14px; display: flex; flex-direction: column; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px; color: var(--color-phosphor-green); font-weight: 700; font-size: 14px;">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                  <span>اكتمل الاعتماد والتنفيذ الفعلي في Odoo بنجاح</span>
                </div>
                <div style="font-size: 13px; color: var(--color-snow); line-height: 1.6; white-space: pre-line;">
                  ${escapeHtml(respText || "تم إدخال كافة السجلات المقبولة في قاعدة بيانات Odoo وتوثيق الحدث رسمياً.")}
                </div>
                <div style="display: flex; gap: 10px; margin-top: 6px; flex-wrap: wrap; align-items: center;">
                  <a href="${odooDirectLink}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary" style="text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    <span>${odooDirectLabel}</span>
                  </a>
                  <button type="button" class="btn btn-sm btn-secondary" onclick="openDedicatedRejectionDrawer()">عرض سجل التدقيق التفصيلي</button>
                  <button type="button" class="btn btn-sm btn-ghost" onclick="resumeOperationInCockpit('${currentOperationId}')">متابعة العملية في قمرة العمليات</button>
                </div>
              </div>
            `;
            }

            if (data.operation) {
              updateProcessStepper(data.operation.events || []);
              updateOperationBadges(data.operation);
            }
          } else {
            throw new Error(
              data.response || data.detail || "تعذر استكمال الاعتماد في Odoo.",
            );
          }
        } catch (err) {
          const isExpired =
            err.message &&
            (err.message.includes("5 دقائق") ||
              err.message.includes("صلاحية") ||
              err.message.includes("expired"));
          if (statusEl) {
            if (isExpired) {
              statusEl.innerHTML = `<span style="color: #38bdf8; font-weight: 600;">⏱ تنبيه أمني: انتهت مهلة الـ 5 دقائق للاعتماد. انقر على الزر مجدداً للتنفيذ المباشر.</span>`;
            } else {
              statusEl.innerHTML = `<span style="color: var(--color-coral); font-weight: 600;">✕ تعذر إتمام الاعتماد: ${escapeHtml(err.message)}</span>`;
            }
          }
          if (approveBtn) {
            approveBtn.disabled = false;
            approveBtn.innerHTML = isExpired
              ? "إعادة الاعتماد والتنفيذ الفوري"
              : "اعتماد وتنفيذ في Odoo";
          }
          if (cancelBtn) cancelBtn.disabled = false;

          if (resultWrap) {
            resultWrap.style.display = "block";
            if (isExpired) {
              resultWrap.innerHTML = `
              <div style="padding: 14px; border-radius: 10px; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); color: #38bdf8; margin-top: 14px; font-size: 13px; line-height: 1.6;">
                <div style="font-weight: 700; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                  <span>مهلة التفويض الأمني انتهت (5 دقائق)</span>
                </div>
                <span>${escapeHtml(err.message)} — تم تمكين زر الاعتماد أعلاه لتجديد التفويض بنقرة واحدة ومتابعة الكتابة فوراً.</span>
              </div>
            `;
            } else {
              resultWrap.innerHTML = `
              <div style="padding: 14px; border-radius: 10px; background: rgba(255, 100, 101, 0.08); border: 1px solid rgba(255, 100, 101, 0.25); color: var(--color-coral); margin-top: 14px; font-size: 13px;">
                <strong>تعذر استكمال الاعتماد:</strong> ${escapeHtml(err.message)}
              </div>
            `;
            }
          }
        }
      }

      async function handleDedicatedCancel() {
        if (!currentOperationId) return;
        const statusEl = document.getElementById("dedicatedUploadStatus");
        const approveBtn = document.getElementById("dedicatedApproveBtn");
        const cancelBtn = document.getElementById("dedicatedCancelBtn");
        const resultWrap = document.getElementById("dedicatedExecutionResult");

        if (statusEl) statusEl.textContent = "جاري إلغاء العملية…";
        if (cancelBtn) cancelBtn.disabled = true;

        try {
          const res = await apiFetch("/api/agents/cancel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: currentChatId,
              operation_id: currentOperationId,
            }),
          });
          const data = await res.json();
          if (statusEl) {
            statusEl.innerHTML =
              '<span style="color: var(--color-smoke);">تم إلغاء عملية الاستيراد بناءً على طلبك دون إجراء أي تعديل في Odoo.</span>';
          }
          if (approveBtn) approveBtn.disabled = true;
          if (cancelBtn) cancelBtn.style.display = "none";
          if (resultWrap) {
            resultWrap.style.display = "block";
            resultWrap.innerHTML = `
            <div style="padding: 12px 14px; border-radius: 8px; background: #181818; border: 1px solid var(--color-charcoal); color: var(--color-silver-mist); font-size: 12px; margin-top: 10px;">
              تم إلغاء العملية ولم يتم حفظ أو تعديل أي سجل في Odoo.
            </div>
          `;
          }
          if (data.operation) {
            updateProcessStepper(data.operation.events || []);
            updateOperationBadges(data.operation);
          }
          resetAllAgentsToIdle();
        } catch (err) {
          if (statusEl)
            statusEl.textContent = "تعذر إلغاء العملية: " + err.message;
          if (cancelBtn) cancelBtn.disabled = false;
        }
      }

      async function populateDedicatedCompanySelector() {
        try {
          const res = await apiFetch("/api/status");
          const data = await res.json();
          const sel = document.getElementById("dedicatedCompanySelect");
          if (!sel) return;

          if (data.companies && data.companies.length > 0) {
            sel.innerHTML =
              '<option value="">اختر المنشأة...</option>' +
              data.companies
                .map(
                  (c) =>
                    `<option value="${c.id}" ${c.id === selectedCompanyId ? "selected" : ""}>${escapeHtml(c.name)}</option>`,
                )
                .join("");
          }
        } catch (e) {
          console.warn("Failed to populate dedicated company selector:", e);
        }
      }
