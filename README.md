# drissionpage-turnstile

Solve Cloudflare Turnstile inside a [DrissionPage](https://github.com/g1879/DrissionPage) browser.

DrissionPage drives a real Chromium, so when a page throws a Turnstile widget, the browser often clears it on its own. This library leans on that: it waits a few seconds for the browser to earn its own token, reads that token when it appears, and only calls a solver when the widget stalls. You pay for a solve exactly when the browser couldn't finish the job — not on every page.

When it does need a solver, it uses [Peak](https://peak.fo/?utm_source=github&utm_medium=readme&utm_campaign=drissionpage-turnstile), a Cloudflare Turnstile API: one call returns the token in about a second, and you're billed only for solves that land.

## Install

```bash
pip install DrissionPage drissionpage-turnstile
```

Set your key once:

```bash
export PEAK_API_KEY=pk_your_key   # 1,000 free solves to start, no card
```

## Use it

```python
import os
from DrissionPage import ChromiumPage
from drissionpage_turnstile import solve_turnstile

page = ChromiumPage()
page.get("https://your-target.example/login")

result = solve_turnstile(page, os.environ["PEAK_API_KEY"])
# token is already in the page's cf-turnstile-response field
page.ele("tag:button@@text():Sign in").click()

print("free native solve" if result.native else f"paid solve, ${result.cost}")
```

That's the whole thing. `solve_turnstile` reads the sitekey off the page, reuses a token the browser already produced if there is one, otherwise asks Peak, drops the token into the widget's hidden input, and fires the page's callback so SPAs notice.

## What it actually does

1. Waits up to `wait_native` seconds (default 4) for the real browser to solve the widget itself. If a token shows up in the response field, it returns that — cost `0`, `native=True`.
2. If nothing appears, it reads the sitekey (from the `data-sitekey` div or the challenge iframe's `src`) and sends `(url, sitekey)` to Peak.
3. It writes the returned token into every `cf-turnstile-response` field and calls the `data-callback` the page registered. Forms read the input on submit; single-page apps wait on the callback — so it does both.

## API

```python
solve_turnstile(page, api_key, proxy=None, url=None, timeout=120.0, wait_native=4.0) -> SolveResult
read_sitekey(page, timeout=15.0, poll=0.5) -> str
request_token(api_key, url, sitekey, proxy=None, timeout=120.0) -> SolveResult
```

`SolveResult` has `.token`, `.cost`, `.elapsed`, and `.native`.

- **`page`** — a DrissionPage `ChromiumPage` or `WebPage`.
- **`proxy`** — pass the same proxy your browser is running behind. Turnstile tokens aren't always IP-bound, but when the target *does* bind them, a token solved from a different IP gets rejected. Matching the IP removes that failure. With no proxy, Peak uses its proxyless pool.
- **`wait_native`** — set to `0` to skip the wait and solve immediately through Peak (useful when you already know the browser can't pass, e.g. headless on a flagged datacenter IP).

## Notes

- The token is single-use and expires in about five minutes, so solve close to when you submit.
- If `solve_turnstile` raises "found nowhere to put it," the page renders the challenge but has no response field yet — wait for the widget, or inject `result.token` where the form expects it.
- This reads the sitekey already on the page; it doesn't start a challenge that isn't there.

## Related

Part of a set of Turnstile integrations for the common stacks — [nodriver](https://github.com/CircuitSavage/nodriver-turnstile), [scrapling](https://github.com/CircuitSavage/scrapling-turnstile), [playwright](https://github.com/CircuitSavage/playwright-turnstile), [selenium](https://github.com/CircuitSavage/selenium-turnstile), [scrapy](https://github.com/CircuitSavage/scrapy-turnstile), [cloudscraper](https://github.com/CircuitSavage/cloudscraper-turnstile), [curl_cffi](https://github.com/CircuitSavage/turnstile-curl). More in [awesome-turnstile-solvers](https://github.com/CircuitSavage/awesome-turnstile-solvers).

## License

MIT
