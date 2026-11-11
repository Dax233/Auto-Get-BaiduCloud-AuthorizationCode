"""Selenium 授权页交互：打开二维码授权页，等待用户完成授权并取出 code。

相比原脚本的 `while True + sleep(1)` 盲轮询，这里用 WebDriverWait 显式等待
「Verifier 输入框出现且值非空」，超时直接给可读错误；浏览器用 context manager
管理，异常时也一定会 quit()。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from .errors import BrowserError

DEFAULT_WAIT_TIMEOUT = 120.0

# 百度授权成功页上承载授权码的元素 id（原脚本硬编码的 XPath 已弃用）
VERIFIER_ELEMENT_ID = "Verifier"


def _load_selenium() -> SimpleNamespace:
    """延迟导入 selenium：只是 import baidu_auth 时不应该强依赖浏览器环境。"""
    try:
        from selenium import webdriver
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:  # pragma: no cover - 依赖缺失属于环境问题
        raise BrowserError(
            "未安装 selenium，无法进行浏览器授权；请先 pip install selenium"
        ) from exc
    return SimpleNamespace(
        webdriver=webdriver,
        TimeoutException=TimeoutException,
        WebDriverException=WebDriverException,
        By=By,
        WebDriverWait=WebDriverWait,
    )


class AuthorizationSession:
    """一次授权页会话，作为 context manager 使用。

    用法::

        with AuthorizationSession(url) as session:
            code = session.wait_for_code()
    """

    def __init__(
        self,
        url: str,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT,
        driver_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self._driver_factory = driver_factory
        self._selenium: SimpleNamespace | None = None
        self._driver: Any | None = None

    def __enter__(self) -> "AuthorizationSession":
        self._selenium = _load_selenium()
        if self._driver_factory is not None:
            self._driver = self._driver_factory()
        else:
            try:
                self._driver = self._selenium.webdriver.Chrome()
            except Exception as exc:  # chromedriver 缺失等启动失败
                raise BrowserError(f"启动 Chrome 失败：{exc}") from exc
        try:
            self._driver.get(self.url)
        except self._selenium.WebDriverException as exc:
            self.close()
            raise BrowserError(f"打开授权页失败：{exc}") from exc
        return self

    def wait_for_code(self) -> str:
        """显式等待授权码出现，返回去空白后的 code。"""
        if self._driver is None or self._selenium is None:
            raise BrowserError("授权会话尚未打开，请先使用 with AuthorizationSession(...)")

        selenium = self._selenium
        by = selenium.By

        def verifier_value(driver: Any) -> str | bool:
            # 元素可能先出现、值后填入，所以等「值非空」而不是等「元素存在」
            for element in driver.find_elements(by.ID, VERIFIER_ELEMENT_ID):
                value = (element.get_attribute("value") or "").strip()
                if value:
                    return value
            return False

        try:
            code = selenium.WebDriverWait(self._driver, self.timeout).until(verifier_value)
        except selenium.TimeoutException as exc:
            raise BrowserError(
                f"等待授权超时（{self.timeout:.0f} 秒）：请在浏览器中完成百度账号授权后重试"
            ) from exc
        if not code:
            raise BrowserError("未能从授权页读取到授权码")
        return str(code)

    def close(self) -> None:
        """关闭浏览器；关闭失败不影响主流程（例如用户已手动关闭窗口）。"""
        driver, self._driver = self._driver, None
        if driver is not None:
            try:
                driver.quit()
            except Exception:  # noqa: BLE001 - 清理阶段不再抛错
                pass

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def wait_for_authorization_code(
    url: str, *, timeout: float = DEFAULT_WAIT_TIMEOUT
) -> str:
    """打开授权页等待用户授权，返回授权码（内部负责关闭浏览器）。"""
    with AuthorizationSession(url, timeout=timeout) as session:
        return session.wait_for_code()
