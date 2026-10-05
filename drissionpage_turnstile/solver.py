"""Solve Cloudflare Turnstile inside a DrissionPage browser.

DrissionPage drives a real Chromium, so the page, cookies, and TLS fingerprint
belong to the browser you're already scraping with. Much of the time that
browser earns its own Turnstile token — this library reads that token when it's
there and only calls the Peak solver when the widget stalls, so you pay for a
solve just when the browser couldn't finish on its own.

The flow is the one you'd do by hand: read the sitekey off the page, hand the
(url, sitekey) pair to the solver, drop the returned token into the widget's
hidden input, and fire the callback the page wired up.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx

PEAK_ENDPOINT = "https://api.peak.fo/solve"


class TurnstileError(RuntimeError):
    """Raised when the sitekey can't be found or the solve fails."""


@dataclass
class SolveResult:
    token: str
    cost: float
    elapsed: float
    native: bool = False  # True when the browser earned the token itself


# Pull the sitekey out of a rendered widget. Covers the explicit-render div, the
# implicit div, and the managed iframe that carries the key in its src.
_FIND_SITEKEY = r"""
const el = document.querySelector('[data-sitekey]');
if (el) return el.getAttribute('data-sitekey');
const f = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
if (f) {
  const m = f.getAttribute('src').match(/[?&]sitekey=([^&]+)/);
  if (m) return decodeURIComponent(m[1]);
}
return null;
"""

# Return a token the browser already placed in the response field, if it looks
# real. Short values are placeholders, not tokens.
_READ_TOKEN = r"""
const i = document.querySelector('input[name="cf-turnstile-response"], textarea[name="cf-turnstile-response"]');
return (i && i.value && i.value.length > 20) ? i.value : null;
"""

# Install the token: fill every response field, then call the page's callback.
# Forms read the input on submit; SPAs lean on the callback. Do both.
_INJECT = r"""
const token = arguments[0];
let n = 0;
document.querySelectorAll(
  'input[name="cf-turnstile-response"], textarea[name="cf-turnstile-response"]'
).forEach((i) => { i.value = token; n++; });
document.querySelectorAll('[name="g-recaptcha-response"]').forEach((i) => { i.value = token; });
try {
  const el = document.querySelector('[data-callback]');
  if (el) {
    const cb = el.getAttribute('data-callback');
    if (cb && typeof window[cb] === 'function') { window[cb](token); n++; }
  }
} catch (e) {}
return n;
"""


def read_sitekey(page, timeout: float = 15.0, poll: float = 0.5) -> str:
    """Wait for the widget to render and return its sitekey."""
    deadline = time.monotonic() + timeout
    while True:
        key = page.run_js(_FIND_SITEKEY)
        if key:
            return str(key)
        if time.monotonic() >= deadline:
            raise TurnstileError(
                f"no Turnstile sitekey on the page after {timeout:.0f}s — "
                "is the widget actually present?"
            )
        time.sleep(poll)


def request_token(
    api_key: str,
    url: str,
    sitekey: str,
    proxy: Optional[str] = None,
    timeout: float = 120.0,
) -> SolveResult:
    """Ask Peak for a token. Pass a proxy to match the browser's exit IP, or
    leave it out to use Peak's proxyless pool."""
    task = "turnstiletask" if proxy else "turnstiletaskproxyless"
    body = {"task_type": task, "url": url, "sitekey": sitekey}
    if proxy:
        body["proxy"] = proxy

    t0 = time.monotonic()
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            PEAK_ENDPOINT,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json=body,
        )
    elapsed = time.monotonic() - t0
    data = r.json()
    if not data.get("success"):
        raise TurnstileError(f"solve failed: {data.get('error') or r.text[:200]}")
    return SolveResult(
        token=data["data"]["token"],
        cost=float(data.get("cost", 0.0)),
        elapsed=elapsed,
    )


def solve_turnstile(
    page,
    api_key: str,
    proxy: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 120.0,
    wait_native: float = 4.0,
) -> SolveResult:
    """End to end for a DrissionPage page.

    Reads the sitekey off ``page``; if the browser already earned a token within
    ``wait_native`` seconds, returns that (cost 0, ``native=True``); otherwise
    solves through Peak and injects the token. ``page`` is a DrissionPage
    ``ChromiumPage`` or ``WebPage``; ``url`` defaults to ``page.url``. The token
    is in the page when this returns.
    """
    page_url = url or page.url

    # Give the real browser a window to solve it itself before paying for one.
    if wait_native > 0:
        deadline = time.monotonic() + wait_native
        while time.monotonic() < deadline:
            tok = page.run_js(_READ_TOKEN)
            if tok:
                return SolveResult(token=str(tok), cost=0.0, elapsed=0.0, native=True)
            time.sleep(0.5)

    sitekey = read_sitekey(page)
    result = request_token(api_key, str(page_url), sitekey, proxy, timeout)
    injected = page.run_js(_INJECT, result.token)
    if not injected:
        raise TurnstileError(
            "got a token but found nowhere to put it — the widget's response "
            "field wasn't on the page. Inject result.token yourself."
        )
    return result
