"""Functools module in python has some absolute bangers like @cache, @partials, et cetera

We could also build a decortor like @on_exit which will call whatever function it is decorated on, when the program is about to terminate.
A thing to remeber is that it will make the function call on all cases, even when we encounter an error and code stops executing, the @on_exit will call the func."""

import time
from functools import wraps
from typing import Callable, Any


def timeme(func: Callable) -> Callable:
    """A decorator function to time how much the function"""

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter_ns()
        result = func(*args, **kwargs)
        end = time.perf_counter_ns()
        print(f"This func {func.__name__} too '{end - start:.6f}' seconds to run.")
        return result

    return wrapper


def retry(retries: int = 3, delay: float = 1) -> Callable:
    """Attempt to call a function, if it fails, try again with a specified delay."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for i in range(1, retries + 1):
                try:
                    print(f"Running ({i}): {func.__name__}()")
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == retries:
                        print(f"Error: {repr(e)}.")
                        print(f'"{func.__name__}()" failed after {retries} retries.')
                        break
                    else:
                        print(f"Error: {repr(e)} -> Retrying...")
                        time.sleep(delay)

        return wrapper

    return decorator


def debug(func: Callable) -> Callable:
    """Print the function signature and return value"""

    @wraps(func)
    def wrapper_debug(*args, **kwargs):
        args_repr = [repr(a) for a in args]
        kwargs_repr = [f"{k}={repr(v)}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        print(f"Calling {func.__name__}({signature})")
        value = func(*args, **kwargs)
        print(f"{func.__name__}() returned {repr(value)}")
        return value

    return wrapper_debug


def slow_down(_func=None, delay: int = 1):
    """Sleep for x second(s) before calling the function"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper_slow_down(*args, **kwargs):
            time.sleep(delay)
            return func(*args, **kwargs)

        return wrapper_slow_down

    if _func is None:
        return decorator
    else:
        return decorator(_func)
