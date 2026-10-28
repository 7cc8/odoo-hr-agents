"""Confirming a pending write must be an explicit, exact answer. It used to be a prefix match, so
«تمام» and «نعمل على ذلك لاحقاً» (start with «تم» / «نعم») triggered the pending action, and any message that
merely contained a plan id counted as a confirmation."""
import time
from unittest.mock import MagicMock

import pytest

from fahas_service import FahasAgent
from katib_service import KatibAgent
from seraj_llm_service import SerajLLMService, classify_pending_reply
from seraj_session_manager import SerajSessionManager

PENDING = "plan_1700000000_abcdef12"


@pytest.mark.parametrize("text", [
    "تأكيد", "تاكيد", "اعتمد", "تأكيد العملية", "اعتمد التعديل", "تأكيد الإضافة",
    "  تأكيد  ", "تأكيد.", "تأكيد!", "تأكيد،", "التأكيد".replace("ال", ""), "تأكيد  \n",
])
def test_exact_confirmation_phrases_confirm(text):
    assert classify_pending_reply(text) == "confirm"


@pytest.mark.parametrize("text", [
    "تمام", "تم", "تمت", "نعمل على ذلك لاحقاً", "نعم", "موافق", "اعتمدت", "تأكيداً",
    "تأكيد الحذف النهائي لكل الموظفين", "ما أبغى أحذف هذا الموظف", "ok", "", "   ",
])
def test_acknowledgements_and_longer_sentences_do_not_confirm(text):
    assert classify_pending_reply(text) == "other"


@pytest.mark.parametrize("text", ["إلغاء", "الغاء", "لا", "لا تنفذ", "لا، ألغِ", "رفض", "Cancel", "تراجع عن العملية"])
def test_cancellation(text):
    assert classify_pending_reply(text) == "cancel"


@pytest.mark.parametrize("text", ["لاحقاً", "لازم أفكر", "لابد", "رفضت"])
def test_words_that_merely_start_with_a_cancel_word_are_not_cancellation(text):
    assert classify_pending_reply(text) == "other"


def test_plan_id_rules():
    assert classify_pending_reply(PENDING, PENDING) == "confirm"
    assert classify_pending_reply(f"تأكيد {PENDING}", PENDING) == "confirm"
    assert classify_pending_reply(f"ما أبغى {PENDING}", PENDING) == "other"       # mentioning the id is not consent
    assert classify_pending_reply("plan_9_deadbeef", PENDING) == "wrong_plan"
    assert classify_pending_reply(f"تأكيد {PENDING} plan_9_deadbeef", PENDING) == "wrong_plan"
    assert classify_pending_reply(PENDING, None) == "wrong_plan"                  # nothing pending under that id


# ---- through the real chat_turn (Katib mocked: we only care whether it is called) ----

@pytest.fixture
def chat():
    mgr = SerajSessionManager.get_instance()
    cid = "pending-confirmation-test"
    mgr.reset_session(cid)
    fahas, katib = MagicMock(spec=FahasAgent), MagicMock(spec=KatibAgent)
    rec = {"records": [{"id": 147, "name": "موظف اختبار", "active": True, "company_id": [15, "ش"]}], "records_count": 1}
    fahas.search_records.return_value = rec
    fahas.execute_query_task.return_value = rec
    katib.execute_approved_action.return_value = {"ok": True, "action": "archive"}
    seraj = SerajLLMService(api_key="sk-or-test", fahas_agent=fahas, katib_agent=katib)
    seraj.chat_turn("احذف الموظف رقم 147", chat_id=cid)
    seraj.chat_turn("أرشفة رقم 147", chat_id=cid)
    assert mgr.get_session(cid).pending_action, "setup: an archive plan should be pending"
    yield seraj, katib, mgr.get_session(cid), cid
    mgr.reset_session(cid)


@pytest.mark.parametrize("text", ["تمام", "نعمل على ذلك لاحقاً", "تم", "نعم", "موافق"])
def test_chat_does_not_execute_on_acknowledgements(chat, text):
    seraj, katib, session, cid = chat
    seraj.chat_turn(text, chat_id=cid)
    katib.execute_approved_action.assert_not_called()
    assert session.pending_action, "the plan stays pending; nothing was consumed or cancelled"


def test_chat_executes_only_on_the_exact_word(chat):
    seraj, katib, session, cid = chat
    seraj.chat_turn("تمام", chat_id=cid)
    katib.execute_approved_action.assert_not_called()
    seraj.chat_turn("تأكيد", chat_id=cid)
    katib.execute_approved_action.assert_called_once()
    assert katib.execute_approved_action.call_args.args[0]["record_id"] == 147


def test_chat_cancel_clears_the_pending_action(chat):
    seraj, katib, session, cid = chat
    seraj.chat_turn("لا تنفذ", chat_id=cid)
    katib.execute_approved_action.assert_not_called()
    assert not session.pending_action


def test_chat_wrong_plan_id_executes_nothing(chat):
    seraj, katib, session, cid = chat
    reply = seraj.chat_turn("تأكيد plan_9_deadbeef", chat_id=cid)
    katib.execute_approved_action.assert_not_called()
    assert "لا يطابق" in reply and session.pending_action
