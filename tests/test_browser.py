"""browser 模块单测：不启动真实浏览器，用假 selenium 对象验证等待与清理。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from baidu_auth import browser
from baidu_auth.errors import BrowserError
from baidu_auth.browser import AuthorizationSession, wait_for_authorization_code


class FakeElement:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_attribute(self, name: str) -> str | None:
        return self._value if name == "value" else None


class FakeDriver:
    def __init__(self, values: list[str] | None = None) -> None:
        self.values = values or []
        self.visited: list[str] = []
        self.quit_called = False

    def get(self, url: str) -> None:
        self.visited.append(url)

    def find_elements(self, by: Any, value: str) -> list[FakeElement]:
        return [FakeElement(v) for v in self.values]

    def quit(self) -> None:
        self.quit_called = True


class FakeTimeout(Exception):
    pass


class FakeWebDriverException(Exception):
    pass


class Waiter:
    """按 driver 上预置的行为执行 until。"""

    def __init__(self, driver: Any, timeout: float) -> None:
        self.driver = driver
        self.timeout = timeout

    def until(self, condition: Any) -> Any:
        result = condition(self.driver)
        if not result:
            raise FakeTimeout()
        return result


def _fake_selenium() -> SimpleNamespace:
    return SimpleNamespace(
        webdriver=SimpleNamespace(Chrome=lambda: FakeDriver()),
        TimeoutException=FakeTimeout,
        WebDriverException=FakeWebDriverException,
        By=SimpleNamespace(ID="id"),
        WebDriverWait=Waiter,
    )


def test_session_waits_for_non_empty_verifier_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "_load_selenium", _fake_selenium)
    driver = FakeDriver(values=["", "AUTH_CODE"])
    factory = lambda: driver  # noqa: E731

    with AuthorizationSession("https://example.com/authorize", driver_factory=factory) as session:
        assert session.wait_for_code() == "AUTH_CODE"

    assert driver.visited == ["https://example.com/authorize"]
    assert driver.quit_called is True


def test_session_timeout_raises_readable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "_load_selenium", _fake_selenium)
    driver = FakeDriver(values=[])

    with pytest.raises(BrowserError, match="等待授权超时"):
        with AuthorizationSession("https://example.com/authorize", timeout=5, driver_factory=lambda: driver) as session:
            session.wait_for_code()

    assert driver.quit_called is True


def test_session_closes_driver_even_if_body_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "_load_selenium", _fake_selenium)
    driver = FakeDriver(values=["CODE"])

    with pytest.raises(RuntimeError, match="boom"):
        with AuthorizationSession("https://example.com/authorize", driver_factory=lambda: driver) as session:
            assert session.wait_for_code() == "CODE"
            raise RuntimeError("boom")

    assert driver.quit_called is True


def test_wait_for_authorization_code_convenience(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "_load_selenium", _fake_selenium)
    driver = FakeDriver(values=["CODE"])
    monkeypatch.setattr(
        browser,
        "AuthorizationSession",
        lambda url, timeout: AuthorizationSession(url, timeout=timeout, driver_factory=lambda: driver),
    )

    assert wait_for_authorization_code("https://example.com/authorize") == "CODE"
    assert driver.quit_called is True


def test_session_requires_enter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "_load_selenium", _fake_selenium)

    with pytest.raises(BrowserError, match="尚未打开"):
        AuthorizationSession("https://example.com/authorize").wait_for_code()
