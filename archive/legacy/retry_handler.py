"""
重试机制
为Feishu API调用提供重试功能
"""

import asyncio
import functools
import time
from typing import Any, Callable


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        retryable_exceptions: tuple = (Exception,),
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions


def retry_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
):
    """
    异步函数重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数增长基数
        retryable_exceptions: 可重试的异常类型
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        print(
                            f"[Retry] {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise

                    # 计算延迟时间（指数退避）
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    print(
                        f"[Retry] {func.__name__} attempt {attempt + 1}/{max_retries + 1} failed: {e}"
                    )
                    print(f"[Retry] Waiting {delay:.1f}s before retry...")

                    await asyncio.sleep(delay)

            # 如果所有重试都失败
            raise last_exception if last_exception else Exception("All retries failed")

        return wrapper

    return decorator


def retry_sync(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
):
    """
    同步函数重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数增长基数
        retryable_exceptions: 可重试的异常类型
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        print(
                            f"[Retry] {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise

                    # 计算延迟时间（指数退避）
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    print(
                        f"[Retry] {func.__name__} attempt {attempt + 1}/{max_retries + 1} failed: {e}"
                    )
                    print(f"[Retry] Waiting {delay:.1f}s before retry...")

                    time.sleep(delay)

            # 如果所有重试都失败
            raise last_exception if last_exception else Exception("All retries failed")

        return wrapper

    return decorator


# Feishu API专用的重试配置
FEISHU_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        Exception,  # 可以根据需要细化
    ),
)


# OpenCode API专用的重试配置
OPENCODE_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    base_delay=2.0,
    max_delay=20.0,
    exponential_base=2.0,
    retryable_exceptions=(ConnectionError, TimeoutError, Exception),
)
