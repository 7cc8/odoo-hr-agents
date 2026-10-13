"""
P3: Persistent Checkpointer Implementation
==========================================
File-based persistent checkpointer for durable state management
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint


class FilePersistentCheckpointer(MemorySaver):
    """
    File-based persistent checkpointer
    
    Extends MemorySaver but persists data to disk for durability
    P3 requirement: company_id و messages مرتبطان بـ thread_id
    """
    
    def __init__(self, checkpoint_dir: Optional[Path] = None):
        super().__init__()
        
        # إعداد مجلد الحفظ
        if checkpoint_dir is None:
            checkpoint_dir = Path(__file__).parent.parent / "checkpoints"
        
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # ملف للحفظ المستمر
        self.persistent_file = self.checkpoint_dir / "seraj_checkpoints.json"
        
        # قفل للـ thread safety
        self._lock = threading.Lock()
        
        # تحميل البيانات المحفوظة سابقاً
        self._load_from_disk()
    
    def _load_from_disk(self) -> None:
        """تحميل checkpoints المحفوظة من القرص"""
        if self.persistent_file.exists():
            try:
                with open(self.persistent_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # استرجاع البيانات إلى memory
                if 'storage' in data:
                    self.storage.update(data['storage'])
                
                print(f"✅ تم تحميل {len(self.storage)} checkpoint من {self.persistent_file}")
                
            except Exception as e:
                print(f"⚠️ خطأ في تحميل checkpoints من القرص: {e}")
    
    def _save_to_disk(self) -> None:
        """حفظ checkpoints الحالية إلى القرص"""
        try:
            # تحويل البيانات لصيغة قابلة للـ JSON serialization
            serializable_data = {
                'storage': {}
            }
            
            for key, checkpoint in self.storage.items():
                # تحويل Checkpoint object إلى dict
                serializable_data['storage'][key] = {
                    'v': checkpoint.v,
                    'ts': checkpoint.ts,
                    'channel_versions': checkpoint.channel_versions,
                    'versions_seen': checkpoint.versions_seen,
                }
            
            # حفظ مؤقت ثم إعادة تسمية للـ atomic operation
            temp_file = self.persistent_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            
            # atomic rename
            temp_file.rename(self.persistent_file)
            
        except Exception as e:
            print(f"⚠️ خطأ في حفظ checkpoints إلى القرص: {e}")
    
    def put(self, config: Dict[str, Any], checkpoint: Checkpoint) -> None:
        """حفظ checkpoint مع الكتابة المستمرة إلى القرص"""
        with self._lock:
            # استدعاء parent method
            super().put(config, checkpoint)
            
            # حفظ إلى القرص
            self._save_to_disk()
    
    def cleanup_old_checkpoints(self, max_age_days: int = 30) -> None:
        """
        تنظيف checkpoints قديمة
        
        Args:
            max_age_days: عدد الأيام للاحتفاظ بالـ checkpoints
        """
        import time
        
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        
        with self._lock:
            old_keys = []
            for key, checkpoint in self.storage.items():
                if checkpoint.ts < cutoff_time:
                    old_keys.append(key)
            
            # حذف checkpoints القديمة
            for key in old_keys:
                del self.storage[key]
            
            if old_keys:
                self._save_to_disk()
                print(f"✅ تم حذف {len(old_keys)} checkpoint قديم")


def get_persistent_checkpointer() -> FilePersistentCheckpointer:
    """
    إنشاء checkpointer دائم باستخدام ملف JSON
    
    P3 requirement: company_id و messages مرتبطان بـ thread_id
    ويجب أن يكون الحفظ دائماً وليس في الذاكرة فقط
    """
    return FilePersistentCheckpointer()


def get_checkpointer_for_environment() -> Optional[FilePersistentCheckpointer]:
    """
    حصول على checkpointer مناسب للبيئة الحالية
    
    Returns:
        - FilePersistentCheckpointer في الإنتاج والتطوير
        - None في langgraph dev (لأن dev server يوفر checkpointer خاص به)
    """
    import sys
    
    # فحص إذا كنا في langgraph dev / API environment
    # يوفر LangGraph dev server / Studio آلية حفظ خاصة به ويتطلب عدم تمرير checkpointer مخصص
    is_langgraph_dev = (
        os.environ.get("LANGGRAPH_ENV") == "dev"
        or "langgraph_api" in sys.modules
        or any("langgraph" in arg.lower() for arg in sys.argv)
    )
    
    if is_langgraph_dev:
        # langgraph dev server يوفر checkpointer خاص به
        return None
    
    # في البيئات الأخرى، نستخدم file-based persistent checkpointer
    return get_persistent_checkpointer()


# إضافة clean-up helper
def cleanup_old_checkpoints(days_to_keep: int = 30) -> None:
    """
    تنظيف checkpoints قديمة للحفاظ على حجم الملفات
    
    Args:
        days_to_keep: عدد الأيام للاحتفاظ بها
    """
    try:
        checkpointer = get_persistent_checkpointer()
        checkpointer.cleanup_old_checkpoints(days_to_keep)
        
        print(f"✅ تم تنظيف checkpoints أقدم من {days_to_keep} يوم")
        
    except Exception as e:
        print(f"⚠️ خطأ في تنظيف checkpoints: {e}")


if __name__ == "__main__":
    # اختبار سريع للـ checkpointer
    print("🔍 اختبار File-based persistent checkpointer...")
    
    try:
        checkpointer = get_persistent_checkpointer()
        print("✅ تم إنشاء persistent checkpointer بنجاح")
        
        # فحص path
        print(f"📁 مسار حفظ checkpoints: {checkpointer.checkpoint_dir}")
        
        if checkpointer.persistent_file.exists():
            size = checkpointer.persistent_file.stat().st_size
            print(f"💾 حجم ملف checkpoints: {size} bytes")
        
        print("✅ اختبار checkpointer اكتمل بنجاح")
        
    except Exception as e:
        print(f"❌ فشل اختبار checkpointer: {e}")