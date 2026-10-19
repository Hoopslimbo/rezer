"""Basic built-in ad blocker.

pywebview does not expose WebView2's network interception, so blocking happens
in-page via injected JS: known ad/tracker domains are neutered for
fetch/XHR/script loads, and common ad elements are hidden/removed with a
MutationObserver. Honest scope: cosmetic + script-level blocking, not
network-level.
"""

# Domains whose requests/scripts get neutralized in-page.
BLOCKED_DOMAINS = [
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "adservice.google.com",
    "ads.yahoo.com",
    "adnxs.com",
    "criteo.com",
    "criteo.net",
    "taboola.com",
    "outbrain.com",
    "amazon-adsystem.com",
    "aax.amazon-adsystem.com",
    "moatads.com",
    "scorecardresearch.com",
    "hotjar.com",
    "fullstory.com",
    "facebook.net/tr",
    "connect.facebook.net/en_US/fbevents",
    "static.ads-twitter.com",
    "ads.linkedin.com",
    "bat.bing.com",
    "analytics.tiktok.com",
]

# CSS selectors hidden on sight.
AD_SELECTORS = [
    ".ad", ".ads", ".advert", ".advertisement", ".sponsored",
    "[id^='google_ads']", "[id*='banner_ad']", "[class*='banner-ad']",
    "[id^='div-gpt-ad']", ".gpt-ad", "[data-ad]", "[data-ad-slot]",
    "iframe[src*='doubleclick']", "iframe[src*='googlesyndication']",
    ".taboola", ".outbrain", "#taboola", "#outbrain",
    "[aria-label='Advertisement']",
]

ADBLOCK_JS = r"""
(function () {
  if (window.__rezerAdblock) return;
  window.__rezerAdblock = true;
  var DOMAINS = %DOMAINS%;
  var SELECTORS = %SELECTORS%;

  function isAdUrl(u) {
    try { u = String(u).toLowerCase(); } catch (e) { return false; }
    for (var i = 0; i < DOMAINS.length; i++) {
      if (u.indexOf(DOMAINS[i]) !== -1) return true;
    }
    return false;
  }

  // Neutralize fetch / XHR to ad domains.
  var _fetch = window.fetch;
  window.fetch = function (input, init) {
    var u = typeof input === 'string' ? input : (input && input.url);
    if (u && isAdUrl(u)) return Promise.reject(new Error('blocked by Rezer'));
    return _fetch.apply(this, arguments);
  };
  var _open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, u) {
    if (u && isAdUrl(u)) { this.__rezerBlocked = true; }
    return _open.apply(this, arguments);
  };
  var _send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    if (this.__rezerBlocked) return;
    return _send.apply(this, arguments);
  };

  // Hide / remove ad elements.
  var css = SELECTORS.join(',') + '{display:none!important;}';
  var st = document.createElement('style');
  st.textContent = css;
  (document.head || document.documentElement).appendChild(st);

  function sweep(root) {
    try {
      var els = (root || document).querySelectorAll(SELECTORS.join(','));
      for (var i = 0; i < els.length; i++) els[i].remove();
      var scripts = document.querySelectorAll('script[src]');
      for (var j = 0; j < scripts.length; j++) {
        if (isAdUrl(scripts[j].src)) scripts[j].remove();
      }
    } catch (e) {}
  }
  sweep(document);
  new MutationObserver(function (muts) {
    for (var i = 0; i < muts.length; i++) {
      var n = muts[i].addedNodes;
      for (var j = 0; j < n.length; j++) {
        if (n[j].nodeType === 1) sweep(n[j]);
      }
    }
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
"""


def injection_js() -> str:
    import json
    js = ADBLOCK_JS.replace("%DOMAINS%", json.dumps(BLOCKED_DOMAINS))
    js = js.replace("%SELECTORS%", json.dumps(AD_SELECTORS))
    return js
