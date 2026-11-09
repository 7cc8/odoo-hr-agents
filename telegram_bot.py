"""Interactive Telegram Bot for Odoo HR Agents (Phase 7).

Allows authorized HR personnel to:
1. Send an Excel template directly in Telegram chat from desktop or mobile.
2. Execute dry-run automatically without modifying parser or validator logic.
3. Receive formatted inspection summary and interactive Inline Keyboard buttons.
4. Authorize creation with written confirmation ("تأكيد") to prevent accidental triggers (Section 5.1).
5. Calls the centralized Backend API (/write) rather than running writer directly (Section 5.2).
6. Strictly enforces silent rejection on unauthorized chat IDs (Section 5.2).
7. Maintains a dedicated interaction audit log in logs/telegram_audit.log.

Backward-compatible Facade module delegating to the modular `bot` package.
"""
from __future__ import annotations

import os
import sys

# Re-export all symbols from bot package
from bot import *
from bot.client import (
    TelegramBotClient,
    get_ssl_context,
    _build_ssl_context,
    log_telegram_audit,
    get_allowed_users,
    is_user_authorized,
    is_autofix_enabled,
    set_autofix_enabled,
    PENDING_CONFIRMATIONS,
    ACTIVE_CONFIG_WIZARDS,
    PENDING_LEAVE_CONFIRMATIONS,
    ACTIVE_LEAVE_WIZARDS,
    PENDING_ATTENDANCE_CONFIRMATIONS,
    ACTIVE_ATTENDANCE_WIZARDS,
    PENDING_DISCIPLINARY_CONFIRMATIONS,
    ACTIVE_DISCIPLINARY_WIZARDS,
    PENDING_EOS_CONFIRMATIONS,
    ACTIVE_EOS_WIZARDS,
    PENDING_GR_CONFIRMATIONS,
    ACTIVE_GR_WIZARDS,
    PENDING_APPRAISAL_CONFIRMATIONS,
    ACTIVE_APPRAISAL_WIZARDS,
    PENDING_LOAN_CONFIRMATIONS,
    ACTIVE_LOAN_WIZARDS,
    PENDING_RECRUITMENT_CONFIRMATIONS,
    ACTIVE_RECRUITMENT_WIZARDS,
    PENDING_CONTRACT_CONFIRMATIONS,
    ACTIVE_CONTRACT_WIZARDS,
    PENDING_PAYROLL_CONFIRMATIONS,
    ACTIVE_PAYROLL_WIZARDS,
    ACTIVE_ANALYTICS_WIZARDS,
    PENDING_LETTER_CONFIRMATIONS,
    ACTIVE_LETTER_WIZARDS,
    PENDING_WARNING_CONFIRMATIONS,
    ACTIVE_WARNING_WIZARDS,
    PENDING_EXPENSE_CONFIRMATIONS,
    ACTIVE_EXPENSE_WIZARDS,
    AUTOFIX_ENABLED_BY_CHAT,
    DEFAULT_COMPANY_ID,
    DEFAULT_MAX_ROWS,
    WRITE_API_TOKEN,
    API_BASE_URL,
    UPLOAD_DIR,
    LOGS_DIR,
    TG_AUDIT_LOG_FILE,
)

if __name__ == "__main__":
    run_telegram_bot_polling()
