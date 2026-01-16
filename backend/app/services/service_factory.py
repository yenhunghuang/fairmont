"""Unified service factory with singleton support.

This module provides a decorator-based approach to create service singletons,
reducing boilerplate code across the codebase.

Usage:
    @service_factory
    def get_my_service() -> MyService:
        return MyService()

    # With parameters (creates instance per unique parameter combination)
    @service_factory
    def get_parser_service(vendor_id: str = "habitus") -> ParserService:
        return ParserService(vendor_id=vendor_id)

Benefits:
    - Eliminates repetitive global variable + None check pattern
    - Thread-safe singleton creation
    - Supports parameterized factories with caching by arguments
    - Clear, consistent API across all services
"""

import functools
import threading
from typing import Any, Callable, TypeVar, ParamSpec

P = ParamSpec("P")
T = TypeVar("T")


def service_factory(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator that converts a factory function into a cached singleton factory.

    For functions with no arguments (or only default arguments), creates a true singleton.
    For functions with arguments, caches instances by argument values.

    Args:
        func: Factory function that creates service instances

    Returns:
        Wrapped function that returns cached singleton instances

    Example:
        @service_factory
        def get_pdf_parser(vendor_id: str = "habitus") -> PDFParserService:
            return PDFParserService(vendor_id=vendor_id)

        # First call creates instance
        parser1 = get_pdf_parser()

        # Second call returns same instance
        parser2 = get_pdf_parser()  # parser1 is parser2

        # Different arguments create different instances
        parser3 = get_pdf_parser(vendor_id="other")  # new instance
    """
    cache: dict[tuple, Any] = {}
    lock = threading.Lock()

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        # Create a hashable key from arguments
        key = (args, tuple(sorted(kwargs.items())))

        if key not in cache:
            with lock:
                # Double-check after acquiring lock
                if key not in cache:
                    cache[key] = func(*args, **kwargs)

        return cache[key]

    # Add method to clear cache (useful for testing)
    wrapper.clear_cache = lambda: cache.clear()  # type: ignore
    wrapper.cache_info = lambda: {"size": len(cache), "keys": list(cache.keys())}  # type: ignore

    return wrapper


def clear_all_service_caches() -> None:
    """Clear all service singleton caches.

    Useful for testing or when services need to be re-initialized.

    Note: This function must be called after all service factories are imported.
    """
    import sys

    services_module = "app.services"
    for module_name in list(sys.modules.keys()):
        if module_name.startswith(services_module):
            module = sys.modules[module_name]
            for attr_name in dir(module):
                attr = getattr(module, attr_name, None)
                if callable(attr) and hasattr(attr, "clear_cache"):
                    attr.clear_cache()
