"""
Utility functions for audio processing.
"""
import sys

def is_test_environment() -> bool:
    """
    Check if the code is running in a test environment.
    
    Returns:
        bool: True if running in a test environment, False otherwise.
    """
    return 'pytest' in sys.modules or 'unittest' in sys.modules or 'test' in sys.argv[0]
