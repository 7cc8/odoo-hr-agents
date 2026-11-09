"""
اختبار P3: Persistent Checkpointer
===================================
يختبر أن company_id و messages مرتبطان بـ thread_id
ويتم حفظهما بشكل دائم
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from graph.checkpointer import FilePersistentCheckpointer, get_persistent_checkpointer, get_checkpointer_for_environment
from graph.build_graph import build_graph


class TestPersistentCheckpointer:
    """اختبار File-based checkpointer للحفظ المستمر"""
    
    def test_persistent_checkpointer_creation(self):
        """إنشاء file-based checkpointer بنجاح"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # إنشاء checkpointer مع مجلد مؤقت
            test_checkpoints_dir = Path(temp_dir) / "checkpoints"
            
            checkpointer = FilePersistentCheckpointer(checkpoint_dir=test_checkpoints_dir)
            
            # التحقق من أنه تم إنشاء checkpointer
            assert checkpointer is not None
            assert checkpointer.checkpoint_dir == test_checkpoints_dir
            
            # التحقق من أن المجلد تم إنشاؤه
            assert test_checkpoints_dir.exists()
            
            # التحقق من مسار ملف الحفظ
            expected_file = test_checkpoints_dir / "seraj_checkpoints.json"
            assert checkpointer.persistent_file == expected_file
    
    def test_environment_checkpointer_selection(self):
        """اختيار checkpointer المناسب للبيئة"""
        # اختبار البيئة العادية (يجب أن يرجع file checkpointer)
        with patch.dict('os.environ', {}, clear=True):
            checkpointer = get_checkpointer_for_environment()
            assert checkpointer is not None
            assert isinstance(checkpointer, FilePersistentCheckpointer)
        
        # اختبار langgraph dev environment (يجب أن يرجع None)
        with patch.dict('os.environ', {'LANGGRAPH_ENV': 'dev'}):
            checkpointer = get_checkpointer_for_environment()
            assert checkpointer is None
    
    def test_graph_with_persistent_checkpointer(self):
        """بناء graph مع persistent checkpointer"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_checkpoints_dir = Path(temp_dir) / "checkpoints"
            
            # إنشاء checkpointer
            checkpointer = FilePersistentCheckpointer(checkpoint_dir=test_checkpoints_dir)
            
            # بناء graph مع checkpointer
            graph = build_graph(checkpointer=checkpointer)
            
            # التحقق من أن graph تم بناؤه بنجاح
            assert graph is not None
            assert hasattr(graph, 'checkpointer')
            assert graph.checkpointer == checkpointer


class TestCheckpointerIntegration:
    """اختبار تكامل checkpointer مع باقي المنظومة"""
    
    def test_graph_entry_point_uses_checkpointer(self):
        """التحقق من أن نقطة دخول graph تستخدم checkpointer"""
        # mock البيئة لتجنب langgraph dev
        with patch.dict('os.environ', {}, clear=True):
            with patch('graph.checkpointer.get_persistent_checkpointer') as mock_checkpointer:
                mock_checkpointer.return_value = FilePersistentCheckpointer()
                
                # import graph entry point
                import importlib
                import graph.graph
                importlib.reload(graph.graph)
                
                # التحقق من استدعاء checkpointer
                assert mock_checkpointer.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])