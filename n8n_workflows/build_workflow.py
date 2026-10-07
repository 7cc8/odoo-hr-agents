"""Build a clean, robust, and UTF-8 encoded n8n Telegram workflow for Odoo HR Agents."""

import json
from pathlib import Path

CREDENTIALS = {
    "telegramApi": {
        "id": "jCdlB4YPyJxECyUz",
        "name": "Telegram account"
    }
}

nodes = []

# 1. Telegram Trigger
nodes.append({
    "parameters": {
        "updates": ["message", "callback_query"],
        "additionalFields": {}
    },
    "name": "Telegram",
    "type": "n8n-nodes-base.telegramTrigger",
    "typeVersion": 1.1,
    "position": [200, 300],
    "id": "node-tg-trigger",
    "credentials": CREDENTIALS,
    "notes": "Receives Excel files and button clicks from HR staff"
})

# 2. Security Whitelist & Event Parser (Code)
js_parser = """const item = $input.first().json;

let senderId = null;
let senderName = '';
let chatId = null;
let eventType = 'text';
let action = '';
let runId = '';
let fileId = '';
let fileName = '';
let text = '';

if (item.callback_query) {
  eventType = 'callback';
  const cb = item.callback_query;
  const cbId = cb.id;
  senderId = cb.from ? String(cb.from.id) : null;
  senderName = (cb.from ? (cb.from.first_name || cb.from.username || '') : '') || 'Telegram User';
  chatId = cb.message && cb.message.chat ? String(cb.message.chat.id) : senderId;
  const data = cb.data || '';
  const idx = data.indexOf(':');
  if (idx !== -1) {
    action = data.slice(0, idx);
    runId = data.slice(idx + 1);
  } else {
    action = data;
  }
  return [{
    json: {
      is_authorized: true,
      event_type: eventType,
      action: action,
      run_id: runId,
      callback_query_id: cbId,
      chat_id: chatId,
      sender_id: senderId,
      sender_name: senderName
    }
  }];
}

if (item.message) {
  const msg = item.message;
  senderId = msg.from ? String(msg.from.id) : null;
  senderName = (msg.from ? (msg.from.first_name || msg.from.username || '') : '') || 'Telegram User';
  chatId = msg.chat ? String(msg.chat.id) : senderId;
  
  // Whitelist check: allow configured chat_id 696492053
  const allowed = ['696492053'];
  const isAuth = allowed.includes(String(chatId)) || allowed.includes(String(senderId));

  if (msg.document) {
    const fn = msg.document.file_name || 'upload.xlsx';
    return [{
      json: {
        is_authorized: isAuth,
        event_type: 'excel_upload',
        file_id: msg.document.file_id,
        file_name: fn,
        chat_id: chatId,
        sender_id: senderId,
        sender_name: senderName
      }
    }];
  }

  return [{
    json: {
      is_authorized: isAuth,
      event_type: 'text',
      text: msg.text || '',
      chat_id: chatId,
      sessionId: chatId,
      sender_id: senderId,
      sender_name: senderName
    }
  }];
}

return [{
  json: {
    is_authorized: false,
    event_type: 'unknown',
    chat_id: chatId
  }
}];
"""

nodes.append({
    "parameters": {
        "jsCode": js_parser
    },
    "name": "Security & Event Parser",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [440, 300],
    "id": "node-parser"
})

# 3. Is Authorized? (If)
nodes.append({
    "parameters": {
        "conditions": {
            "boolean": [
                {
                    "value1": "={{ $json.is_authorized }}",
                    "value2": True
                }
            ]
        }
    },
    "name": "Is Authorized?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 1,
    "position": [680, 300],
    "id": "node-is-auth"
})

# 4. Send Unauthorized Message
nodes.append({
    "parameters": {
        "chatId": "={{ $json.chat_id }}",
        "text": "⛔ <b>عذراً، غير مصرح لك باستخدام هذا البوت.</b>\nحسابك غير مدرج في قائمة مسؤولي الموارد البشرية المعتمدين.",
        "additionalFields": {
            "parse_mode": "HTML",
            "appendAttribution": False
        }
    },
    "name": "Send Unauthorized",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [680, 520],
    "id": "node-send-unauthorized",
    "credentials": CREDENTIALS
})

# 5. Route Event Type (Switch)
nodes.append({
    "parameters": {
        "dataType": "string",
        "value1": "={{ $json.event_type }}",
        "rules": {
            "rules": [
                {"value2": "excel_upload", "output": 0},
                {"value2": "callback", "output": 1},
                {"value2": "text", "output": 2}
            ]
        }
    },
    "name": "Route Event Type",
    "type": "n8n-nodes-base.switch",
    "typeVersion": 1,
    "position": [920, 240],
    "id": "node-route-event"
})

# ==================== BRANCH 0: EXCEL UPLOAD ====================

# 6. Ack Upload
nodes.append({
    "parameters": {
        "chatId": "={{ $json.chat_id }}",
        "text": "⏳ جارِ استلام وتحليل ملف <code>{{ $json.file_name }}</code> تجريبياً...",
        "additionalFields": {
            "parse_mode": "HTML",
            "appendAttribution": False
        }
    },
    "name": "Ack Upload",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [1160, 100],
    "id": "node-ack-upload",
    "credentials": CREDENTIALS
})

# 7. Download Excel File (Native Telegram Node file:get)
nodes.append({
    "parameters": {
        "resource": "file",
        "operation": "get",
        "fileId": "={{ $('Route Event Type').first().json.file_id }}",
        "download": True,
        "additionalFields": {}
    },
    "name": "Download Excel File",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [1380, 100],
    "id": "node-download-excel",
    "credentials": CREDENTIALS,
    "notes": "Downloads binary stream securely using official Telegram API credentials"
})

# 8. Run Dry-Run via API
nodes.append({
    "parameters": {
        "method": "POST",
        "url": "http://host.docker.internal:8000/api/dry-run",
        "sendBody": True,
        "contentType": "multipart-form-data",
        "bodyParameters": {
            "parameters": [
                {
                    "parameterType": "formBinaryData",
                    "name": "file",
                    "inputDataFieldName": "data"
                }
            ]
        },
        "options": {
            "timeout": 120000
        }
    },
    "name": "Run Dry-Run via API",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [1600, 100],
    "id": "node-run-dry-run",
    "notes": "Executes dry_run_report via resilient API on host"
})

# 9. Format Dry-Run Summary (Code)
js_format_summary = """const rep = $input.first().json;
const routeData = $('Route Event Type').first().json;
const chatId = routeData.chat_id;
const fileName = routeData.file_name;

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const h = rep.header || {};
const s = rep.summary || {};
const counts = s.status_counts || {};
const rows = rep.rows || [];
const runId = h.run_id || rep.run_id || 'unknown';

const accepted = counts.accepted !== undefined ? counts.accepted : (s.accepted !== undefined ? s.accepted : 0);
const needsReview = counts.needs_review !== undefined ? counts.needs_review : (s.needs_review !== undefined ? s.needs_review : 0);
const rejected = counts.rejected !== undefined ? counts.rejected : (s.rejected !== undefined ? s.rejected : 0);
const total = s.row_count !== undefined ? s.row_count : (s.total_rows !== undefined ? s.total_rows : rows.length);

let previewRows = '';
for (const r of rows.slice(0, 8)) {
  const ico = r.final_status === 'accepted' ? '✅' : r.final_status === 'rejected' ? '❌' : '⚠️';
  const name = escapeHtml(r.display_name || ('صف ' + (r.excel_row_number || r.row_number)));
  const job = r.display_job ? ` (${escapeHtml(r.display_job)})` : '';
  const reason = (r.final_status !== 'accepted' && r.validation_messages && r.validation_messages.length > 0)
    ? `\\n   ↳ <i>${escapeHtml(r.validation_messages[0])}</i>`
    : '';
  previewRows += `${ico} <b>${name}</b>${job}${reason}\\n`;
}

let summaryText = [
  `📊 <b>نتائج الفحص التجريبي (Dry-Run)</b>`,
  `────────────────────`,
  `📁 <b>الملف:</b> <code>${escapeHtml(fileName)}</code>`,
  `🆔 <b>معرّف الفحص:</b> <code>${escapeHtml(runId)}</code>`,
  `📈 <b>إجمالي الصفوف:</b> <b>${total}</b>`,
  ``,
  `  • جاهز للاعتماد (accepted): <b>${accepted}</b> ✅`,
  `  • يحتاج مراجعة (needs_review): <b>${needsReview}</b> ⚠️`,
  `  • مرفوض (rejected): <b>${rejected}</b> ❌`,
  `────────────────────`,
  previewRows ? `📋 <b>عينة من الصفوف والملاحظات:</b>\\n${previewRows}────────────────────` : ''
].filter(Boolean).join('\\n');

if (accepted > 0) {
  summaryText += `\\n\\n🏢 <b>الشركة:</b> شركة النخبة الذكية للتقنية (15)\\nهل ترغب في اعتماد وإنشاء <b>(${accepted})</b> موظف(ين) في Odoo الآن؟`;
} else {
  summaryText += `\\n\\n⚠️ <i>لا توجد صفوف مقبولة للاعتماد. يرجى مراجعة الملاحظات وتصحيح الملف ثم إعادة إرساله، أو اكتب سؤالك هنا وسأساعدك في حله فوراً!</i>`;
}

return [{
  json: {
    chat_id: chatId,
    run_id: runId,
    has_accepted: accepted > 0,
    accepted_count: accepted,
    summary_text: summaryText
  }
}];
"""

nodes.append({
    "parameters": {
        "jsCode": js_format_summary
    },
    "name": "Format Dry-Run Summary",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1820, 100],
    "id": "node-format-summary"
})

# 10. Has Accepted Rows? (If)
nodes.append({
    "parameters": {
        "conditions": {
            "boolean": [
                {
                    "value1": "={{ $json.has_accepted }}",
                    "value2": True
                }
            ]
        }
    },
    "name": "Has Accepted Rows?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 1,
    "position": [2040, 100],
    "id": "node-has-accepted"
})

# 10a. Send Approval Prompt (when accepted > 0)
nodes.append({
    "parameters": {
        "chatId": "={{ $json.chat_id }}",
        "text": "={{ $json.summary_text }}",
        "replyMarkup": "inlineKeyboard",
        "inlineKeyboard": {
            "rows": [
                {
                    "row": {
                        "buttons": [
                            {
                                "text": "={{ '🚀 اعتماد وإنشاء (' + $json.accepted_count + ') في Odoo' }}",
                                "additionalFields": {
                                    "callback_data": "={{ 'approve:' + $json.run_id }}"
                                }
                            },
                            {
                                "text": "❌ إلغاء",
                                "additionalFields": {
                                    "callback_data": "={{ 'cancel:' + $json.run_id }}"
                                }
                            }
                        ]
                    }
                }
            ]
        },
        "additionalFields": {
            "parse_mode": "HTML",
            "appendAttribution": False
        }
    },
    "name": "Send Dry-Run Summary & Approval Buttons",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [2280, 20],
    "id": "node-send-summary",
    "credentials": CREDENTIALS
})

# 10b. Send Rejection Notice (when accepted === 0)
nodes.append({
    "parameters": {
        "chatId": "={{ $json.chat_id }}",
        "text": "={{ $json.summary_text }}",
        "replyMarkup": "inlineKeyboard",
        "inlineKeyboard": {
            "rows": [
                {
                    "row": {
                        "buttons": [
                            {
                                "text": "❌ إغلاق التقرير",
                                "additionalFields": {
                                    "callback_data": "={{ 'cancel:' + $json.run_id }}"
                                }
                            }
                        ]
                    }
                }
            ]
        },
        "additionalFields": {
            "parse_mode": "HTML",
            "appendAttribution": False
        }
    },
    "name": "Send Rejection Notice",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [2280, 180],
    "id": "node-send-rejection",
    "credentials": CREDENTIALS
})

# ==================== BRANCH 1: CALLBACK QUERY (APPROVE / CANCEL) ====================

# 11. Is Approve Action? (If)
nodes.append({
    "parameters": {
        "conditions": {
            "string": [
                {
                    "value1": "={{ $('Route Event Type').first().json.action }}",
                    "value2": "approve",
                    "operation": "equal"
                }
            ]
        }
    },
    "name": "Is Approve Action?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 1,
    "position": [1160, 320],
    "id": "node-is-approve"
})

# 12. Send Cancel Confirmation
nodes.append({
    "parameters": {
        "chatId": "={{ $('Route Event Type').first().json.chat_id }}",
        "text": "🚫 <b>تم إلغاء عملية الاعتماد للفحص:</b> <code>{{ $('Route Event Type').first().json.run_id }}</code>\nيمكنك إرسال ملف Excel جديد في أي وقت.",
        "additionalFields": {
            "parse_mode": "HTML",
            "appendAttribution": False
        }
    },
    "name": "Send Cancel Confirmation",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [1400, 460],
    "id": "node-send-cancel",
    "credentials": CREDENTIALS
})

# 13. Send Progress Update
nodes.append({
    "parameters": {
        "chatId": "={{ $('Route Event Type').first().json.chat_id }}",
        "text": "⏳ <b>جارِ الاعتماد والإنشاء في Odoo...</b>\nمعرّف الفحص: <code>{{ $('Route Event Type').first().json.run_id }}</code>\nيرجى الانتظار بضع ثوانٍ.",
        "additionalFields": {
            "parse_mode": "HTML",
            "appendAttribution": False
        }
    },
    "name": "Send Progress Update",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [1400, 280],
    "id": "node-send-progress",
    "credentials": CREDENTIALS
})

# 14. Execute in Odoo via API
nodes.append({
    "parameters": {
        "method": "POST",
        "url": "http://host.docker.internal:8000/api/approve-and-execute",
        "sendBody": True,
        "contentType": "json",
        "body": "={{ JSON.stringify({ run_id: $('Route Event Type').first().json.run_id, approved_by: $('Route Event Type').first().json.sender_name + ' (Telegram ID: ' + $('Route Event Type').first().json.sender_id + ')', company_id: 15, max_rows: 10 }) }}",
        "options": {
            "timeout": 300000
        }
    },
    "name": "Execute in Odoo via API",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [1640, 280],
    "id": "node-execute-api",
    "notes": "Generates approval.json and runs writer.py with environment guard"
})

# 15. Format Final Result (Code)
js_format_final = """const res = $input.first().json;
const routeData = $('Route Event Type').first().json;
const chatId = routeData.chat_id;

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

if (res.status !== 'success') {
  return [{
    json: {
      chat_id: chatId,
      text: `❌ <b>فشل الاعتماد أو الإنشاء في Odoo:</b>\\n<code>${escapeHtml(res.detail || JSON.stringify(res))}</code>`
    }
  }];
}

const created = res.created_count || 0;
const failed = res.failed_count || 0;
const skipped = res.skipped_count || 0;
const items = res.created_items || [];

let namesList = '';
for (const it of items) {
  namesList += `  • <b>${escapeHtml(it.name)}</b> (Odoo ID: <code>${escapeHtml(it.odoo_id)}</code>)\\n`;
}

const text = [
  `🎉 <b>تم اكتمال الإنشاء في Odoo بنجاح!</b>`,
  `────────────────────`,
  `🏢 <b>الشركة:</b> شركة النخبة الذكية للتقنية (15)`,
  `🆔 <b>معرّف الفحص:</b> <code>${escapeHtml(res.run_id)}</code>`,
  ``,
  `✅ <b>تم إنشاؤهم بنجاح:</b> <b>${created}</b>`,
  `❌ <b>فشل:</b> <b>${failed}</b>`,
  `⏭️ <b>تم تخطيهم:</b> <b>${skipped}</b>`,
  `────────────────────`,
  items.length > 0 ? `👥 <b>الموظفون الجدد:</b>\\n${namesList}────────────────────` : '',
  `✨ تم توثيق الاعتماد وتحديث قاعدة بيانات Odoo بأمان.`
].filter(Boolean).join('\\n');

return [{ json: { chat_id: chatId, text: text } }];
"""

nodes.append({
    "parameters": {
        "jsCode": js_format_final
    },
    "name": "Format Final Result",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1880, 280],
    "id": "node-format-final"
})

# 16. Send Final Confirmation
nodes.append({
    "parameters": {
        "chatId": "={{ $json.chat_id }}",
        "text": "={{ $json.text }}",
        "additionalFields": {
            "parse_mode": "HTML",
            "appendAttribution": False
        }
    },
    "name": "Send Final Confirmation",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [2120, 280],
    "id": "node-send-final",
    "credentials": CREDENTIALS
})

# ==================== BRANCH 2: AI HR AGENT (TEXT / INQUIRIES / COMMANDS) ====================

AI_SYSTEM_PROMPT = """أنت المساعد الذكي المعتمد لإدارة الموارد البشرية وأتمتة استيراد الموظفين في Odoo ERP لشركة النخبة الذكية للتقنية (Company ID: 15).
لديك صلاحيات كاملة لمساعدة مسؤولي الموارد البشرية عبر الأدوات المتاحة لك:
1. الإجابة عن حالة النظام والاتصال بقاعدة بيانات Odoo عبر أداة check_odoo_status.
2. الاستعلام عن أحدث فحوصات الإكسل (Dry-Run) عبر أداة list_recent_runs.
3. فحص وتحليل أي تقرير فحص بدقة بالغة وتوضيح أسباب رفض أو قبول الصفوف عبر أداة inspect_run_details (معرف الفحص run_id).
4. تنفيذ الاعتماد وإنشاء الموظفين المقبولين في Odoo فورياً عند طلب المستخدم الصريح عبر أداة approve_and_create_employees.
5. الإجابة على أي استفسارات تخص سياسات الإدخال، الحقول الإلزامية (الاسم، البريد الوظيفي، المسمى الوظيفي، الشركة، تاريخ التعيين)، وصيغ الهواتف المعتمدة عبر أداة hr_import_rules.

قواعدك الأساسية:
- تحدث دائماً باللغة العربية بأسلوب راقٍ واحترافي ومباشر.
- استخدم أدواتك دائماً لجلب البيانات الحقيقية من النظام بدلاً من التخمين.
- إذا طلب المستخدم اعتماد فحص معين بالاسم أو المعرف، نفذ ذلك عبر أداة الاعتماد وأخبره بالنتيجة وأرقام الموظفين الجدد التي تم إنشاؤها في Odoo.
"""

# 17. AI Agent Node
nodes.append({
    "parameters": {
        "promptType": "define",
        "text": "={{ $json.text }}",
        "options": {
            "systemMessage": AI_SYSTEM_PROMPT
        }
    },
    "name": "Odoo HR AI Agent",
    "type": "@n8n/n8n-nodes-langchain.agent",
    "typeVersion": 1.7,
    "position": [1160, 560],
    "id": "node-ai-agent"
})

# 18. OpenRouter Chat Model
nodes.append({
    "parameters": {
        "model": "qwen/qwen3.8-27b:free",
        "options": {
            "temperature": 0.2
        }
    },
    "name": "OpenRouter Chat Model",
    "type": "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
    "typeVersion": 1,
    "position": [960, 780],
    "id": "node-ai-model",
    "credentials": {
        "openRouterApi": {
            "id": "zqFny3jxESduKu51",
            "name": "n8n Assistant model"
        }
    }
})

# 19. Window Buffer Memory
nodes.append({
    "parameters": {
        "sessionKey": "telegram_admin_696492053",
        "contextWindowLength": 10
    },
    "name": "Window Buffer Memory",
    "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
    "typeVersion": 1.1,
    "position": [1160, 780],
    "id": "node-ai-memory"
})

# 20. Tool: Check Odoo Status
nodes.append({
    "parameters": {
        "name": "check_odoo_status",
        "description": "فحص حالة الاتصال بنظام Odoo ERP والشركة النشطة وحالة قاعدة البيانات",
        "jsCode": "let d;\ntry {\n  d = await (await fetch('http://host.docker.internal:8000/api/status')).json();\n} catch (e) {\n  d = { error: e.message };\n}\nreturn JSON.stringify(d);"
    },
    "name": "Tool: Odoo Status",
    "type": "@n8n/n8n-nodes-langchain.toolCode",
    "typeVersion": 1.1,
    "position": [1360, 760],
    "id": "node-tool-status"
})

# 21. Tool: List Recent Runs
nodes.append({
    "parameters": {
        "name": "list_recent_runs",
        "description": "جلب قائمة أحدث عمليات الفحص التجريبي لملفات الموظفين ومعرفات الفحص (run_id) وعدد المقبول والمرفوض",
        "jsCode": "let d;\ntry {\n  d = await (await fetch('http://host.docker.internal:8000/api/runs')).json();\n} catch (e) {\n  d = { error: e.message };\n}\nreturn JSON.stringify(d);"
    },
    "name": "Tool: Recent Runs",
    "type": "@n8n/n8n-nodes-langchain.toolCode",
    "typeVersion": 1.1,
    "position": [1520, 760],
    "id": "node-tool-runs"
})

# 22. Tool: Inspect Run Details
nodes.append({
    "parameters": {
        "name": "inspect_run_details",
        "description": "جلب تفاصيل فحص تجريبي معين بالكامل (أسباب الرفض، الصفوف المقبولة، التنبيهات) عبر معرف الفحص run_id. المدخل query هو معرف الفحص",
        "jsCode": "const runId = (typeof query === 'string' ? query : (query.run_id || '')).trim();\ntry {\n  const d = await (await fetch(`http://host.docker.internal:8000/api/runs/${encodeURIComponent(runId)}`)).json();\n  return JSON.stringify(d);\n} catch (e) {\n  return JSON.stringify({ error: `تعذر جلب تفاصيل الفحص ${runId}: ${e.message}` });\n}"
    },
    "name": "Tool: Inspect Run",
    "type": "@n8n/n8n-nodes-langchain.toolCode",
    "typeVersion": 1.1,
    "position": [1680, 760],
    "id": "node-tool-inspect"
})

# 23. Tool: Approve and Execute Import
nodes.append({
    "parameters": {
        "name": "approve_and_create_employees",
        "description": "اعتماد وإنشاء الموظفين المقبولين في نظام Odoo ERP للشركة 15. استخدم هذه الأداة عندما يطلب المستخدم صراحة اعتماد أو تنفيذ الفحص. المدخل هو معرف الفحص run_id",
        "jsCode": "const runId = (typeof query === 'string' ? query : (query.run_id || '')).trim();\ntry {\n  const res = await fetch('http://host.docker.internal:8000/api/approve-and-execute', {\n    method: 'POST',\n    headers: { 'Content-Type': 'application/json' },\n    body: JSON.stringify({ run_id: runId, approved_by: 'Telegram AI Assistant (User Confirmed)', company_id: 15, max_rows: 10 })\n  });\n  const d = await res.json();\n  return JSON.stringify(d);\n} catch (e) {\n  return JSON.stringify({ error: `فشل التنفيذ في Odoo: ${e.message}` });\n}"
    },
    "name": "Tool: Approve and Execute",
    "type": "@n8n/n8n-nodes-langchain.toolCode",
    "typeVersion": 1.1,
    "position": [1840, 760],
    "id": "node-tool-approve"
})

# 24. Tool: HR Import Rules
nodes.append({
    "parameters": {
        "name": "hr_import_rules",
        "description": "قواعد وشروط استيراد ملفات الإكسل للموظفين (الحقول الإلزامية، صيغة الهواتف، الأقسام، شروط القبول والرفض)",
        "jsCode": "return JSON.stringify({\n  required_fields: ['name (الاسم)', 'work_email (البريد الوظيفي)', 'job_title (المسمى الوظيفي)', 'company (اسم الشركة أو معرف 15)', 'hiring_date (تاريخ التعيين YYYY-MM-DD)'],\n  phone_rules: 'يجب أن يبدأ بـ 05 أو +966 ويتكون من 10 أرقام سعودية صحيحة',\n  email_rules: 'بريد فريد غير مكرر في Odoo أو داخل نفس الملف',\n  company_default: 'شركة النخبة الذكية للتقنية (معرف: 15)',\n  safety_rules: 'تطبيق قاعدة الشخصين للموافقة (Human Approval) وتحديد أقصى حد 10 موظفين عبر تيليقرام'\n});"
    },
    "name": "Tool: HR Rules",
    "type": "@n8n/n8n-nodes-langchain.toolCode",
    "typeVersion": 1.1,
    "position": [2000, 760],
    "id": "node-tool-rules"
})

# 25. Send AI Response to Telegram
nodes.append({
    "parameters": {
        "chatId": "={{ $('Route Event Type').first().json.chat_id }}",
        "text": "={{ $json.output }}",
        "additionalFields": {
            "parse_mode": "None",
            "appendAttribution": False
        }
    },
    "name": "Send AI Response",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [1460, 560],
    "id": "node-send-ai-response",
    "credentials": CREDENTIALS
})

# Connections Mapping
connections = {
    "Telegram": {
        "main": [[{"node": "Security & Event Parser", "type": "main", "index": 0}]]
    },
    "Security & Event Parser": {
        "main": [[{"node": "Is Authorized?", "type": "main", "index": 0}]]
    },
    "Is Authorized?": {
        "main": [
            [{"node": "Route Event Type", "type": "main", "index": 0}],
            [{"node": "Send Unauthorized", "type": "main", "index": 0}]
        ]
    },
    "Route Event Type": {
        "main": [
            [{"node": "Ack Upload", "type": "main", "index": 0}],
            [{"node": "Is Approve Action?", "type": "main", "index": 0}],
            [{"node": "Odoo HR AI Agent", "type": "main", "index": 0}]
        ]
    },
    # Excel Upload flow
    "Ack Upload": {
        "main": [[{"node": "Download Excel File", "type": "main", "index": 0}]]
    },
    "Download Excel File": {
        "main": [[{"node": "Run Dry-Run via API", "type": "main", "index": 0}]]
    },
    "Run Dry-Run via API": {
        "main": [[{"node": "Format Dry-Run Summary", "type": "main", "index": 0}]]
    },
    "Format Dry-Run Summary": {
        "main": [[{"node": "Has Accepted Rows?", "type": "main", "index": 0}]]
    },
    "Has Accepted Rows?": {
        "main": [
            [{"node": "Send Dry-Run Summary & Approval Buttons", "type": "main", "index": 0}],
            [{"node": "Send Rejection Notice", "type": "main", "index": 0}]
        ]
    },
    # Callback flow
    "Is Approve Action?": {
        "main": [
            [{"node": "Send Progress Update", "type": "main", "index": 0}],
            [{"node": "Send Cancel Confirmation", "type": "main", "index": 0}]
        ]
    },
    "Send Progress Update": {
        "main": [[{"node": "Execute in Odoo via API", "type": "main", "index": 0}]]
    },
    "Execute in Odoo via API": {
        "main": [[{"node": "Format Final Result", "type": "main", "index": 0}]]
    },
    "Format Final Result": {
        "main": [[{"node": "Send Final Confirmation", "type": "main", "index": 0}]]
    },
    # AI Agent Flow
    "Odoo HR AI Agent": {
        "main": [[{"node": "Send AI Response", "type": "main", "index": 0}]]
    },
    "OpenRouter Chat Model": {
        "ai_languageModel": [[{"node": "Odoo HR AI Agent", "type": "ai_languageModel", "index": 0}]]
    },
    "Window Buffer Memory": {
        "ai_memory": [[{"node": "Odoo HR AI Agent", "type": "ai_memory", "index": 0}]]
    },
    "Tool: Odoo Status": {
        "ai_tool": [[{"node": "Odoo HR AI Agent", "type": "ai_tool", "index": 0}]]
    },
    "Tool: Recent Runs": {
        "ai_tool": [[{"node": "Odoo HR AI Agent", "type": "ai_tool", "index": 0}]]
    },
    "Tool: Inspect Run": {
        "ai_tool": [[{"node": "Odoo HR AI Agent", "type": "ai_tool", "index": 0}]]
    },
    "Tool: Approve and Execute": {
        "ai_tool": [[{"node": "Odoo HR AI Agent", "type": "ai_tool", "index": 0}]]
    },
    "Tool: HR Rules": {
        "ai_tool": [[{"node": "Odoo HR AI Agent", "type": "ai_tool", "index": 0}]]
    }
}

workflow = {
    "id": "FnkQptJrIZaEsmCX",
    "name": "Odoo HR Agents - Telegram Inbound & Approval Workflow",
    "nodes": nodes,
    "connections": connections,
    "settings": {
        "executionOrder": "v1",
        "saveManualExecutions": True
    },
    "tags": [],
    "pinData": {}
}

out_path = Path(__file__).resolve().parent / "odoo_hr_telegram_workflow.json"
out_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"SUCCESS: Workflow written to {out_path} ({len(nodes)} nodes, {out_path.stat().st_size} bytes)")
