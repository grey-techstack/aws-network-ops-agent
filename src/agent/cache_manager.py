"""Cache manager for tool results."""

import hashlib
import json
import time
from typing import Any, Dict, Optional


class CacheManager:
    """Manages caching of tool execution results with session-based expiration."""
    
    def __init__(self, session_ttl_seconds: int = 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._session_ttl = session_ttl_seconds

    def _generate_cache_key(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """Generate a unique cache key based on tool name and parameters."""
        sorted_params = json.dumps(parameters, sort_keys=True)
        key_string = f"{tool_name}:{sorted_params}"
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def get(self, tool_name: str, parameters: Dict[str, Any]) -> Optional[Any]:
        """Retrieve a cached result if it exists and hasn't expired."""
        cache_key = self._generate_cache_key(tool_name, parameters)
        
        if cache_key not in self._cache:
            return None
        
        cache_entry = self._cache[cache_key]
        
        # Check if entry has expired
        if time.time() > cache_entry["expires_at"]:
            del self._cache[cache_key]
            return None
        
        return cache_entry["result"]
    
    def set(self, tool_name: str, parameters: Dict[str, Any], result: Any) -> None:
        """Store a tool execution result in the cache."""
        cache_key = self._generate_cache_key(tool_name, parameters)
        
        self._cache[cache_key] = {
            "tool_name": tool_name,
            "parameters": parameters,
            "result": result,
            "cached_at": time.time(),
            "expires_at": time.time() + self._session_ttl
        }
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
    
    def clear_expired(self) -> int:
        """Remove all expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if current_time > entry["expires_at"]
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        current_time = time.time()
        active_entries = sum(
            1 for entry in self._cache.values()
            if current_time <= entry["expires_at"]
        )
        
        return {
            "total_entries": len(self._cache),
            "active_entries": active_entries,
            "expired_entries": len(self._cache) - active_entries
        }
