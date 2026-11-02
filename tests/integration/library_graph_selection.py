"""Run the real Library client in Chromium against an owned in-memory fixture.

No host, credentials, network, library writes, or graph build are used. Example:
python tests/integration/library_graph_selection.py --browser /path/to/chrome
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser")
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    source_path = args.source or Path(__file__).resolve().parents[2] / "src/scitex_scholar/_django/static/scholar/js/library.js"
    source = source_path.read_text()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.browser, headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content('''<button id="scholar-tab-graph"></button>
          <section id="tab-library" class="active">
          <select id="librarySort"><option value="relevance">Relevance</option><option value="title-desc">Title</option></select>
          <input id="librarySelectAll" type="checkbox" disabled>
          <button id="libraryGraphSelected" disabled>Graph selected</button>
          <span id="librarySelectionStatus"></span><span id="libraryStats"></span>
          <div id="libraryLoading"></div><div id="libraryError"><span id="libraryErrorMessage"></span></div>
          <div id="libraryList"></div></section>''')
        page.evaluate('''() => {
          window.STX_MOUNT = "/fixture";
          window.scholarT = (message, values={}) => message.replace(/%\\(([^)]+)\\)s/g, (_, key) => values[key]);
          window.events = []; window.calls = [];
          document.addEventListener("scholar:build-graph", event => { window.events.push(event.detail); event.stopImmediatePropagation(); }, true);
          const rows = Array.from({length:22}, (_, index) => ({paper_id:"owned-fixture-"+index,title:"Paper "+String(index).padStart(2,"0"),doi:"10.1234/fixture-"+index,authors:[],year:2024}));
          rows.push({paper_id:"owned-invalid",title:"Missing DOI",doi:"not-a-doi",authors:[]});
          window.fetch = async (url, options={}) => {
            const method = options.method || "GET";
            window.calls.push({url:String(url),method});
            if (method !== "GET") throw new Error("Mutation forbidden in this fixture");
            const body = String(url).endsWith("/api/library") ? {papers:rows,total:rows.length} : {available:false};
            return new Response(JSON.stringify(body), {status:200,headers:{"Content-Type":"application/json"}});
          };
        }''')
        page.add_script_tag(content=source)
        page.evaluate("document.dispatchEvent(new Event('DOMContentLoaded'))")
        page.wait_for_function("document.querySelectorAll('.library-item').length === 23")
        assert page.locator("#libraryGraphSelected").is_disabled()
        assert page.locator(".library-item__select:disabled").count() == 1
        page.locator('[data-paper-id="owned-fixture-0"] input[type=checkbox]').check()
        page.locator('[data-paper-id="owned-fixture-1"] input[type=checkbox]').check()
        page.locator("#librarySort").select_option("title-desc")
        assert page.locator(".library-item__select:checked").count() == 2
        page.locator("#libraryGraphSelected").click()
        assert page.evaluate("window.events[0].dois") == ["10.1234/fixture-0", "10.1234/fixture-1"]
        page.locator("#librarySelectAll").check()
        assert page.locator("#libraryGraphSelected").is_disabled()
        assert "20" in page.locator("#librarySelectionStatus").inner_text()
        assert page.evaluate("window.events.length") == 1
        for index in (20,21):
            page.locator(f'[data-paper-id="owned-fixture-{index}"] input[type=checkbox]').uncheck()
        page.locator("#libraryGraphSelected").click()
        expected = [f"10.1234/fixture-{index}" for index in range(20)]
        assert page.evaluate("window.events[1].dois") == expected
        assert not errors, errors
        assert page.evaluate("window.calls.every(call => call.method === 'GET')")
        print(json.dumps({"scope":"private in-memory Chromium fixture; no network or persistent writes", "client_sha256":hashlib.sha256(source.encode()).hexdigest(),"rows":23,"invalid_doi_disabled":True,"two_seed_event_correct":True,"selection_survives_sort":True,"over_limit_disabled_without_truncation":True,"twenty_seed_event_correct":True,"page_errors":errors}))
        browser.close()


if __name__ == "__main__":
    main()
