"""LLM caching configuration for the evaluator.

This module provides centralized caching setup for all LLM calls in the evaluator.
Uses LiteLLM's built-in disk caching to reduce API costs and speed up repeated runs.
"""

import os
import litellm
from pathlib import Path
from typing import Optional

# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


# Global flags to track cache state
_cache_initialized = False
_cache_disabled = False


def disable_cache(verbose: bool = True) -> None:
    """Globally disable LLM caching.
    
    Call this BEFORE any init_cache() calls to prevent caching.
    Once disabled, init_cache() becomes a no-op.
    
    Args:
        verbose: Whether to print status message
    """
    global _cache_disabled
    _cache_disabled = True
    if verbose:
        print(f"{Colors.YELLOW}⚠ LLM caching disabled globally{Colors.RESET}")


def is_cache_disabled() -> bool:
    """Check if caching has been globally disabled."""
    return _cache_disabled


def get_cache_dir() -> Path:
    """Get the cache directory path.
    
    Returns:
        Path to the cache directory (defaults to .litellm_cache in project root)
    """
    cache_dir = os.getenv("LITELLM_CACHE_DIR", ".litellm_cache")
    return Path(cache_dir)


def init_cache(
    cache_type: str = "disk",
    cache_dir: Optional[str] = None,
    ttl: Optional[int] = None,
    verbose: bool = True
) -> bool:
    """Initialize LiteLLM caching.
    
    This should be called once at startup. Subsequent calls are no-ops.
    If caching has been globally disabled via disable_cache() or the
    LITELLM_CACHE_DISABLED environment variable is set to "true", this is a no-op.
    
    Args:
        cache_type: Type of cache ("disk", "redis", "s3", or "local" for in-memory)
        cache_dir: Directory for disk cache (default: .litellm_cache)
        ttl: Time-to-live for cache entries in seconds (default: None = forever)
        verbose: Whether to print cache initialization status
        
    Returns:
        True if cache was initialized, False if already initialized or disabled
    """
    global _cache_initialized, _cache_disabled
    
    # Check environment variable for cache disable
    env_disabled = os.getenv("LITELLM_CACHE_DISABLED", "").lower() in ("true", "1", "yes")
    if env_disabled and not _cache_disabled:
        _cache_disabled = True
        if verbose:
            print(f"{Colors.YELLOW}⚠ LLM caching disabled via LITELLM_CACHE_DISABLED{Colors.RESET}")
    
    # Respect global disable flag
    if _cache_disabled:
        return False
    
    if _cache_initialized:
        if verbose:
            print(f"{Colors.YELLOW}⚠ LLM cache already initialized{Colors.RESET}")
        return False
    
    # Set cache directory
    if cache_dir is None:
        cache_dir = str(get_cache_dir())
    
    # Ensure cache directory exists for disk cache
    if cache_type == "disk":
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
    
    # Configure LiteLLM cache
    cache_params = {
        "type": cache_type,
    }
    
    if cache_type == "disk":
        cache_params["disk_cache_dir"] = cache_dir
    
    if ttl is not None:
        cache_params["ttl"] = ttl
    
    # Initialize the cache
    litellm.cache = litellm.Cache(**cache_params)
    
    # Enable caching globally
    litellm.enable_cache()
    
    _cache_initialized = True
    
    if verbose:
        print(f"{Colors.GREEN}✓ LLM caching enabled{Colors.RESET}")
        print(f"  Type: {cache_type}")
        if cache_type == "disk":
            print(f"  Directory: {cache_dir}")
        if ttl:
            print(f"  TTL: {ttl}s")
    
    return True


def is_cache_enabled() -> bool:
    """Check if caching is currently enabled.
    
    Returns:
        True if caching is enabled
    """
    return _cache_initialized and litellm.cache is not None


def get_cache_stats() -> dict:
    """Get cache statistics (if available).
    
    Returns:
        Dictionary with cache statistics including disk cache info
    """
    stats = {
        "initialized": _cache_initialized,
    }
    
    # Always check disk cache stats (even if not initialized in this process)
    cache_dir = get_cache_dir()
    if cache_dir.exists():
        cache_files = list(cache_dir.glob("*"))
        stats["cache_dir"] = str(cache_dir)
        stats["cache_files"] = len(cache_files)
        stats["cache_size_bytes"] = sum(f.stat().st_size for f in cache_files if f.is_file())
        stats["cache_size_mb"] = round(stats["cache_size_bytes"] / (1024 * 1024), 2)
        stats["has_cache"] = stats["cache_files"] > 0
    else:
        stats["cache_dir"] = str(cache_dir)
        stats["cache_files"] = 0
        stats["cache_size_mb"] = 0
        stats["has_cache"] = False
    
    return stats


def clear_cache(verbose: bool = True) -> bool:
    """Clear the LLM cache.
    
    Args:
        verbose: Whether to print status
        
    Returns:
        True if cache was cleared successfully
    """
    import shutil
    
    cache_dir = get_cache_dir()
    
    if cache_dir.exists():
        # Get stats before clearing
        files_count = len(list(cache_dir.glob("*")))
        
        # Remove cache directory
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        if verbose:
            print(f"{Colors.GREEN}✓ Cache cleared ({files_count} files removed){Colors.RESET}")
        return True
    else:
        if verbose:
            print(f"{Colors.YELLOW}⚠ Cache directory does not exist{Colors.RESET}")
        return False


def print_cache_status():
    """Print current cache status to console."""
    stats = get_cache_stats()
    
    print(f"\n{Colors.BLUE}=== LLM Cache Status ==={Colors.RESET}")
    print(f"  Directory: {stats.get('cache_dir', 'N/A')}")
    print(f"  Has cached data: {stats.get('has_cache', False)}")
    print(f"  Files: {stats.get('cache_files', 0)}")
    print(f"  Size: {stats.get('cache_size_mb', 0)} MB")
    print()
