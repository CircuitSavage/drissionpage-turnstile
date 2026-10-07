"""Unit tests that stub out the browser and the network.

Run with: pytest -q
"""

import pytest

from drissionpage_turnstile import TurnstileError, solve_turnstile
from drissionpage_turnstile import solver


class FakePage:
    """Just enough of a DrissionPage page for the solver."""

    def __init__(self, sitekey=None, native_token=None, has_field=True):
        self.url = "https://protected.example/login"
        self._sitekey = sitekey
        self._native_token = native_token
        self._has_field = has_field
        self.injected = None

    def run_js(self, js, *args):
        if args:  # the inject call passes the token as an argument
            if not self._has_field:
                return 0
            self.injected = args[0]
            return 1
        if "input[name=" in js and "forEach" not in js:
            return self._native_token
        return self._sitekey


def test_returns_native_token_without_solving(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not have called Peak")

    monkeypatch.setattr(solver, "request_token", boom)

    page = FakePage(native_token="existing-token-value-0123456789")
    result = solve_turnstile(page, api_key="pk_test")
    assert result.token == "existing-token-value-0123456789"
    assert result.native is True
    assert result.cost == 0.0


def test_solves_and_injects_when_no_native_token(monkeypatch):
    def fake_request_token(api_key, url, sitekey, proxy=None, timeout=120.0):
        assert sitekey == "0x4AAAAAAABkMYinukE8nzKd"
        return solver.SolveResult(token="SOLVED-TOKEN", cost=0.0009, elapsed=0.8)

    monkeypatch.setattr(solver, "request_token", fake_request_token)

    page = FakePage(sitekey="0x4AAAAAAABkMYinukE8nzKd", native_token=None)
    result = solve_turnstile(page, api_key="pk_test", wait_native=0)
    assert result.token == "SOLVED-TOKEN"
    assert result.native is False
    assert page.injected == "SOLVED-TOKEN"


def test_raises_when_no_response_field(monkeypatch):
    def fake_request_token(api_key, url, sitekey, proxy=None, timeout=120.0):
        return solver.SolveResult(token="SOLVED-TOKEN", cost=0.0009, elapsed=0.8)

    monkeypatch.setattr(solver, "request_token", fake_request_token)

    page = FakePage(sitekey="0xSITEKEY", native_token=None, has_field=False)
    with pytest.raises(TurnstileError):
        solve_turnstile(page, api_key="pk_test", wait_native=0)


def test_read_sitekey_times_out():
    page = FakePage(sitekey=None)
    with pytest.raises(TurnstileError):
        solver.read_sitekey(page, timeout=0.2, poll=0.05)


def test_request_token_raises_on_failure(monkeypatch):
    class FakeResponse:
        text = '{"success": false, "error": "bad sitekey"}'

        def json(self):
            return {"success": False, "error": "bad sitekey"}

    class FakeClient:
        def __init__(self, timeout=120.0):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            return FakeResponse()

    monkeypatch.setattr(solver.httpx, "Client", FakeClient)
    with pytest.raises(TurnstileError):
        solver.request_token("pk_test", "https://x.example/", "0xSITEKEY")
