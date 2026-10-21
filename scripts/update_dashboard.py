# -*- coding: utf-8 -*-
"""Comprehensive updater for dashboard.html"""

import sys
from pathlib import Path

path = Path("templates/dashboard.html")
html = path.read_text(encoding="utf-8")

# Extract everything before <script>
script_start = html.find("  <!-- ==================== LOGIC & REAL-TIME STATE ENGINE ==================== -->")
if script_start == -1:
    script_start = html.find("<script>")
assert script_start != -1

html_before_script = html[:script_start]

new_script = """  <!-- ==================== LOGIC & REAL-TIME STATE ENGINE ==================== -->
  <script>
    // =========================================================================
    // 1. AUTHENTICATION & SECURE API FETCH
    // =========================================================================
    function getApiToken() {
      const meta = document.querySelector('meta[name="api-token"]');
      return meta ? meta.getAttribute('content') : (window.ODDO_API_TOKEN || "");
    }

    async function apiFetch(url, options = {}) {
      const token = getApiToken();
      options.headers = options.headers || {};
      if (token) {
        if (options.headers instanceof Headers) {
          if (!options.headers.has("X-API-Key")) options.headers.set("X-API-Key", token);
        } else {
          if (!options.headers["X-API-Key"]) options.headers["X-API-Key"] = token;
        }
      }
      return fetch(url, options);
    }

    // =========================================================================
    // 2. GLOBAL STATE
    // =========================================================================
    let currentOperationId = null;
    let lastEventSequence = 0;
    let pollingInterval = null;
    let selectedCompanyId = 15;
    let activeAgentsData = [];
    let streamConsecutiveErrors = 0;

    // Sijil Server-Side Pagination State
    let sijilPage = 1;
    let sijilLimit = 10;
    let sijilTotal = 0;

    const AGENTS_META = {
      seraj: { name_ar: "سراج", color: "var(--agent-seraj)", role: "المنسق والمحاور ومتابع المهام", icon: "sparkles" },
      fahas: { name_ar: "فاحص", color: "var(--agent-fahas)", role: "القراءة والتحقق من بيانات Odoo", icon: "search" },
      modaqeq: { name_ar: "مدقق", color: "var(--agent-modaqeq)", role: "التحقق من البيانات والقواعد", icon: "shield-check" },
      mowafaq: { name_ar: "موفق", color: "var(--agent-mowafaq)", role: "المطابقة عند الحاجة", icon: "git-merge" },
      hares: { name_ar: "حارس", color: "var(--agent-hares)", role: "الصلاحيات والسياسات والاعتماد", icon: "lock" },
      musleh: { name_ar: "مصلح", color: "var(--agent-musleh)", role: "التشخيص والمعالجة ضمن الحدود", icon: "wrench" },
      katib: { name_ar: "كاتب", color: "var(--agent-katib)", role: "تنفيذ العملية المعتمدة في Odoo", icon: "pencil" },
      sijil: { name_ar: "سجل", color: "var(--agent-sijil)", role: "توثيق الأحداث والنتائج وإصدار PDF", icon: "book-open" },
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
      inconclusive: "النتيجة غير محسومة",
      disconnected: "انقطع اتصال متابعة الأحداث"
    };

    // =========================================================================
    // 3. INITIALIZATION
    // =========================================================================
    document.addEventListener("DOMContentLoaded", () => {
      renderAgentsStrip();
      loadSystemStatus();
      loadAgentsOverview();
      loadRecentAuditMetrics();
      loadOperationsList();
      checkSavedMotionPreference();

      const ta = document.getElementById('chatInput');
      if (ta) ta.addEventListener('input', () => autoResizeTextarea(ta));
    });

    // View Switching
    function switchView(viewId) {
      document.querySelectorAll(".view-section").forEach(el => el.classList.remove("is-visible"));
      document.querySelectorAll(".nav-tab-btn").forEach(el => el.classList.remove("is-active"));

      const target = document.getElementById(viewId);
      if (target) target.classList.add("is-visible");

      const btn = document.querySelector(`.nav-tab-btn[data-view="${viewId}"]`);
      if (btn) btn.classList.add("is-active");

      if (viewId === "view-operations") loadOperationsList();
      if (viewId === "view-sijil") loadRecentAuditMetrics();
      if (viewId === "view-settings") loadSystemStatus();
    }

    // =========================================================================
    // 4. SYSTEM STATUS & CONNECTION (LIVE SOURCE)
    // =========================================================================
    async function loadSystemStatus() {
      try {
        const res = await apiFetch("/api/status");
        const data = await res.json();
        if (data.status === "online" || data.status === "success") {
          const connEl = document.getElementById("connectionScopePillText");
          if (connEl) {
            connEl.textContent = data.connection_name || (data.odoo?.database ? `odoo (${data.odoo.database})` : "default");
          }

          const compSelect = document.getElementById("companySelector");
          if (compSelect && data.companies && data.companies.length > 0) {
            compSelect.innerHTML = data.companies.map(c => `
              <option value="${c.id}" ${c.selected || c.id === selectedCompanyId ? 'selected' : ''}>
                ${escapeHtml(c.name)}
              </option>
            `).join("");
            if (data.selected_company_id) {
              selectedCompanyId = data.selected_company_id;
            }
          }

          const settingsBox = document.getElementById("systemSettingsInfoBox");
          if (settingsBox) {
            settingsBox.innerHTML = `
              • وضع التشغيل: <span class="badge badge-success">${escapeHtml(data.mode || 'test_safe (آمن ومحمي)')}</span><br>
              • خادم Odoo: <span class="mono">${escapeHtml(data.odoo?.url || 'متصل')} (${escapeHtml(data.odoo?.database || 'hr_db')})</span><br>
              • مفتاح التعديل في أودو: <span class="mono">Write Gateway Guard Active</span><br>
              • الفحص الرقابي المستقل: <span class="badge badge-success">Readback Active (فاحص)</span><br>
              • دفتر السجلات اللاتراجعي: <span class="badge badge-success">Append-Only Active (سجل)</span>
            `;
          }
        }
      } catch (err) {
        console.warn("System status error:", err);
      }
    }

    function handleCompanyChange(newCompanyId) {
      if (currentOperationId) {
        const confirmChange = confirm(
          "⚠️ تنبيه حوكمة:\\nتوجد عملية جارية حالياً برقم (" + currentOperationId + ").\\n" +
          "تغيير الشركة الآن لن يغير نطاق العملية الجارية بصمت.\\n" +
          "هل ترغب بتغيير نطاق العمليات الجديدة فقط؟"
        );
        if (!confirmChange) {
          document.getElementById("companySelector").value = selectedCompanyId;
          return;
        }
      }
      selectedCompanyId = parseInt(newCompanyId, 10);
    }

    // =========================================================================
    // 5. AGENTS STRIP & CHARACTERS (PROPER TERMINATION)
    // =========================================================================
    function resetAllAgentsToIdle() {
      document.querySelectorAll(".agent-character-card").forEach(c => {
        c.classList.remove("is-active");
      });
      document.querySelectorAll("[id^='agentStatusBubble_']").forEach(b => {
        b.textContent = "جاهز";
      });
    }

    function renderAgentsStrip() {
      const container = document.getElementById("agentsStrip");
      if (!container) return;
      container.innerHTML = "";

      Object.entries(AGENTS_META).forEach(([key, meta]) => {
        const card = document.createElement("div");
        card.className = "agent-character-card";
        card.id = `agentCard_${key}`;
        card.style.setProperty("--agent-color", meta.color);
        card.onclick = () => openAgentDetails(key);

        card.innerHTML = `
          <div class="agent-avatar-wrap">
            ${getAgentSvg(meta.icon)}
          </div>
          <div class="agent-name">${meta.name_ar} ${meta.is_helper ? '<span style="font-size: 9px; color: var(--color-silver-mist); font-weight: normal;">(أداة)</span>' : ''}</div>
          <div class="agent-role-short">${meta.role}</div>
          <div class="agent-status-bubble" id="agentStatusBubble_${key}">جاهز</div>
        `;
        container.appendChild(card);
      });
    }

    function getAgentSvg(iconName) {
      switch(iconName) {
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
      agents.forEach(a => {
        const bubble = document.getElementById(`agentStatusBubble_${a.id}`);
        const card = document.getElementById(`agentCard_${a.id}`);
        if (bubble) bubble.textContent = a.status_label || STATUS_MAP_AR[a.status_code] || "جاهز";
        if (card) {
          if (a.status_code !== "ready" && a.status_code !== "completed" && a.status_code !== "failed") {
            card.classList.add("is-active");
          } else {
            card.classList.remove("is-active");
          }
        }
      });
    }

    function renderAgentsFullGrid(agents) {
      const grid = document.getElementById("agentsFullGrid");
      if (!grid) return;
      grid.innerHTML = "";

      agents.forEach(a => {
        const meta = AGENTS_META[a.id] || { color: "var(--color-phosphor-green)", icon: "sparkles" };
        const card = document.createElement("div");
        card.className = "agent-full-card";
        card.onclick = () => openAgentDetails(a.id);
        card.style.cursor = "pointer";
        card.innerHTML = `
          <div class="agent-full-card-header">
            <div class="agent-avatar-wrap" style="border-color: ${meta.color}; width: 48px; height: 48px;">
              ${getAgentSvg(meta.icon)}
            </div>
            <div>
              <div style="font-size: 16px; font-weight: 700; color: var(--color-snow);">${a.name_ar}</div>
              <div style="font-size: 11px; color: var(--color-silver-mist);">${a.title_ar || meta.role}</div>
            </div>
            <span class="badge ${a.status_code === 'ready' ? 'badge-neutral' : 'badge-success'}" style="margin-right: auto;">
              ${a.status_label || STATUS_MAP_AR[a.status_code] || "جاهز"}
            </span>
          </div>
          <div style="font-size: 12.5px; color: var(--color-silver-mist); line-height: 1.5;">${a.description_short || meta.role}</div>
          <div style="font-size: 11.5px; background: #181818; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--color-charcoal);">
            <span style="color: var(--color-smoke);">آخر مهمة:</span>
            <span style="color: var(--color-snow); font-weight: 500;"> ${escapeHtml(a.last_task || "في انتظار المهام")}</span>
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

    async function handleChatSubmit(e) {
      if (e) e.preventDefault();
      const input = document.getElementById("chatInput");
      const text = input.value.trim();
      if (!text) return;

      input.value = "";
      autoResizeTextarea(input);
      appendUserMessage(text);
      showTypingIndicator();
      setSerajBusy("سراج يعالج الطلب…");

      try {
        const payload = {
          message: text,
          chat_id: "web_cockpit_user",
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
          document.getElementById("activeOpIdBadge").textContent = currentOperationId;

          appendSerajMessage(data.response, data.pending_action, data.pending_clarification, data.operation);
          if (data.operation) {
            updateProcessStepper(data.operation.events || []);
            updateOperationBadges(data.operation);
          }
          startLiveEventPolling(currentOperationId);
        } else {
          appendSerajMessage("⚠️ عذراً، واجه سراج صعوبة في معالجة طلبك: " + (data.detail || "خطأ غير معروف"));
        }
      } catch (err) {
        appendSerajMessage("❌ تعذر الاتصال بخادم المنظومة: " + err.message);
      } finally {
        hideTypingIndicator();
        setSerajIdle();
        loadAgentsOverview();
      }
    }

    async function handleApprovePlan() {
      if (!currentOperationId) return;
      appendUserMessage("تأكيد");
      showTypingIndicator();
      setSerajBusy("جاري تنفيذ العملية المعتمدة عبر «كاتب»…");

      try {
        const res = await apiFetch("/api/agents/approve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id: "web_cockpit_user", operation_id: currentOperationId }),
        });
        const data = await res.json();
        appendSerajMessage(data.response, null, null, data.operation);
        if (data.operation) {
          updateProcessStepper(data.operation.events || []);
          updateOperationBadges(data.operation);
        }
      } catch (err) {
        appendSerajMessage("❌ تعذر إتمام الاعتماد: " + err.message);
      } finally {
        hideTypingIndicator();
        setSerajIdle();
        loadAgentsOverview();
      }
    }

    async function handleCancelPlan() {
      if (!currentOperationId) return;
      appendUserMessage("إلغاء");
      showTypingIndicator();
      setSerajBusy("جاري إلغاء العملية…");

      try {
        const res = await apiFetch("/api/agents/cancel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id: "web_cockpit_user", operation_id: currentOperationId }),
        });
        const data = await res.json();
        appendSerajMessage(data.response, null, null, data.operation);
        if (data.operation) {
          updateProcessStepper(data.operation.events || []);
          updateOperationBadges(data.operation);
        }
        resetAllAgentsToIdle();
      } catch (err) {
        appendSerajMessage("❌ تعذر إلغاء العملية: " + err.message);
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
      formData.append("chat_id", "web_cockpit_user");
      if (currentOperationId) formData.append("operation_id", currentOperationId);

      appendUserMessage(`📎 تم إرفاق الملف: «${file.name}» (${Math.round(file.size / 1024)} KB)`);
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
          document.getElementById("activeOpIdBadge").textContent = currentOperationId;

          if (data.dry_run_report) {
            if (data.dry_run_report.summary) {
              const r = data.dry_run_report;
              const repMsg = `✅ ${data.message}\\n\\n` +
                `📋 **تقرير الفحص الأولي المحكوم (Dry-Run)** لملف «${data.filename}»:\\n` +
                `• إجمالي الصفوف المفحوصة: ${r.total_rows}\\n` +
                `• الصفوف المقبولة والمطابقة: ${r.accepted_count}\\n` +
                `• الصفوف المرفوضة أو غير المطابقة: ${r.rejected_count}\\n` +
                `🔒 جرى الفحص بصورة جافة وآمنة دون إجراء أي كتابة أو تعديل غير معتمد في Odoo.`;
              appendSerajMessage(repMsg);
            } else if (data.dry_run_report.error) {
              appendSerajMessage(`❌ تعذر استكمال فحص ملف الإكسل «${data.filename}»:\\n${data.dry_run_report.error}`);
            }
          } else {
            appendSerajMessage(`✅ ${data.message}\\nجاري متابعة معالجة الملف في المنظومة.`);
          }
          startLiveEventPolling(currentOperationId);
        } else {
          appendSerajMessage("❌ فشل رفع الملف: " + (data.detail || "خطأ"));
        }
      } catch (err) {
        appendSerajMessage("❌ تعذر رفع الملف: " + err.message);
      } finally {
        hideTypingIndicator();
        setSerajIdle();
        input.value = "";
      }
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

    function appendSerajMessage(text, pendingAction, pendingClarification, opData) {
      const container = document.getElementById("chatMessages");
      const msg = document.createElement("div");
      msg.className = "msg-bubble msg-assistant";

      let actionCardHtml = "";

      if (pendingClarification && pendingClarification.type === "clarify_delete_or_archive") {
        const target = pendingClarification.target || "السجل";
        actionCardHtml = `
          <div class="chat-action-card">
            <div class="action-card-header">
              <span class="action-card-title">❓ تحديد نوع الإجراء المطلوب نظاماً</span>
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
      } else if (pendingAction) {
        actionCardHtml = `
          <div class="chat-action-card card-approval">
            <div class="action-card-header">
              <span class="action-card-title">⚠️ يتطلب اعتماد بشري قبل التنفيذ</span>
              <span class="badge badge-warning">بانتظار الاعتماد</span>
            </div>
            <div class="action-card-grid">
              <div><span class="label">الإجراء:</span><span class="val">${escapeHtml(pendingAction.action || 'تعديل سجل')}</span></div>
              <div><span class="label">المستهدف:</span><span class="val">${escapeHtml(pendingAction.target || 'Odoo')}</span></div>
              <div><span class="label">المنفذ:</span><span class="val">كاتب (بإشراف حارس)</span></div>
              <div><span class="label">البيئة:</span><span class="val mono">${selectedCompanyId === 15 ? 'النخبة (15)' : 'شركة ' + selectedCompanyId}</span></div>
            </div>
            <div class="action-buttons-group">
              <button class="btn btn-sm btn-success" onclick="handleApprovePlan()">تأكيد واعتماد الخطة</button>
              <button class="btn btn-sm btn-secondary" onclick="handleCancelPlan()">إلغاء الأمر</button>
            </div>
          </div>
        `;
      }

      msg.innerHTML = `
        <div class="msg-avatar">
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--agent-seraj)"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
        </div>
        <div class="msg-content-wrapper">
          <div class="msg-meta"><span style="color: var(--agent-seraj); font-weight: 600;">سراج</span> • <span class="mono">${getTimeStr()}</span></div>
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
        body: JSON.stringify({ message: choice, chat_id: "web_cockpit_user", operation_id: currentOperationId, company_id: selectedCompanyId }),
      })
      .then(r => r.json())
      .then(data => {
        appendSerajMessage(data.response, data.pending_action, data.pending_clarification, data.operation);
        if (data.operation) updateProcessStepper(data.operation.events || []);
        startLiveEventPolling(currentOperationId);
      })
      .catch(err => appendSerajMessage("❌ تعذر التوجيه: " + err.message))
      .finally(() => { hideTypingIndicator(); setSerajIdle(); });
    }

    function setSerajBusy(text) {
      const bubble = document.getElementById("agentStatusBubble_seraj");
      if (bubble) bubble.textContent = text || "يعمل الآن…";
      const card = document.getElementById("agentCard_seraj");
      if (card) card.classList.add("is-active");
    }

    function setSerajIdle() {
      const bubble = document.getElementById("agentStatusBubble_seraj");
      if (bubble) bubble.textContent = "جاهز";
      const card = document.getElementById("agentCard_seraj");
      if (card) card.classList.remove("is-active");
    }

    function showTypingIndicator() {
      const el = document.getElementById("typingIndicator");
      if (el) {
        el.classList.add("is-visible");
        const container = document.getElementById("chatMessages");
        if (container) container.scrollTop = container.scrollHeight;
      }
    }

    function hideTypingIndicator() {
      const el = document.getElementById("typingIndicator");
      if (el) el.classList.remove("is-visible");
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
      streamConsecutiveErrors = 0;
      setStreamConnected(true, "المتابعة نشطة ومستمرة");

      let snapshotCycleCounter = 0;

      pollingInterval = setInterval(async () => {
        try {
          // A. Fetch incremental events since last sequence
          const res = await apiFetch(`/api/agents/operations/${opId}/events?after=${lastEventSequence}`);
          const data = await res.json();
          let op = null;

          if (data.status === "success") {
            streamConsecutiveErrors = 0;

            if (data.events && data.events.length > 0) {
              data.events.forEach(evt => {
                lastEventSequence = Math.max(lastEventSequence, evt.sequence || 0);
              });
              const opRes = await apiFetch(`/api/agents/operations/${opId}`);
              const opData = await opRes.json();
              if (opData.status === "success" && opData.operation) {
                op = opData.operation;
                updateProcessStepper(op.events || []);
                updateOperationBadges(op);
              }
            } else {
              // Periodic snapshot verification every 4 cycles (~6s) to ensure ground truth
              snapshotCycleCounter++;
              if (snapshotCycleCounter % 4 === 0) {
                const opRes = await apiFetch(`/api/agents/operations/${opId}`);
                const opData = await opRes.json();
                if (opData.status === "success" && opData.operation) {
                  op = opData.operation;
                  updateOperationBadges(op);
                }
              }
            }

            // B. Strictly terminate ONLY when reaching a confirmed terminal state
            const terminalStatuses = ["completed", "failed", "cancelled"];
            if (op && terminalStatuses.includes(op.status)) {
              clearInterval(pollingInterval);
              pollingInterval = null;
              resetAllAgentsToIdle();
              updateProcessStepper(op.events || []);
              updateOperationBadges(op);
              setStreamConnected(true, "اكتملت العملية");
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
          setStreamConnected(false, `انقطع الاتصال بالمتابعة (${err.message})`);
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

    function updateOperationBadges(op) {
      const stBadge = document.getElementById("activeOpStatusBadge");
      const agBadge = document.getElementById("activeOpAgentBadge");
      if (stBadge) {
        stBadge.textContent = op.status_label || STATUS_MAP_AR[op.status] || op.status;
        stBadge.className = `badge ${op.status === 'completed' ? 'badge-success' : (op.status === 'failed' ? 'badge-error' : 'badge-warning')}`;
      }
      if (agBadge) agBadge.textContent = op.active_agent || "سراج";

      document.querySelectorAll(".agent-character-card").forEach(c => c.classList.remove("is-active"));
      if (op.active_agent && op.status !== "completed" && op.status !== "failed") {
        const card = document.getElementById(`agentCard_${op.active_agent}`);
        if (card) card.classList.add("is-active");
      }
    }

    function updateProcessStepper(events) {
      const stepper = document.getElementById("processStepper");
      const countEl = document.getElementById("processStepCount");
      if (!stepper) return;

      if (!events || events.length === 0) {
        stepper.innerHTML = `
          <div style="padding: 24px; text-align: center; color: var(--color-smoke); font-size: 13px;">
            في انتظار بدء مهام العملية...
          </div>
        `;
        if (countEl) countEl.textContent = "0 خطوات";
        return;
      }

      if (countEl) countEl.textContent = `${events.length} خطوات منجزة`;
      stepper.innerHTML = "";

      events.forEach((evt, idx) => {
        const meta = AGENTS_META[evt.agent] || { name_ar: evt.agent, color: "var(--color-silver-mist)" };
        const isLatest = idx === events.length - 1;
        const isCompleted = evt.status === "completed" || !isLatest;
        const isWaiting = evt.status === "waiting_approval" || evt.status === "waiting_clarification";

        const node = document.createElement("div");
        node.className = `step-node ${isWaiting ? 'is-waiting' : (isCompleted ? 'is-completed' : 'is-active')}`;
        node.onclick = () => openEventDetails(evt);

        node.innerHTML = `
          <div class="step-icon-box" style="border-color: ${meta.color}; color: ${meta.color};">
            ${idx + 1}
          </div>
          <div class="step-content">
            <div class="step-header">
              <span class="step-agent-badge" style="color: ${meta.color}; border: 1px solid ${meta.color}; font-size: 11px; padding: 1px 6px; border-radius: 4px;">
                ${meta.name_ar}
              </span>
              <span class="step-status-tag" style="font-size: 11px; color: var(--color-smoke);">
                ${evt.status_label || STATUS_MAP_AR[evt.status] || evt.status}
              </span>
            </div>
            <div class="step-desc">${escapeHtml(evt.description_ar || evt.event_type)}</div>
            <div class="step-time mono">${evt.timestamp ? evt.timestamp.substring(11, 19) : ''}</div>
          </div>
        `;
        stepper.appendChild(node);
      });
    }

    function openEventDetails(evt) {
      const overlay = document.getElementById("detailsDrawerOverlay");
      const title = document.getElementById("drawerTitle");
      const body = document.getElementById("drawerBody");
      if (!overlay || !body) return;

      title.textContent = `تفاصيل الخطوة: «${evt.description_ar || evt.event_type}»`;
      body.innerHTML = `
        <div style="background: #141414; padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
          <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 6px;">الوكيل المنفذ</div>
          <div style="font-size: 16px; font-weight: 700; color: var(--color-snow);">${AGENTS_META[evt.agent]?.name_ar || evt.agent}</div>
        </div>
        <div style="background: #141414; padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
          <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 6px;">الحالة والمعرف</div>
          <div class="mono" style="font-size: 13px; color: var(--color-silver-mist);">Sequence: #${evt.sequence || '—'} | Status: ${evt.status}</div>
        </div>
        <div style="background: #141414; padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
          <div style="font-size: 12px; color: var(--color-smoke); margin-bottom: 6px;">البيانات الفنية والتحقق</div>
          <pre style="margin: 0; font-size: 11.5px; color: var(--color-snow); max-height: 200px; overflow-y: auto;">${escapeHtml(JSON.stringify(evt.metadata || {}, null, 2))}</pre>
        </div>
      `;
      overlay.classList.add("is-open");
    }

    // =========================================================================
    // 10. AGENT DRAWER DETAILS (CENTERED MODAL)
    // =========================================================================
    function openAgentDetails(agentKey) {
      const meta = AGENTS_META[agentKey] || {};
      const agentData = activeAgentsData.find(a => a.id === agentKey) || {};
      const overlay = document.getElementById("detailsDrawerOverlay");
      const title = document.getElementById("drawerTitle");
      const body = document.getElementById("drawerBody");
      if (!overlay || !body) return;

      title.textContent = `بطاقة الوكيل: «${meta.name_ar}»`;

      body.innerHTML = `
        <div style="display: flex; align-items: center; gap: 14px; background: #141414; padding: 16px; border-radius: 12px; border: 1px solid var(--color-charcoal);">
          <div class="agent-avatar-wrap" style="border-color: ${meta.color}; width: 50px; height: 50px; margin: 0;">
            ${getAgentSvg(meta.icon)}
          </div>
          <div>
            <div style="font-size: 17px; font-weight: 700; color: var(--color-snow);">${meta.name_ar}</div>
            <div style="font-size: 12px; color: var(--color-silver-mist);">${meta.role}</div>
          </div>
        </div>

        <div style="background: #141414; padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
          <div style="font-size: 11px; color: var(--color-smoke); margin-bottom: 4px;">الحالة التشغيلية الآن</div>
          <span class="badge ${agentData.status_code === 'ready' ? 'badge-neutral' : 'badge-success'}">
            ${agentData.status_label || STATUS_MAP_AR[agentData.status_code] || 'جاهز'}
          </span>
        </div>

        <div style="background: #141414; padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
          <div style="font-size: 11px; color: var(--color-smoke); margin-bottom: 4px;">المهمة الحالية / الأخيرة</div>
          <div style="font-size: 13.5px; color: var(--color-snow); line-height: 1.5;">${escapeHtml(agentData.last_task || 'في انتظار استلام المهام')}</div>
        </div>

        <div style="background: #141414; padding: 14px; border-radius: 10px; border: 1px solid var(--color-charcoal);">
          <div style="font-size: 11px; color: var(--color-smoke); margin-bottom: 4px;">الصلاحيات والحدود المعمارية</div>
          <div style="font-size: 12.5px; color: var(--color-silver-mist); line-height: 1.6;">
            ${agentKey === 'fahas' ? '• قراءة واستعلام فقط (Read-Only) في Odoo.<br>• التحقق المستقل بعد التنفيذ (Readback Verification).<br>• لا يملك أي صلاحيات كتابة أو تعديل.' : ''}
            ${agentKey === 'katib' ? '• المنفذ الحصري لعمليات الكتابة في Odoo.<br>• لا يُنفذ أي أمر إلا بعد التحقق المزدوج واعتماد الخطة.<br>• يُحظر الحذف الكلي غير المحكوم حماية للبيانات.' : ''}
            ${agentKey === 'seraj' ? '• واجهة المحادثة والتنسيق العام بين كافة الوكلاء.<br>• استلام الطلبات وشرح النتائج بلغة طبيعية.<br>• لا يقرأ أو يكتب في Odoo مباشرة دون الوكلاء المختصين.' : ''}
            ${agentKey === 'sijil' ? '• الرقابة والتدقيق غير القابل للتلاعب (Append-only).<br>• توثيق البصمات الرقمية وتوليد تقارير PDF الرسمية.<br>• قياس مؤشرات الحوكمة ونسب المطابقة.' : ''}
            ${!['fahas', 'katib', 'seraj', 'sijil'].includes(agentKey) ? '• يعمل ضمن منظومة التحقق والحوكمة المعتمدة.<br>• لا يتدخل في المحادثة المباشرة مع المستخدم بل يفوض الرد لسراج.' : ''}
          </div>
        </div>
      `;

      overlay.classList.add("is-open");
    }

    function closeDetailsDrawer(e) {
      const overlay = document.getElementById("detailsDrawerOverlay");
      if (overlay) overlay.classList.remove("is-open");
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
          tbody.innerHTML = data.operations.map(op => `
            <tr>
              <td class="mono" style="font-weight: 600; color: var(--color-snow);">${escapeHtml(op.operation_id)}</td>
              <td>${escapeHtml(op.operation_type || 'محادثة')}</td>
              <td>${escapeHtml(op.requester || 'المستخدم')}</td>
              <td>${escapeHtml(op.company_name || 'شركة النخبة (15)')}</td>
              <td><span style="color: ${AGENTS_META[op.active_agent]?.color || 'var(--color-silver-mist)'}; font-weight: 600;">${AGENTS_META[op.active_agent]?.name_ar || op.active_agent}</span></td>
              <td><span class="badge ${op.status === 'completed' ? 'badge-success' : (op.status === 'failed' ? 'badge-error' : 'badge-warning')}">${op.status_label || STATUS_MAP_AR[op.status] || op.status}</span></td>
              <td class="mono" style="font-size: 11px;">${op.created_at ? op.created_at.substring(0, 19).replace('T', ' ') : '—'}</td>
              <td>
                <div style="display: flex; gap: 6px;">
                  <button class="btn btn-sm btn-secondary" onclick="resumeOperationInCockpit('${op.operation_id}')">متابعة</button>
                  <button class="btn btn-sm btn-iris" onclick="openOperationInSijil('${op.operation_id}')">سجل</button>
                  <button class="btn btn-sm btn-secondary" onclick="exportSingleOpPdf('${op.operation_id}')">PDF</button>
                </div>
              </td>
            </tr>
          `).join("");
        }
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--color-coral); padding: 20px;">تعذر تحميل العمليات: ${err.message}</td></tr>`;
      }
    }

    async function resumeOperationInCockpit(opId) {
      if (!opId) return;
      currentOperationId = opId;
      document.getElementById("activeOpIdBadge").textContent = opId;
      switchView("view-cockpit");

      try {
        const res = await apiFetch(`/api/agents/operations/${opId}`);
        const data = await res.json();
        if (data.status === "success" && data.operation) {
          const op = data.operation;

          // A. Restore conversation messages
          const chatContainer = document.getElementById("chatMessages");
          if (chatContainer) {
            chatContainer.innerHTML = "";
            if (op.user_query) {
              appendUserMessage(op.user_query);
            }

            const events = op.events || [];
            let lastDesc = null;
            events.forEach(evt => {
              if (evt.description_ar && evt.event_type !== "start") {
                lastDesc = evt.description_ar;
              }
            });

            if (op.status === "completed") {
              appendSerajMessage(lastDesc || `تم إنجاز العملية «${op.user_query}» ومطابقتها رقابياً بنجاح.`, null, null, op);
            } else {
              appendSerajMessage(lastDesc || `جاري متابعة معالجة العملية «${op.user_query}» في مركز العمليات.`, null, null, op);
            }
          }

          // B. Update stepper & badges
          updateProcessStepper(op.events || []);
          updateOperationBadges(op);

          // C. Handle active or terminal state
          const terminalStatuses = ["completed", "failed", "cancelled"];
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
        const res = await apiFetch(`/api/sijil/recent?limit=${sijilLimit}&offset=${offset}`);
        const data = await res.json();

        const records = data.operations || data.records || [];
        sijilTotal = data.total || records.length;

        if (data.status === "success" && records.length > 0) {
          tbody.innerHTML = records.map(r => {
            const ident = r.identifier || r.record_id || r.operation_id || r.plan_id || '—';
            const typeLabel = r.type || r.domain_ar || r.domain || 'عملية موثقة';
            const statusOk = r.status_raw === 'success' || r.readback_verified;
            let ts = '—';
            if (r.timestamp) {
              const raw = String(r.timestamp);
              if (raw.includes('-')) {
                ts = raw.substring(0, 19).replace('T', ' ');
              } else if (raw.length >= 15) {
                ts = `${raw.substring(0,4)}-${raw.substring(4,6)}-${raw.substring(6,8)} ${raw.substring(9,11)}:${raw.substring(11,13)}:${raw.substring(13,15)}`;
              } else {
                ts = raw;
              }
            }
            return `
            <tr>
              <td class="mono" style="font-size: 11.5px; color: var(--color-iris-glow);">${escapeHtml(ident)}</td>
              <td><span class="badge badge-neutral">${escapeHtml(typeLabel)}</span></td>
              <td>${escapeHtml(r.action || r.operation_type || 'قيد نظامي')}</td>
              <td>${escapeHtml(r.target || r.user_query || '—')}</td>
              <td><span class="badge ${statusOk ? 'badge-success' : 'badge-warning'}">${escapeHtml(r.status || (statusOk ? 'ناجحة' : 'قيد المراجعة'))}</span></td>
              <td class="mono" style="font-size: 11px;">${ts}</td>
              <td>
                <div style="display: flex; gap: 6px;">
                  <button class="btn btn-sm btn-iris" onclick="openOperationInSijil('${ident}')">سجل</button>
                  <button class="btn btn-sm btn-secondary" onclick="exportSingleOpPdf('${ident}')">PDF</button>
                </div>
              </td>
            </tr>
          `;
          }).join("");
        } else if (data.status === "success") {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--color-smoke); padding: 20px;">لا توجد عمليات موثقة بعد.</td></tr>';
        } else {
          tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--color-coral); padding: 20px;">خطأ: ${escapeHtml(data.detail || 'تعذر تحميل سجلات التدقيق')}</td></tr>`;
        }

        // Update pagination controls
        const totalPages = Math.max(1, Math.ceil(sijilTotal / sijilLimit));
        const infoEl = document.getElementById("sijilPaginationInfo");
        const pageBadge = document.getElementById("sijilPageBadge");
        const prevBtn = document.getElementById("sijilPrevBtn");
        const nextBtn = document.getElementById("sijilNextBtn");

        if (infoEl) infoEl.textContent = `الصفحة ${sijilPage} من ${totalPages} (إجمالي ${sijilTotal} سجل)`;
        if (pageBadge) pageBadge.textContent = sijilPage;
        if (prevBtn) prevBtn.disabled = sijilPage <= 1;
        if (nextBtn) nextBtn.disabled = sijilPage >= totalPages;

        // Load summary metrics
        const sRes = await apiFetch("/api/sijil/summary");
        const sData = await sRes.json();
        if (sData.status === "success") {
          const el = document.getElementById("metricBlockedDeletions");
          if (el) el.textContent = sData.summary.blocked_deletions_count || 0;
        }
      } catch (err) {
        console.warn("Sijil metrics error:", err);
      }
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
        const res = await apiFetch(`/api/sijil/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        if (data.status === "success" && data.match_type === "single" && data.operation) {
          const op = data.operation;
          resultBox.innerHTML = `
            <div style="background: #181818; border: 1px solid var(--color-charcoal); border-radius: 12px; padding: 18px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div style="font-size: 15px; font-weight: 700; color: var(--color-snow);">نتيجة المطابقة: ${escapeHtml(op.operation_type || 'عملية موثقة')}</div>
                <div style="display: flex; gap: 8px;">
                  <button class="btn btn-sm btn-iris" onclick="openOperationInSijil('${op.operation_id || op.plan_id}')">عرض السجل الكامل</button>
                  <button class="btn btn-sm btn-secondary" onclick="exportSingleOpPdf('${op.plan_id || op.operation_id}')">تحميل PDF</button>
                </div>
              </div>
              <div style="font-size: 13px; color: var(--color-silver-mist); line-height: 1.6;">
                • معرف العملية: <span class="mono">${escapeHtml(op.operation_id)}</span><br>
                • رمز الخطة: <span class="mono">${escapeHtml(op.plan_id || '—')}</span><br>
                • السجل المستهدف: ${escapeHtml(op.scope?.target_record_name || '—')}<br>
                • البصمة الرقمية: <span class="mono" style="color: var(--color-iris-glow);">${escapeHtml(op.technical_details?.sha256_digest || '—')}</span>
              </div>
            </div>
          `;
        } else if (data.status === "multiple_matches" || (data.status === "success" && data.candidates)) {
          const list = (data.candidates || []).slice(0, 5).map(c => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--color-charcoal);">
              <div>
                <span class="mono" style="color: var(--color-iris-glow);">${escapeHtml(c.record_id || c.operation_id)}</span>
                <span style="color: var(--color-snow); margin-right: 8px;">${escapeHtml(c.target || c.title || 'سجل')}</span>
              </div>
              <div style="display: flex; gap: 6px;">
                <button class="btn btn-sm btn-iris" onclick="openOperationInSijil('${c.record_id || c.operation_id}')">سجل</button>
                <button class="btn btn-sm btn-secondary" onclick="exportSingleOpPdf('${c.record_id || c.operation_id}')">PDF</button>
              </div>
            </div>
          `).join("");
          resultBox.innerHTML = `
            <div style="background: #181818; border: 1px solid var(--color-charcoal); border-radius: 12px; padding: 18px;">
              <div style="font-size: 14px; font-weight: 700; color: var(--color-amber); margin-bottom: 10px;">عُثر على عدة سجلات متطابقة:</div>
              <div>${list}</div>
            </div>
          `;
        } else {
          resultBox.innerHTML = `
            <div style="background: #181818; border: 1px solid var(--color-charcoal); border-radius: 12px; padding: 18px; text-align: center; color: var(--color-coral);">
              ${escapeHtml(data.message || 'لم يُعثر على سجل مطابق لمعيار البحث في دفتر سجل.')}
            </div>
          `;
        }
      } catch (err) {
        resultBox.innerHTML = `<div style="text-align: center; color: var(--color-coral); padding: 20px;">خطأ في البحث: ${err.message}</div>`;
      }
    }

    async function openOperationInSijil(ident) {
      if (!ident || ident === '—') return;
      const overlay = document.getElementById("opDetailModalOverlay");
      const body = document.getElementById("opDetailModalBody");
      if (!overlay || !body) {
        switchView("view-sijil");
        const input = document.getElementById("sijilSearchInput");
        if (input) { input.value = ident; executeSijilSearch(); }
        return;
      }

      body.innerHTML = '<div style="text-align:center;padding:30px;color:var(--color-smoke);">جاري تحميل التوثيق…</div>';
      overlay.classList.add("is-open");

      try {
        const res = await apiFetch(`/api/sijil/operation/${encodeURIComponent(ident)}`);
        if (res.status === 404) {
          const res2 = await apiFetch(`/api/agents/operations/${encodeURIComponent(ident)}`);
          const d2 = await res2.json();
          if (d2.status === "success" && d2.operation) {
            renderOpDetailModal(d2.operation, ident);
            return;
          }
          body.innerHTML = '<div style="text-align:center;padding:30px;color:var(--color-coral);">لم يُعثر على توثيق لهذا المعرف في سجل.</div>';
          return;
        }
        const data = await res.json();
        if (data.status === "success" && data.operation) {
          renderOpDetailModal(data.operation, ident);
        } else {
          body.innerHTML = '<div style="text-align:center;padding:30px;color:var(--color-coral);">لم يُعثر على توثيق لهذا المعرف في سجل.</div>';
        }
      } catch (err) {
        body.innerHTML = `<div style="text-align:center;padding:30px;color:var(--color-coral);">خطأ: ${escapeHtml(err.message)}</div>`;
      }
    }

    function renderOpDetailModal(op, ident) {
      const body = document.getElementById("opDetailModalBody");
      const opIdentifier = op.operation_id || op.plan_id || ident;
      const rows = [
        ['نوع العملية', op.operation_type || op.type || '—'],
        ['معرف العملية', opIdentifier],
        ['رمز الخطة', op.plan_id || '—'],
        ['الحالة', op.final_status || op.status || 'معتمدة ومطابقة'],
        ['الطلب الأصلي', op.user_query || op.request_summary || '—'],
        ['الوكيل المنفذ', op.executing_agent || op.active_agent || '—'],
        ['وقت الإنشاء', op.created_at ? op.created_at.substring(0,19).replace('T',' ') : (op.timestamp || '—')],
        ['المستهدف', op.scope?.target_record_name || op.target || '—'],
        ['البصمة الرقمية', op.technical_details?.sha256_digest || '—'],
      ];
      const rowsHtml = rows.map(([label, val]) =>
        `<div class="op-detail-row">
          <span class="op-detail-label">${label}</span>
          <span class="op-detail-value mono" style="font-size:12px;">${escapeHtml(String(val))}</span>
         </div>`
      ).join('');

      body.innerHTML = `
        <div>${rowsHtml}</div>
        <div style="display:flex;gap:10px;margin-top:20px;flex-wrap:wrap;">
          <button class="btn btn-sm btn-iris" onclick="exportSingleOpPdf('${escapeHtml(opIdentifier)}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width:13px;height:13px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            تصدير تقرير PDF أبيض A4
          </button>
          <button class="btn btn-sm btn-secondary" onclick="resumeOperationInCockpit('${escapeHtml(opIdentifier)}')">
            متابعة في لوحة التحكم
          </button>
          <button class="btn btn-sm btn-secondary" onclick="document.getElementById('opDetailModalOverlay').classList.remove('is-open')">
            إغلاق
          </button>
        </div>
      `;
    }

    function exportFullSijilPdf() {
      const token = getApiToken();
      const url = "/api/sijil/report/pdf" + (token ? "?api_key=" + encodeURIComponent(token) : "");
      window.open(url, "_blank");
    }

    function exportSingleOpPdf(ident) {
      if (!ident) return;
      const token = getApiToken();
      const url = `/api/sijil/operation/${encodeURIComponent(ident)}/pdf` + (token ? "?api_key=" + encodeURIComponent(token) : "");
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

    function formatMarkdownText(text) {
      if (!text) return "";
      let html = escapeHtml(text);
      html = html.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
      html = html.replace(/\\*(.*?)\\*/g, '<em>$1</em>');
      html = html.replace(/`(.*?)`/g, '<code>$1</code>');
      html = html.replace(/\\n/g, '<br>');
      return html;
    }

    function getTimeStr() {
      const now = new Date();
      return now.toTimeString().substring(0, 8);
    }
  </script>

  <!-- ==================== OPERATION DETAIL MODAL (CENTERED) ==================== -->
  <div id="opDetailModalOverlay" class="op-modal-overlay" onclick="if(event.target===this)this.classList.remove('is-open')">
    <div class="op-modal" role="dialog" aria-modal="true" aria-label="تفاصيل التوثيق">
      <button class="op-modal-close" onclick="document.getElementById('opDetailModalOverlay').classList.remove('is-open')" title="إغلاق">×</button>
      <div class="op-modal-title">
        <svg viewBox="0 0 24 24" fill="none" stroke="var(--agent-sijil)" style="width:18px;height:18px;vertical-align:middle;margin-left:8px;"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>
        توثيق العملية — الوكيل «سجل»
      </div>
      <div id="opDetailModalBody">
        <div style="text-align:center;padding:30px;color:var(--color-smoke);">جاري التحميل…</div>
      </div>
    </div>
  </div>

</body>
</html>
"""

full_content = html_before_script + new_script
path.write_text(full_content, encoding="utf-8")
print("Updated dashboard.html successfully! New size:", len(full_content))
