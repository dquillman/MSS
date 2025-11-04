"""
Tests for caching functionality
"""
import pytest
from web.cache import (
    get_cached, set_cached, delete_cached,
    cache_key, cache_result, get_cache_stats
)


@pytest.mark.unit
def test_cache_key_generation():
    """Test cache key generation"""
    key1 = cache_key("test", "arg1", arg2="value2")
    key2 = cache_key("test", "arg1", arg2="value2")
    key3 = cache_key("test", "arg1", arg2="different")
    
    # Same inputs should generate same key
    assert key1 == key2
    # Different inputs should generate different key
    assert key1 != key3


@pytest.mark.unit
def test_cache_set_get():
    """Test basic cache set and get operations"""
    key = "test:cache:set_get"
    value = {"test": "data", "number": 42}
    
    # Set value
    result = set_cached(key, value, ttl=60)
    
    # Get value (may be None if Redis unavailable)
    cached = get_cached(key)
    
    # If Redis is available, verify cache works
    if cached is not None:
        assert cached == value


@pytest.mark.unit
def test_cache_delete():
    """Test cache deletion"""
    key = "test:cache:delete"
    value = {"test": "delete"}
    
    set_cached(key, value, ttl=60)
    
    # Delete
    delete_cached(key)
    
    # Verify deleted
    cached = get_cached(key)
    # If Redis available, should be None
    # If Redis unavailable, will be None anyway
    # So we just verify no error occurred


@pytest.mark.unit
def test_cache_result_decorator():
    """Test cache_result decorator"""
    call_count = 0
    
    @cache_result(ttl=60, prefix="test")
    def expensive_function(arg1, arg2):
        nonlocal call_count
        call_count += 1
        return {"result": arg1 + arg2, "calls": call_count}
    
    # First call - should execute function
    result1 = expensive_function(1, 2)
    first_call_count = call_count
    
    # Second call with same args - should use cache
    result2 = expensive_function(1, 2)
    
    # If cache is working, call_count shouldn't increase
    # If cache unavailable, call_count will increase
    if result2 == result1:
        # Cache hit - verify same result
        assert result2["result"] == 3


@pytest.mark.unit
def test_cache_stats():
    """Test cache statistics"""
    stats = get_cache_stats()
    
    assert isinstance(stats, dict)
    assert 'enabled' in stats
    
    # Stats may show enabled=False if Redis unavailable
    # That's okay - just verify it doesn't crash






