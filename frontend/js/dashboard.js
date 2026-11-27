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

let pendingOperatorToken;

function requestOperatorToken() {
  if (pendingOperatorToken) return pendingOperatorToken;
  const dialog = document.getElementById("operatorTokenDialog");
  const input = document.getElementById("operatorTokenDialogInput");
  dialog.returnValue = "";
  dialog.showModal();
  pendingOperatorToken = new Promise((resolve) => {
    dialog.addEventListener("close", () => {
      const token = dialog.returnValue === "submit" ? input.value.trim() : "";
      input.value = "";
      pendingOperatorToken = null;
      resolve(token);
    }, { once: true });
  });
  return pendingOperatorToken;
}

async function promptForApiToken() {
  const token = await requestOperatorToken();
  if (!token) return;
  setApiToken(token);
  syncSettingsTokenInput();
  if (document.getElementById("view-sijil")?.classList.contains("is-visible")) {
    loadRecentAuditMetrics();
  }
}

async function apiFetch(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  const storedToken = getApiToken();
  if (storedToken && !headers.has("X-API-Key")) headers.set("X-API-Key", storedToken);
  const send = () => fetch(url, {
    ...options,
    headers,
    signal: options.signal || AbortSignal.timeout(method === "POST" ? 120000 : 30000),
  });
  const response = await send();
  if (response.status !== 401 || method === "GET" || options.silentAuth) {
    return response;
  }
  const token = await requestOperatorToken();
  if (!token || options.signal?.aborted) return response;
  headers.set("X-API-Key", token);
  const retry = await send();
  if (retry.status !== 401 && retry.status !== 403) {
    setApiToken(token);
    syncSettingsTokenInput();
  }
  return retry;
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
  renderAgentsStrip();
  loadSystemStatus();
  syncSettingsTokenInput();
  loadLlmSettings();
  populateTemplateCompanySelector();
  loadAgentsOverview();
  loadChatSessions();
  loadRecentAuditMetrics();
  loadOperationsList();
  checkSavedMotionPreference();
  initTimelineResize();
  initChatDragResize();
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
      services: "view-services",
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
    if (typeof loadMemoryData === "function") loadMemoryData();
    if (typeof loadCostTelemetry === "function") loadCostTelemetry();
  }

  if (viewId === "view-operations" || viewId === "view-sijil") setTimeout(window.initMoxenPilar, 150);

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
        window.cachedCompanies = data.companies;
        renderCompaniesOverview(data.companies);
      } else if (compSelect) {
        compSelect.innerHTML =
          '<option value="">لا توجد شركات متاحة</option>';
        compSelect.disabled = true;
        renderCompaniesOverview([]);
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
          odooText.textContent = "Odoo متصل";
          odooBadge.title = `قاعدة Odoo: ${data.odoo.database || "غير محددة"}`;
        }
      }

      const connectionState = document.getElementById("settingsOdooStatus");
      const connectionDetail = document.getElementById("settingsOdooDetail");
      if (connectionState && connectionDetail) {
        connectionState.textContent = isConnected ? "Odoo متصل" : "Odoo غير متصل";
        connectionState.dataset.state = isConnected ? "connected" : "disconnected";
        connectionDetail.textContent = isConnected
          ? `قاعدة البيانات: ${data.odoo.database || "غير محددة"} · الشركات المتاحة: ${data.companies?.length ?? 0}`
          : "راجع بيانات الاتصال ثم اختر «فحص الاتصال وحفظه».";
      }
    }
  } catch (err) {
    const state = document.getElementById("settingsOdooStatus");
    const detail = document.getElementById("settingsOdooDetail");
    if (state && detail) {
      state.textContent = "تعذر فحص اتصال Odoo";
      state.dataset.state = "disconnected";
      detail.textContent = "يمكنك إعادة الفحص من بيانات الاتصال.";
    }
    console.warn("System status error:", err);
  }
}

function renderCompaniesOverview(companies) {
  const container = document.getElementById("companiesOverviewList");
  const badge = document.getElementById("companiesOverviewBadge");
  if (!container) return;

  if (!companies || companies.length === 0) {
    if (badge) {
      badge.textContent = "لا توجد منشآت";
      badge.className = "badge badge-neutral";
    }
    container.innerHTML = `
          <div style="text-align: center; padding: 24px; color: var(--color-silver-mist); font-size: 13px;">
            لا توجد منشآت مسجلة في قاعدة بيانات Odoo الحالية.
          </div>`;
    return;
  }

  if (badge) {
    badge.textContent = `${companies.length} منشآت مسجلة`;
    badge.className = "badge badge-success";
  }

  container.innerHTML = companies.map((c, idx) => {
    const isCurrent = c.id === selectedCompanyId;
    return `
          <div style="
            display: grid;
            grid-template-columns: 70px 2fr 1.5fr 110px;
            gap: 16px;
            align-items: center;
            padding: 12px 16px;
            background: ${isCurrent ? 'rgba(var(--ok-rgb), 0.05)' : 'rgba(var(--ink-rgb), 0.015)'};
            border: 1px solid ${isCurrent ? 'rgba(var(--ok-rgb), 0.3)' : 'rgba(var(--ink-rgb), 0.05)'};
            border-radius: 8px;
            transition: background-color 150ms ease-out;
          ">
            <div style="text-align: center">
              <span class="mono" style="
                background: ${isCurrent ? 'rgba(var(--ok-rgb), 0.15)' : 'rgba(var(--ink-rgb), 0.05)'};
                color: ${isCurrent ? 'var(--color-phosphor-green)' : 'var(--color-silver-mist)'};
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 700;
              ">#${c.id || (idx + 1)}</span>
            </div>
            <div>
              <div style="font-weight: 700; color: ${isCurrent ? 'var(--ink)' : 'var(--color-snow)'}; font-size: 13.5px">
                ${escapeHtml(c.name || 'منشأة')}
              </div>
              <div style="font-size: 12px; color: ${isCurrent ? 'var(--color-phosphor-green)' : 'var(--color-smoke)'}; margin-top: 2px;">
                ${isCurrent ? 'المنشأة المحددة للعمليات الحالية • نشطة' : 'منشأة مصرح بها في النظام'}
              </div>
            </div>
            <div>
              <div style="width: 100%; height: 8px; background: rgba(var(--ink-rgb), 0.06); border-radius: 4px; overflow: hidden;">
                <div style="width: ${isCurrent ? '100%' : '35%'}; height: 100%; background: ${isCurrent ? 'var(--color-phosphor-green)' : 'var(--color-slate)'}; border-radius: 4px;"></div>
              </div>
            </div>
            <div style="text-align: center">
              <span class="badge ${isCurrent ? 'badge-success' : 'badge-neutral'}" style="font-size: 12px; padding: 4px 10px;">
                ${isCurrent ? 'نشطة' : 'جاهزة'}
              </span>
            </div>
          </div>
        `;
  }).join("");
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
  Object.assign(window.hrReferenceOptions, {departments: [], jobs: []});
  loadHrReferenceOptions();
  document.getElementById("settingsSelectedCompany").textContent =
    `الشركة المختارة: ${document.getElementById("companySelector").selectedOptions[0]?.textContent.trim()}`;
  if (window.cachedCompanies) {
    renderCompaniesOverview(window.cachedCompanies);
  }
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
    name: "Google Gemini",
    base_url: "https://generativelanguage.googleapis.com/v1beta/openai",
    model: "gemini-flash-lite-latest",
    models: [
      { id: "gemini-flash-lite-latest", label: "Gemini Flash-Lite", badge: "افتراضي" },
      { id: "gemini-flash-latest", label: "Gemini Flash", badge: "أحدث إصدار" },
      { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash", badge: "" },
    ],
    placeholder_key: "مفتاح Google AI Studio",
    key_url: "https://aistudio.google.com/app/apikey",
  },
  claude: {
    name: "Anthropic Claude",
    base_url: "https://openrouter.ai/api/v1",
    model: "anthropic/claude-3.7-sonnet",
    models: [
      { id: "anthropic/claude-3.7-sonnet", label: "Claude 3.7 Sonnet", badge: "هجين" },
      { id: "anthropic/claude-3.5-sonnet", label: "Claude 3.5 Sonnet", badge: "دقيق" },
      { id: "anthropic/claude-3.5-haiku", label: "Claude 3.5 Haiku", badge: "سريع" },
    ],
    placeholder_key: "sk-ant-... أو sk-or-...",
    key_url: "https://console.anthropic.com/settings/keys",
  },
  openrouter: {
    name: "OpenRouter",
    base_url: "https://openrouter.ai/api/v1",
    model: "anthropic/claude-3.7-sonnet",
    models: [
      { id: "anthropic/claude-3.7-sonnet", label: "Claude 3.7 Sonnet", badge: "هجين" },
      { id: "google/gemini-2.5-pro", label: "Gemini 2.5 Pro", badge: "استدلال" },
      { id: "openai/gpt-4o", label: "GPT-4o", badge: "شامل" },
      { id: "deepseek/deepseek-r1", label: "DeepSeek R1", badge: "تفكير" },
      { id: "meta-llama/llama-3.3-70b-instruct", label: "Llama 3.3 70B", badge: "مفتوح" },
    ],
    placeholder_key: "sk-or-v1-...",
    key_url: "https://openrouter.ai/keys",
  },
  openai: {
    name: "OpenAI",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o",
    models: [
      { id: "gpt-4o", label: "GPT-4o", badge: "شامل" },
      { id: "o3-mini", label: "o3-mini", badge: "استدلال" },
      { id: "o1", label: "o1", badge: "تفكير" },
      { id: "gpt-4.5-preview", label: "GPT-4.5 Preview", badge: "تجريبي" },
      { id: "gpt-4o-mini", label: "GPT-4o-mini", badge: "سريع" },
    ],
    placeholder_key: "sk-proj-...",
    key_url: "https://platform.openai.com/api-keys",
  },
  deepseek: {
    name: "DeepSeek",
    base_url: "https://api.deepseek.com/v1",
    model: "deepseek-reasoner",
    models: [
      { id: "deepseek-reasoner", label: "DeepSeek R1", badge: "تفكير" },
      { id: "deepseek-chat", label: "DeepSeek V3", badge: "سريع" },
    ],
    placeholder_key: "sk-...",
    key_url: "https://platform.deepseek.com/api_keys",
  },
  groq: {
    name: "Groq",
    base_url: "https://api.groq.com/openai/v1",
    model: "llama-3.3-70b-versatile",
    models: [
      { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B Versatile", badge: "متنوع" },
      { id: "deepseek-r1-distill-llama-70b", label: "DeepSeek R1 Distill 70B", badge: "تفكير" },
      { id: "qwen-2.5-32b", label: "Qwen 2.5 32B", badge: "متعدد اللغات" },
    ],
    placeholder_key: "gsk_...",
    key_url: "https://console.groq.com/keys",
  },
  mistral: {
    name: "Mistral AI",
    base_url: "https://api.mistral.ai/v1",
    model: "mistral-large-latest",
    models: [
      { id: "mistral-large-latest", label: "Mistral Large", badge: "شامل" },
      { id: "codestral-latest", label: "Codestral", badge: "كود" },
    ],
    placeholder_key: "...",
    key_url: "https://console.mistral.ai/api-keys",
  },
  together: {
    name: "Together AI",
    base_url: "https://api.together.xyz/v1",
    model: "deepseek-ai/DeepSeek-R1",
    models: [
      { id: "deepseek-ai/DeepSeek-R1", label: "DeepSeek R1", badge: "تفكير" },
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
      { id: "sonar-pro", label: "Sonar Pro", badge: "بحث" },
      { id: "sonar-reasoning", label: "Sonar Reasoning", badge: "تفكير" },
    ],
    placeholder_key: "pplx-...",
    key_url: "https://www.perplexity.ai/settings/api",
  },
  custom: {
    name: "مشغل مخصص (Custom Provider)",
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
                class="settings-quick-pill"
                onclick="selectQuickModel('${escapeHtml(m.id)}')"
                title="اعتماد هذا النموذج"
              >
                <span class="mono">${escapeHtml(m.id)}</span>
                <span class="pill-tag">${escapeHtml(m.badge || "مقترح")}</span>
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
    // عند اختيار أي مزود محدد، نعتمد نموذج المزود الموصى به مباشرة
    if (modelInput) {
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

function setActiveProvider(provider) {
  const cloud = provider === "cloud";
  document.getElementById("llmActiveProvider").value = cloud ? "cloud" : "local";
  document.getElementById("btnSelectCloud").setAttribute("aria-pressed", String(cloud));
  document.getElementById("btnSelectLocal").setAttribute("aria-pressed", String(!cloud));
  document.getElementById("cloudSettingsSection").style.display = cloud ? "block" : "none";
  document.getElementById("localSettingsSection").style.display = cloud ? "none" : "block";
  document.getElementById("llmTestResultBox").style.display = "none";
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

    document.getElementById("llmAllowFallback").checked =
      cfg.mode === "auto" && cfg.fallback_enabled !== false;

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
    let resolvedCloudModel = cloud.model || "openrouter/auto";
    if (
      (cloud.provider === "gemini" || String(cloud.base_url || "").includes("googleapis.com")) &&
      (resolvedCloudModel.includes("openrouter") || !resolvedCloudModel)
    ) {
      resolvedCloudModel = CLOUD_PRESETS.gemini.model;
    }
    if (cloudModel) cloudModel.value = resolvedCloudModel;

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
    const activeLocalModel = local.model || "qwen3.5:9b";
    if (localModel) localModel.value = activeLocalModel;

    // Datalist of installed models
    let dl = document.getElementById("localModelSuggestions");
    if (!dl && localModel) {
      dl = document.createElement("datalist");
      dl.id = "localModelSuggestions";
      document.body.appendChild(dl);
      localModel.setAttribute("list", "localModelSuggestions");
    }
    if (dl && Array.isArray(health.local?.models)) {
      dl.innerHTML = health.local.models.map(m => `<option value="${escapeHtml(m)}"></option>`).join("");
    }

    // 5. Status Badges
    const effBadge = document.getElementById("llmEffectiveBadge");
    if (effBadge) {
      effBadge.textContent = health.effective_engine
        ? `المحرك المحدد: ${health.effective_engine}`
        : `المحرك المحدد: Ollama المحلي (${activeLocalModel})`;
      effBadge.className =
        health.effective_engine &&
          (cfg.active_provider === "cloud" ? !cloud.has_api_key : !health.local?.available)
          ? "badge badge-warning"
          : "badge badge-success";
    }

    const localBadge = document.getElementById("localStatusBadge");
    if (localBadge) {
      if (health.local && health.local.available) {
        localBadge.innerHTML = `<span style="color: var(--color-phosphor-green);">متصل (${health.local.latency_ms || 0}ms) • ${escapeHtml(activeLocalModel)}</span>`;
      } else {
        localBadge.textContent = health.local?.status === "model_missing" ? "النموذج غير مثبّت" : "غير متصل";
      }
    }

    const cloudBadge = document.getElementById("cloudStatusBadge");
    if (cloudBadge) {
      if (health.cloud && health.cloud.available) {
        cloudBadge.innerHTML = `<span style="color: var(--color-phosphor-green);">متصل (${health.cloud.latency_ms || 0}ms)</span>`;
      } else if (cloud.has_api_key || cloud.has_key) {
        cloudBadge.innerHTML = `<span style="color: var(--color-amber);">المفتاح محفوظ</span>`;
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

      if (active === "cloud" && hasKey) {
        topDot.style.background = "var(--ink)";
        topDot.style.boxShadow = "none";
        topText.textContent =
          `AI: سحابي (${provName})`;
        topBadge.title = `الذكاء السحابي نشط (${provModel}) - وضع: ${mode} - انقر لتغيير الإعدادات`;
      } else if (active === "cloud" && !hasKey) {
        topDot.style.background = "var(--color-coral)";
        topDot.style.boxShadow = "none";
        topText.textContent = `AI: سحابي (مفقود API Key)`;
        topBadge.title = `المشغل السحابي يحتاج مفتاح API Key - انقر لتهيئته`;
      } else {
        const curLocModel = locModel;
        topDot.style.background = "var(--color-phosphor-green)";
        topDot.style.boxShadow = "none";
        topText.textContent = `AI: محلي (${curLocModel})`;
        topBadge.title = `المحرك المحلي نشط (${curLocModel}) - وضع: ${mode} - انقر لتغيير الإعدادات`;
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
      data.available === true;

    if (resultBox) {
      if (isSuccess) {
        resultBox.style.background = "rgba(var(--ok-rgb),0.12)";
        resultBox.style.border = "1px solid var(--color-phosphor-green)";
        resultBox.style.color = "var(--color-snow)";
        resultBox.innerHTML = `<strong>${target === "cloud" ? "استجاب النموذج بنجاح" : "خادم Ollama متصل"}</strong><br>
              المشغل: <span class="mono">${escapeHtml(data.provider || target)}</span> · 
              زمن الاستجابة: <span class="mono">${data.latency_ms || 0}ms</span> · 
              النموذج: <span class="mono">${escapeHtml(data.model || payload.model || (data.models && data.models[0]) || "افتراضي")}</span><br>
              <span>${target === "cloud" ? "احفظ الإعدادات لاستخدام هذا النموذج في المحادثة." : escapeHtml(data.message || "")}</span>`;
      } else {
        resultBox.style.background = "rgba(var(--bad-rgb),0.15)";
        resultBox.style.border = "1px solid var(--color-coral)";
        resultBox.style.color = "var(--bad)";

        const adviceText =
          target === "local"
            ? "تأكد من تشغيل تطبيق Ollama محلياً أو اضغط على زر «تشغيل خادم Ollama» أعلاه."
            : "";

        resultBox.innerHTML = `<strong>فشل الاتصال:</strong> ${escapeHtml(data.message || "تعذر الوصول إلى الخادم.")}<br>
              <span style="font-size: 12.5px; color: var(--color-silver-mist);">${adviceText}</span>`;
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
    const mode = document.getElementById("llmAllowFallback").checked ? "auto" : "manual";
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

const AGENT_STATIONS_MAP = {
  seraj: {
    station_num: "المحطة 01",
    station_role: "المنسق والمحاور العام",
    chips: [
      { label: "💬 استشارة عامة", prompt: "أريد استشارة حول لوائح الموارد البشرية وإجراءات المنشأة" },
      { label: "📊 ملخص العمليات", prompt: "لخص لي حالة العمليات والأنشطة المنفذة اليوم" },
      { label: "📋 مهمة جديدة", prompt: "أريد تنفيذ مهمة جديدة في إدارة الموارد البشرية" }
    ]
  },
  fahas: {
    station_num: "المحطة 02",
    station_role: "استعلام Odoo وفحص السجلات",
    chips: [
      { label: "👥 استعلام موظفين", prompt: "كم عدد الموظفين النشطين في المنشأة الحالية في Odoo؟" },
      { label: "🏢 هيكل الأقسام", prompt: "استعرض قائمة الأقسام المعتمدة في Odoo للمنشأة الحالية" },
      { label: "⏱️ سجلات الحضور", prompt: "افحص سجلات الحضور والانصراف لشهر الحالي في Odoo" }
    ]
  },
  modaqeq: {
    station_num: "المحطة 03",
    station_role: "نظام العمل والامتثال القانوني",
    chips: [
      { label: "⚖️ تجربة م/53", prompt: "هل فترة التجربة المحددة بـ 90 يوماً متوافقة مع المادة 53 من نظام العمل؟" },
      { label: "🛡️ استقطاع GOSI", prompt: "احسب استقطاع التأمينات وساند لراتب أساسي 8000 وبدل سكن 2000" },
      { label: "⏱️ ساعات العمل م/98", prompt: "ما هو الحد الأقصى لساعات العمل اليومية والأسبوعية وفق المادة 98؟" }
    ]
  },
  mowafaq: {
    station_num: "المحطة 04",
    station_role: "المطابقة الذكية وتسكين الموظفين",
    chips: [
      { label: "🧩 مطابقة مسمى", prompt: "طابق المسمى الوظيفي 'أخصائي توظيف' مع الوظائف المعتمدة في Odoo" },
      { label: "🔄 تسكين قسم", prompt: "طابق قسم 'التسويق الرقمي' مع الأقسام المعرفة في المنشأة" },
      { label: "📑 مطابقة مرشح", prompt: "طابق بيانات المرشح مع سجل الموظفين الحاليين لمنع التكرار" }
    ]
  },
  musleh: {
    station_num: "المحطة 05",
    station_role: "التشخيص الذاتي والتسويات",
    chips: [
      { label: "🔧 تشخيص تناقض", prompt: "شخص سبب عدم تطابق بيانات الرواتب في ملف الإكسل مع Odoo" },
      { label: "💡 مقترح تسوية", prompt: "اقترح خطة تسوية لفروقات بدلات السكن للموظفين المنقولين" },
      { label: "🩺 فحص التكرارات", prompt: "افحص هل توجد سجلات مكررة أو حقول ناقصة في ملف استيراد الموظفين" }
    ]
  },
  hares: {
    station_num: "المحطة 06",
    station_role: "حوكمة الأمان وعزل الصلاحيات HITL",
    chips: [
      { label: "🔒 فحص الصلاحيات", prompt: "تحقق من صلاحيات المشغل وسياسات حماية البيانات PII قبل الاعتماد" },
      { label: "🛡️ شروط HITL", prompt: "ما هي شروط بوابة الاعتماد البشري HITL المطلوبة للعملية الحالية؟" },
      { label: "🚫 سياسة الحذف", prompt: "ما هي الضوابط والقيود الصارمة المطبقة على حذف أو أرشفة الموظفين؟" }
    ]
  },
  katib: {
    station_num: "المحطة 07",
    station_role: "المنفذ الحصري للكتابة في Odoo",
    chips: [
      { label: "✍️ إضافة موظف", prompt: "أضف موظف جديد باسم " },
      { label: "✏️ تعديل مسمى", prompt: "عدل المسمى الوظيفي لموظف برقم الهوية " },
      { label: "📄 صياغة خطاب", prompt: "صغ خطاب تعريف بالراتب رسمي لموظف موجه لجهة رسمية" }
    ]
  },
  sijil: {
    station_num: "المحطة 08",
    station_role: "التوثيق اللاتراجعي والختم الرقمي",
    chips: [
      { label: "📜 تقرير PDF", prompt: "استخرج تقرير الحوكمة والتدقيق الشامل للعمليات بصيغة PDF" },
      { label: "🔍 بصمة SHA-256", prompt: "تحقق من البصمة الرقمية للدفتر اللاتراجعي وتكامل السجلات" },
      { label: "📊 مؤشرات المطابقة", prompt: "استعرض مؤشرات التحقق الراجع ونسبة المطابقة المستقلة" }
    ]
  }
};

function sendAgentPrompt(agentId, promptText, e) {
  if (e) e.stopPropagation();
  switchView('view-cockpit');
  setTimeout(() => {
    const input = document.getElementById("chatInput");
    if (input) {
      input.value = promptText;
      autoResizeTextarea(input);
      input.focus();
    }
    const chatBox = document.getElementById("mainChatBox");
    if (chatBox) chatBox.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 50);
}
window.sendAgentPrompt = sendAgentPrompt;

function renderAgentsFullGrid(agents) {
  const grid = document.getElementById("agentsFullGrid");
  if (!grid || document.getElementById("agentFlightDialog").open) return;
  grid.replaceChildren();

  for (const agent of agents) {
    const meta = AGENTS_META[agent.id] || resolveAgentMeta(agent.id);
    const station = AGENT_STATIONS_MAP[agent.id];
    const chips = station?.chips || [];
    const status = agent.status_code;
    const badge = ["failed", "error"].includes(status) ? "badge-error"
      : ["ready", "idle", "online"].includes(status) ? "badge-neutral" : "badge-warning";
    const statusLabel = agent.status_label || STATUS_MAP_AR[status] || "غير معروف";
    const card = document.createElement("article");
    card.className = "agent-directory-card";
    card.style.setProperty("--directory-agent-color", meta.color || "var(--accent)");
    card.innerHTML = `
      <header class="agent-directory-identity">
        <div class="agent-directory-avatar" data-pieza="avatar" aria-hidden="true">
          ${meta.img ? `<img src="${meta.img}" alt="">` : getAgentSvg(meta.icon || "cpu")}
        </div>
        <div class="agent-directory-name">
          <h3 data-pieza="name">${escapeHtml(agent.name_ar || meta.name_ar)}</h3>
          <span class="agent-station-number" data-pieza="station">${escapeHtml(station?.station_num || "")}</span>
          <p>${escapeHtml(agent.title_ar || meta.role || "")}</p>
        </div>
        <span class="badge ${badge}">${escapeHtml(statusLabel)}</span>
      </header>
      <dl class="agent-directory-metrics">
        <div><dt>العمليات</dt><dd>${escapeHtml(String(agent.operation_count ?? 0))}</dd></div>
        <div><dt>الأحداث</dt><dd>${escapeHtml(String(agent.event_count ?? 0))}</dd></div>
        <div><dt>آخر نشاط</dt><dd dir="ltr">${escapeHtml(agent.last_active_at?.slice(11, 19) || "—")}</dd></div>
      </dl>
      ${chips.length ? `<details class="agent-directory-prompts">
        <summary>أمثلة الطلبات</summary>
        <div>${chips.map(chip => {
          const label = chip.label.replace(/^[^\p{L}\p{N}]+/u, "");
          return `<button type="button" class="btn btn-sm btn-secondary" data-agent-prompt>${escapeHtml(label)}</button>`;
        }).join("")}</div>
      </details>` : ""}
      <div class="agent-directory-actions">
        <button type="button" class="btn btn-sm btn-secondary" data-agent-inquiry>توجيه استفسار</button>
        <button type="button" class="btn btn-sm btn-secondary" data-agent-details aria-haspopup="dialog" aria-controls="agentFlightDialog" aria-expanded="false">التفاصيل</button>
      </div>`;
    card.querySelector("img")?.addEventListener("error", event => {
      event.currentTarget.parentElement.innerHTML = getAgentSvg(meta.icon || "cpu");
    });
    card.querySelectorAll("[data-agent-prompt]").forEach((button, index) => {
      button.addEventListener("click", event => sendAgentPrompt(agent.id, chips[index].prompt, event));
    });
    card.querySelector("[data-agent-inquiry]").addEventListener("click", event => directInquiryToAgent(agent.id, event));
    card.querySelector("[data-agent-details]").addEventListener("click", event => openAgentDetails(agent.id, event.currentTarget));
    grid.appendChild(card);
  }
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

let chatAbortController = null;

async function stopCurrentSerajOperation() {
  if (chatAbortController) {
    try { chatAbortController.abort(); } catch (e) { }
  }
  if (currentOperationId) {
    try {
      await fetch(`/api/seraj/cancel/${currentOperationId}`, { method: "POST" });
    } catch (e) { }
  }
  stopLiveEventPolling();
  hideTypingIndicator();
  setChatButtonStopping(false);
  setSerajIdle();
  chatRequestInFlight = false;
  appendSerajMessage("⏹ تم إيقاف استجابة سراج والوكلاء بناءً على طلبك.");
}

function setChatButtonStopping(isStopping) {
  const btn = document.getElementById("chatSendBtn");
  if (!btn) return;
  if (isStopping) {
    btn.setAttribute("data-modo", "parar");
    btn.classList.add("is-stopping");
    btn.setAttribute("aria-label", "إيقاف سراج والوكلاء");
    btn.innerHTML = `<span>إيقاف</span><svg viewBox="0 0 24 24" fill="currentColor" style="width:13px; height:13px;"><rect x="5" y="5" width="14" height="14" rx="2"></rect></svg>`;
  } else {
    btn.removeAttribute("data-modo");
    btn.classList.remove("is-stopping");
    btn.setAttribute("aria-label", "أرسل الرسالة");
    btn.innerHTML = `<span>إرسال</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>`;
  }
}

async function handleChatSubmit(e) {
  if (e) e.preventDefault();

  const sendBtn = document.getElementById("chatSendBtn");
  if (sendBtn && sendBtn.getAttribute("data-modo") === "parar") {
    await stopCurrentSerajOperation();
    return;
  }

  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text || chatRequestInFlight) return;

  // دائماً توليد turn_id / operation_id جديد ومستقل لكل رسالة لفصل خطواتها عن الرسائل السابقة
  currentOperationId = "op_" + Math.floor(Date.now() / 1000) + "_" + Math.random().toString(16).slice(2, 8);
  lastEventSequence = 0;

  const activeBadge = document.getElementById("activeOpIdBadge");
  if (activeBadge) activeBadge.textContent = currentOperationId;

  window.currentOperationObj = null;
  if (typeof updateProcessStepper === "function") updateProcessStepper([], null);
  if (typeof renderAgentTimeline === "function") renderAgentTimeline([], "in_progress");

  input.value = "";
  autoResizeTextarea(input);
  appendUserMessage(text);
  showTypingIndicator();
  setSerajBusy("سراج يعالج الطلب…");
  setChatButtonStopping(true);
  chatRequestInFlight = true;

  // بدء متابعة الخطوات الحية فوراً مع انطلاق الطلب في الخلفية
  startLiveEventPolling(currentOperationId);

  chatAbortController = new AbortController();

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
      signal: chatAbortController.signal,
    });

    const data = await res.json();
    if (data.status === "success") {
      currentOperationId = data.operation_id || currentOperationId;
      currentOperationStatus = data.operation?.status;
      if (activeBadge) activeBadge.textContent = currentOperationId;

      appendSerajMessage(
        data.response,
        data.pending_action,
        data.pending_clarification,
        data.operation,
        data.rejected_rows_details,
        data.llm_meta,
        data.reasoning_steps,
        { timestamp: data.timestamp, duration: data.thinking_duration_sec },
      );
      if (data.operation) {
        updateProcessStepper(data.operation.events || [], data.operation);
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
      ) {
        startLiveEventPolling(currentOperationId);
      }
    } else {
      appendSerajMessage(
        "عذراً، واجه سراج صعوبة في معالجة طلبك: " +
        (data.detail || "خطأ غير معروف"),
      );
    }
  } catch (err) {
    if (err.name === "AbortError") {
      // تم الإلغاء عبر stopCurrentSerajOperation
    } else {
      appendSerajMessage("تعذر الاتصال بخادم المنظومة: " + err.message);
    }
  } finally {
    chatRequestInFlight = false;
    setChatButtonStopping(false);
    chatAbortController = null;
    hideTypingIndicator();
    setSerajIdle();
    loadAgentsOverview();
    loadChatSessions();
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
      updateProcessStepper(data.operation.events || [], data.operation);
      updateOperationBadges(data.operation);
    }
  } catch (err) {
    appendSerajMessage("تعذر إتمام الاعتماد: " + err.message);
  } finally {
    hideTypingIndicator();
    setSerajIdle();
    loadAgentsOverview();
    loadChatSessions();
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
      updateProcessStepper(data.operation.events || [], data.operation);
      updateOperationBadges(data.operation);
    }
    resetAllAgentsToIdle();
  } catch (err) {
    appendSerajMessage("تعذر إلغاء العملية: " + err.message);
  } finally {
    hideTypingIndicator();
    setSerajIdle();
    loadAgentsOverview();
    loadChatSessions();
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
        updateProcessStepper(data.operation.events || [], data.operation);
        updateOperationBadges(data.operation);
      }
    } else {
      if (data.operation) {
        currentOperationId = data.operation_id;
        updateOperationBadges(data.operation);
        updateProcessStepper(data.operation.events || [], data.operation);
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
const chatMessageTexts = new WeakMap();

function attachChatMessageActions(message, originalText, previousRequest) {
  if (typeof originalText !== "string" || !originalText.trim()) return;
  chatMessageTexts.set(message, originalText);
  const content = message.querySelector(".chat-message-text, .seraj-content-body");
  const actions = document.createElement("div");
  actions.className = "chat-message-actions";

  function addAction(label, handler) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-sm btn-secondary";
    button.textContent = label;
    button.addEventListener("click", handler);
    actions.appendChild(button);
  }

  addAction("نسخ", async () => {
    try {
      await navigator.clipboard.writeText(content.innerText);
      showToast("تم نسخ الرسالة", "success");
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(content);
      selection.removeAllRanges();
      selection.addRange(range);
      showToast("تعذر النسخ تلقائيًا. انسخ النص المحدد.", "warning");
    }
  });

  addAction("رد", () => {
    const input = document.getElementById("chatInput");
    if (!input || input.disabled) return;
    const text = content.innerText.trim();
    const excerpt = text.length > 500 ? text.slice(0, 500) + "…" : text;
    const draft = input.value.trimEnd();
    input.value = `${draft}\n\nردًا على هذه الرسالة:\n${excerpt.split("\n").map(line => "> " + line).join("\n")}`;
    input.focus();
    input.setSelectionRange(draft.length, draft.length);
    autoResizeTextarea(input);
  });

  const request = message.matches(".msg-user") ? originalText : previousRequest;
  if (request) {
    addAction("إعادة الطلب", () => {
      const input = document.getElementById("chatInput");
      if (!input || input.disabled) return;
      if (input.value.trim() && input.value !== request) {
        showToast("أرسل المسودة الحالية أو امسحها قبل إعادة الطلب.", "warning");
        input.focus();
        return;
      }
      input.value = request;
      input.focus();
      autoResizeTextarea(input);
    });
  }

  content.closest(".msg-content-wrapper").appendChild(actions);
}

function appendUserMessage(text, timestamp) {
  const container = document.getElementById("chatMessages");
  const msg = document.createElement("div");
  msg.className = "msg-bubble msg-user";
  const messageTime = getTimeStr(timestamp);
  msg.innerHTML = `
        <div class="msg-avatar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
        </div>
        <div class="msg-content-wrapper">
          <div class="msg-meta"><span>أنت</span> ${messageTime ? `• <span class="mono">${messageTime}</span>` : ""}</div>
          <div class="msg-card chat-message-text" dir="auto">${escapeHtml(text)}</div>
        </div>
      `;
  attachChatMessageActions(msg, text);
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function showSerajEngine(meta, { missing = false } = {}) {
  const subtitle = document.getElementById("serajEngineSubtitle");
  if (!subtitle) return;
  if (!meta) {
    subtitle.textContent = missing ? "محرك الرد غير مسجّل" : "يظهر المحرك بعد وصول الرد";
    return;
  }
  const model = meta.model ? ` · ${meta.model}` : "";
  if (meta.provider === "local" || meta.provider === "ollama") {
    subtitle.textContent = `آخر رد: Ollama · محلي${model}`;
  } else if (meta.provider === "cloud") {
    subtitle.textContent = `آخر رد: ${meta.provider_name || "مزود سحابي"} · سحابي${model}`;
  } else if (meta.provider === "fallback") {
    subtitle.textContent = "آخر رد: قواعد سراج";
  } else {
    subtitle.textContent = "آخر رد: بدون نموذج مسجّل";
  }
}

function rememberedSerajEngine(scope, id) {
  if (!id) return null;
  try { return JSON.parse(sessionStorage.getItem(`seraj-engine:${scope}:${id}`)); }
  catch { return null; }
}

function appendSerajMessage(
  text,
  pendingAction,
  pendingClarification,
  opData,
  rejectionDetails,
  llmMeta,
  reasoningSteps,
  messageMeta = {},
) {
  hideTypingIndicator();
  setSerajIdle();

  const container = document.getElementById("chatMessages");
  const msg = document.createElement("div");
  msg.className = "msg-bubble msg-assistant";

  if (llmMeta) {
    showSerajEngine(llmMeta);
    const provider = {provider: llmMeta.provider, model: llmMeta.model, provider_name: llmMeta.provider_name};
    const operationId = opData?.operation_id || currentOperationId;
    try {
      if (operationId) sessionStorage.setItem(`seraj-engine:operation:${operationId}`, JSON.stringify(provider));
      if (currentChatId) sessionStorage.setItem(`seraj-engine:chat:${currentChatId}`, JSON.stringify(provider));
    } catch {}
  }

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

  if (llmMeta?.fallback_reason) {
    llmBadgeHtml += `<span class="badge badge-warning">${escapeHtml(llmMeta.fallback_reason)}</span>`;
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

  const elapsedSeconds = Number.isFinite(messageMeta.duration) ? messageMeta.duration.toFixed(1) : null;
  const steps = Array.isArray(reasoningSteps) ? reasoningSteps.filter(step => step.type === "tool") : [];
  const durationLabel = elapsedSeconds === null ? "" : ` · ${elapsedSeconds} ث`;
  let cavilaBadgeHtml = "";
  if (steps.length) {
    cavilaBadgeHtml = `
      <div class="cv-cajon">
        <button type="button" class="cv-etiqueta is-pensado" aria-expanded="false" onclick="toggleCavilaSteps(this)">
          <span class="cv-penso"><svg class="cv-flecha" viewBox="0 0 24 24" aria-hidden="true"><polyline points="9 18 15 12 9 6"></polyline></svg>
          خطوات التنفيذ${durationLabel}</span>
        </button>
        <div class="cv-pasos" style="height: 0;">
          <ol>${steps.map(step => {
            const agent = resolveAgentMeta(step.agent);
            const description = describeAgentActivity({event_type: "tool_execution", metadata: {tool: step.tool}, description_ar: step.summary});
            return `<li>
              <div class="cv-step-content">
                <b style="color: ${agent.color || "var(--ink)"};">${escapeHtml(agent.name_ar)}</b>
                <span>${escapeHtml(step.summary && !/[a-z]{2,}|[{}]/i.test(step.summary.replace(/Odoo/g, "أودو")) ? step.summary : description)}</span>
              </div>
              ${Number.isFinite(step.duration_ms) ? `<small>${step.duration_ms} مللي ثانية</small>` : ""}
            </li>`;
          }).join("")}</ol>
        </div>
      </div>`;
  } else if (elapsedSeconds !== null) {
    cavilaBadgeHtml = `<div class="cv-cajon"><span class="cv-etiqueta">مدة الرد${durationLabel}</span></div>`;
  }
  const messageTime = getTimeStr(messageMeta.timestamp);

  msg.innerHTML = `
        <div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">
          <img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/images/svg/seraj.svg';">
        </div>
        <div class="msg-content-wrapper">
          <div class="msg-meta" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
            <span style="color: var(--agent-seraj); font-weight: 600;">سراج</span>
            ${messageTime ? `<span>•</span><span class="mono">${messageTime}</span>` : ""}
            ${llmBadgeHtml}
          </div>
          <div class="msg-card">
            ${cavilaBadgeHtml}
            <div class="seraj-content-body">${formatMarkdownText(text)}</div>
            ${actionCardHtml}
          </div>
        </div>
      `;
  const previousMessage = container.lastElementChild;
  const previousRequest = previousMessage?.matches(".msg-user")
    ? chatMessageTexts.get(previousMessage)
    : null;
  attachChatMessageActions(msg, text, previousRequest);
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
        data.reasoning_steps,
        { timestamp: data.timestamp, duration: data.thinking_duration_sec },
      );
      if (data.operation) {
        updateProcessStepper(data.operation.events || [], data.operation);
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
  showSerajEngine();
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
  loadChatSessions();
  const input = document.getElementById("chatInput");
  if (input) {
    input.value = "";
    autoResizeTextarea(input);
    input.focus();
  }
}

let activeChatSessions = [];

function toggleSessionPopover(e) {
  if (e) e.stopPropagation();
  const popover = document.getElementById("sessionPopoverMenu");
  const btn = document.getElementById("sessionMenuBtn");
  if (!popover) return;
  const isOpen = popover.style.display !== "none";
  if (isOpen) {
    closeSessionPopover();
  } else {
    popover.style.display = "flex";
    if (btn) btn.setAttribute("aria-expanded", "true");
    loadChatSessions();
  }
}

function closeSessionPopover() {
  const popover = document.getElementById("sessionPopoverMenu");
  const btn = document.getElementById("sessionMenuBtn");
  if (popover && popover.style.display !== "none") {
    popover.style.display = "none";
    if (btn) btn.setAttribute("aria-expanded", "false");
  }
}

// Close session popover on outside click
document.addEventListener("click", function (e) {
  const wrap = document.querySelector(".chat-session-menu-wrap");
  if (wrap && !wrap.contains(e.target)) {
    closeSessionPopover();
  }
});

async function loadChatSessions() {
  const listEl = document.getElementById("sessionPopoverList");
  const countBadge = document.getElementById("sessionPopoverCount");
  const labelEl = document.getElementById("sessionMenuCurrentLabel");
  const selector = document.getElementById("chatSessionSelector");

  try {
    const res = await fetch("/api/seraj/sessions");
    if (!res.ok) return;
    const data = await res.json();
    activeChatSessions = data.sessions || [];

    if (countBadge) countBadge.textContent = activeChatSessions.length;

    // Update button label with current session title
    const active = activeChatSessions.find(s => s.chat_id === currentChatId);
    if (labelEl) {
      if (active && active.title) {
        labelEl.textContent = active.title.length > 14 ? active.title.slice(0, 14) + "…" : active.title;
        labelEl.title = active.title;
      } else {
        labelEl.textContent = "سجل الجلسات";
        labelEl.title = "سجل الجلسات والمحادثات السابقة";
      }
    }

    // Render Popover List
    if (listEl) {
      listEl.innerHTML = "";
      if (activeChatSessions.length === 0) {
        listEl.innerHTML = '<div style="text-align: center; color: var(--color-smoke); padding: 18px; font-size: 12px;">لا توجد جلسات سابقة مسجلة.</div>';
      } else {
        activeChatSessions.forEach(s => {
          const item = document.createElement("div");
          const isActive = s.chat_id === currentChatId;
          item.className = `session-popover-item ${isActive ? "is-active" : ""}`;
          item.onclick = () => {
            closeSessionPopover();
            switchChatSession(s.chat_id);
          };

          const msgCountStr = s.message_count ? ` · ${s.message_count} رسالة` : "";
          const timeStr = s.last_active_at ? s.last_active_at.slice(0, 16).replace("T", " ") : (s.created_at ? s.created_at.slice(0, 16).replace("T", " ") : "الآن");

          item.innerHTML = `
                <div class="session-item-content">
                  <div class="session-item-title">${escapeHtml(s.title || "محادثة مع سراج")}${isActive ? " (الحالية)" : ""}</div>
                  <div class="session-item-time">${escapeHtml(timeStr)}${msgCountStr}</div>
                </div>
                <button type="button" class="btn-delete-session-item" onclick="deleteSpecificSession('${s.chat_id}', event)" title="حذف هذه الجلسة فقط">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 12px; height: 12px;">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              `;
          listEl.appendChild(item);
        });
      }
    }

    // Backwards compatibility for selector if exists
    if (selector) {
      selector.innerHTML = '<option value="" disabled>سجل الجلسات السابقة...</option>';
      let foundCurrent = false;
      activeChatSessions.forEach(s => {
        const opt = document.createElement("option");
        opt.value = s.chat_id;
        const msgCountStr = s.message_count ? ` (${s.message_count})` : "";
        opt.textContent = `${s.title}${msgCountStr}`;
        if (s.chat_id === currentChatId) {
          opt.selected = true;
          foundCurrent = true;
        }
        selector.appendChild(opt);
      });
      if (!foundCurrent && currentChatId) {
        const opt = document.createElement("option");
        opt.value = currentChatId;
        opt.textContent = "جلسة حالية (جديدة)";
        opt.selected = true;
        selector.insertBefore(opt, selector.children[1] || null);
      }
    }
  } catch (e) {
    console.warn("Failed to load chat sessions:", e);
  }
}

async function deleteSpecificSession(chatId, e) {
  if (e) e.stopPropagation();
  if (!chatId) return;
  try {
    const res = await apiFetch(`/api/seraj/session/${encodeURIComponent(chatId)}`, {
      method: "DELETE"
    });
    if (!res.ok) throw Error("لم تُحذف الجلسة.");
    if (chatId === currentChatId) startNewChatSession();
    else loadChatSessions();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function switchChatSession(chatId) {
  if (!chatId || chatId === currentChatId || chatRequestInFlight) return;
  hideHitlGate();
  currentOperationId = null;
  currentChatId = chatId;
  const previousEngine = rememberedSerajEngine("chat", chatId);
  showSerajEngine(previousEngine, { missing: true });
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
                <span>سراج</span> • <span class="mono">استرجاع الجلسة</span>
              </div>
              <div class="msg-card">
                جاري استرجاع سجل محادثة هذه الجلسة…
              </div>
            </div>
          </div>
        `;
  }

  try {
    const res = await apiFetch(`/api/seraj/session/${encodeURIComponent(chatId)}`);
    if (chatId !== currentChatId) return;
    if (!res.ok) {
      if (chatMessages) {
        chatMessages.innerHTML = `
              <div class="msg-bubble msg-assistant">
                <div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">
                  <img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/images/svg/seraj.svg';">
                </div>
                <div class="msg-content-wrapper">
                  <div class="msg-meta"><span>سراج</span></div>
                  <div class="msg-card">تعذر استرجاع سجل هذه الجلسة من الخادم.</div>
                </div>
              </div>
            `;
      }
      return;
    }

    const data = await res.json();
    const session = data.session || {};
    const history = session.history || [];

    if (chatMessages) {
      chatMessages.innerHTML = "";
      if (history.length === 0) {
        chatMessages.innerHTML = `
              <div class="msg-bubble msg-assistant">
                <div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">
                  <img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/images/svg/seraj.svg';">
                </div>
                <div class="msg-content-wrapper">
                  <div class="msg-meta">
                    <span>سراج</span> • <span class="mono">${session.title || 'جلسة'}</span>
                  </div>
                  <div class="msg-card">
                    هذه الجلسة خالية من الرسائل السابقة. يمكنك بدء الحوار الآن.
                  </div>
                </div>
              </div>
            `;
      } else {
        history.forEach(msg => {
          if (msg.role === "user") {
            appendUserMessage(msg.content, msg.timestamp ?? null);
          } else if (msg.role === "assistant") {
            appendSerajMessage(msg.content, null, null, null, null, null, msg.reasoning_steps,
              { timestamp: msg.timestamp ?? null, duration: msg.thinking_duration_sec });
          }
        });
      }

      // Re-insert typing indicator
      const typing = document.createElement("div");
      typing.id = "typingIndicator";
      typing.className = "typing-indicator msg-bubble msg-assistant";
      typing.setAttribute("role", "status");
      typing.setAttribute("aria-label", "سراج يكتب الرد");
      typing.setAttribute("aria-live", "polite");
      typing.style.display = "none";
      typing.innerHTML = `
            <div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">
              <img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src='/images/svg/seraj.svg';">
            </div>
            <div class="typing-dots">
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
            </div>
          `;
      chatMessages.appendChild(typing);
    }

    if (session.company_id && typeof selectCompany === "function") {
      selectCompany(session.company_id);
    }
  } catch (err) {
    console.error("Error switching session:", err);
  } finally {
    loadChatSessions();
  }
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

function initChatDragResize() {
  const chat = document.getElementById("mainChatBox");
  const grid = chat?.closest(".cockpit-grid");
  if (!grid) return;

  const dimensions = {
    width: { element: grid, property: "--chat-width", storage: "odoo_chat_box_width_px", minimum: 360 },
    height: { element: chat, property: "--chat-height", storage: "odoo_chat_box_height", minimum: 420 },
  };
  function applySize(axis, size, persist = false) {
    const {element, property, storage, minimum} = dimensions[axis];
    const maximum = axis === "height" ? parseFloat(getComputedStyle(chat).maxBlockSize) : Infinity;
    const value = Math.min(maximum, Math.max(minimum, Math.round(size)));
    if (!Number.isFinite(value)) return;
    element.style.setProperty(property, `${value}px`);
    if (persist) {
      try { localStorage.setItem(storage, String(value)); } catch {}
    }
  }
  for (const [axis, dimension] of Object.entries(dimensions)) {
    try {
      const saved = Number(localStorage.getItem(dimension.storage));
      if (saved > 0) applySize(axis, saved);
    } catch {}
  }

  const handles = [
    ["chatBottomResizeHandle", ["height"]],
    ["chatSideResizeHandle", ["width"]],
    ["chatCornerResizeHandle", ["width", "height"]],
  ];
  for (const [id, axes] of handles) {
    const handle = document.getElementById(id);
    if (!handle) continue;

    function reset() {
      for (const axis of axes) {
        const {element, property, storage} = dimensions[axis];
        element.style.removeProperty(property);
        try { localStorage.removeItem(storage); } catch {}
      }
    }
    handle.addEventListener("dblclick", reset);
    handle.addEventListener("keydown", event => {
      if (event.key === "Home") {
        reset();
      } else {
        const horizontal = ["ArrowLeft", "ArrowRight"].includes(event.key);
        const axis = horizontal ? "width" : "height";
        if (!axes.includes(axis) || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
        const direction = horizontal && getComputedStyle(grid).direction === "rtl" ? -1 : 1;
        const grow = horizontal
          ? (event.key === "ArrowRight" ? direction : -direction)
          : (event.key === "ArrowDown" ? 1 : -1);
        const bounds = chat.getBoundingClientRect();
        applySize(axis, bounds[axis] + grow * (event.shiftKey ? 160 : 40), true);
      }
      event.preventDefault();
    });

    let drag;
    function resize() {
      if (!drag) return;
      if (axes.includes("width")) applySize("width", drag.width + (drag.x - drag.startX) * drag.direction);
      if (axes.includes("height")) applySize("height", drag.height + drag.y + window.scrollY - drag.startY);
    }
    function scrollWhileDragging() {
      if (!drag) return;
      if (
        axes.includes("height") &&
        drag.y > window.innerHeight - 70 &&
        chat.getBoundingClientRect().height < parseFloat(getComputedStyle(chat).maxBlockSize) - 1
      ) {
        window.scrollBy({top: 14, behavior: "instant"});
        resize();
      }
      drag.frame = requestAnimationFrame(scrollWhileDragging);
    }
    handle.addEventListener("pointerdown", event => {
      if (drag || event.button !== 0) return;
      event.preventDefault();
      const {width, height} = chat.getBoundingClientRect();
      drag = {width, height, x: event.clientX, y: event.clientY, startX: event.clientX,
        startY: event.clientY + window.scrollY, direction: getComputedStyle(grid).direction === "rtl" ? -1 : 1};
      handle.setPointerCapture(event.pointerId);
      handle.classList.add("is-active");
      chat.classList.add("is-resizing");
      drag.frame = requestAnimationFrame(scrollWhileDragging);
    });
    handle.addEventListener("pointermove", event => {
      if (!drag || !handle.hasPointerCapture(event.pointerId)) return;
      drag.x = event.clientX;
      drag.y = event.clientY;
      resize();
    });
    handle.addEventListener("lostpointercapture", () => {
      if (!drag) return;
      cancelAnimationFrame(drag.frame);
      drag = null;
      handle.classList.remove("is-active");
      chat.classList.remove("is-resizing");
      const bounds = chat.getBoundingClientRect();
      for (const axis of axes) applySize(axis, bounds[axis], true);
    });
  }
}

async function clearAllChatSessions(event) {
  event?.stopPropagation();
  if (!confirm("هل تريد حذف جميع جلسات المحادثة؟")) return;
  try {
    const res = await apiFetch("/api/seraj/sessions", {
      method: "DELETE",
    });
    const data = await res.json();
    if (!res.ok) throw Error(data.detail || "لم يُحذف سجل الجلسات.");
    closeSessionPopover();
    showToast(data.message || "تم مسح كافة الجلسات بنجاح.", "success");
    startNewChatSession();
  } catch (err) {
    showToast("تعذر مسح الجلسات: " + err.message, "error");
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
  const waitingText = "سراج ومنظومة الوكلاء يستدلون على الطلب…";
  el.className = "typing-indicator msg-bubble msg-assistant is-visible";
  el.setAttribute("role", "status");
  el.setAttribute("aria-label", "سراج ومنظومة الوكلاء يستدلون على الطلب");
  el.setAttribute("aria-live", "polite");
  el.innerHTML =
    '<div class="msg-avatar" style="border-color: var(--agent-seraj); overflow: hidden; background: var(--paper-2);">' +
    '<img src="/images/seraj.webp" alt="سراج" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.src=\'/images/svg/seraj.svg\';">' +
    '</div>' +
    '<div class="msg-content-wrapper">' +
    '<div class="msg-card">' +
    '<div class="cv-waiting">' +
    '<svg class="cv-late" aria-hidden="true" viewBox="0 0 24 24"><path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z"/></svg>' +
    `<span class="cv-pensando">${waitingText}<span class="cv-shimmer" aria-hidden="true">${waitingText}</span></span>` +
    '</div>' +
    '</div>' +
    '</div>';
  const container = document.getElementById("chatMessages");
  if (container) {
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }
}

function toggleCavilaSteps(btn) {
  if (!btn) return;
  const isExpanded = btn.getAttribute("aria-expanded") === "true";
  btn.setAttribute("aria-expanded", isExpanded ? "false" : "true");
  const pasos = btn.closest(".cv-cajon")?.querySelector(".cv-pasos");
  if (!pasos) return;
  if (!isExpanded) {
    pasos.style.height = pasos.scrollHeight + "px";
    pasos.classList.add("is-abierto");
  } else {
    pasos.style.height = "0";
    pasos.classList.remove("is-abierto");
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
  stopLiveEventPolling();
  lastEventSequence = 0;
  streamConsecutiveErrors = 0;
  setStreamConnected(false, "جارٍ الاتصال بسجل العملية…");

  const endpoint = `/api/agents/operations/${encodeURIComponent(opId)}`;
  const terminal = new Set(["completed", "failed", "cancelled", "inconclusive"]);
  let reportedStatus = null;
  let busy = false;
  const isCurrent = () => pollingInterval === timer && opId === currentOperationId;

  async function poll() {
    if (!isCurrent() || busy) return;
    busy = true;
    try {
      const response = await apiFetch(`${endpoint}/events?after=${lastEventSequence}`);
      if (!isCurrent()) return;
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!isCurrent()) return;
      if (data.status !== "success") throw new Error("تعذر قراءة سجل العملية");
      if (data.operation_status === "unknown") {
        if (chatRequestInFlight) return;
        throw new Error("لم يظهر سجل العملية بعد");
      }

      if (data.events?.length || reportedStatus !== data.operation_status) {
        const snapshot = await apiFetch(endpoint);
        if (!isCurrent()) return;
        if (!snapshot.ok) throw new Error(`HTTP ${snapshot.status}`);
        const payload = await snapshot.json();
        if (!isCurrent()) return;
        if (!payload.operation) throw new Error("تعذر قراءة حالة العملية");
        const op = payload.operation;
        const events = op.events || [];
        updateOperationBadges(op);
        updateProcessStepper(events, op);
        lastEventSequence = events.reduce((seq, event) => Math.max(seq, event.sequence || 0), lastEventSequence);
        reportedStatus = currentOperationStatus = op.status;
      }

      streamConsecutiveErrors = 0;
      if (terminal.has(reportedStatus) && !chatRequestInFlight) {
        stopLiveEventPolling();
        resetAllAgentsToIdle();
        setStreamConnected(true, "انتهت متابعة العملية");
        hideTypingIndicator();
      } else {
        setStreamConnected(true, "متصل بسجل العملية");
      }
    } catch (err) {
      if (!isCurrent()) return;
      streamConsecutiveErrors++;
      setStreamConnected(false, `تعذر تحديث سجل العملية (${err.message})`);
      if (streamConsecutiveErrors >= 8) {
        stopLiveEventPolling();
        showStreamRecoveryOption(opId);
      }
    } finally {
      busy = false;
    }
  }

  const timer = setInterval(poll, 500);
  pollingInterval = timer;
  void poll();
}

function stopLiveEventPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
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
  const dockBadge = document.getElementById("dockGlobalStatusBadge");
  const dockStatusText = document.getElementById("dockGlobalStatusText");
  const status = op?.status || "idle";
  const state = ["failed", "error", "inconclusive"].includes(status) ? "error"
    : status.startsWith("waiting") ? "warning"
    : ["completed", "approved", "success"].includes(status) ? "success" : "neutral";
  if (dockBadge) dockBadge.className = `badge badge-${state}`;
  const routeTarget = document.getElementById("route-step-target");
  if (
    evtList.length > 0 &&
    op &&
    op.status !== "completed" &&
    op.status !== "failed" &&
    op.status !== "cancelled" && status !== "inconclusive"
  ) {
    const latest = evtList[evtList.length - 1];
    const agentKey = latest.agent || activeAgent || "seraj";
    const meta = resolveAgentMeta(agentKey);
    if (dockStatusText) {
      dockStatusText.textContent = `${meta.name_ar}: ${latest.status_label || STATUS_MAP_AR[status] || "يعالج الطلب…"}`;
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
        op?.status_label || STATUS_MAP_AR[status] || "جاهز";
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
  const company = selectedCompanyId;
  if (!company) return;
  try {
    const res = await apiFetch("/api/reference/hr-options?company_id=" + encodeURIComponent(company));
    if (company !== selectedCompanyId || !res.ok) return;
    const {data} = await res.json();
    if (data && company === selectedCompanyId) {
      Object.assign(window.hrReferenceOptions, data);
      if (window.currentHitlPendingAction) renderHitlDiffTable(window.currentHitlPendingAction);
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

  const employeePlan = !pendingAction.model || pendingAction.model === "hr.employee";
  const type = pendingAction.action_type || pendingAction.type || "create";
  if (addBtn) addBtn.style.display = employeePlan && ["create", "update"].includes(type) ? "inline-flex" : "none";

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
      if (!employeePlan) window.currentHitlPendingValues = {name: window.currentHitlPendingValues.name};
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


document.addEventListener("click", function (e) {
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
  const draft = window.currentHitlPendingAction;
  if (draft && (draft.action_type || draft.type) === "create") {
    (draft.removedFields ||= new Set()).add(fieldKey);
  }
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
    for (const key of act.removedFields || []) {
      if (!(key in modifiedPayload)) modifiedPayload[key] = "";
    }

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
  if (agBadge) agBadge.textContent = resolveAgentMeta(op.active_agent).name_ar;

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

const EVENT_ACTIVITY_LABELS = {
  operation_started: "بدء معالجة الطلب",
  operation_cancelled: "إلغاء العملية",
  intent_decomposition: "فهم الطلب وتحديد الخطوات",
  odoo_search_read: "البحث في السجلات",
  odoo_query: "البحث في السجلات",
  search_records: "البحث في السجلات",
  legal_compliance_audit: "مراجعة ضوابط العمل",
  deliver_legal_advisory: "تقديم الاستشارة",
  labor_law_consultation: "مراجعة نظام العمل",
  synthesize_response: "إعداد الرد",
  run_hr_calculation_sandbox: "إجراء الحسابات المطلوبة",
  file_received: "استلام الملف",
  spreadsheet_analysis: "فحص بيانات الملف",
  spreadsheet_error: "تعذّر فحص الملف",
  dry_run_completed: "إعداد تقرير الفحص",
  write_started: "بدء تطبيق التعديلات",
  write_completed: "انتهاء تطبيق التعديلات",
  write_error: "تعذّر تطبيق التعديلات",
  action_approved: "اعتماد العملية",
  plan_prepared: "إعداد الطلب للمراجعة والاعتماد",
  query_received: "استلام الطلب",
  batch_import: "مراجعة السجلات المرفوعة",
  record_inspection: "فحص السجل",
  operation_documented: "توثيق العملية",
  tool_execution: "معالجة الطلب",
};

function describeAgentActivity(event) {
  const known = (key) => Object.hasOwn(EVENT_ACTIVITY_LABELS, key) ? EVENT_ACTIVITY_LABELS[key] : "";
  const description = String(event.description_ar || event.title || "").trim();
  const tool = event.metadata?.tool || description.match(/\b([a-z][a-z0-9_]*_[a-z0-9_]+)\s*\(/i)?.[1];
  if (tool === "run_hr_calculation_sandbox" && /السكن|النقل/.test(description)) return "حساب بدلات الموظف";
  if (tool || event.event_type === "tool_execution" || event.action === "tool_execution") {
    return known(tool) || "معالجة الطلب";
  }
  const plain = description.replace(/\bOdoo\b/gi, "أودو");
  if (/[\u0621-\u064A]/.test(plain) && !/[a-z]{2,}|[_{}<>\u0060]/i.test(plain)) return plain;
  return known(event.event_type) || known(event.action) || "خطوة في معالجة الطلب";
}

function describeEventStatus(status) {
  if (["success", "completed"].includes(status)) return "اكتمل";
  if (["approved", "approval_verified"].includes(status)) return "تم الاعتماد";
  if (["failed", "error"].includes(status)) return "تعذّر التنفيذ";
  if (status === "rejected") return "رُفض";
  if (status === "querying_odoo") return "يبحث في السجلات";
  if (status === "in_progress") return "قيد التنفيذ";
  return Object.hasOwn(STATUS_MAP_AR, status) ? STATUS_MAP_AR[status] : "مسجّل";
}

function updateProcessStepper(events, opOverride) {
  const stepper = document.getElementById("processStepper");
  if (!stepper) return;

  const evtList = Array.isArray(events) ? events : [];
  const op = opOverride || window.currentOperationObj || {};
  const opStatus = op.status || (evtList.length ? "in_progress" : "idle");
  const terminal = ["completed", "failed", "cancelled", "inconclusive"].includes(opStatus);
  const completed = evtList.filter(e => ["completed", "success"].includes(e.status)).length;
  const count = document.getElementById("processStepCount");
  const subtitle = document.getElementById("stepperSubtitle");

  if (count) count.textContent = evtList.length ? `${completed} / ${evtList.length} أحداث مكتملة` : "—";
  if (subtitle) subtitle.textContent = describeEventStatus(opStatus);
  document.getElementById("processStepperCard")?.style.setProperty("display", "block");

  stepper.innerHTML = evtList.length ? evtList.map((evt, index) => {
    const meta = resolveAgentMeta(evt.agent);
    const done = ["completed", "success"].includes(evt.status);
    const failed = ["failed", "error", "rejected", "inconclusive"].includes(evt.status);
    const waiting = String(evt.status).startsWith("waiting");
    const active = !terminal && index === evtList.length - 1 && !waiting;
    const state = done ? "completed" : failed ? "failed" : waiting ? "waiting" : active ? "active" : "idle";
    return `<div class="step-node is-${state}">
      <div class="step-icon-box" aria-hidden="true">${done ? "✓" : index + 1}</div>
      <div class="step-content">
        <div class="step-header-line step-event-header">
          <span class="step-desc">${escapeHtml(describeAgentActivity(evt))}</span>
          <span class="step-agent-badge">${escapeHtml(meta.name_ar)}</span>
        </div>
        <div class="step-event-meta">
          <span class="step-status-tag">${escapeHtml(describeEventStatus(evt.status))}</span>
          ${evt.timestamp ? `<time datetime="${escapeHtml(evt.timestamp)}" dir="ltr">${escapeHtml(String(evt.timestamp).split("T")[1]?.slice(0, 8) || evt.timestamp)}</time>` : ""}
        </div>
      </div>
    </div>`;
  }).join("") : `<div class="stepper-idle-banner">${op.operation_id ? "لا توجد أحداث مسجلة لهذه العملية بعد." : "تظهر الأحداث هنا عند بدء العملية."}</div>`;

  updateCockpitTelemetry(evtList, op.active_agent || evtList.at(-1)?.agent || "seraj", op);
  renderAgentTimeline(evtList, opStatus);

  if (opStatus === "waiting_approval") {
    const pending = op.pending_action || op.plan || window.currentHitlPendingAction;
    if (pending) {
      window.currentHitlPendingAction = pending;
      renderHitlDiffTable(pending);
      showHitlGate(op.operation_id || currentOperationId, 1, 0);
    }
  } else if (terminal) {
    hideHitlGate();
  }
}

function openEventDetails(evt) {
  const overlay = document.getElementById("detailsDrawerOverlay");
  const title = document.getElementById("drawerTitle");
  const subtitle = document.getElementById("drawerSubtitle");
  const body = document.getElementById("drawerBody");
  if (!overlay || !body || !evt) return;

  const agent = resolveAgentMeta(evt.agent);
  const time = String(evt.timestamp || "").match(/(?:T| )(\d{2}:\d{2}:\d{2})/)?.[1];
  title.textContent = describeAgentActivity(evt);
  if (subtitle) subtitle.textContent = "تفاصيل الخطوة";
  body.innerHTML = `
    <div class="drawer-event-summary">
      <div class="drawer-event-section">
        <div class="drawer-event-label">الوكيل</div>
        <strong style="color: ${agent.color};">${escapeHtml(agent.name_ar)}</strong>
      </div>
      <div class="drawer-event-section">
        <div class="drawer-event-label">الحالة</div>
        <strong>${escapeHtml(describeEventStatus(evt.status))}</strong>
        ${time ? `<time class="mono" dir="ltr">${escapeHtml(time)}</time>` : ""}
      </div>
    </div>
  `;
  overlay.classList.add("is-open");
}

// =========================================================================
// 10. AGENT DRAWER DETAILS (CENTERED MODAL)
// =========================================================================
const AGENT_TOOLS_CATALOG = {
  seraj: [
    { title: "منسق الحوار وتوزيع المهام", name_en: "seraj_chat_orchestrator", badge: "تنسيق عام", badge_class: "badge-primary", desc: "استقبال استفسارات المشغل وتحليل النوايا وتوجيهها للوكيل المختص مع صياغة الردود الشارحة." },
    { title: "استعلام المعرفة العمالية", name_en: "query_hr_knowledge", badge: "قراءة وتفسير", badge_class: "badge-neutral", desc: "البحث في اللائحة ونظام العمل السعودي وتزويد الوكلاء بالمواد والضوابط القانونية." },
    { title: "متابع خط الأنابيب والعمليات", name_en: "summarize_operation_pipeline", badge: "متابعة حية", badge_class: "badge-neutral", desc: "متابعة تسلسل المهام ونقاط التسليم بين الوكلاء والتحقق من اكتمال دورة العمل." }
  ],
  fahas: [
    { title: "استعلام سجلات الموظفين", name_en: "search_employees", badge: "قراءة فقط (Read-Only)", badge_class: "badge-success", desc: "فحص ومطابقة بيانات الموظفين في Odoo (الهوية، الاسم، الشركة) دون أي صلاحية تعديل." },
    { title: "فحص الهيكل التنظيمي", name_en: "get_department_structure", badge: "قراءة فقط (Read-Only)", badge_class: "badge-success", desc: "استرجاع قائمة الأقسام والفروع ومراكز العمل للتأكد من مطابقة مدخلات الملفات." },
    { title: "تدقيق سجلات الحضور", name_en: "inspect_attendance_logs", badge: "قراءة فقط (Read-Only)", badge_class: "badge-success", desc: "قراءة حركات الحضور والانصراف لحساب ساعات العمل الإضافي والتأخير ومطابقتها." },
    { title: "مطابقة مسيرات الرواتب", name_en: "verify_payroll_entries", badge: "تحقق مستقل", badge_class: "badge-neutral", desc: "المراجعة المستقلة لقيود الأجور والتأمينات قبل وبعد الاعتماد للتأكد من السلامة." }
  ],
  modaqeq: [
    { title: "فحص الامتثال لنظام العمل", name_en: "check_labor_law_compliance", badge: "رقابة قانونية ملزمة", badge_class: "badge-warning", desc: "مطابقة شروط العقود والإجازات وساعات العمل مع 40 مادة مفهرسة وفرض الفيتو القانوني عند المخالفة." },
    { title: "تدقيق استقطاعات التأمينات GOSI", name_en: "audit_gosi_deductions", badge: "تدقيق مالي", badge_class: "badge-warning", desc: "التأكد من نسب استقطاع ساند والتأمينات (القديم 21.5% والجديد المتدرج و2% أخطار مهنية)." },
    { title: "التحقق من فترة التجربة (م/53)", name_en: "verify_probation_period", badge: "امتثال نظامي", badge_class: "badge-neutral", desc: "منع تجاوز فترة التجربة 90 يوماً إلا بموافقة كتابية صريحة لا تتعدى 180 يوماً." }
  ],
  mowafaq: [
    { title: "مطابقة المرشحين بالموظفين", name_en: "match_candidate_to_employee", badge: "مطابقة ذكية", badge_class: "badge-primary", desc: "استخدام خوارزميات التشابه الدلالي لربط طلبات التوظيف بسجلات الموظفين ومنع الازدواجية." },
    { title: "توفيق المسميات الوظيفية", name_en: "resolve_job_position", badge: "مطابقة دلالية", badge_class: "badge-neutral", desc: "حل الاختلاف اللفظي بين مسميات ملفات الإكسل وقائمة الوظائف المعتمدة في Odoo." },
    { title: "تسكين الأقسام والفروع", name_en: "semantic_fuzzy_matcher", badge: "مطابقة تقريبية", badge_class: "badge-neutral", desc: "مطابقة النصوص المتباينة للأقسام والمواقع واقتراح الكيان الأنسب بدرجة ثقة محددة." }
  ],
  musleh: [
    { title: "تشخيص الشذوذ والتباين", name_en: "reconcile_discrepancies", badge: "تشخيص ذاتي", badge_class: "badge-warning", desc: "كشف الفجوات بين البيانات المرفوعة وسجلات Odoo وتحديد مكمن الخلل وسببه الجذري." },
    { title: "توليد مقترحات التسوية", name_en: "suggest_contract_fixes", badge: "اقتراح حلول", badge_class: "badge-neutral", desc: "تقديم خيارات وحلول تسوية للمشغل لمعالجة الفروقات في البدلات أو تواريخ العقود." },
    { title: "معالجة وتوحيد الصيغ", name_en: "format_corrections", badge: "معالجة منضبطة", badge_class: "badge-neutral", desc: "تصحيح تنسيق أرقام الهواتف والتواريخ والأرقام دون المساس بجوهر ومحتوى البيانات." }
  ],
  hares: [
    { title: "بوابة الاعتماد البشري (HITL)", name_en: "hitl_gatekeeper", badge: "سلطة فيتو أمنية", badge_class: "badge-danger", desc: "اشتراط الموافقة الصريحة للمشغل البشري قبل أي كتابة أو تعديل وتأمين مدة صلاحية الاعتماد." },
    { title: "حماية البيانات الحساسة PII", name_en: "audit_action_security", badge: "أمان وخصوصية", badge_class: "badge-danger", desc: "حجب الهويات والحسابات البنكية وحماية بيئة الإنتاج من أي تسريب بياني." },
    { title: "التحقق من الصلاحيات والحدود", name_en: "verify_user_permissions", badge: "عزل الصلاحيات", badge_class: "badge-warning", desc: "منع تنفيذ أي كتابة تتجاوز حدود المنشأة المصرح بها أو صلاحيات الدور المعين." }
  ],
  katib: [
    { title: "إنشاء وتحديث سجل الموظف", name_en: "create_or_update_employee", badge: "تنفيذ ذري محكوم", badge_class: "badge-success", desc: "المنفذ الحصري لإنشاء وتعديل وتحديث بيانات الموظف في Odoo عبر بوابات معزولة." },
    { title: "صياغة الخطابات والقرارات", name_en: "generate_hr_letter", badge: "صياغة معتمدة", badge_class: "badge-neutral", desc: "توليد خطابات التعريف والقرارات الإدارية ومطابقة بنودها مع أنظمة المنشأة." },
    { title: "تنفيذ خطة الكتابة المعتمدة", name_en: "execute_odoo_write_plan", badge: "كتابة مشروطة", badge_class: "badge-success", desc: "تطبيق التعديلات المعتمدة كحزمة ذرية واحدة والتأكد من نجاح الكتابة قبل التوثيق." }
  ],
  sijil: [
    { title: "القيد في الدفتر اللاتراجعي", name_en: "record_audit_log", badge: "توثيق دائم", badge_class: "badge-primary", desc: "تسجيل كل حدث وقرار في دفتر سجل محمي من التعديل مع معرف العملية والطابع الزمني." },
    { title: "إصدار تقارير الحوكمة PDF", name_en: "generate_pdf_report", badge: "تقارير رسمية", badge_class: "badge-primary", desc: "توليد ملفات PDF رسمية موثقة بختم الحوكمة ومؤشرات الامتثال وتفاصيل العمليات." },
    { title: "التحقق من البصمة SHA-256", name_en: "verify_audit_trail_integrity", badge: "ختم تشفيري", badge_class: "badge-neutral", desc: "تأكيد عدم التلاعب بالسجلات من خلال فحص سلسلة البصمات الرقمية التراكمية." }
  ]
};

function openAgentDetails(agentKey, trigger = null) {
  const normKey = (agentKey === "mudaqqiq" || agentKey === "modaqeq") ? "modaqeq" : ((agentKey === "muwaffaq" || agentKey === "mowafaq") ? "mowafaq" : agentKey);
  const meta = AGENTS_META[normKey] || AGENTS_META[agentKey] || {};
  const agentData = activeAgentsData.find((a) => a.id === agentKey || a.id === normKey) || {};
  const dialog = trigger && document.getElementById("agentFlightDialog");
  const overlay = dialog || document.getElementById("detailsDrawerOverlay");
  const title = document.getElementById(dialog ? "agentFlightTitle" : "drawerTitle");
  const body = document.getElementById(dialog ? "agentFlightBody" : "drawerBody");
  if (!overlay || !body) return;

  title.textContent = `بطاقة الوكيل: «${meta.name_ar || "وكيل المنظومة"}»`;
  const subtitle = dialog ? null : document.getElementById("drawerSubtitle");
  if (subtitle) subtitle.textContent = "المهام والصلاحيات";

  const recentTasks = agentData.recent_tasks || [];
  const lastTask = agentData.last_task;
  const lastActivity = lastTask
    ? describeAgentActivity({ description_ar: lastTask })
    : "في انتظار استلام المهام";
  const toolsList = AGENT_TOOLS_CATALOG[normKey] || [];

  body.innerHTML = `
        <!-- Agent Identity Banner -->
        <div class="agent-detail-identity" style="display: flex; align-items: center; gap: 14px; background: var(--paper-2); padding: 16px; border-radius: 3px; border: 1px solid var(--rule-strong);">
          <div data-hueco="avatar">
          <div class="agent-avatar-wrap" style="border-color: ${meta.color}; width: 52px; height: 52px; margin: 0; flex-shrink: 0;">
            ${meta.img ? `<img src="${meta.img}" alt="${escapeHtml(meta.name_ar)}" class="agent-avatar-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />` : ""}
            <div class="agent-avatar-svg-fallback" style="${meta.img ? "display:none;" : "display:flex;"} width:100%; height:100%; align-items:center; justify-content:center;">
              ${getAgentSvg(meta.icon)}
            </div>
          </div>
          </div>
          <div style="flex: 1; min-width: 0;">
            <div data-hueco="name"><div style="font-size: 18px; font-weight: 700; color: var(--color-snow);">${escapeHtml(meta.name_ar || agentKey)}</div></div>
            <div data-hueco="station"></div>
            <div style="font-size: 12.5px; color: var(--color-silver-mist); margin-top: 2px;">${escapeHtml(agentData.title_ar || meta.role)}</div>
          </div>
          <span class="badge ${agentData.status_code === "ready" || agentData.status_code === "idle" ? "badge-success" : (agentData.status_code === "failed" ? "badge-danger" : "badge-warning")}" style="display: inline-flex; align-items: center; gap: 4px;">
            <span>${agentData.status_label || STATUS_MAP_AR[agentData.status_code] || "جاهز"}</span>
          </span>
        </div>

        <!-- Task & Activity Status -->
        <div style="background: var(--paper-2); padding: 14px; border-radius: 10px; border: 1px solid var(--rule);">
          <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 4px;">المهمة الحالية / الأخيرة</div>
          <div style="font-size: 13.5px; color: var(--color-snow); line-height: 1.5; font-weight: 500;">
            ${escapeHtml(lastActivity)}
          </div>
          <div style="margin-top: 8px; font-size: 11.5px; color: var(--color-silver-mist);">
            إجمالي العمليات: <strong class="mono" style="color: var(--color-snow);">${agentData.operation_count || 0}</strong> عملية ·
            إجمالي الأحداث: <strong class="mono" style="color: var(--color-snow);">${agentData.event_count || 0}</strong> حدث موثق
          </div>
        </div>

        <!-- Real Activities -->
        <div style="background: var(--paper-2); padding: 14px; border-radius: 10px; border: 1px solid var(--rule);">
          <div class="settings-section-title" style="margin-bottom: 10px; font-size: 13.5px; font-weight: 700; color: var(--color-snow);">آخر الأنشطة</div>
          ${recentTasks.length > 0
      ? recentTasks.map(t => `
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; background: var(--paper); padding: 9px 12px; border-radius: 8px; border: 1px solid var(--rule); margin-bottom: 6px;">
                  <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 11px; color: var(--color-smoke); font-family: var(--font-mono);">${escapeHtml(t.timestamp ? t.timestamp.slice(0, 19).replace("T", " ") : "")}</div>
                    <p style="font-size: 12.5px; color: var(--color-snow); margin: 3px 0 0 0; line-height: 1.4;">${escapeHtml(describeAgentActivity(t))}</p>
                  </div>
                  ${t.operation_id ? `<button class="btn btn-sm btn-secondary" style="padding: 4px 8px; font-size: 11px; flex-shrink: 0;" onclick="closeDetailsDrawer();resumeOperationInCockpit('${escapeHtml(t.operation_id)}')">فتح العملية</button>` : ""}
                </div>
              `).join("")
      : `<div style="text-align: center; color: var(--color-silver-mist); padding: 16px; background: var(--paper); border-radius: 8px; border: 1px dashed var(--rule); font-size: 12px;">
                  لا توجد مهام مسجلة لهذا الوكيل.
                 </div>`
    }
        </div>

        <!-- Architectural Boundaries & Arabic Tool Cards -->
        <div style="background: var(--paper-2); padding: 14px; border-radius: 10px; border: 1px solid var(--rule);">
          <div class="settings-section-title" style="margin-bottom: 8px; font-size: 13.5px; font-weight: 700; color: var(--color-snow);">الأدوات المعتمدة والصلاحيات المنضبطة</div>
          <div style="font-size: 12.5px; color: var(--color-silver-mist); margin-bottom: 12px; line-height: 1.5;">
            ${escapeHtml(agentData.description_short || meta.role || "يعمل ضمن ميثاق الحوكمة والفصل المعماري.")}
          </div>
          <div class="agent-tools-grid">
            ${toolsList.map(tool => `
              <div class="agent-tool-item-card">
                <div class="agent-tool-header">
                  <div class="agent-tool-title">${escapeHtml(tool.title)}</div>
                  <span class="badge ${tool.badge_class}">${escapeHtml(tool.badge)}</span>
                </div>
                <div style="font-size: 12px; color: var(--color-silver-mist); line-height: 1.45; margin-top: 3px;">${escapeHtml(tool.desc)}</div>
              </div>
            `).join("")}
          </div>
        </div>
      `;

  if (dialog) openAgentFlight(dialog, trigger);
  else overlay.classList.add("is-open");
}

function closeDetailsDrawer(e) {
  const agentDialog = document.getElementById("agentFlightDialog");
  if (agentDialog?.open) agentDialog.querySelector("[data-flight-close]").click();
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
let operationsLoadId = 0;
function changeOpsPage(delta) {
  opsPage = Math.max(1, Math.min(Math.ceil(opsTotal / opsLimit), opsPage + delta));
  loadOperationsList();
}

async function loadOperationsList() {
  const tbody = document.getElementById("operationsTableBody");
  if (!tbody) return;

  const requestId = ++operationsLoadId;
  try {
    const params = new URLSearchParams({limit: opsLimit, offset: (opsPage - 1) * opsLimit, q: currentOpsSearch, group: currentOpsFilter});
    const res = await apiFetch("/api/agents/operations?" + params);
    if (!res.ok) throw Error(String(res.status));
    const data = await res.json();
    if (requestId !== operationsLoadId) return;
    if (data.status === "success" && data.operations) {
      opsTotal = data.total;
      const pages = Math.max(1, Math.ceil(opsTotal / opsLimit));
      if (opsPage > pages) { opsPage = pages; return loadOperationsList(); }
      document.getElementById("opsPaginationInfo").textContent = opsTotal + " عملية";
      document.getElementById("opsPageBadge").textContent = opsPage + " / " + pages;
      document.getElementById("opsPrevBtn").disabled = opsPage <= 1;
      document.getElementById("opsNextBtn").disabled = opsPage >= pages;
      if (data.operations.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--color-smoke); padding: 30px;">لا توجد عمليات مطابقة.</td></tr>`;
        return;
      }
      tbody.innerHTML = data.operations
        .map(
          (op) => `
            <tr data-status="${escapeHtml(op.status || '')}" data-id="${escapeHtml(op.operation_id || '')}" data-type="${escapeHtml(op.operation_type || '')}" data-agent="${escapeHtml(op.active_agent || '')}" data-company="${escapeHtml(op.company_name || '')}">
              <td class="mono" style="font-weight: 600; color: var(--color-snow);">${escapeHtml(op.operation_id)}</td>
              <td>${escapeHtml(op.operation_type || "محادثة")}</td>
              <td>${escapeHtml(op.requester || "المستخدم")}</td>
              <td>${escapeHtml(op.company_name || (op.company_id ? "شركة " + op.company_id : "الشركة المحددة"))}</td>
              <td><span style="color: ${AGENTS_META[op.active_agent]?.color || "var(--color-silver-mist)"}; font-weight: 600;">${AGENTS_META[op.active_agent]?.name_ar || op.active_agent}</span></td>
              <td><span class="badge ${op.status === "completed" ? "badge-success" : (op.status === "failed" || op.status === "cancelled" || op.status === "rejected") ? "badge-error" : "badge-warning"}">${op.status_label || STATUS_MAP_AR[op.status] || op.status}</span></td>
              <td class="mono" style="font-size: 12px;">${op.created_at ? (typeof formatLocalDateTime === "function" ? formatLocalDateTime(op.created_at) : op.created_at.substring(0, 19).replace("T", " ")) : "—"}</td>
              <td>
                <div class="operation-row-actions">
                  <button type="button" class="btn btn-sm btn-secondary" onclick="resumeOperationInCockpit(this.closest('tr').dataset.id)">متابعة</button>
                  <button type="button" class="btn btn-sm btn-secondary" onclick="openOperationInSijil(this.closest('tr').dataset.id)">سجل</button>
                  <button type="button" class="btn btn-sm btn-secondary" onclick="exportSingleOpPdf(this.closest('tr').dataset.id)">PDF</button>
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
    if (requestId !== operationsLoadId) return;
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--color-coral); padding: 20px;">تعذر تحميل العمليات: ${escapeHtml(err.message)}</td></tr>`;
  }
}
window.loadOperationsList = loadOperationsList;

window.refreshOperationsList = async function (btn) {
  const targetBtn = btn || document.querySelector('[onclick*="refreshOperationsList"]');
  if (targetBtn) {
    targetBtn.disabled = true;
    const oldHtml = targetBtn.innerHTML;
    targetBtn.innerHTML = `<span class="spinner" style="width: 13px; height: 13px; border: 2px solid currentColor; border-top-color: transparent; border-radius: 50%; display: inline-block; animation: spin 0.6s linear infinite; vertical-align: middle; margin-left: 5px;"></span> <span>جاري التحديث...</span>`;
    try {
      await loadOperationsList();
      if (typeof showToast === "function") {
        showToast("تم تحديث سجل العمليات التشغيلية بنجاح", "success");
      }
    } catch (err) {
      if (typeof showToast === "function") {
        showToast("تعذر تحديث سجل العمليات: " + err.message, "error");
      }
    } finally {
      targetBtn.disabled = false;
      targetBtn.innerHTML = oldHtml;
    }
  } else {
    await loadOperationsList();
  }
};

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
      showSerajEngine(op.llm_meta || rememberedSerajEngine("operation", currentOperationId), { missing: true });
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

        if (!messages.some(message => message.role === "assistant")) {
          const notice = document.createElement("p");
          notice.className = "chat-history-notice";
          notice.textContent = "نص الرد غير محفوظ في سجل هذه العملية.";
          chatContainer.appendChild(notice);
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
            <tr data-domain="${escapeHtml(typeLabel)}" data-status="${statusOk ? 'verified' : 'review'}">
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

      if (typeof filterSijilTable === "function") {
        filterSijilTable();
      }
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
        sData.summary.four_eyes_tokens_count ?? "—";
      document.getElementById("metricAuditEvents").textContent =
        sData.summary.total_events?.toLocaleString("ar-SA") ?? "—";
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

// =========================================================================
// HIGH-VALUE AUDITOR FILTERS FOR SIJIL
// =========================================================================
window.currentSijilDomain = "all";
window.currentSijilStatus = "all";
window.currentSijilSearch = "";

window.filterSijilTable = function () {
  const tbody = document.getElementById("sijilRecentTableBody");
  if (!tbody) return;
  const rows = tbody.querySelectorAll("tr");
  const q = (window.currentSijilSearch || "").toLowerCase().trim();

  rows.forEach(tr => {
    if (tr.children.length === 1 && tr.children[0].getAttribute("colspan")) return;
    const domain = (tr.getAttribute("data-domain") || "").toLowerCase();
    const status = (tr.getAttribute("data-status") || "").toLowerCase();
    const text = tr.textContent.toLowerCase();

    // 1. Domain match
    let matchDomain = true;
    if (window.currentSijilDomain === "employees") {
      matchDomain = domain.includes("موظف") || domain.includes("employee") || text.includes("موظف") || text.includes("استيراد");
    } else if (window.currentSijilDomain === "contracts_payroll") {
      matchDomain = domain.includes("عقد") || domain.includes("راتب") || domain.includes("gosi") || text.includes("عقد") || text.includes("راتب") || text.includes("تأمينات");
    } else if (window.currentSijilDomain === "leaves_attendance") {
      matchDomain = domain.includes("إجاز") || domain.includes("اجاز") || domain.includes("حضور") || domain.includes("دوام") || text.includes("إجاز") || text.includes("حضور");
    } else if (window.currentSijilDomain === "disciplinary_letters") {
      matchDomain = domain.includes("إنذار") || domain.includes("خطاب") || domain.includes("جزاء") || text.includes("إنذار") || text.includes("خطاب") || text.includes("إنهاء");
    } else if (window.currentSijilDomain === "deletions_security") {
      matchDomain = domain.includes("حذف") || domain.includes("أرشف") || domain.includes("أمان") || text.includes("حذف") || text.includes("أرشف") || text.includes("إلغاء");
    }

    // 2. Status match
    let matchStatus = true;
    if (window.currentSijilStatus === "verified") {
      matchStatus = status === "verified" || text.includes("ناجح") || text.includes("مكتمل") || text.includes("100%");
    } else if (window.currentSijilStatus === "review") {
      matchStatus = status === "review" || text.includes("مراجعة") || text.includes("مرفوض") || text.includes("فشل");
    }

    // 3. Search match
    const matchSearch = !q || text.includes(q);

    tr.style.display = (matchDomain && matchStatus && matchSearch) ? "" : "none";
  });
};

window.applySijilDomainFilter = function (domain, btn) {
  window.currentSijilDomain = domain;
  if (btn) {
    const bar = btn.closest(".sijil-filter-toolbar");
    if (bar) bar.querySelectorAll("[id^='sijilDomain']").forEach(c => c.classList.remove("is-active"));
    btn.classList.add("is-active");
  }
  filterSijilTable();
};

window.applySijilStatusFilter = function (status, btn) {
  window.currentSijilStatus = status;
  if (btn) {
    const bar = btn.closest(".sijil-filter-toolbar");
    if (bar) bar.querySelectorAll("[id^='sijilStatus']").forEach(c => c.classList.remove("is-active"));
    btn.classList.add("is-active");
  }
  filterSijilTable();
};

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

let noticeTimer;
function showToast(message, type = "info") {
  const notice = document.getElementById("dashboardNotice");
  notice.dataset.type = type;
  notice.textContent = message;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { notice.textContent = ""; }, type === "error" ? 8000 : 3500);
}

async function downloadAuditReport(path, filename) {
  try {
    const response = await apiFetch(path);
    if (!response.ok) {
      showToast(response.status === 401 ? "أدخل رمز المشغّل في الإعدادات لتنزيل التقرير." : "تعذر إنشاء التقرير.", "error");
      return;
    }
    const href = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = href;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(href), 60000);
  } catch {
    showToast("تعذر تنزيل التقرير. تحقق من الاتصال.", "error");
  }
}

function exportFullSijilPdf() {
  return downloadAuditReport("/api/sijil/report/pdf", "sijil.pdf");
}

function exportSingleOpPdf(ident) {
  if (ident) return downloadAuditReport("/api/sijil/operation/" + encodeURIComponent(ident) + "/pdf", "operation-" + ident + ".pdf");
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

  let tbodyHtml = "<tbody>";
  rows.forEach((row) => {
    let isFocal = false;
    row.forEach((c) => {
      const match = c.match(/([1-9]\d*)\s*(موظف|سجل|عنصر|طلب)/);
      if (match) {
        isFocal = true;
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

  return `<div class="editorial-table-wrapper">
    <table class="editorial-table">${theadHtml}${tbodyHtml}</table>
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

      processedBlocks.push({ table: renderEditorialTable(headers, rows) });
    } else {
      processedBlocks.push(line);
      i++;
    }
  }

  // 3. Format inline markdown for non-table lines
  const intermediate = processedBlocks
    .map((block) => {
      if (typeof block === "object") {
        return block.table;
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

function getTimeStr(timestamp) {
  if (timestamp === null) return "";
  const date = timestamp ? new Date(timestamp) : new Date();
  if (!Number.isFinite(date.valueOf())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Riyadh", hourCycle: "h23", hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(date);
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
  if (raw.includes("مدقق") || raw === "mudaqqiq" || raw.includes("modaqeq"))
    return AGENTS_META.modaqeq;
  if (raw.includes("موفق") || raw === "muwaffaq" || raw.includes("mowafaq"))
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
  return { name_ar: "وكيل المنظومة", color: "var(--color-phosphor-green)" };
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
            <div style="padding: 16px; text-align: center; color: var(--color-smoke); font-size: 12.5px;">
              في انتظار بدء تنفيذ العمليات...
            </div>
          `;
    if (badge) {
      badge.textContent = "جاهز";
      badge.className = "badge badge-neutral";
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

    // Format execution time / duration in ms or s
    let execTimeHtml = "";
    const durMs = evt.duration_ms || evt.execution_time_ms || (evt.metadata && evt.metadata.execution_time_ms);
    if (durMs !== null && durMs !== undefined) {
      const formattedTime = durMs >= 1000 ? `${(durMs / 1000).toFixed(1)} ث` : `${Math.round(durMs)} مللي ثانية`;
      execTimeHtml = `<span class="timeline-duration-badge mono" style="font-size:11px; color:var(--color-sky-blue); background:rgba(56, 189, 248, 0.1); padding:2px 7px; border-radius:4px; font-variant-numeric:tabular-nums; margin-inline-start:4px;" title="المدة الزمنية للخطوة">⏱ ${formattedTime}</span>`;
    }

    const isSuccess = ["success", "completed", "approved", "approval_verified"].includes(statusCls);
    const isFailed = ["failed", "error", "rejected"].includes(statusCls);
    const statusLabel = describeEventStatus(statusCls);
    const statusBadgeClass = isFailed ? "badge-error" : isSuccess ? "badge-success" : "badge-neutral";
    const actionText = describeAgentActivity(evt);

    const fromMeta = evt.from_agent
      ? resolveAgentMeta(evt.from_agent)
      : null;
    const toMeta = evt.to_agent ? resolveAgentMeta(evt.to_agent) : null;
    const routingHtml =
      fromMeta && toMeta && evt.from_agent !== evt.to_agent
        ? `<span class="timeline-route-chip">مسار: ${escapeHtml(fromMeta.name_ar)} ← ${escapeHtml(toMeta.name_ar)}</span>`
        : "";

    div.innerHTML = `
          <div class="timeline-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
            <div class="timeline-header-right" style="display: flex; align-items: center; gap: 7px;">
              <div style="width: 22px; height: 22px; border-radius: 2px; overflow: hidden; border: 1.5px solid ${agentColor}; flex-shrink: 0; background: var(--paper-2);">
                <img src="/images/agent-${evt.agent || 'seraj'}.webp" alt="${meta.name_ar}" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.src='/images/${evt.agent || 'seraj'}.webp';">
              </div>
              <span class="action timeline-action-code" style="font-weight: 600; font-size: 13px; color: var(--color-snow);">${escapeHtml(actionText)}</span>
              ${routingHtml}
            </div>
            <div class="timeline-header-left" style="display: flex; align-items: center; gap: 6px;">
              <span class="mono timeline-seq" style="font-size: 11px;">#${evt.sequence || idx + 1}</span>
              ${execTimeHtml}
              <span class="timestamp timeline-time-mono" title="التوقيت الزمني">${exactTimeStr}</span>
              <span class="status-icon timeline-status-chip ${statusBadgeClass}" style="border-radius: 2px;">
                <span class="timeline-status-dot"></span>
                <span>${statusLabel}</span>
              </span>
            </div>
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
  stopTimelinePolling();
  if (operationId === currentOperationId) {
    startLiveEventPolling(operationId);
    return;
  }
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
              <button type="button" onclick="downloadCatalogTemplate('${escapeHtml(domain.template)}')" class="hr-domain-dl-link" title="تحميل قالب ${escapeHtml(domain.name_ar)} المعتمد">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                <span>تحميل القالب</span>
              </button>
            </div>
          `;
    grid.appendChild(card);
  });
}

window.downloadCatalogTemplate = function (templateKey) {
  const langEl = document.getElementById("catalogTemplateLanguage");
  const incEl = document.getElementById("catalogIncludeExample");
  const companyEl =
    document.getElementById("dedicatedCompanySelect") ||
    document.getElementById("companySelect");
  const lang = langEl ? langEl.value : "bilingual";
  const includeExample = incEl ? incEl.checked : true;
  const companyId = companyEl && companyEl.value ? companyEl.value : "";

  let url = `/api/template/download/${encodeURIComponent(templateKey)}?lang=${encodeURIComponent(lang)}&include_example=${includeExample}`;
  if (companyId) {
    url += `&company_id=${encodeURIComponent(companyId)}`;
  }

  const a = document.createElement("a");
  a.href = url;
  a.setAttribute("download", "");
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  showToast(
    `جاري تنزيل ${templateKey.includes("master") ? "القالب الشامل (Master)" : "قالب الاستيراد"} (${lang === "bilingual" ? "ثنائي اللغة" : lang === "en" ? "الإنجليزية" : "العربية"})…`,
    "success",
  );
};

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
let dedicatedReportFolder = null;
let dedicatedChatId = null;
let dedicatedBusy = false;

function syncDedicatedUploadControls() {
  const company = document.getElementById("dedicatedCompanySelect");
  const button = document.getElementById("startDryRunBtn");
  button.disabled = dedicatedBusy || !dedicatedSelectedFile || !company.value;
  company.disabled = dedicatedBusy;
  document.getElementById("dedicatedFileInput").disabled = dedicatedBusy;
  document.getElementById("dedicatedDropZone").disabled = dedicatedBusy;
  const remove = document.querySelector("#dedicatedFileCard button");
  if (remove) remove.disabled = dedicatedBusy;
}

function resetDedicatedReport(label, message) {
  dedicatedOperationId = null;
  dedicatedReportFolder = null;
  dedicatedChatId = null;
  document.getElementById("dedicatedOpBadge").textContent = label;
  document.getElementById("dedicatedResultsTitle").textContent = message;
  document.getElementById("dedicatedResultsEmpty").style.display = "";
  document.getElementById("dedicatedResultsContent").style.display = "none";
  const feedback = document.getElementById("dedicatedExecutionResult");
  feedback.style.display = "none";
  feedback.replaceChildren();
  document.getElementById("moxenFaenaPanel").style.display = "none";
}

function refreshDedicatedSelection(message) {
  const company = document.getElementById("dedicatedCompanySelect").value;
  const ready = dedicatedSelectedFile && company;
  const title = ready ? "ابدأ الفحص لعرض نتائج الملف"
    : dedicatedSelectedFile ? "اختر المنشأة التي تريد فحص الملف لها"
    : "اختر منشأة وملفًا لبدء الفحص";
  resetDedicatedReport(ready ? "جاهز للفحص" : "بانتظار الاختيار", title);
  document.getElementById("dedicatedUploadStatus").textContent = message || "";
  syncDedicatedUploadControls();
}

function handleDedicatedCompanyChange() {
  if (dedicatedBusy) return;
  refreshDedicatedSelection();
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
  const file = input.files?.[0];
  if (file) processDedicatedFileSelection(file);
  input.value = "";
}

function processDedicatedFileSelection(file) {
  if (dedicatedBusy) return;
  const error = !/\.xlsx$/i.test(file.name) ? "اختر ملف Excel بصيغة .xlsx."
    : !file.size ? "الملف فارغ. اختر ملفًا آخر."
    : file.size > 10 * 1024 * 1024 ? "حجم الملف يتجاوز 10 ميجابايت."
    : "";
  if (error) {
    clearDedicatedFile();
    document.getElementById("dedicatedUploadStatus").textContent = error;
    return;
  }

  dedicatedSelectedFile = file;
  document.getElementById("dedicatedFileName").textContent = file.name;
  document.getElementById("dedicatedFileSize").textContent = `${Math.max(1, Math.round(file.size / 1024))} كيلوبايت`;
  document.getElementById("dedicatedFileCard").style.display = "flex";
  refreshDedicatedSelection();
}

function clearDedicatedFile() {
  if (dedicatedBusy) return;
  dedicatedSelectedFile = null;
  document.getElementById("dedicatedFileInput").value = "";
  document.getElementById("dedicatedFileCard").style.display = "none";
  refreshDedicatedSelection();
}

async function startDedicatedDryRun() {
  const company = document.getElementById("dedicatedCompanySelect");
  const file = dedicatedSelectedFile;
  if (!file || !company.value || dedicatedBusy) return;

  const companyName = company.selectedOptions[0].textContent.trim();
  const status = document.getElementById("dedicatedUploadStatus");
  const chatId = `web_upload_${crypto.randomUUID()}`;
  const formData = new FormData();
  formData.append("file", file);
  formData.append("chat_id", chatId);
  formData.append("company_id", company.value);

  dedicatedBusy = true;
  syncDedicatedUploadControls();
  resetDedicatedReport("جارٍ الفحص", `يجري فحص الملف لمنشأة «${companyName}»`);
  status.textContent = "جارٍ فحص الملف…";

  try {
    const response = await apiFetch("/api/agents/upload", { method: "POST", body: formData });
    const data = await response.json();
    const report = data.dry_run_report;
    if (!response.ok || data.status !== "success" || !data.operation_id || !report?.folder) {
      const detail = typeof data.detail === "string" && /[\u0621-\u064A]/.test(data.detail) ? data.detail : "";
      throw new Error(detail || "تعذّر فحص الملف. تأكد من استخدام قالب Excel صالح ثم أعد المحاولة.");
    }

    dedicatedOperationId = data.operation_id;
    dedicatedReportFolder = report.folder;
    dedicatedChatId = chatId;
    const total = report.total_rows ?? report.summary?.row_count ?? 0;
    const accepted = report.accepted_count ?? report.summary?.status_counts?.accepted ?? 0;
    const rejected = report.rejected_count ?? report.summary?.status_counts?.rejected ?? 0;
    document.getElementById("dedicatedOpBadge").textContent = "اكتمل الفحص";
    document.getElementById("dedicatedResultsEmpty").style.display = "none";
    document.getElementById("dedicatedResultsContent").style.display = "block";
    document.getElementById("dedicatedResultMsg").textContent = total
      ? `نتيجة فحص «${file.name}»`
      : "الملف لا يحتوي على صفوف بيانات للفحص.";
    document.getElementById("dedicatedTemplateDetected").textContent = `${companyName} · ${report.template_title || "ملف Excel"}`;
    document.getElementById("metricTotalRows").textContent = total;
    document.getElementById("metricAcceptedRows").textContent = accepted;
    document.getElementById("metricRejectedRows").textContent = rejected;

    const approve = document.getElementById("dedicatedApproveBtn");
    approve.textContent = "اعتماد وتنفيذ في Odoo";
    approve.style.removeProperty("background");
    approve.style.removeProperty("color");
    approve.disabled = accepted === 0;
    const cancel = document.getElementById("dedicatedCancelBtn");
    cancel.style.display = "";
    cancel.disabled = false;
    status.textContent = "اكتمل الفحص. راجع النتيجة قبل الاعتماد.";

    if (data.operation) {
      currentOperationId = data.operation_id;
      document.getElementById("activeOpIdBadge").textContent = currentOperationId;
      updateOperationBadges(data.operation);
      updateProcessStepper(data.operation.events || [], data.operation);
    }
  } catch (error) {
    const message = /[\u0621-\u064A]/.test(error.message) ? error.message : "تعذّر الاتصال بالخادم. أعد المحاولة.";
    resetDedicatedReport("تعذّر الفحص", message);
    status.textContent = message;
  } finally {
    dedicatedBusy = false;
    syncDedicatedUploadControls();
  }
}

const FAILURE_CODE_MAP_AR = {
  department_not_found: "القسم غير معرف في Odoo",
  job_not_found: "المسمى الوظيفي غير مسجل",
  missing_required_field: "حقول إلزامية مفقودة",
  invalid_email: "صيغة البريد الإلكتروني غير صالحة",
  invalid_date: "صيغة التاريخ غير صحيحة",
  employee_not_found: "الموظف غير مسجل مسبقاً",
  appraisal_unavailable: "استيراد تقييمات الأداء غير متاح في قاعدة Odoo",
  appraisal_year_invalid: "سنة التقييم غير صالحة",
  appraisal_score_invalid: "درجة التقييم غير صالحة",
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

  const reportData = data && data.report ? data.report : data || {};
  const runId =
    reportData.header?.run_id ||
    reportData.run_id ||
    targetIdentifier ||
    "فحص تدقيقي";
  const templateTitle =
    reportData.summary?.template_title ||
    reportData.header?.template_title ||
    reportData.template_title ||
    "بيانات الموارد البشرية";
  const rows = Array.isArray(reportData.rows) ? reportData.rows : [];
  const totalRows =
    reportData.summary?.row_count ??
    reportData.total_rows ??
    rows.length;
  const acceptedCount =
    reportData.summary?.status_counts?.accepted ??
    reportData.status_counts?.accepted ??
    reportData.accepted_count ??
    rows.filter((r) => r.final_status === "accepted").length;
  const rejectedCount =
    reportData.summary?.status_counts?.rejected ??
    reportData.status_counts?.rejected ??
    reportData.rejected_count ??
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
        const name =
          r.display_name ||
          r.fields?.name?.value ||
          r.fields?.emp_name?.value ||
          r.fields?.employee_name?.value ||
          r.fields?.company_name?.value ||
          r.fields?.candidate_name?.value ||
          (r.fields?.emp_id?.value
            ? `موظف #${r.fields.emp_id.value}`
            : "") ||
          "—";
        const jobVal =
          r.fields?.job?.value ||
          r.fields?.job_id?.value ||
          r.fields?.job_title?.value ||
          r.fields?.contract_type?.value ||
          r.fields?.leave_type?.value ||
          r.fields?.tx_type?.value ||
          "";
        const deptVal =
          r.fields?.dept?.value ||
          r.fields?.department?.value ||
          r.fields?.department_id?.value ||
          r.fields?.branch?.value ||
          r.fields?.city?.value ||
          "";
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

  container.innerHTML = kpisHtml + toolbarHtml + tableHtml;
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


}

async function loadExcelRunHistory(details) {
  if (!details.open || details.getAttribute("aria-busy") === "true") return;
  const status = document.getElementById("excelRunHistoryStatus");
  const list = document.getElementById("excelRunHistoryList");
  details.setAttribute("aria-busy", "true");
  status.textContent = "جارٍ تحميل الفحوصات…";
  list.replaceChildren();
  try {
    const response = await apiFetch("/api/runs");
    if (!response.ok) throw new Error();
    const runs = await response.json();
    status.textContent = runs.length ? "" : "لا توجد فحوصات محفوظة.";
    const dateFormat = new Intl.DateTimeFormat("ar-SA-u-ca-gregory", {dateStyle: "medium", timeStyle: "short"});
    for (const run of runs) {
      const row = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-sm btn-secondary";
      const date = dateFormat.format(run.created_at * 1000);
      button.textContent = run.summary?.template_title ? `${run.summary.template_title} · ${date}` : `فحص ${date}`;
      button.addEventListener("click", () => openDedicatedRejectionDrawer(run.folder));
      row.append(button);
      list.append(row);
    }
  } catch {
    status.textContent = "تعذر تحميل سجل الفحوصات. أغلق القائمة وافتحها للمحاولة مجدداً.";
  } finally {
    details.removeAttribute("aria-busy");
  }
}

function openDedicatedRejectionDrawer(targetIdentifier = dedicatedReportFolder) {
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
  if (dedicatedBusy) return;
  if (!dedicatedOperationId || !dedicatedReportFolder) {
    const statusEl = document.getElementById("dedicatedUploadStatus");
    if (statusEl)
      statusEl.innerHTML =
        '<span style="color:var(--color-coral);">يرجى فحص ملف أولاً قبل طلب الاعتماد.</span>';
    return;
  }

  dedicatedBusy = true;
  syncDedicatedUploadControls();
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
        chat_id: dedicatedChatId,
        operation_id: dedicatedOperationId,
        report_folder: dedicatedReportFolder,
        approved_by: "مشغّل النظام",
      }),
    });
    const data = await res.json();

    if (res.ok && data.status === "success") {
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
        const isRecruitment = data.template_type === "recruitment" || respText.includes("التوظيف");
        const showOdooLink = data.template_type !== "appraisal";
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
                  ${showOdooLink ? `<a href="${escapeHtml(odooDirectLink)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary" style="text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    <span>${odooDirectLabel}</span>
                  </a>` : ""}
                  <button type="button" class="btn btn-sm btn-secondary" onclick="openDedicatedRejectionDrawer()">عرض سجل التدقيق التفصيلي</button>
                  <button type="button" class="btn btn-sm btn-ghost" onclick="resumeOperationInCockpit('${escapeHtml(dedicatedOperationId)}')">متابعة العملية في قمرة العمليات</button>
                </div>
              </div>
            `;
      }

      if (data.operation) {
        updateProcessStepper(data.operation.events || [], data.operation);
        updateOperationBadges(data.operation);
      }
    } else {
      const message = data.response || data.detail;
      throw new Error(typeof message === "string" ? message : "تعذّر استكمال الاعتماد في Odoo.");
    }
  } catch (err) {
    if (statusEl) statusEl.textContent = err.message;
    if (approveBtn) {
      approveBtn.disabled = false;
      approveBtn.textContent = "اعتماد وتنفيذ في Odoo";
    }
    if (cancelBtn) cancelBtn.disabled = false;
  } finally {
    dedicatedBusy = false;
    syncDedicatedUploadControls();
  }
}

async function handleDedicatedCancel() {
  if (dedicatedBusy || !dedicatedOperationId || !dedicatedChatId) return;
  dedicatedBusy = true;
  syncDedicatedUploadControls();
  const operationId = dedicatedOperationId;
  const status = document.getElementById("dedicatedUploadStatus");
  const cancel = document.getElementById("dedicatedCancelBtn");
  const approve = document.getElementById("dedicatedApproveBtn");
  const wasApproveDisabled = approve.disabled;
  status.textContent = "جارٍ إلغاء العملية…";
  cancel.disabled = true;
  approve.disabled = true;

  try {
    const response = await apiFetch("/api/agents/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: dedicatedChatId, operation_id: operationId }),
    });
    const data = await response.json();
    if (!response.ok || data.status !== "success") {
      throw new Error(typeof data.detail === "string" ? data.detail : "تعذّر إلغاء العملية.");
    }

    dedicatedBusy = false;
    clearDedicatedFile();
    status.textContent = "أُلغيت العملية.";
    if (data.operation && currentOperationId === operationId) {
      updateOperationBadges(data.operation);
      updateProcessStepper(data.operation.events || [], data.operation);
    }
  } catch (error) {
    status.textContent = error.message;
    cancel.disabled = false;
    approve.disabled = wasApproveDisabled;
  } finally {
    dedicatedBusy = false;
    syncDedicatedUploadControls();
  }
}

async function populateDedicatedCompanySelector() {
  try {
    const res = await apiFetch("/api/status");
    const data = await res.json();
    const sel = document.getElementById("dedicatedCompanySelect");
    if (!sel || dedicatedBusy) return;

    const previous = sel.value;
    if (data.companies && data.companies.length > 0) {
      sel.innerHTML =
        '<option value="">اختر المنشأة...</option>' +
        data.companies
          .map(
            (c) =>
              `<option value="${c.id}" ${String(c.id) === String(previous || selectedCompanyId || "") ? "selected" : ""}>${escapeHtml(c.name)}</option>`,
          )
          .join("");
    }
    if (previous && previous !== sel.value) refreshDedicatedSelection();
    else syncDedicatedUploadControls();
  } catch (e) {
    console.warn("Failed to populate dedicated company selector:", e);
  }
}

// =========================================================================
// 10. MOXEN PILAR: TABLE COLUMN RESIZING WITH LASER GUIDE & LIVE BADGE
// =========================================================================
function initMoxenPilarTable(table) {
  if (!table || table._pilarInitialized || table.closest(".chat-messages, .seraj-bubble, .msg-bubble")) return;
  table._pilarInitialized = true;

  const ths = table.querySelectorAll("thead th");
  if (!ths || ths.length === 0) return;

  let laserGuide = table.parentElement.querySelector(".pi-guia");
  if (!laserGuide) {
    laserGuide = document.createElement("div");
    laserGuide.className = "pi-guia";
    laserGuide.innerHTML = `<span class="pi-medida mono">0px</span>`;
    table.parentElement.style.position = "relative";
    table.parentElement.appendChild(laserGuide);
  }

  const badge = laserGuide.querySelector(".pi-medida");

  ths.forEach((th) => {
    let handle = th.querySelector(".pi-borde");
    if (!handle) {
      handle = document.createElement("div");
      handle.className = "pi-borde";
      handle.style.cssText = "position:absolute; top:0; right:0; bottom:0; width:10px; cursor:col-resize; user-select:none; z-index:10;";
      th.style.position = "relative";
      th.appendChild(handle);
    }

    let startX = 0;
    let startW = 0;

    handle.onmousedown = (e) => {
      e.preventDefault();
      e.stopPropagation();
      startX = e.clientX;
      startW = th.offsetWidth;
      laserGuide.classList.add("is-active");

      const updateGuide = (currX, currW) => {
        const tableRect = table.parentElement.getBoundingClientRect();
        const leftPos = currX - tableRect.left;
        laserGuide.style.left = `${leftPos}px`;
        if (badge) badge.textContent = `${Math.round(currW)}px`;
      };

      updateGuide(e.clientX, startW);

      const onMouseMove = (moveEvt) => {
        const diff = startX - moveEvt.clientX; // RTL: moving left increases width
        const newW = Math.max(70, startW + diff);
        th.style.width = `${newW}px`;
        th.style.minWidth = `${newW}px`;
        updateGuide(moveEvt.clientX, newW);
      };

      const onMouseUp = () => {
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
        laserGuide.classList.remove("is-active");
      };

      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    };

    // Double click for auto-fit spring
    handle.ondblclick = (e) => {
      e.preventDefault();
      th.style.width = "auto";
      th.style.minWidth = "auto";
      showToast("تمت ملاءمة عرض العمود تلقائياً", "info");
    };
  });
}

// Initialize on operations log table
setTimeout(() => {
  const opsTable = document.querySelector("#operationsLogTable table, #auditTable");
  if (opsTable) initMoxenPilarTable(opsTable);
}, 1500);

// =========================================================================
// 11. AGENT MEMORY CENTER (SQLITE BACKEND)
// =========================================================================
let memoryEpisodesCache = [];
let memoryEpisodesTotal = 0;
let memoryEpisodesSearchTimer = null;

window.switchMemoryInlineTab = function (tab) {
  const tabFacts = document.getElementById("memInlineTabBtnFacts");
  const tabEpisodes = document.getElementById("memInlineTabBtnEpisodes");
  const tabEntities = document.getElementById("memInlineTabBtnEntities");

  const panelFacts = document.getElementById("memInlinePanelFacts");
  const panelEpisodes = document.getElementById("memInlinePanelEpisodes");
  const panelEntities = document.getElementById("memInlinePanelEntities");

  [tabFacts, tabEpisodes, tabEntities].forEach(b => {
    if (b) b.setAttribute("aria-pressed", "false");
  });
  [panelFacts, panelEpisodes, panelEntities].forEach(p => {
    if (p) p.style.display = "none";
  });

  if (tab === "facts") {
    if (tabFacts) tabFacts.setAttribute("aria-pressed", "true");
    if (panelFacts) panelFacts.style.display = "block";
  } else if (tab === "episodes") {
    if (tabEpisodes) tabEpisodes.setAttribute("aria-pressed", "true");
    if (panelEpisodes) panelEpisodes.style.display = "block";
    if (memoryEpisodesCache.length === 0) loadMemoryEpisodes();
  } else if (tab === "entities") {
    if (tabEntities) tabEntities.setAttribute("aria-pressed", "true");
    if (panelEntities) panelEntities.style.display = "block";
  }
};

window.loadMemoryData = async function (forceReload = false) {
  try {
    const [itemsRes, episodesRes] = await Promise.all([
      apiFetch("/api/memory/items"),
      apiFetch("/api/memory/episodes?limit=50&offset=0")
    ]);
    const itemsData = await itemsRes.json();
    const epData = await episodesRes.json();

    if (itemsData.status === "success") {
      const facts = itemsData.facts || [];
      const entities = itemsData.active_entities_by_session || {};
      const stats = itemsData.stats || {};
      if (epData.status === "success") {
        stats.episodes = epData.total || stats.episodes || 0;
        memoryEpisodesCache = epData.items || [];
        memoryEpisodesTotal = epData.total || 0;
      }
      renderMemoryQuickStats(stats);
      renderMemoryFacts(facts);
      renderMemoryActiveEntities(entities);
      renderMemoryEpisodes(memoryEpisodesCache, memoryEpisodesTotal);

      const badgeFacts = document.getElementById("memInlineFactsCountBadge");
      const badgeEpisodes = document.getElementById("memInlineEpisodesCountBadge");
      const badgeSessions = document.getElementById("memInlineSessionsCountBadge");
      if (badgeFacts) badgeFacts.textContent = facts.length;
      if (badgeEpisodes) badgeEpisodes.textContent = memoryEpisodesTotal;
      if (badgeSessions) badgeSessions.textContent = Object.keys(entities).length;
    }
  } catch (err) {
    console.warn("Failed to load memory data:", err);
  }
};

window.loadCostTelemetry = async function () {
  const values = ["telemetryReqCount", "telemetryTokenCount", "telemetryCostUsd", "telemetryAvgLatency"]
    .map(id => document.getElementById(id));
  const breakdown = document.getElementById("costTelemetryBreakdown");
  const note = document.getElementById("costTelemetryNote");
  if (!breakdown) return;
  const number = new Intl.NumberFormat("ar-SA");
  const dollars = new Intl.NumberFormat("en-US", {style: "currency", currency: "USD", maximumFractionDigits: 8});
  const format = (value, formatter) => value == null ? "—" : formatter.format(value);
  try {
    const response = await apiFetch("/api/telemetry/cost");
    const data = await response.json();
    if (!response.ok || data.status !== "success") throw new Error("تعذر تحميل قياسات الاستهلاك.");
    const metrics = [
      format(data.total_requests, number),
      format(data.total_tokens, number),
      format(data.total_cost_usd, dollars),
      data.avg_latency_ms == null ? "—" : `${number.format(Math.round(data.avg_latency_ms))} مللي ثانية`,
    ];
    values.forEach((element, index) => { if (element) element.textContent = metrics[index]; });
    const names = {ollama: "Ollama المحلي", openai: "OpenAI", openrouter: "OpenRouter", gemini: "Gemini", groq: "Groq", deepseek: "DeepSeek", custom: "مزود سحابي مخصص"};
    breakdown.innerHTML = Object.entries(data.by_provider || {}).map(([provider, usage]) => `
      <div class="telemetry-provider-row">
        <strong>${escapeHtml(names[provider] || provider)} · ${number.format(usage.count)} استجابة</strong>
        <span>التوكنات ${format(usage.tokens, number)} · التكلفة <bdi>${format(usage.cost_usd, dollars)}</bdi></span>
      </div>`).join("") || "لا توجد استجابات نموذج مقاسة بعد.";
    note.textContent = `أرسل المزود بيانات التوكنات لـ ${number.format(data.usage_reported_requests)} من ${number.format(data.total_requests)} استجابة. إجمالي التكلفة السحابية يظهر عند توفر تكلفة جميع الاستجابات السحابية.`;
  } catch (err) {
    values.forEach(element => { if (element) element.textContent = "—"; });
    note.textContent = "";
    breakdown.textContent = "تعذر تحميل قياسات الاستهلاك.";
  }
};

async function loadMemoryEpisodes(q = "") {
  const epListContainer = document.getElementById("memInlineEpisodesList");
  if (epListContainer) {
    epListContainer.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--color-silver-mist);">جاري جلب حلقات الذاكرة من SQLite...</div>`;
  }
  try {
    const url = q ? `/api/memory/episodes?limit=50&offset=0&q=${encodeURIComponent(q)}` : `/api/memory/episodes?limit=50&offset=0`;
    const res = await apiFetch(url);
    const data = await res.json();
    if (data.status === "success") {
      memoryEpisodesCache = data.items || [];
      memoryEpisodesTotal = data.total || 0;
      renderMemoryEpisodes(memoryEpisodesCache, memoryEpisodesTotal);
    }
  } catch (e) {
    console.warn("Error fetching episodes:", e);
  }
}

window.handleEpisodeSearch = function (query) {
  clearTimeout(memoryEpisodesSearchTimer);
  memoryEpisodesSearchTimer = setTimeout(() => {
    loadMemoryEpisodes(query);
  }, 300);
};

function renderMemoryQuickStats(stats) {
  const container = document.getElementById("memoryQuickStats");
  if (!container) return;
  container.innerHTML = `
          <div class="settings-stat-box">
            <div class="settings-stat-lbl">الحقائق الدائمة (SQLite)</div>
            <div class="settings-stat-num">${stats.long_term_facts || 0}</div>
            <div style="font-size: 11px; color: var(--muted); margin-top: 4px;">قواعد وسياسات نظام العمل</div>
          </div>
          <div class="settings-stat-box">
            <div class="settings-stat-lbl">سجل الحلقات (Episodes)</div>
            <div class="settings-stat-num">${stats.episodes || 0}</div>
            <div style="font-size: 11px; color: var(--muted); margin-top: 4px;">تفاعلات الوكلاء الموثقة</div>
          </div>
          <div class="settings-stat-box">
            <div class="settings-stat-lbl">الذاكرة النشطة للجلسات</div>
            <div class="settings-stat-num" style="color: var(--ok);">${stats.working_memories || 0}</div>
            <div style="font-size: 11px; color: var(--muted); margin-top: 4px;">الكيانات المحقونة بالسياق</div>
          </div>
          <div class="settings-stat-box">
            <div class="settings-stat-lbl">محرك التخزين</div>
            <div class="settings-stat-num mono" style="font-size: 15px;">memory.db</div>
            <div style="font-size: 11px; color: var(--muted); margin-top: 4px;">SQLite + JSON Mirror</div>
          </div>
        `;
}

function renderMemoryFacts(facts) {
  const inlineContainer = document.getElementById("memInlineFactsList");

  if (facts.length === 0) {
    const emptyHtml = `<div style="text-align: center; padding: 24px; color: var(--color-silver-mist); font-size: 13px;">لا توجد قواعد محفوظة.</div>`;
    if (inlineContainer) inlineContainer.innerHTML = emptyHtml;
    return;
  }

  const categoryLabels = {
    "نظام العمل": "نظام العمل واللوائح",
    "الحوكمة والأمان": "الحوكمة وضوابط الاعتماد",
    "التأمينات الاجتماعية": "التأمينات الاجتماعية GOSI",
    "سياسة المنشأة": "سياسات وإجراءات المنشأة",
    "قواعد Odoo": "قواعد بيانات Odoo ERP",
    general: "عام",
  };

  const html = facts.map(f => `
          <div class="mem-fact-card" style="background: var(--paper-1); border: 1px solid var(--border-color, var(--rule-strong)); border-radius: 2px; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="badge badge-info" style="font-size: 11px;">${escapeHtml(categoryLabels[f.category] || f.category || "عام")}</span>
                <span style="font-weight: 600; font-size: 13.5px; color: var(--ink);">${escapeHtml(f.key || "قاعدة")}</span>
              </div>
              <div style="display: flex; align-items: center; gap: 6px;">
                <span class="badge badge-neutral" style="font-size: 10.5px; font-variant-numeric: tabular-nums;" title="الأهمية ${f.importance}/5">مستوى ${f.importance || 3}/5</span>
                <button type="button" class="btn btn-xs btn-secondary" onclick="editMemoryFactInline('${f.id}')" style="font-size: 11px; padding: 3px 8px;">تعديل</button>
                <button type="button" class="btn btn-xs btn-secondary" onclick="deleteMemoryFact('${f.id}')" style="font-size: 11px; padding: 3px 8px; color: var(--bad, #dc3838);">حذف</button>
              </div>
            </div>
            <div style="font-size: 13px; color: var(--ink-2); line-height: 1.6;">${escapeHtml(f.content)}</div>
            <div style="font-size: 11px; color: var(--muted); font-family: var(--font-mono); margin-top: 2px;">المعرف: ${f.id} · تاريخ التحديث: ${(f.updated_at || f.created_at || '').substring(0, 16).replace('T', ' ')}</div>
          </div>
        `).join('');

  if (inlineContainer) inlineContainer.innerHTML = html;
}

function renderMemoryEpisodes(episodes, total) {
  const container = document.getElementById("memInlineEpisodesList");
  const pagInfo = document.getElementById("memInlineEpisodesPaginationInfo");
  if (pagInfo) pagInfo.textContent = `عرض ${episodes.length} من أصل ${total} حلقة في SQLite`;
  if (!container) return;

  if (episodes.length === 0) {
    container.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--color-silver-mist); font-size: 13px;">لا توجد حلقات ذاكرة مسجلة مطابقة للبحث.</div>`;
    return;
  }

  container.innerHTML = `
          <table class="data-table" style="width: 100%; font-size: 12.5px;">
            <thead>
              <tr>
                <th style="width: 140px;">معرف الحلقة</th>
                <th style="width: 100px;">الوكيل</th>
                <th>استفسار المستخدم / العملية</th>
                <th>نتيجة الفحص والرد</th>
                <th style="width: 80px;">الحالة</th>
                <th style="width: 110px;">التوقيت</th>
              </tr>
            </thead>
            <tbody>
              ${episodes.map(ep => `
                <tr>
                  <td style="font-family: var(--font-mono); font-size: 11px; color: var(--ink);">${escapeHtml(ep.episode_id)}</td>
                  <td><span class="badge badge-neutral" style="font-size: 10.5px;">${escapeHtml(ep.agent || 'seraj')}</span></td>
                  <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(ep.user_query || '')}">
                    ${escapeHtml(ep.user_query || '—')}
                  </td>
                  <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(ep.result_summary || '')}">
                    ${escapeHtml(ep.result_summary || '—')}
                  </td>
                  <td>
                    <span class="badge ${ep.success ? 'badge-success' : 'badge-danger'}" style="font-size: 10.5px;">
                      ${ep.success ? 'ناجحة' : 'تعثرت'}
                    </span>
                  </td>
                  <td style="font-family: var(--font-mono); font-size: 11px; color: var(--muted);">${(ep.created_at || '').substring(0, 16).replace('T', ' ')}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
}

function renderMemoryActiveEntities(entitiesBySession) {
  const inlineContainer = document.getElementById("memInlineEntitiesList");
  const keys = Object.keys(entitiesBySession);

  if (keys.length === 0) {
    const emptyHtml = `<div style="text-align: center; padding: 24px; color: var(--color-silver-mist); font-size: 13px;">لا توجد بيانات مرتبطة بالجلسات الحالية.</div>`;
    if (inlineContainer) inlineContainer.innerHTML = emptyHtml;
    return;
  }

  const html = keys.map(k => {
    const item = entitiesBySession[k];
    const ents = item.entities || {};
    return `
            <div style="background: var(--paper-1); border: 1px solid var(--border-color, var(--rule-strong)); border-radius: 2px; padding: 12px 14px;">
              <div style="font-size: 13px; font-weight: 600; color: var(--ink); margin-bottom: 6px;">
                الجلسة: ${escapeHtml(item.title || k)}
              </div>
              <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 6px;">
                ${ents.employee_name ? `<span class="badge badge-info">الموظف: ${escapeHtml(ents.employee_name)} (ID: ${ents.employee_id || '-'})</span>` : ''}
                ${ents.department_name ? `<span class="badge badge-secondary">القسم: ${escapeHtml(ents.department_name)}</span>` : ''}
                ${ents.job_title ? `<span class="badge badge-secondary">المسمى: ${escapeHtml(ents.job_title)}</span>` : ''}
                ${ents.company_name ? `<span class="badge badge-secondary">الشركة: ${escapeHtml(ents.company_name)}</span>` : ''}
              </div>
              <div style="font-size: 12px; color: var(--ink-2);">الملخص المحقون: ${escapeHtml(item.summary || 'سياق قياسي')}</div>
            </div>
          `;
  }).join('');

  if (inlineContainer) inlineContainer.innerHTML = html;
}

window.submitMemoryFactInline = async function (e) {
  if (e) e.preventDefault();
  const factId = document.getElementById("memInlineFactId").value;
  const content = document.getElementById("memInlineFactContent").value.trim();
  const category = document.getElementById("memInlineFactCategory").value;
  const importance = parseInt(document.getElementById("memInlineFactImportance").value) || 3;
  const submitBtn = document.getElementById("memInlineSubmitBtn");

  if (!content) return;
  if (submitBtn) submitBtn.disabled = true;

  try {
    if (factId) {
      await apiFetch(`/api/memory/items/${factId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category, importance, content }),
      });
      showToast("تم تحديث الحقيقة في ذاكرة SQLite بنجاح", "success");
    } else {
      await apiFetch("/api/memory/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category, importance, content }),
      });
      showToast("تم إضافة الحقيقة لقاعدة بيانات الذاكرة بنجاح", "success");
    }
    cancelEditMemoryFactInline();
    await loadMemoryData(true);
  } catch (err) {
    showToast("تعذر حفظ عنصر الذاكرة: " + err.message, "error");
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
};

window.editMemoryFactInline = async function (id) {
  try {
    const res = await apiFetch("/api/memory/items");
    const data = await res.json();
    const fact = (data.facts || []).find(f => f.id === id);
    if (!fact) return;

    document.getElementById("memInlineFactId").value = fact.id;
    document.getElementById("memInlineFactContent").value = fact.content || "";
    document.getElementById("memInlineFactCategory").value = fact.category || "general";
    document.getElementById("memInlineFactImportance").value = fact.importance || 3;

    const formTitle = document.getElementById("memInlineFormTitle");
    const cancelBtn = document.getElementById("memInlineCancelBtn");
    const submitBtn = document.getElementById("memInlineSubmitBtn");
    if (formTitle) formTitle.textContent = `تعديل القاعدة: ${fact.id}`;
    if (cancelBtn) cancelBtn.style.display = "inline-block";
    if (submitBtn) submitBtn.textContent = "تحديث القاعدة";

    const contentInput = document.getElementById("memInlineFactContent");
    if (contentInput) {
      contentInput.focus();
      contentInput.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  } catch (err) {
    console.warn("Could not edit fact inline", err);
  }
};

window.cancelEditMemoryFactInline = function () {
  document.getElementById("memInlineFactId").value = "";
  document.getElementById("memInlineFactContent").value = "";
  const formTitle = document.getElementById("memInlineFormTitle");
  const cancelBtn = document.getElementById("memInlineCancelBtn");
  const submitBtn = document.getElementById("memInlineSubmitBtn");
  if (formTitle) formTitle.textContent = "+ إضافة قاعدة دائمة جديدة إلى ذاكرة الوكلاء";
  if (cancelBtn) cancelBtn.style.display = "none";
  if (submitBtn) submitBtn.textContent = "حفظ للذاكرة";
};

window.deleteMemoryFact = async function (id) {
  if (!confirm("هل أنت متأكد من حذف هذه المعلومة من ذاكرة سراج وقاعدة بيانات SQLite؟")) return;
  try {
    await apiFetch(`/api/memory/items/${id}`, { method: "DELETE" });
    await loadMemoryData(true);
    showToast("تم حذف الحقيقة بنجاح من الذاكرة", "info");
  } catch (err) {
    showToast("تعذر الحذف: " + err.message, "error");
  }
};

window.clearAllMemoryFacts = async function () {
  if (!confirm("تحذير: هل أنت متأكد من مسح كافة الحقائق المحفوظة في ذاكرة SQLite؟")) return;
  try {
    await apiFetch("/api/memory/clear", { method: "DELETE" });
    await loadMemoryData(true);
    showToast("تم مسح ذاكرة الحقائق بنجاح", "info");
  } catch (err) {
    showToast("تعذر المسح: " + err.message, "error");
  }
};

// =========================================================================
// 12. MOXEN PILAR: TABLES COLUMN RESIZING & DENSITY SWITCHING
// =========================================================================
window.initMoxenPilar = function () {
  ["operationsTable", "sijilTable", "approvalDiffTable"].forEach(tableId => {
    const table = document.getElementById(tableId);
    if (!table) return;
    const guia = document.getElementById(`${tableId}Guia`);
    const wrap = table.closest(".operations-table-wrap") || table.parentElement;

    const ths = table.querySelectorAll("thead th");
    ths.forEach((th, idx) => {
      let handle = th.querySelector(".pi-borde");
      if (!handle) {
        handle = document.createElement("span");
        handle.className = "pi-borde";
        handle.title = "اسحب لتعديل العرض / نقر مزدوج للملاءمة";
        th.appendChild(handle);
      }

      // Double click: spring auto-fit
      handle.addEventListener("dblclick", (e) => {
        e.stopPropagation();
        autoFitMoxenColumn(th, table);
      });

      // Drag resize with laser guide line
      handle.addEventListener("mousedown", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const startX = e.pageX;
        const startWidth = th.offsetWidth;
        const tableRect = table.getBoundingClientRect();

        if (guia) {
          guia.classList.add("is-active");
          const medida = guia.querySelector(".pi-medida");
          if (medida) medida.textContent = `${startWidth}px`;
        }

        function onMouseMove(moveEvent) {
          const diff = (document.dir === "rtl") ? (startX - moveEvent.pageX) : (moveEvent.pageX - startX);
          const newWidth = Math.max(70, Math.min(600, startWidth + diff));
          th.style.width = `${newWidth}px`;
          th.style.minWidth = `${newWidth}px`;

          if (guia) {
            const thRect = th.getBoundingClientRect();
            const offsetRight = (document.dir === "rtl") ? (tableRect.right - thRect.left) : (thRect.right - tableRect.left);
            guia.style.transform = `translateX(${offsetRight * ((document.dir === "rtl") ? -1 : 1)}px)`;
            const medida = guia.querySelector(".pi-medida");
            if (medida) medida.textContent = `${newWidth}px`;
          }
        }

        function onMouseUp() {
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", onMouseUp);
          if (guia) guia.classList.remove("is-active");
        }

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
      });
    });
  });
};

function autoFitMoxenColumn(th, table) {
  const text = th.textContent.trim();
  const fontWidthEstimate = Math.max(90, text.length * 13 + 36);
  th.style.width = `${fontWidthEstimate}px`;
  th.style.minWidth = `${fontWidthEstimate}px`;
}

window.setMoxenTableDensity = function (tableId, density, btn) {
  const table = document.getElementById(tableId);
  if (!table) return;
  table.classList.remove("density-comoda", "density-normal", "density-compacta");
  table.classList.add(`density-${density}`);

  const rowHeight = density === "comoda" ? "54px" : density === "compacta" ? "32px" : "42px";
  const padding = density === "comoda" ? "14px 16px" : density === "compacta" ? "6px 10px" : "10px 14px";
  const ths = table.querySelectorAll("th, td");
  ths.forEach(cell => {
    cell.style.padding = padding;
  });

  if (btn) {
    const group = btn.parentElement.querySelectorAll(".pi-densidad-btn");
    group.forEach(b => b.classList.remove("is-active"));
    btn.classList.add("is-active");
  }
};

window.resetMoxenTableColumns = function (tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const ths = table.querySelectorAll("thead th");
  ths.forEach(th => {
    th.style.width = "";
    th.style.minWidth = "";
  });
  showToast("تمت استعادة أبعاد الأعمدة الافتراضية بنجاح", "info");
};

// =========================================================================
// 13. MOXEN MIRADOR: SEARCH, SAVED VIEWS & CASSETTE REWIND
// =========================================================================
let currentOpsFilter = "all";
let currentOpsSearch = "";

function filterOperationsTable() {
  opsPage = 1;
  loadOperationsList();
}

window.applyMoxenMiradorView = function (viewType, btn) {
  currentOpsFilter = viewType;
  const bar = btn ? btn.closest(".moxen-mirador-bar") : null;
  if (bar) {
    bar.querySelectorAll(".mi-chip").forEach(c => c.classList.remove("is-active"));
    btn.classList.add("is-active");
  }
  filterOperationsTable();
};

window.handleOpsSearch = function (query) {
  currentOpsSearch = query;
  filterOperationsTable();
};

window.resetMoxenMiradorFilters = function (btn) {
  currentOpsFilter = "all";
  currentOpsSearch = "";
  const searchInput = document.getElementById("opsSearchInput");
  if (searchInput) searchInput.value = "";
  const allBtn = document.getElementById("miViewAllOps");
  if (allBtn) {
    const bar = allBtn.closest(".moxen-mirador-bar");
    if (bar) bar.querySelectorAll(".mi-chip").forEach(c => c.classList.remove("is-active"));
    allBtn.classList.add("is-active");
  }
  const cinta = btn ? btn.querySelector(".mi-cinta") : null;
  if (cinta) {
    cinta.classList.add("es-rebobina");
    setTimeout(() => { cinta.classList.remove("es-rebobina"); }, 450);
  }
  filterOperationsTable();
  showToast("تمت استعادة العرض الافتراضي لكافة العمليات", "info");
};

// Init on document ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    setTimeout(window.initMoxenPilar, 400);
  });
} else {
  setTimeout(window.initMoxenPilar, 400);
}
