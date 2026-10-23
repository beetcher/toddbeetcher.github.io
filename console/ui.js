/* Console shared parts (step 1.3a). Loaded before console.js. Stations use these instead of building their own.
   window.UI.confirm(opts)  -> Promise<boolean>. A real dialog: the page behind it is inert, Escape or Cancel answers no, focus returns to where it was.
        opts: { title, message, yes, no, danger } . The safe button (Cancel) has focus first when danger is true.
   window.UI.dismiss() -> closes an open dialog as 'no' (used when the Console locks).
   window.UI.chip(kind, text) -> a status chip. kind: ok | warn | err | info | quiet. The words always carry the meaning; colour only helps.
   window.UI.banner(kind, text) -> a message strip. kind: ok | warn | err | info. Errors are announced at once (role=alert).
   window.UI.empty(title, hint, actionNode) -> an empty-state block. */
(function () {
  "use strict";
  var dlg = null, pending = null, opener = null;

  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }

  function ensure() {
    if (dlg) return dlg;
    dlg = el("dialog", "uidlg"); dlg.id = "uiDialog";
    dlg.setAttribute("aria-labelledby", "uiTitle"); dlg.setAttribute("aria-describedby", "uiMsg");
    var t = el("h2", "uititle"); t.id = "uiTitle";
    var m = el("p", "uimsg"); m.id = "uiMsg";
    var row = el("div", "uibtns");
    var no = el("button", "quiet", "Cancel"); no.type = "button"; no.id = "uiNo";
    var yes = el("button", "", "Yes"); yes.type = "button"; yes.id = "uiYes";
    row.appendChild(no); row.appendChild(yes);
    dlg.appendChild(t); dlg.appendChild(m); dlg.appendChild(row);
    document.body.appendChild(dlg);
    yes.addEventListener("click", function () { finish(true); });
    no.addEventListener("click", function () { finish(false); });
    dlg.addEventListener("cancel", function (e) { e.preventDefault(); finish(false); });   // Escape
    dlg.addEventListener("click", function (e) { if (e.target === dlg) finish(false); });   // the dimmed area around the box
    return dlg;
  }

  function finish(answer) {
    if (!pending) return;
    var done = pending; pending = null;
    if (dlg.open) dlg.close();
    if (opener && opener.focus && document.contains(opener)) { try { opener.focus(); } catch (e) {} }
    opener = null;
    done(answer);
  }

  function confirmDialog(opts) {
    opts = opts || {};
    if (!ensure().showModal) return Promise.resolve(window.confirm(opts.message || opts.title || "Are you sure?"));
    if (pending) finish(false);
    opener = document.activeElement;
    $t("uiTitle").textContent = opts.title || "Are you sure?";
    $t("uiMsg").textContent = opts.message || "";
    $t("uiMsg").hidden = !opts.message;
    $t("uiYes").textContent = opts.yes || "Yes";
    $t("uiNo").textContent = opts.no || "Cancel";
    dlg.classList.toggle("danger", !!opts.danger);
    return new Promise(function (resolve) {
      pending = resolve;
      dlg.showModal();
      $t(opts.danger ? "uiNo" : "uiYes").focus();
    });
  }
  function $t(id) { return document.getElementById(id); }

  function chip(kind, text) { return el("span", "chip chip-" + (kind || "quiet"), text); }

  function banner(kind, text) {
    var b = el("div", "banner banner-" + (kind || "info"), text);
    b.setAttribute("role", kind === "err" ? "alert" : "status");
    return b;
  }

  function empty(title, hint, action) {
    var d = el("div", "empty"); d.appendChild(el("p", "empty-title", title));
    if (hint) d.appendChild(el("p", "empty-hint", hint));
    if (action) d.appendChild(action);
    return d;
  }

  window.UI = { dismiss: function () { finish(false); }, confirm: confirmDialog, chip: chip, banner: banner, empty: empty };
})();
