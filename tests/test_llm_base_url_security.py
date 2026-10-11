"""
اختبار أمان LLM_BASE_URL
==========================
يتحقق من أن seraj_llm_service يرفض عناوين URL خارجية
إلا إذا كان LLM_ALLOW_REMOTE=1
"""
import os
import pytest
from seraj_llm_service import SerajLLMService


def test_llm_base_url_localhost_allowed():
    """localhost مسموح بدون LLM_ALLOW_REMOTE"""
    os.environ["LLM_BASE_URL"] = "http://localhost:11434/v1"
    os.environ["LLM_MODEL"] = "llama3.2"
    os.environ.pop("LLM_ALLOW_REMOTE", None)  # تأكد أنه غير مضبوط
    
    svc = SerajLLMService(api_key="test-key")
    
    # يجب أن لا يرفع خطأ عند استدعاء _call_openrouter
    # (سيفشل في urlopen لكن لن يرفع ValueError من فحص الأمان)
    try:
        svc._call_openrouter("llama3.2", [{"role": "user", "content": "test"}])
    except ValueError as e:
        if "خادم خارجي" in str(e):
            pytest.fail(f"localhost يجب أن يكون مسموحاً: {e}")
        # أخطاء أخرى (urlopen فشل) مقبولة
    except Exception:
        pass  # أخطاء الاتصال مقبولة


def test_llm_base_url_127_allowed():
    """127.0.0.1 مسموح بدون LLM_ALLOW_REMOTE"""
    os.environ["LLM_BASE_URL"] = "http://127.0.0.1:11434/v1"
    os.environ["LLM_MODEL"] = "llama3.2"
    os.environ.pop("LLM_ALLOW_REMOTE", None)
    
    svc = SerajLLMService(api_key="test-key")
    
    try:
        svc._call_openrouter("llama3.2", [{"role": "user", "content": "test"}])
    except ValueError as e:
        if "خادم خارجي" in str(e):
            pytest.fail(f"127.0.0.1 يجب أن يكون مسموحاً: {e}")
    except Exception:
        pass


def test_llm_base_url_remote_blocked():
    """عنوان خارجي يُرفض بدون LLM_ALLOW_REMOTE=1"""
    os.environ["LLM_BASE_URL"] = "http://example.com:11434/v1"
    os.environ["LLM_MODEL"] = "llama3.2"
    os.environ.pop("LLM_ALLOW_REMOTE", None)
    
    svc = SerajLLMService(api_key="test-key")
    
    with pytest.raises(ValueError) as exc_info:
        svc._call_openrouter("llama3.2", [{"role": "user", "content": "test"}])
    
    assert "خادم خارجي" in str(exc_info.value)
    assert "example.com" in str(exc_info.value)
    assert "LLM_ALLOW_REMOTE=1" in str(exc_info.value)


def test_llm_base_url_remote_allowed_with_flag():
    """عنوان خارجي مسموح مع LLM_ALLOW_REMOTE=1"""
    os.environ["LLM_BASE_URL"] = "http://example.com:11434/v1"
    os.environ["LLM_MODEL"] = "llama3.2"
    os.environ["LLM_ALLOW_REMOTE"] = "1"
    
    svc = SerajLLMService(api_key="test-key")
    
    # يجب أن لا يرفع ValueError من فحص الأمان
    try:
        svc._call_openrouter("llama3.2", [{"role": "user", "content": "test"}])
    except ValueError as e:
        if "خادم خارجي" in str(e):
            pytest.fail(f"عنوان خارجي يجب أن يكون مسموحاً مع LLM_ALLOW_REMOTE=1: {e}")
    except Exception:
        pass  # أخطاء الاتصال مقبولة
    finally:
        os.environ.pop("LLM_ALLOW_REMOTE", None)


def test_llm_base_url_ipv6_localhost_allowed():
    """::1 (IPv6 localhost) مسموح"""
    os.environ["LLM_BASE_URL"] = "http://[::1]:11434/v1"
    os.environ["LLM_MODEL"] = "llama3.2"
    os.environ.pop("LLM_ALLOW_REMOTE", None)
    
    svc = SerajLLMService(api_key="test-key")
    
    try:
        svc._call_openrouter("llama3.2", [{"role": "user", "content": "test"}])
    except ValueError as e:
        if "خادم خارجي" in str(e):
            pytest.fail(f"::1 يجب أن يكون مسموحاً: {e}")
    except Exception:
        pass
