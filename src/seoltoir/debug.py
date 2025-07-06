"""
Debug utilities for Seoltoir web browser.
"""

# Global debug flag
DEBUG_MODE = True

def debug_print(*args, **kwargs):
    """Print debug messages only if debug mode is enabled."""
    if DEBUG_MODE:
        import sys
        print("[SEOLTOIR-DEBUG]", *args, **kwargs, file=sys.stderr, flush=True)

def set_debug_mode(enabled: bool):
    """Set the debug mode globally."""
    global DEBUG_MODE
    DEBUG_MODE = enabled 