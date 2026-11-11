"""CLI 单测：环境变量回退、参数校验、错误退出码、成功输出。"""

from __future__ import annotations

from typing import Any

import pytest

from baidu_auth import cli
from baidu_auth.errors import ConfigurationError, OAuthError
from baidu_auth.oauth import AccessToken


def _args(**overrides: Any) -> Any:
    parser = cli.build_parser()
    defaults = {
        "--client-id": "ARG_KEY",
        "--client-secret": "ARG_SECRET",
    }
    defaults.update(overrides)
    argv: list[str] = []
    for key, value in defaults.items():
        argv.extend([key, str(value)])
    return parser.parse_args(argv)


# ---------- 参数解析 ----------


def test_parser_defaults() -> None:
    args = _args()

    assert args.client_id == "ARG_KEY"
    assert args.client_secret == "ARG_SECRET"
    assert args.redirect_uri == "oob"
    assert args.scope == "basic,netdisk"
    assert args.wait_timeout == 120
    assert args.http_timeout == 15.0


# ---------- 凭证解析：参数 > 环境变量 ----------


def test_resolve_credentials_prefers_arguments() -> None:
    env = {"BAIDU_CLIENT_ID": "ENV_KEY", "BAIDU_CLIENT_SECRET": "ENV_SECRET"}

    assert cli.resolve_credentials(_args(), env) == ("ARG_KEY", "ARG_SECRET")


def test_resolve_credentials_falls_back_to_environment() -> None:
    args = cli.build_parser().parse_args([])
    env = {"BAIDU_CLIENT_ID": " ENV_KEY ", "BAIDU_CLIENT_SECRET": "ENV_SECRET"}

    assert cli.resolve_credentials(args, env) == ("ENV_KEY", "ENV_SECRET")


def test_resolve_credentials_blank_argument_falls_back_to_environment() -> None:
    args = _args(**{"--client-id": "   "})
    env = {"BAIDU_CLIENT_ID": "ENV_KEY"}

    assert cli.resolve_credentials(args, env) == ("ENV_KEY", "ARG_SECRET")


def test_resolve_credentials_missing_id_error_mentions_both_sources() -> None:
    args = cli.build_parser().parse_args([])

    with pytest.raises(ConfigurationError) as excinfo:
        cli.resolve_credentials(args, {})

    message = str(excinfo.value)
    assert "--client-id" in message
    assert "BAIDU_CLIENT_ID" in message


def test_resolve_credentials_missing_secret_error() -> None:
    args = cli.build_parser().parse_args(["--client-id", "KEY"])

    with pytest.raises(ConfigurationError, match="BAIDU_CLIENT_SECRET"):
        cli.resolve_credentials(args, {})


# ---------- main(): 退出码与输出 ----------


def test_main_fails_fast_without_credentials(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("BAIDU_CLIENT_ID", raising=False)
    monkeypatch.delenv("BAIDU_CLIENT_SECRET", raising=False)

    assert cli.main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "配置错误" in captured.err
    assert "BAIDU_CLIENT_ID" in captured.err


def test_main_happy_path_prints_only_access_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Any] = {}

    def fake_wait(url: str, *, timeout: float) -> str:
        seen["url"] = url
        seen["timeout"] = timeout
        return "CODE"

    def fake_request(code: str, client_id: str, client_secret: str, **kwargs: Any) -> AccessToken:
        seen["code"] = code
        seen["client_secret"] = client_secret
        seen["request_kwargs"] = kwargs
        return AccessToken(access_token="ACCESS_TOKEN")

    monkeypatch.setattr(cli, "wait_for_authorization_code", fake_wait)
    monkeypatch.setattr(cli, "request_access_token", fake_request)

    exit_code = cli.main(["--client-id", "KEY", "--client-secret", "SECRET"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "ACCESS_TOKEN\n"
    assert "SECRET" not in captured.out
    assert "SECRET" not in captured.err
    assert "client_id=KEY" in seen["url"]
    assert seen["code"] == "CODE"
    assert seen["client_secret"] == "SECRET"
    assert seen["request_kwargs"]["redirect_uri"] == "oob"


def test_main_returns_1_on_oauth_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def boom(*args: Any, **kwargs: Any) -> str:
        raise OAuthError("授权码已失效")

    monkeypatch.setattr(cli, "wait_for_authorization_code", lambda url, *, timeout: "CODE")
    monkeypatch.setattr(cli, "request_access_token", boom)

    assert cli.main(["--client-id", "KEY", "--client-secret", "SECRET"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "授权失败" in captured.err
    assert "授权码已失效" in captured.err


def test_main_returns_130_on_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def interrupt(*args: Any, **kwargs: Any) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "wait_for_authorization_code", interrupt)

    assert cli.main(["--client-id", "KEY", "--client-secret", "SECRET"]) == 130
    assert "已取消" in capsys.readouterr().err
