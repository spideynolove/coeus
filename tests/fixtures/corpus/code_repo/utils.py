"""Utility functions for the calculator app."""

import time
from typing import Any, Callable


def timer(func: Callable) -> Callable:
    """Decorator to time function execution.
    
    Args:
        func: Function to time.
        
    Returns:
        Wrapped function that prints execution time.
    """
    def wrapper(*args: **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__} took {end - start:.6f} seconds")
        return result
    return wrapper


def format_number(num: float, precision: int = 2) -> str:
    """Format a number with specified precision.
    
    Args:
        num: Number to format.
        precision: Decimal places.
        
    Returns:
        Formatted string.
    """
    return f"{num:.{precision}f}"


def validate_number(value: Any) -> bool:
    """Check if value is a valid number.
    
    Args:
        value: Value to check.
        
    Returns:
        True if value is int or float.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)
