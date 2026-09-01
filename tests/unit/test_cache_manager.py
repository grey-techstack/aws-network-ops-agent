"""Unit tests for CacheManager."""

import time
import pytest
from src.agent.cache_manager import CacheManager


class TestCacheManager:
    """Test suite for CacheManager class."""
    
    def test_cache_key_generation_consistency(self):
        """Test that same parameters generate same cache key."""
        manager = CacheManager()
        
        params1 = {"fqdn": "demo.example.com", "account_id": "123456"}
        params2 = {"account_id": "123456", "fqdn": "demo.example.com"}
        
        key1 = manager._generate_cache_key("route53", params1)
        key2 = manager._generate_cache_key("route53", params2)
        
        assert key1 == key2
    
    def test_cache_key_generation_uniqueness(self):
        """Test that different parameters generate different cache keys."""
        manager = CacheManager()
        
        params1 = {"fqdn": "demo.example.com"}
        params2 = {"fqdn": "test.example.com"}
        
        key1 = manager._generate_cache_key("route53", params1)
        key2 = manager._generate_cache_key("route53", params2)
        
        assert key1 != key2
    
    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        manager = CacheManager()
        
        tool_name = "route53"
        parameters = {"fqdn": "demo.example.com"}
        result = {"hosted_zone_id": "Z123", "records": []}
        
        manager.set(tool_name, parameters, result)
        cached_result = manager.get(tool_name, parameters)
        
        assert cached_result == result
    
    def test_cache_miss(self):
        """Test that cache returns None for non-existent entries."""
        manager = CacheManager()
        
        result = manager.get("route53", {"fqdn": "nonexistent.com"})
        
        assert result is None
    
    def test_cache_expiration(self):
        """Test that cache entries expire after TTL."""
        manager = CacheManager(session_ttl_seconds=1)
        
        tool_name = "route53"
        parameters = {"fqdn": "demo.example.com"}
        result = {"hosted_zone_id": "Z123"}
        
        manager.set(tool_name, parameters, result)
        
        # Should be cached immediately
        assert manager.get(tool_name, parameters) == result
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        assert manager.get(tool_name, parameters) is None
    
    def test_cache_clear(self):
        """Test that clear removes all cache entries."""
        manager = CacheManager()
        
        manager.set("route53", {"fqdn": "demo.example.com"}, {"result": "data1"})
        manager.set("cloudfront", {"distribution_id": "E123"}, {"result": "data2"})
        
        assert manager.get("route53", {"fqdn": "demo.example.com"}) is not None
        assert manager.get("cloudfront", {"distribution_id": "E123"}) is not None
        
        manager.clear()
        
        assert manager.get("route53", {"fqdn": "demo.example.com"}) is None
        assert manager.get("cloudfront", {"distribution_id": "E123"}) is None
    
    def test_clear_expired(self):
        """Test that clear_expired removes only expired entries."""
        manager = CacheManager(session_ttl_seconds=1)
        
        # Add entry that will expire
        manager.set("route53", {"fqdn": "old.com"}, {"result": "old"})
        
        time.sleep(1.1)
        
        # Add entry that won't expire
        manager.set("route53", {"fqdn": "new.com"}, {"result": "new"})
        
        removed_count = manager.clear_expired()
        
        assert removed_count == 1
        assert manager.get("route53", {"fqdn": "old.com"}) is None
        assert manager.get("route53", {"fqdn": "new.com"}) == {"result": "new"}
    
    def test_cache_stats(self):
        """Test cache statistics reporting."""
        manager = CacheManager(session_ttl_seconds=1)
        
        manager.set("route53", {"fqdn": "demo1.com"}, {"result": "data1"})
        manager.set("route53", {"fqdn": "demo2.com"}, {"result": "data2"})
        
        stats = manager.get_cache_stats()
        
        assert stats["total_entries"] == 2
        assert stats["active_entries"] == 2
        assert stats["expired_entries"] == 0
        
        # Wait for expiration
        time.sleep(1.1)
        
        stats = manager.get_cache_stats()
        
        assert stats["total_entries"] == 2
        assert stats["active_entries"] == 0
        assert stats["expired_entries"] == 2
    
    def test_different_tools_same_params(self):
        """Test that different tools with same params have different cache entries."""
        manager = CacheManager()
        
        params = {"name": "test"}
        
        manager.set("tool1", params, {"result": "from_tool1"})
        manager.set("tool2", params, {"result": "from_tool2"})
        
        assert manager.get("tool1", params) == {"result": "from_tool1"}
        assert manager.get("tool2", params) == {"result": "from_tool2"}
