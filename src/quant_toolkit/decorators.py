"""Functools module in python has some absolute bangers like @cache, @partials, et cetera

We could also build a decortor like @on_exit which will call whatever function it is decorated on, when the program is about to terminate.
A thing to remeber is that it will make the function call on all cases, even when we encounter an error and code stops executing, the @on_exit will call the func.
Or we could import atexit module and use something like @atexit.register decorator to the function we want to call when the program is about to terminate."""

import time
from functools import wraps
import inspect
from typing import Callable, Union, get_type_hints, Any
import datetime
import logging


def validate_params(func):
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

                # Handle Union types
                if (
                    hasattr(expected_type, "__origin__")
                    and expected_type.__origin__ is Any
                ):
                    continue

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


def time_logger(func: Callable) -> Callable:
    """A decorator function to time how much time the function takes to run."""

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"This func {func.__name__} takes '{end - start:.4f}' seconds to run.")
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
                        print(f"Error: {repr(e)} -> Retrying...{i + 1}/{retries}")
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
        print(f"Calling {func.__name__} with args ({signature})")
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


def rate_limiter(max_calls: int, period: int):
    """Limit the number of calls to a function within a given period"""

    def decorator(func: Callable) -> Callable:
        last_called = []

        def wrapper(*args, **kwargs):
            nonlocal last_called
            now = time.time()
            last_calls = [call for call in last_called if now - call < period]
            if len(last_calls) > max_calls:
                raise RuntimeError("Rate limit exceeded. Please try again later.")
            last_calls.append(now)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def memoize(func: Callable) -> Callable:
    """Store the result of the function call in a cache"""

    cache = {}

    @wraps(func)
    def wrapper_memoize(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    return wrapper_memoize


class logit:
    """A class to log the function call. This doesn't handle error logging and thus we need another function to do that for us."""

    def __init__(
        self,
        func: Callable,
        path: str = r"/home/cheesecake/Downloads/logs/logfile.log",
        loggin_level: int = logging.DEBUG,
    ):
        self.func = func
        self.path = path
        self.loggin_level = loggin_level

    def __call__(self, *args, **kwargs):
        """wrapper function"""
        start = time.perf_counter_ns()
        result = self.func(*args, **kwargs)
        end = time.perf_counter_ns()
        func_name = self.func.__name__

        message = f"""Running {func_name}
                      Execution time: {end - start:.6f} seconds
                      Address: {self.path}
                      Logging level: {self.loggin_level}
                      Date: {datetime.datetime.now()}"""

        logging.basicConfig(filename=self.path, level=self.loggin_level)
        logging.debug(message)
        return result


class MyLogger:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)

    def get_logger(self, name=None):
        return logging.getLogger(name)


def get_default_logger():
    return MyLogger().get_logger()


def log(_func=None, *, my_logger: Union[MyLogger, logging.Logger] = None):
    def decorator_log(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_default_logger()
            try:
                if my_logger is None:
                    first_args = next(
                        iter(args), None
                    )  # capture first arg to check for `self`
                    logger_params = [  # does kwargs have any logger
                        x
                        for x in kwargs.values()
                        if isinstance(x, logging.Logger) or isinstance(x, MyLogger)
                    ] + [  # # does args have any logger
                        x
                        for x in args
                        if isinstance(x, logging.Logger) or isinstance(x, MyLogger)
                    ]
                    if hasattr(first_args, "__dict__"):  # is first argument `self`
                        logger_params = (
                            logger_params
                            + [
                                x
                                for x in first_args.__dict__.values()  # does class (dict) members have any logger
                                if isinstance(x, logging.Logger)
                                or isinstance(x, MyLogger)
                            ]
                        )
                    h_logger = next(
                        iter(logger_params), MyLogger()
                    )  # get the next/first/default logger
                else:
                    h_logger = my_logger  # logger is passed explicitly to the decorator

                if isinstance(h_logger, MyLogger):
                    logger = h_logger.get_logger(func.__name__)
                else:
                    logger = h_logger

                args_repr = [repr(a) for a in args]
                kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                signature = ", ".join(args_repr + kwargs_repr)
                logger.debug(f"function {func.__name__} called with args {signature}")
            except Exception:
                pass

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                logger.exception(
                    f"Exception raised in {func.__name__}. exception: {str(e)}"
                )
                raise e

        return wrapper

    if _func is None:
        return decorator_log
    else:
        return decorator_log(_func)
