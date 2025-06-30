"""
Debug utilities for Seoltoir web browser.
"""

# Global debug flag
DEBUG_MODE = False

def debug_print(*args, **kwargs):
    """Print debug messages only if debug mode is enabled."""
    if DEBUG_MODE:
        print(*args, **kwargs)

def set_debug_mode(enabled: bool):
    """Set the debug mode globally."""
    global DEBUG_MODE
    DEBUG_MODE = enabled 