"""Production-ready decorators for validation, timing, retry logic, caching, and rate limiting.

Provides a comprehensive set of decorators for common cross-cutting concerns:
- Parameter validation with type checking
- Performance monitoring and timing
- Retry logic with configurable attempts and delays
- Function debugging and inspection
- Rate limiting for API calls
- Result caching (memoization)
- Execution delays
"""

import time
from functools import wraps
import inspect
from typing import Callable, get_type_hints, Any, TypeVar, ParamSpec, Optional, Union
from collections.abc import Hashable

# Type variables for better type hints
P = ParamSpec('P')
T = TypeVar('T')


def validate_params(func: Callable[P, T]) -> Callable[P, T]:
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get function signature
        sig = inspect.signature(func)
        params = sig.parameters

        # Get type hints
        type_hints = get_type_hints(func)

        # Convert args to a dictionary of param_name: value
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        for param_name, value in bound_args.arguments.items():
            # Check if parameter exists in type hints
            if param_name in type_hints:
                expected_type = type_hints[param_name]

                # Handle special types (Any, Optional, Union)
                if hasattr(expected_type, "__origin__"):
                    # Skip Any type
                    if expected_type.__origin__ is Any:
                        continue
                    # Handle Optional[T] which is Union[T, None]
                    if expected_type.__origin__ is Union:
                        # Get the args excluding None
                        type_args = [t for t in expected_type.__args__ if t is not type(None)]
                        if value is None and type(None) in expected_type.__args__:
                            continue  # None is valid for Optional
                        if any(isinstance(value, t) for t in type_args):
                            continue
                        expected_type = type_args[0] if len(type_args) == 1 else expected_type

                # Check if value matches expected type
                if not isinstance(value, expected_type):
                    raise TypeError(
                        f"Parameter '{param_name}' expects type {expected_type.__name__} but received {type(value).__name__}"
                    )

            # Check if required parameter is None
            param = params[param_name]
            if param.default == inspect.Parameter.empty and value is None:
                raise ValueError(f"Required parameter '{param_name}' cannot be None")
        return func(*args, **kwargs)

    return wrapper


def time_logger(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to measure and log function execution time.
    
    Prints execution time to stdout with microsecond precision for sub-second
    operations and second precision for longer operations.
    """
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration = time.perf_counter() - start
            if duration < 0.001:
                print(f"{func.__name__} took {duration * 1_000_000:.2f}μs")
            elif duration < 1:
                print(f"{func.__name__} took {duration * 1000:.2f}ms")
            else:
                print(f"{func.__name__} took {duration:.4f}s")
    return wrapper


def retry(retries: int = 3, delay: float = 1.0, backoff: float = 1.0, 
          exceptions: tuple[type[Exception], ...] = (Exception,)) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry a function call with exponential backoff.
    
    Args:
        retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for exponential delay
        exceptions: Tuple of exception types to catch and retry
    
    Raises:
        The last exception if all retries fail
    """
    if retries < 1:
        raise ValueError("retries must be at least 1")
    if delay < 0:
        raise ValueError("delay must be non-negative")
    if backoff < 1:
        raise ValueError("backoff must be at least 1")

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(1, retries + 1):
                try:
                    if attempt > 1:
                        print(f"Retry {attempt}/{retries}: {func.__name__}")
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        print(f"{func.__name__} failed after {retries} attempts: {e}")
                        raise
                    print(f"Attempt {attempt} failed: {e}. Retrying in {current_delay:.1f}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception  # Should never reach here
        return wrapper
    return decorator


def debug(func: Callable[P, T]) -> Callable[P, T]:
    """Debug decorator that prints function calls, arguments, and return values.
    
    Truncates long representations to keep output readable.
    """
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        # Truncate long representations
        def truncate_repr(obj: Any, max_len: int = 100) -> str:
            rep = repr(obj)
            return rep if len(rep) <= max_len else rep[:max_len-3] + '...'
        
        args_repr = [truncate_repr(a) for a in args]
        kwargs_repr = [f"{k}={truncate_repr(v)}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        
        print(f"→ {func.__name__}({signature})")
        try:
            result = func(*args, **kwargs)
            print(f"← {func.__name__} returned: {truncate_repr(result)}")
            return result
        except Exception as e:
            print(f"✗ {func.__name__} raised: {type(e).__name__}: {e}")
            raise
    return wrapper


def slow_down(_func: Optional[Callable[P, T]] = None, *, delay: float = 1.0) -> Union[Callable[[Callable[P, T]], Callable[P, T]], Callable[P, T]]:
    """Add a delay before function execution.
    
    Can be used with or without parentheses:
        @slow_down  # 1 second delay
        @slow_down(delay=2.5)  # 2.5 second delay
    
    Args:
        delay: Delay in seconds before executing the function
    """
    if delay < 0:
        raise ValueError("delay must be non-negative")
    
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            time.sleep(delay)
            return func(*args, **kwargs)
        return wrapper
    
    if _func is None:
        return decorator
    else:
        return decorator(_func)


def rate_limiter(max_calls: int, period: float) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Limit function calls to max_calls within a time period.
    
    Args:
        max_calls: Maximum number of calls allowed
        period: Time period in seconds
    
    Raises:
        RuntimeError: When rate limit is exceeded
    """
    if max_calls < 1:
        raise ValueError("max_calls must be at least 1")
    if period <= 0:
        raise ValueError("period must be positive")
    
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        call_times: list[float] = []
        
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            nonlocal call_times
            now = time.time()
            
            # Remove calls outside the time window
            call_times = [t for t in call_times if now - t < period]
            
            # Check rate limit
            if len(call_times) >= max_calls:
                wait_time = period - (now - call_times[0])
                raise RuntimeError(
                    f"Rate limit exceeded ({max_calls} calls per {period}s). "
                    f"Try again in {wait_time:.1f}s."
                )
            
            # Record this call and execute
            call_times.append(now)
            return func(*args, **kwargs)
        
        # Add utility method to reset rate limit
        wrapper.reset_rate_limit = lambda: call_times.clear()
        return wrapper
    
    return decorator


def memoize(func: Callable[P, T]) -> Callable[P, T]:
    """Cache function results based on arguments.
    
    Note: Only works with hashable arguments. For unhashable arguments,
    falls back to calling the function without caching.
    
    The wrapper includes cache management methods:
    - wrapper.cache_info(): Get cache statistics
    - wrapper.cache_clear(): Clear the cache
    """
    cache: dict[tuple[Hashable, ...], T] = {}
    hits = misses = 0
    
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        nonlocal hits, misses
        
        # Try to create a hashable key
        try:
            # Convert kwargs to sorted tuple for consistent hashing
            key = (args, tuple(sorted(kwargs.items())))
            hash(key)  # Test if hashable
        except TypeError:
            # Arguments not hashable, skip caching
            misses += 1
            return func(*args, **kwargs)
        
        if key in cache:
            hits += 1
            return cache[key]
        else:
            misses += 1
            result = func(*args, **kwargs)
            cache[key] = result
            return result
    
    # Add cache management methods
    wrapper.cache_info = lambda: {'hits': hits, 'misses': misses, 'size': len(cache)}
    wrapper.cache_clear = lambda: (cache.clear(), setattr(wrapper, 'hits', 0), setattr(wrapper, 'misses', 0))
    
    return wrapper


def singleton(cls: type[T]) -> type[T]:
    """Ensure a class has only one instance (Singleton pattern).
    
    Thread-safe implementation using a lock.
    
    Example:
        @singleton
        class DatabaseConnection:
            def __init__(self):
                self.connection = connect_to_db()
    """
    instances = {}
    lock = None
    
    @wraps(cls)
    def get_instance(*args, **kwargs):
        nonlocal lock
        if lock is None:
            import threading
            lock = threading.Lock()
        
        if cls not in instances:
            with lock:
                # Double-check locking pattern
                if cls not in instances:
                    instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance


# Future decorator ideas:
# 
# 1. @deprecated(reason="", version="")
#    - Mark functions as deprecated with warnings
#    - Include migration path and removal version
#    - Uses warnings.warn() with DeprecationWarning
#
# 2. @synchronized(lock=None)
#    - Thread synchronization for critical sections
#    - Can share locks between functions or create per-function locks
#    - Useful for thread-safe operations on shared resources
