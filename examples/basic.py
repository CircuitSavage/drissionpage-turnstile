"""Solve a Turnstile widget on a protected page with DrissionPage + Peak.

    pip install DrissionPage drissionpage-turnstile
    PEAK_API_KEY=pk_... python basic.py

DrissionPage drives a real Chromium, so it often clears Turnstile on its own.
solve_turnstile() waits a few seconds for that, and only calls Peak if the
widget hasn't produced a token by then — so you pay only when you have to.
"""

import os

from DrissionPage import ChromiumPage

from drissionpage_turnstile import solve_turnstile

API_KEY = os.environ["PEAK_API_KEY"]
# Match the browser's exit IP when the target binds the token to an IP.
PROXY = os.environ.get("PROXY")  # e.g. "http://user:pass@host:port"

page = ChromiumPage()
page.get("https://your-target.example/login")  # a page with a Turnstile widget

result = solve_turnstile(page, API_KEY, proxy=PROXY)
source = "browser (free)" if result.native else f"Peak (${result.cost})"
print(f"token in page via {source}: {result.token[:24]}...")

# The token now sits in the cf-turnstile-response field. Submit as normal.
page.ele("tag:button@@text():Sign in").click()
