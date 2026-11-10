"""oauth 模块纯逻辑单测：URL 构造、token 响应解析、网络错误包装。"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
import requests

from baidu_auth.errors import ConfigurationError, OAuthError
from baidu_auth.oauth import (
    AUTHORIZE_ENDPOINT,
    DEFAULT_REDIRECT_URI,
    DEFAULT_SCOPE,
    TOKEN_ENDPOINT,
    build_authorize_url,
    parse_token_response,
    request_access_token,
)


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


# ---------- 授权页 URL 构造 ----------


def test_build_authorize_url_defaults() -> None:
    url = build_authorize_url("APP_KEY")

    parsed = urlparse(url)
    assert url.startswith(AUTHORIZE_ENDPOINT + "?")
    assert parsed.scheme == "https"
    params = _query(url)
    assert params["response_type"] == ["code"]
    assert params["client_id"] == ["APP_KEY"]
    assert params["redirect_uri"] == [DEFAULT_REDIRECT_URI]
    assert params["scope"] == [DEFAULT_SCOPE]
    assert params["qrcode"] == ["1"]


def test_build_authorize_url_encodes_special_characters() -> None:
    url = build_authorize_url("a b&c=d/e?f")

    assert "a b&c=d/e?f" not in url
    assert _query(url)["client_id"] == ["a b&c=d/e?f"]


def test_build_authorize_url_custom_scope_redirect_and_no_qrcode() -> None:
    url = build_authorize_url(
        "key", redirect_uri="https://example.com/cb", scope="basic", qrcode=False
    )

    params = _query(url)
    assert params["redirect_uri"] == ["https://example.com/cb"]
    assert params["scope"] == ["basic"]
    assert "qrcode" not in params


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_build_authorize_url_rejects_empty_client_id(bad: object) -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        build_authorize_url(bad)
    assert "client_id" in str(excinfo.value)
    assert "BAIDU_CLIENT_ID" in str(excinfo.value)


def test_build_authorize_url_rejects_empty_scope() -> None:
    with pytest.raises(ConfigurationError, match="scope"):
        build_authorize_url("key", scope="  ")


# ---------- token 响应解析 ----------


def test_parse_token_response_success() -> None:
    token = parse_token_response(
        {
            "access_token": " 1.a.b ",
            "expires_in": "2592000",
            "refresh_token": "2.c.d",
            "scope": "basic netdisk",
        }
    )

    assert token.access_token == "1.a.b"
    assert token.expires_in == 2592000
    assert token.refresh_token == "2.c.d"
    assert token.scope == "basic netdisk"


def test_parse_token_response_ignores_bad_expires_in() -> None:
    assert parse_token_response({"access_token": "t", "expires_in": "oops"}).expires_in is None
    assert parse_token_response({"access_token": "t"}).expires_in is None


def test_parse_token_response_error_payload() -> None:
    with pytest.raises(OAuthError) as excinfo:
        parse_token_response(
            {"error": "invalid_grant", "error_description": "授权码已失效"},
            status_code=400,
        )
    message = str(excinfo.value)
    assert "HTTP 400" in message
    assert "授权码已失效" in message


def test_parse_token_response_error_without_description() -> None:
    with pytest.raises(OAuthError, match="invalid_client"):
        parse_token_response({"error": "invalid_client"})


def test_parse_token_response_missing_access_token() -> None:
    with pytest.raises(OAuthError, match="access_token"):
        parse_token_response({"expires_in": 1})


@pytest.mark.parametrize("payload", [None, [], "oops", 42])
def test_parse_token_response_non_object(payload: object) -> None:
    with pytest.raises(OAuthError, match="JSON"):
        parse_token_response(payload)


def test_access_token_repr_masks_token() -> None:
    token = parse_token_response({"access_token": "1.very-secret-token-value"})

    assert "very-secret-token-value" not in repr(token)
    assert "AccessToken(" in repr(token)


# ---------- token 请求 ----------


class FakeResponse:
    def __init__(self, payload: object = None, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response or FakeResponse({"access_token": "token"})
        self.error = error
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, data: dict[str, str], timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "data": data, "timeout": timeout})
        if self.error is not None:
            raise self.error
        return self.response


def test_request_access_token_posts_form_and_returns_token() -> None:
    session = FakeSession()

    token = request_access_token(
        "CODE", "KEY", "SECRET", redirect_uri="oob", timeout=9, session=session
    )

    assert token.access_token == "token"
    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == TOKEN_ENDPOINT
    assert call["timeout"] == 9
    form = call["data"]
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == "CODE"
    assert form["client_id"] == "KEY"
    assert form["client_secret"] == "SECRET"
    assert form["redirect_uri"] == "oob"
    # secret 只能出现在表单里，不能进 URL
    assert "SECRET" not in str(call["url"])


def test_request_access_token_wraps_network_error() -> None:
    session = FakeSession(error=requests.ConnectionError("boom"))

    with pytest.raises(OAuthError, match="boom"):
        request_access_token("CODE", "KEY", "SECRET", session=session)


def test_request_access_token_wraps_invalid_json() -> None:
    session = FakeSession(response=FakeResponse(ValueError("no json"), status_code=502))

    with pytest.raises(OAuthError, match="HTTP 502"):
        request_access_token("CODE", "KEY", "SECRET", session=session)


def test_request_access_token_propagates_api_error() -> None:
    session = FakeSession(
        response=FakeResponse(
            {"error": "invalid_grant", "error_description": "code 已使用"}, status_code=400
        )
    )

    with pytest.raises(OAuthError, match="code 已使用"):
        request_access_token("CODE", "KEY", "SECRET", session=session)


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"code": " "}, "authorization code"),
        ({"client_id": " "}, "client_id"),
        ({"client_secret": ""}, "client_secret"),
    ],
)
def test_request_access_token_validates_inputs(kwargs: dict[str, str], field: str) -> None:
    params = {"code": "CODE", "client_id": "KEY", "client_secret": "SECRET"}
    params.update(kwargs)

    with pytest.raises(ConfigurationError, match=field):
        request_access_token(**params, session=FakeSession())
