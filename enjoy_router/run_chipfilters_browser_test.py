#!/usr/bin/env python3
"""Browser test (Console run sheet H-1): the shared chip filter control in console/filters.js, on a blank page with console.css.
Covers: chips and their labels, popover, counts, Clear, Clear all, Escape, click outside, one popover at a time, "Only show" (start none),
pick-one, search inside a long list, keyboard walk, spoken names, setOptions / setCounts / setSelection, right-edge placement, the phone bottom sheet.
Screenshots go to $CF_SHOTS (default: a temp folder, printed at the end). Run from enjoy_router/:  python3 run_chipfilters_browser_test.py"""
import sys, os, pathlib, tempfile
HERE = pathlib.Path(__file__).resolve().parent
CONSOLE = HERE.parent / "console"
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("skip: playwright is not installed here"); sys.exit(0)

fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

work = pathlib.Path(tempfile.mkdtemp(prefix="cftest-"))
shots = pathlib.Path(os.environ.get("CF_SHOTS") or work)
shots.mkdir(parents=True, exist_ok=True)
page_file = work / "cf.html"
page_file.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="{(CONSOLE / 'console.css').as_uri()}"></head>
<body><main><h2>Messages</h2><div id="mount"></div><button id="after" type="button" class="btn-secondary">Something else on the page</button>
<ul id="rows"><li>row one</li><li>row two</li></ul></main>
<script src="{(CONSOLE / 'filters.js').as_uri()}"></script></body></html>""")

SETUP = """
window.__log = [];
var kinds = ['Access invite','Class cancelled','Class changed','Instructor placed','No trainer alert','No trainer digest','Participant left','Placement confirmation','Request received','Reminder'];
var regions = ['Colorado Front Range','Colorado West Slope','Colorado Southeast','Idaho','Montana','Nebraska','Oregon','Utah','Wyoming North','Wyoming South','No region yet'];
window.cf = UI.chipFilters({
  mount: document.getElementById('mount'), label: 'Message filters',
  filters: [
    { id: 'status', label: 'Status', kind: 'multi', options: [['sent','Sent',68],['failed','Failed',0],['unknown','Unknown',0],['not_sent','Not sent',6],['skipped','Skipped',0]].map(function (a) { return { value: a[0], label: a[1], count: a[2] }; }) },
    { id: 'kind', label: 'Message', kind: 'multi', options: kinds.map(function (k) { return { value: k.toLowerCase().replace(/ /g, '_'), label: k }; }) },
    { id: 'how', label: 'How it was sent', kind: 'multi', options: [{ value: 'automatic', label: 'Automatic' }, { value: 'manual', label: 'By hand' }] },
    { id: 'only', label: 'Only show', kind: 'multi', start: 'none', options: [{ value: 'notes', label: 'Has notes' }, { value: 'redir', label: 'Went to a test address' }] },
    { id: 'region', label: 'Region', kind: 'search-multi', options: regions.map(function (r) { return { value: r, label: r }; }) },
    { id: 'sort', label: 'Sort', kind: 'one', options: [{ value: 'new', label: 'Newest first' }, { value: 'old', label: 'Oldest first' }] },
    { id: 'attention', label: 'Needs attention', kind: 'toggle', noun: 'messages', title: 'Failed, unknown, or not sent and not yet handled' }
  ],
  onChange: function (sel) { window.__log.push(JSON.parse(JSON.stringify(sel))); }
});
"""

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(page_file.as_uri()); pg.evaluate(SETUP)

    chip = lambda name: pg.locator(".cf-chip", has=pg.locator(".cf-lab", has_text=name)).first
    def pop_of(name): return pg.locator(".cf-chipwrap", has=chip(name)).locator(".cf-pop")
    def labels(): return pg.eval_on_selector_all(".cf-chip .cf-lab", "els => els.map(e => e.textContent)")
    def opt(name, value): return pop_of(name).locator("label.cf-opt", has=pg.locator("input[value='%s']" % value))
    def log_n(): return pg.evaluate("window.__log.length")
    def sel(): return pg.evaluate("window.cf.getSelection()")

    # --- the row
    check("seven chips, each named for its filter, none narrowed", labels() == ["Status", "Message", "How it was sent", "Only show", "Region", "Sort", "Needs attention"], labels())
    check("Clear all is hidden while nothing is narrowed", not pg.locator(".cf-clearall").is_visible())
    check("the sheet title is a phone-only thing: hidden on desktop", pg.locator(".cf-title:visible").count() == 0)
    check("every chip is 40 px tall and the popovers start closed", all(h == 40 for h in pg.eval_on_selector_all(".cf-chip", "els => els.map(e => Math.round(e.getBoundingClientRect().height))")) and pg.locator(".cf-pop:visible").count() == 0)
    check("a chip says what it is for a screen reader", chip("Status").get_attribute("aria-label") == "Status filter, all selected", chip("Status").get_attribute("aria-label"))
    pg.screenshot(path=str(shots / "cf-1440-closed.png"))

    # --- open, counts, tick boxes
    chip("Status").click()
    check("Status opens a popover with five ticked entries and their counts", pop_of("Status").is_visible() and pop_of("Status").locator("input:checked").count() == 5 and pop_of("Status").locator(".cf-n").all_inner_texts() == ["68", "0", "0", "6", "0"], pop_of("Status").locator(".cf-n").all_inner_texts())
    check("the chip says it is open", chip("Status").get_attribute("aria-expanded") == "true")
    pg.screenshot(path=str(shots / "cf-1440-open.png"))
    n0 = log_n()
    opt("Status", "sent").click(); opt("Status", "skipped").click()
    check("unticking two entries narrows the chip to 3 of 5", labels()[0] == "Status: 3 of 5" and chip("Status").get_attribute("data-on") == "true", labels())
    check("the spoken name follows: 3 of 5 selected", chip("Status").get_attribute("aria-label") == "Status filter, 3 of 5 selected", chip("Status").get_attribute("aria-label"))
    check("onChange fired once per tick with the new choice", log_n() == n0 + 2 and "sent" not in sel()["status"] and "skipped" not in sel()["status"] and len(sel()["status"]) == 3, sel())
    check("Clear all appears", pg.locator(".cf-clearall").is_visible())
    opt("Status", "unknown").click(); opt("Status", "failed").click()
    check("one or two entries are named on the chip", labels()[0] == "Status: Not sent", labels())
    opt("Status", "sent").click()
    check("two entries are both named, in the list's order", labels()[0] == "Status: Sent, Not sent", labels())

    # --- Clear (this filter) and Escape
    pop_of("Status").get_by_role("button", name="Clear Status filter").click()
    check("Clear puts the filter back to everything", labels()[0] == "Status" and chip("Status").get_attribute("data-on") == "false" and pop_of("Status").locator("input:checked").count() == 5)
    check("and the Clear all link goes away again", not pg.locator(".cf-clearall").is_visible())
    pg.keyboard.press("Escape")
    check("Escape closes the popover and puts focus back on the chip", not pop_of("Status").is_visible() and pg.evaluate("document.activeElement.classList.contains('cf-chip') && document.activeElement.textContent.indexOf('Status') === 0"))

    # --- click outside, one popover at a time
    chip("Message").click(); check("Message opens with ten entries", pop_of("Message").locator("input").count() == 10 and pop_of("Message").is_visible())
    chip("How it was sent").click()
    check("opening another chip closes the first", pop_of("How it was sent").is_visible() and not pop_of("Message").is_visible())
    pg.click("#after")
    check("a click elsewhere on the page closes it", not pop_of("How it was sent").is_visible())

    # --- Only show (start none)
    chip("Only show").click()
    check("'Only show' starts with nothing ticked and the chip is off", pop_of("Only show").locator("input:checked").count() == 0 and labels()[3] == "Only show" and chip("Only show").get_attribute("aria-label") == "Only show filter, none selected")
    pop_of("Only show").locator("label", has_text="Has notes").click()
    check("ticking one narrows it: 'Only show: Has notes'", labels()[3] == "Only show: Has notes" and chip("Only show").get_attribute("aria-label") == "Only show filter, 1 selected", labels())
    check("the selection lists only what is ticked", sel()["only"] == ["notes"], sel())
    pg.keyboard.press("Escape")

    # --- pick one
    chip("Sort").click()
    check("pick-one shows radio buttons, the first is chosen", pop_of("Sort").locator("input[type=radio]").count() == 2 and pop_of("Sort").locator("input:checked").count() == 1)
    pop_of("Sort").locator("label", has_text="Oldest first").click()
    check("choosing with the mouse closes it and names the choice", not pop_of("Sort").is_visible() and labels()[5] == "Sort: Oldest first" and sel()["sort"] == ["old"], (labels(), sel()["sort"]))

    # --- search inside a long list
    chip("Region").click()
    check("the search box has focus when a long list opens", pg.evaluate("document.activeElement.classList.contains('cf-search')"))
    pg.keyboard.type("col")
    vis = pop_of("Region").locator("label.cf-opt:visible").all_inner_texts()
    check("typing narrows the list", len(vis) == 3 and all("Colorado" in v for v in vis), vis)
    pg.fill(".cf-search", "zzz")
    check("no match says so", pop_of("Region").locator(".cf-none").is_visible() and pop_of("Region").locator("label.cf-opt:visible").count() == 0)
    pg.fill(".cf-search", "idaho")
    pop_of("Region").locator("label.cf-opt:visible").first.click()
    check("an entry found by search can be unticked", sel()["region"].count("Idaho") == 0 and labels()[4] == "Region: 10 of 11", (labels()[4], sel()["region"]))
    pg.keyboard.press("Escape")

    # --- Clear all fires once
    n1 = log_n(); pg.click(".cf-clearall")
    check("Clear all resets every chip and fires onChange once", labels() == ["Status", "Message", "How it was sent", "Only show", "Region", "Sort", "Needs attention"] and log_n() == n1 + 1 and not pg.locator(".cf-clearall").is_visible(), (labels(), log_n() - n1))
    check("focus goes to the first chip after Clear all", pg.evaluate("document.activeElement.textContent.indexOf('Status') === 0"))

    # --- keyboard walk
    chip("Status").focus(); pg.keyboard.press("ArrowDown")
    check("Down on a chip opens it and focuses the first tick box", pop_of("Status").is_visible() and pg.evaluate("document.activeElement.type === 'checkbox'"))
    pg.keyboard.press("ArrowDown"); pg.keyboard.press("ArrowDown")
    check("Down moves between tick boxes", pg.evaluate("document.activeElement.value") == "unknown", pg.evaluate("document.activeElement.value"))
    pg.keyboard.press("ArrowUp")
    pg.keyboard.press("Space")
    check("Space ticks and unticks", labels()[0] == "Status: 4 of 5" and "failed" not in sel()["status"], (labels()[0], sel()["status"]))
    pg.keyboard.press("Escape")
    check("Escape returns to the chip", pg.evaluate("document.activeElement.classList.contains('cf-chip')"))
    pg.keyboard.press("Enter")
    check("Enter on the chip opens it again", pop_of("Status").is_visible())
    for _ in range(6): pg.keyboard.press("Tab")   # four more entries, Clear, Done
    check("Tab runs through the entries, then Clear, then Done, all still inside the popover", pop_of("Status").is_visible() and pg.evaluate("document.activeElement.textContent") == "Done", pg.evaluate("document.activeElement.textContent"))
    pg.keyboard.press("Tab")
    check("one more Tab leaves the popover, closes it, and lands on the next chip", not pop_of("Status").is_visible() and pg.evaluate("document.activeElement.classList.contains('cf-chip') && document.activeElement.textContent.indexOf('Message') === 0"), pg.evaluate("document.activeElement.textContent"))
    pg.click(".cf-clearall")

    # --- switch chip (J-1)
    sw = chip("Needs attention")
    check("a switch chip has no caret, no popover, and starts off", sw.locator(".cf-caret").count() == 0 and pg.locator(".cf-chipwrap", has=sw).locator(".cf-pop").count() == 0 and sw.get_attribute("aria-pressed") == "false" and sw.get_attribute("data-on") == "false")
    check("its spoken name says off", sw.get_attribute("aria-label") == "Needs attention filter, off", sw.get_attribute("aria-label"))
    check("it carries its hover hint", sw.get_attribute("title") == "Failed, unknown, or not sent and not yet handled")
    pg.evaluate("window.cf.setBadge('attention', 6)")
    check("a badge number shows beside the words and is spoken with its noun", sw.locator(".cf-badge").inner_text() == "6" and sw.get_attribute("aria-label") == "Needs attention filter, off, 6 messages", sw.get_attribute("aria-label"))
    n3 = log_n(); sw.click()
    check("clicking turns it on, fires onChange once, and shows Clear all", sw.get_attribute("aria-pressed") == "true" and sw.get_attribute("data-on") == "true" and log_n() == n3 + 1 and sel()["attention"] == ["on"] and pg.locator(".cf-clearall").is_visible(), (sel()["attention"], log_n() - n3))
    check("spoken name says on", sw.get_attribute("aria-label") == "Needs attention filter, on, 6 messages", sw.get_attribute("aria-label"))
    sw.click()
    check("clicking again turns it off", sw.get_attribute("aria-pressed") == "false" and sel()["attention"] == [] and not pg.locator(".cf-clearall").is_visible())
    sw.focus(); pg.keyboard.press("Space")
    check("Space toggles it from the keyboard", sw.get_attribute("aria-pressed") == "true")
    pg.screenshot(path=str(shots / "cf-1440-switch-on.png"))
    pg.click(".cf-clearall")
    check("Clear all switches it off too", sw.get_attribute("aria-pressed") == "false" and sel()["attention"] == [])
    pg.evaluate("window.cf.setSelection({ attention: ['on'] })")
    check("setSelection can switch it on without firing onChange", sw.get_attribute("aria-pressed") == "true")
    pg.evaluate("window.cf.clearAll(); window.cf.setBadge('attention', '')")
    check("an empty badge is hidden", sw.locator(".cf-badge:visible").count() == 0 and sw.get_attribute("aria-label") == "Needs attention filter, off")

    # --- live result line inside the popover (J-1)
    chip("Status").click()
    check("the result line is hidden until there is text", pop_of("Status").locator(".cf-result:visible").count() == 0)
    pg.evaluate("window.cf.setResult('4 messages of 74')")
    check("setResult shows a polite live line above Clear and Done", pop_of("Status").locator(".cf-result").inner_text() == "4 messages of 74" and pop_of("Status").locator(".cf-result").get_attribute("role") == "status" and pop_of("Status").locator(".cf-result").get_attribute("aria-live") == "polite")
    pg.evaluate("window.cf.setResult('2 messages of 74')")
    check("it follows later changes", pop_of("Status").locator(".cf-result").inner_text() == "2 messages of 74")
    check("it sits between the list and the footer", pg.evaluate("(function(){var p=document.querySelector('.cf-pop:not([hidden])'),c=Array.prototype.map.call(p.children,function(e){return e.className});return c.indexOf('cf-result')>c.indexOf('cf-list') && c.indexOf('cf-result')<c.indexOf('cf-foot')})()"))
    pg.keyboard.press("Escape")
    chip("Region").click()
    check("every popover shows the same line, including a searched one", pop_of("Region").locator(".cf-result").inner_text() == "2 messages of 74")
    pg.keyboard.press("Escape")
    pg.evaluate("window.cf.setResult('')")
    chip("Status").click()
    check("an empty line is hidden again", pop_of("Status").locator(".cf-result:visible").count() == 0)
    pg.keyboard.press("Escape")

    # --- where focus lands on open (J-1, item 6)
    chip("Status").click()
    check("opened by mouse, focus rests on the popover itself: no entry shows a focus ring", pg.evaluate("document.activeElement.classList.contains('cf-pop')") and pop_of("Status").locator("input:focus").count() == 0, pg.evaluate("document.activeElement.className"))
    pg.keyboard.press("Escape")
    chip("Status").focus(); pg.keyboard.press("Enter")
    check("opened by Enter, focus goes to the first entry", pg.evaluate("document.activeElement.type === 'checkbox' && document.activeElement.value === 'sent'"), pg.evaluate("document.activeElement.value"))
    pg.keyboard.press("Escape")
    chip("Region").click()
    check("a searched list always focuses its search box, even by mouse", pg.evaluate("document.activeElement.classList.contains('cf-search')"))
    pg.keyboard.press("Escape")
    chip("Status").click(); pg.keyboard.press("ArrowDown")
    check("opened by mouse, Down still starts at the first entry", pg.evaluate("document.activeElement.type === 'checkbox'"), pg.evaluate("document.activeElement.className"))
    pg.keyboard.press("Escape")

    # --- code interface
    n2 = log_n()
    pg.evaluate("window.cf.setSelection({ status: ['sent', 'failed'], sort: ['new'] })")
    check("setSelection changes the chips but does not fire onChange", labels()[0] == "Status: Sent, Failed" and labels()[5] == "Sort" and log_n() == n2, (labels(), log_n() - n2))
    pg.evaluate("window.cf.setOptions('status', [{value:'sent',label:'Sent'},{value:'failed',label:'Failed'},{value:'unknown',label:'Unknown'},{value:'not_sent',label:'Not sent'},{value:'skipped',label:'Skipped'},{value:'bounced',label:'Bounced'}])")
    check("setOptions keeps the person's choices and ticks a brand new entry", sel()["status"] == ["sent", "failed", "bounced"], sel()["status"])
    pg.evaluate("window.cf.setCounts({ status: { sent: 5, failed: 2 } })")
    chip("Status").click()
    check("setCounts fills the numbers beside the entries", pop_of("Status").locator(".cf-n").all_inner_texts()[:2] == ["5", "2"], pop_of("Status").locator(".cf-n").all_inner_texts())
    pg.evaluate("window.cf.setCounts({})")
    check("setCounts({}) blanks them", pop_of("Status").locator(".cf-n:visible").count() == 0)
    pg.keyboard.press("Escape")
    pg.evaluate("window.cf.setNote('Search covers the whole log, so these filters are ignored.'); window.cf.setCount('Showing 6 of 74')")
    check("a note and a count can sit after the chips", pg.locator(".cf-note").is_visible() and "ignored" in pg.locator(".cf-note").inner_text() and pg.locator(".cf-count").inner_text() == "Showing 6 of 74")
    pg.evaluate("window.cf.setNote(''); window.cf.clearAll()")
    check("an empty note is hidden", not pg.locator(".cf-note").is_visible())
    pg.evaluate("window.cf.setSelection({ status: ['sent','failed'], kind: ['access_invite'] })")
    pg.screenshot(path=str(shots / "cf-1440-narrowed.png"))
    pg.evaluate("window.cf.clearAll()")

    # --- placement near the right edge (desktop widths)
    pg.set_viewport_size({"width": 760, "height": 900})
    pg.evaluate("document.getElementById('mount').style.marginLeft = '420px'")
    ok = True; bad = ""
    for name in ["Status", "Message", "How it was sent", "Only show", "Region", "Sort"]:
        chip(name).click(); r = pg.evaluate("(function(){var r=document.querySelector('.cf-pop:not([hidden])').getBoundingClientRect();return [r.left, r.right, window.innerWidth]})()")
        if r[0] < 0 or r[1] > r[2]: ok = False; bad = (name, r)
        pg.keyboard.press("Escape")
    check("every popover stays inside the window, even a chip near the right edge", ok, bad)
    pg.evaluate("document.getElementById('mount').style.marginLeft = ''")

    # --- phone
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(100)
    check("on a phone the chips are 44 px tall and wrap onto more than one line", all(h == 44 for h in pg.eval_on_selector_all(".cf-chip", "els => els.map(e => Math.round(e.getBoundingClientRect().height))")) and pg.evaluate("document.querySelector('.cf-row').getBoundingClientRect().height") > 60)
    pg.screenshot(path=str(shots / "cf-390-closed.png"))
    chip("Status").click()
    r = pg.evaluate("(function(){var p=document.querySelector('.cf-pop:not([hidden])'),r=p.getBoundingClientRect();return {l:r.left,r:r.right,b:r.bottom,w:window.innerWidth,h:window.innerHeight,pos:getComputedStyle(p).position,row:p.querySelector('label.cf-opt').getBoundingClientRect().height}})()")
    check("the popover is a full-width bottom sheet", r["pos"] == "fixed" and r["l"] == 0 and r["r"] == r["w"] and abs(r["b"] - r["h"]) < 1, r)
    check("entries are 48 px tall for a thumb", round(r["row"]) >= 48, r)
    check("the sheet names its filter at the top", pop_of("Status").locator(".cf-title").is_visible() and pop_of("Status").locator(".cf-title").inner_text() == "Status")
    check("a dimmed backdrop is behind it", pg.locator(".cf-open .cf-back").is_visible())
    pg.screenshot(path=str(shots / "cf-390-open.png"))
    pg.mouse.click(190, 40)
    check("tapping the backdrop closes the sheet", not pop_of("Status").is_visible())
    chip("Region").click()
    check("reopening a searched list starts with the search empty and every entry back", pg.evaluate("document.querySelector('.cf-pop:not([hidden]) .cf-search').value") == "" and pop_of("Region").locator("label.cf-opt:visible").count() == 11)
    pg.keyboard.type("wyo")
    check("search works in the sheet", pop_of("Region").locator("label.cf-opt:visible").count() == 2)
    pg.screenshot(path=str(shots / "cf-390-search.png"))
    pg.get_by_role("button", name="Done with Region filter").click()
    check("Done closes the sheet", not pop_of("Region").is_visible())

    check("no script errors", not errors, errors)
    b.close()

print("screenshots in " + str(shots))
print("\n" + ("ALL OK" if not fails else "FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
