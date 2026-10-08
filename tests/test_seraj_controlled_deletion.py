import time, unittest
from unittest.mock import MagicMock, patch
from deletion_policy import create_deletion_plan, DeletionPolicyError
from fahas_service import FahasAgent
from katib_service import KatibAgent
from seraj_llm_service import SerajLLMService
from seraj_session_manager import SerajSessionManager


class TestSerajControlledDeletion(unittest.TestCase):
    def setUp(self):
        self.session_mgr = SerajSessionManager.get_instance()
        self.chat_id = 'test_del_88'
        self.session_mgr.reset_session(self.chat_id)
        self.mock_fahas = MagicMock(spec=FahasAgent)
        self.mock_katib = MagicMock(spec=KatibAgent)
        self.seraj = SerajLLMService(api_key='sk-or-test', fahas_agent=self.mock_fahas, katib_agent=self.mock_katib)

    def tearDown(self):
        self.session_mgr.reset_session(self.chat_id)

    def test_1_ambiguous_delete_asks_clarification(self):
        resp = self.seraj.chat_turn('احذف سارة', chat_id=self.chat_id)
        self.assertIn('توضيح', resp)
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNone(session.pending_action)
        self.assertIsNotNone(session.pending_clarification)
        self.assertEqual(session.pending_clarification.get('type'), 'clarify_delete_or_archive')
        self.mock_fahas.search_records.assert_not_called()
        self.mock_katib.execute_approved_action.assert_not_called()

    def test_2_multiple_matches_asks_for_id_selection(self):
        self.mock_fahas.search_records.return_value = {
            'records': [
                {'id': 10, 'name': 'سارة عبدالله', 'job_title': 'اخصائية', 'company_id': [15, 'النخبة']},
                {'id': 25, 'name': 'سارة الغامدي', 'job_title': 'مسؤولة', 'company_id': [15, 'النخبة']},
            ],
            'records_count': 2,
        }
        resp = self.seraj.chat_turn('حذف نهائي سارة', chat_id=self.chat_id)
        self.assertIn('تعدد', resp)
        self.assertIn('10', resp)
        self.assertIn('25', resp)
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNone(session.pending_action)
        self.mock_katib.execute_approved_action.assert_not_called()

    def test_3_user_cancellation_stops_execution(self):
        self.mock_fahas.search_records.return_value = {
            'records': [{'id': 7, 'name': 'فهد الاحمدي', 'job_title': 'مبرمج', 'company_id': [15, 'النخبة'], 'active': True}],
            'records_count': 1,
        }
        resp1 = self.seraj.chat_turn('ارشفة فهد', chat_id=self.chat_id)
        self.assertIn('انتظار', resp1)
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNotNone(session.pending_action)
        resp2 = self.seraj.chat_turn('الغاء', chat_id=self.chat_id)
        self.assertIn('الغاء', resp2.lower().replace('إ','ا'))
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNone(session.pending_action)
        self.mock_katib.execute_approved_action.assert_not_called()

    def test_4_expired_approval_ttl_rejected(self):
        session = self.session_mgr.get_session(self.chat_id)
        session.pending_action = {
            'action_type': 'archive', 'model': 'hr.employee', 'record_id': 5,
            'record_name': 'اختبار منتهي', 'plan_id': 'abc123',
            'expires_at': time.time() - 10, 'consumed': False,
            'user_id': str(self.chat_id),
        }
        resp = self.seraj.chat_turn('تاكيد', chat_id=self.chat_id)
        self.assertIn('انتهت', resp)
        self.assertIsNone(session.pending_action)
        self.mock_katib.execute_approved_action.assert_not_called()

    def test_5_consumed_token_reuse_rejected(self):
        session = self.session_mgr.get_session(self.chat_id)
        session.pending_action = {
            'action_type': 'delete', 'model': 'hr.employee', 'record_id': 9,
            'record_name': 'تجريبي', 'plan_id': 'xyz999',
            'expires_at': time.time() + 300, 'consumed': True,
            'user_id': str(self.chat_id),
        }
        resp = self.seraj.chat_turn('تاكيد', chat_id=self.chat_id)
        self.assertIn('استهلاك', resp)
        self.mock_katib.execute_approved_action.assert_not_called()

    def test_6_disallowed_model_rejected(self):
        resp = self.seraj.chat_turn('حذف نهائي المستخدم', chat_id=self.chat_id)
        self.assertIn('سياسة', resp)
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNone(session.pending_action)

    def test_7_odoo_rejection_stops_without_cascade(self):
        session = self.session_mgr.get_session(self.chat_id)
        session.pending_action = {
            'action_type': 'delete', 'model': 'hr.employee', 'record_id': 42,
            'record_name': 'موظف مرتبط', 'plan_id': 'fk001',
            'model_label': 'سجل الموظفين (hr.employee)',
            'expires_at': time.time() + 300, 'consumed': False,
            'user_id': str(self.chat_id), 'connection_id': 'default',
        }
        self.mock_katib.execute_approved_action.return_value = {
            'ok': False, 'status': 'odoo_rejected',
            'error': 'FOREIGN KEY CONSTRAINT: hr.payslip references this employee',
        }
        resp = self.seraj.chat_turn('تاكيد', chat_id=self.chat_id)
        self.mock_katib.execute_approved_action.assert_called_once()
        self.assertIn('رفض', resp)

    def test_8_successful_archiving_with_fahas_verification(self):
        self.mock_fahas.search_records.return_value = {
            'records': [{'id': 20, 'name': 'نورة خالد', 'job_title': 'مساعدة', 'company_id': [15, 'النخبة'], 'active': True}],
            'records_count': 1,
        }
        resp1 = self.seraj.chat_turn('ارشفة نورة خالد', chat_id=self.chat_id)
        self.assertIn('انتظار', resp1)
        self.mock_katib.execute_approved_action.return_value = {'ok': True, 'action': 'archive', 'record_id': 20}
        self.mock_fahas.verify_record_status.return_value = {
            'verified': True, 'state': 'archived',
            'record': {'id': 20, 'name': 'نورة خالد', 'active': False},
        }
        resp2 = self.seraj.chat_turn('تاكيد', chat_id=self.chat_id)
        self.mock_katib.execute_approved_action.assert_called_once()
        self.mock_fahas.verify_record_status.assert_called_once_with(
            model='hr.employee', record_id=20,
            expected_state='archived', connection_id='default',
        )
        self.assertIn('فاحص', resp2)
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNone(session.pending_action)

    def test_9_successful_delete_with_fahas_verification(self):
        session = self.session_mgr.get_session(self.chat_id)
        session.pending_action = {
            'action_type': 'delete', 'model': 'hr.employee', 'record_id': 99,
            'record_name': 'موظف تجريبي', 'plan_id': 'del999',
            'model_label': 'سجل الموظفين (hr.employee)',
            'expires_at': time.time() + 300, 'consumed': False,
            'user_id': str(self.chat_id), 'connection_id': 'default',
        }
        self.mock_katib.execute_approved_action.return_value = {'ok': True, 'action': 'delete', 'model': 'hr.employee', 'record_id': 99}
        self.mock_fahas.verify_record_status.return_value = {'verified': True, 'state': 'deleted'}
        resp = self.seraj.chat_turn('تاكيد', chat_id=self.chat_id)
        self.mock_katib.execute_approved_action.assert_called_once()
        self.mock_fahas.verify_record_status.assert_called_once_with(
            model='hr.employee', record_id=99, expected_state='deleted', connection_id='default',
        )
        self.assertIn('الحذف النهائي', resp)
        self.assertIn('فاحص', resp)

    def test_10_fahas_inconclusive_on_connection_error(self):
        session = self.session_mgr.get_session(self.chat_id)
        session.pending_action = {
            'action_type': 'delete', 'model': 'hr.employee', 'record_id': 55,
            'record_name': 'موظف للاختبار', 'plan_id': 'inc001',
            'model_label': 'سجل الموظفين (hr.employee)',
            'expires_at': time.time() + 300, 'consumed': False,
            'user_id': str(self.chat_id), 'connection_id': 'default',
        }
        self.mock_katib.execute_approved_action.return_value = {'ok': True, 'action': 'delete', 'model': 'hr.employee', 'record_id': 55}
        self.mock_fahas.verify_record_status.return_value = {
            'verified': False, 'state': 'inconclusive',
            'error': 'Connection timeout',
            'message': 'نتيجة التحقق غير محسومة بسبب تعذر الاتصال',
        }
        resp = self.seraj.chat_turn('تاكيد', chat_id=self.chat_id)
        self.assertIn('غير محسومة', resp)
        self.assertNotIn('تم الحذف النهائي', resp)


class TestDeletionPolicyUnit(unittest.TestCase):
    def test_create_plan_ok(self):
        plan = create_deletion_plan(
            action_type='delete', model='hr.employee', record_id=42,
            record_name='موظف', company_id=15, user_id='u1',
        )
        self.assertEqual(plan.count, 1)
        self.assertFalse(plan.consumed)
        self.assertGreater(plan.expires_at, time.time())

    def test_plan_ttl_expires(self):
        plan = create_deletion_plan(action_type='archive', model='hr.employee', record_id=7, record_name='t', user_id='u2')
        plan.expires_at = time.time() - 1
        valid, msg = plan.is_valid(current_user_id='u2')
        self.assertFalse(valid)
        self.assertIn('انتهت', msg)

    def test_plan_consumed(self):
        plan = create_deletion_plan(action_type='archive', model='hr.employee', record_id=8, record_name='t', user_id='u3')
        plan.consumed = True
        valid, msg = plan.is_valid(current_user_id='u3')
        self.assertFalse(valid)
        self.assertIn('استهلاك', msg)

    def test_disallowed_model_raises(self):
        with self.assertRaises(DeletionPolicyError):
            create_deletion_plan(action_type='delete', model='res.users', record_id=1, record_name='x', user_id='u4')

    def test_invalid_record_id_raises(self):
        with self.assertRaises(DeletionPolicyError):
            create_deletion_plan(action_type='archive', model='hr.employee', record_id=-1, record_name='y', user_id='u5')


class TestFahasVerifyRecordStatus(unittest.TestCase):
    def _get_fahas(self):
        return FahasAgent.get_instance()

    def test_archived_success(self):
        fahas = self._get_fahas()
        with patch.object(fahas, 'search_records', return_value={'records': [{'id': 5, 'active': False}], 'records_count': 1}):
            r = fahas.verify_record_status(model='hr.employee', record_id=5, expected_state='archived')
        self.assertTrue(r['verified'])
        self.assertEqual(r['state'], 'archived')

    def test_deleted_success(self):
        fahas = self._get_fahas()
        with patch.object(fahas, 'count_records', return_value={'count': 0}):
            r = fahas.verify_record_status(model='hr.employee', record_id=5, expected_state='deleted')
        self.assertTrue(r['verified'])
        self.assertEqual(r['state'], 'deleted')

    def test_inconclusive_on_error(self):
        fahas = self._get_fahas()
        with patch.object(fahas, 'search_records', side_effect=Exception('timeout')):
            r = fahas.verify_record_status(model='hr.employee', record_id=5, expected_state='archived')
        self.assertFalse(r['verified'])
        self.assertEqual(r['state'], 'inconclusive')

    def test_still_active_not_verified(self):
        fahas = self._get_fahas()
        with patch.object(fahas, 'search_records', return_value={'records': [{'id': 5, 'active': True}], 'records_count': 1}):
            r = fahas.verify_record_status(model='hr.employee', record_id=5, expected_state='archived')
        self.assertFalse(r['verified'])
        self.assertEqual(r['state'], 'still_active')


if __name__ == '__main__':
    unittest.main()
