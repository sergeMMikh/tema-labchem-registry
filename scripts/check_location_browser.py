"""Read-only browser regression check against a running development server.

Install playwright and run `python -m playwright install chromium` first.
Run: python scripts/check_location_browser.py http://127.0.0.1:8767
"""

import sys

from playwright.sync_api import expect, sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto((sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8767") + "/locations/")
    tree = page.locator("#location-tree")
    results = page.locator("#location-results")
    cabinet = tree.get_by_role("link", name="Bellow Fume hood", exact=True)
    expect(cabinet).to_have_count(1)
    # A collapsed cabinet has a direct leaf link, not a details/summary disclosure.
    assert cabinet.evaluate("e => e.parentElement.tagName") != "SUMMARY"
    cabinet.scroll_into_view_if_needed()
    before = tree.evaluate("e => e.scrollTop")
    window_top = page.evaluate("window.scrollY")
    page.evaluate("window.locationRegressionMarker = true")
    cabinet.click()
    expect(results).to_have_attribute("data-selected", cabinet.get_attribute("data-location"))
    assert page.evaluate("window.locationRegressionMarker") is True
    assert tree.evaluate("e => e.scrollTop") == before
    assert page.evaluate("window.scrollY") == window_top
    assert "Unspecified shelf" not in results.locator("h2").inner_text()
    expect(results.locator(".content-row").first).to_be_visible()
    results.evaluate("e => e.scrollTop = e.scrollHeight")
    assert tree.evaluate("e => e.scrollTop") == before
    assert page.evaluate("window.scrollY") == window_top
    saved_url = page.url
    other = tree.locator("a[data-location]:visible").last
    other.scroll_into_view_if_needed()
    other_top = tree.evaluate("e => e.scrollTop")
    other.click()
    expect(results).to_have_attribute("data-selected", other.get_attribute("data-location"))
    page.go_back()
    expect(page).to_have_url(saved_url)
    expect(results).to_have_attribute("data-selected", cabinet.get_attribute("data-location"))
    assert tree.evaluate("e => e.scrollTop") == other_top
    page.reload()
    assert tree.evaluate("e => e.scrollTop") == other_top
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert tree.evaluate("e => getComputedStyle(e).overflowY") == "auto"
    assert results.evaluate("e => getComputedStyle(e).overflowY") == "auto"
    assert not errors, errors
    browser.close()
    print("PASS: collapsed shelf, independent scrolling, no reload, history, restoration, mobile")
