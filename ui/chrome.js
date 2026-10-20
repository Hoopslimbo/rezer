/* Rezer browser chrome — injected into every page by the Python host.
 * Builds: tab strip, nav bar, bookmark bar, password prompt, Luna sidebar.
 * Talks to Python through `pywebview.api`. State arrives via RezerChrome.sync().
 */
(function () {
  if (window.__rezerChrome) return;
  window.__rezerChrome = true;

  var api = function () { return (window.pywebview && window.pywebview.api) || null; };
  function call(name) {
    var a = api();
    if (!a || !a[name]) return Promise.resolve(null);
    var args = Array.prototype.slice.call(arguments, 1);
    try { return Promise.resolve(a[name].apply(a, args)); }
    catch (e) { return Promise.resolve(null); }
  }

  var CHROME_H = 114, CHROME_H_NOBM = 82;

  /* ---------- DOM ---------- */
  var chrome = document.createElement('div');
  chrome.id = 'rezer-chrome';
  chrome.innerHTML =
    '<div id="rz-tabs">' +
    '<button id="rz-newtab" title="New tab (Ctrl+T)">+</button>' +
    '<div id="rz-tablist"><div id="rz-tabspacer"></div></div>' +
    '<button class="rz-iconbtn" id="rz-luna-btn" title="Luna AI">&#9790;</button>' +
    '<button class="rz-iconbtn" id="rz-menu-btn" title="Menu">&#8942;</button></div>' +
    '<div id="rz-nav">' +
    '<span id="rz-private-badge">PRIVATE</span>' +
    '<button class="rz-iconbtn" id="rz-back" title="Back">&#8592;</button>' +
    '<button class="rz-iconbtn" id="rz-fwd" title="Forward">&#8594;</button>' +
    '<button class="rz-iconbtn" id="rz-reload" title="Reload">&#8635;</button>' +
    '<input id="rz-addr" type="text" spellcheck="false" autocomplete="off" placeholder="Search or enter address"/>' +
    '<button class="rz-iconbtn" id="rz-star" title="Bookmark this page">&#9734;</button>' +
    '<button class="rz-iconbtn" id="rz-shot" title="Screenshot">&#128247;</button>' +
    '<button class="rz-iconbtn" id="rz-settings" title="Settings">&#9881;</button>' +
    '</div>' +
    '<div id="rz-suggest"></div>' +
    '<div id="rz-bookmarks"></div>' +
    '<div id="rz-pw-prompt"><span>Save password for this site?</span>' +
    '<button class="rz-primary" id="rz-pw-yes">Save</button>' +
    '<button id="rz-pw-no">No</button></div>' +
    '<div id="rz-menu" style="display:none;position:absolute;right:8px;top:70px;background:var(--rz-bg);' +
    'border:1px solid var(--rz-border);border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.15);' +
    'min-width:200px;padding:6px;z-index:10;"></div>';
  document.documentElement.appendChild(chrome);

  var luna = document.createElement('div');
  luna.id = 'rezer-luna';
  luna.innerHTML =
    '<div id="rz-luna-head"><img id="rz-luna-logo" alt="Luna"/>' +
    '<b>Luna</b><button class="rz-iconbtn" id="rz-luna-x" title="Close">&#10005;</button></div>' +
    '<div id="rz-luna-actions">' +
    '<button id="rz-luna-sum">Summarize this page</button>' +
    '<button id="rz-luna-exp">Explain selection</button></div>' +
    '<div id="rz-luna-msgs"></div>' +
    '<div id="rz-luna-inputrow"><input id="rz-luna-input" placeholder="Ask Luna anything..."/>' +
    '<button id="rz-luna-send">Send</button></div>';
  document.documentElement.appendChild(luna);

  var toast = document.createElement('div');
  toast.id = 'rz-toast';
  document.documentElement.appendChild(toast);
  var toastT = null;
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('rz-show');
    clearTimeout(toastT);
    toastT = setTimeout(function () { toast.classList.remove('rz-show'); }, 2200);
  }

  function padPage() {
    var bm = document.getElementById('rz-bookmarks');
    var h = (!bm || bm.classList.contains('rz-hidden')) ? CHROME_H_NOBM : CHROME_H;
    document.documentElement.style.paddingTop = h + 'px';
    document.documentElement.style.setProperty('--rz-chrome-h', h + 'px');
  }

  /* ---------- state ---------- */
  var S = null; // last synced state
  var addrFocused = false;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  var didInitialFocus = false;
  window.RezerChrome = {
    sync: function (state) {
      S = state;
      applyTheme(state.themeColor);
      renderTabs(state);
      renderAddr(state);
      renderBookmarks(state);
      renderMisc(state);
      padPage();
      // On a fresh document showing the new-tab page, put the cursor in the
      // address bar (like Chrome's new tab). Only on the first sync of this
      // document, so later state pushes never steal focus from the page.
      if (!didInitialFocus) {
        didInitialFocus = true;
        if (state.activeUrl === 'rezer://newtab') {
          var inp = document.getElementById('rz-addr');
          if (inp) inp.focus();
        }
      }
    },
    lunaReply: function (text) {
      var thinking = document.querySelector('#rz-luna-msgs .rz-thinking');
      if (thinking) thinking.remove();
      addMsg('luna', text);
    }
  };

  function isDarkColor(hex) {
    try {
      var c = String(hex || '#ffffff').replace('#', '');
      if (c.length === 3) c = c[0] + c[0] + c[1] + c[1] + c[2] + c[2];
      var r = parseInt(c.substr(0, 2), 16), g = parseInt(c.substr(2, 2), 16), b = parseInt(c.substr(4, 2), 16);
      var lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      return lum < 0.5;
    } catch (e) { return false; }
  }

  function applyTheme(color) {
    color = color || '#ffffff';
    var root = document.documentElement.style;
    root.setProperty('--rz-bg', color);
    // auto-contrast: dark theme color -> light text, and vice versa
    if (isDarkColor(color)) {
      root.setProperty('--rz-text', '#f2f2f2');
      root.setProperty('--rz-muted', '#a3a3a3');
      root.setProperty('--rz-border', '#3d3d3d');
      root.setProperty('--rz-hover', 'rgba(255,255,255,0.08)');
      root.setProperty('--rz-active', 'rgba(255,255,255,0.14)');
    } else {
      root.setProperty('--rz-text', '#1a1a1a');
      root.setProperty('--rz-muted', '#6b7280');
      root.setProperty('--rz-border', '#e2e2e2');
      root.setProperty('--rz-hover', 'rgba(0,0,0,0.06)');
      root.setProperty('--rz-active', 'rgba(0,0,0,0.1)');
    }
  }

  function faviconUrl(u) {
    try {
      var p = new URL(u);
      if (p.protocol === 'http:' || p.protocol === 'https:') return p.origin + '/favicon.ico';
    } catch (e) {}
    return null;
  }

  function renderTabs(state) {
    var list = document.getElementById('rz-tablist');
    var spacer = document.getElementById('rz-tabspacer');
    // remove old tabs (the spacer stays as the insert anchor at the end)
    var olds = list.querySelectorAll('.rz-tab');
    for (var i = 0; i < olds.length; i++) olds[i].remove();
    state.tabs.forEach(function (t) {
      var b = document.createElement('button');
      b.className = 'rz-tab' + (t.id === state.activeId ? ' rz-active' : '');
      b.title = t.title || t.url;
      b.innerHTML = '<span class="rz-tab-title">' + esc(t.title || t.url) + '</span>' +
        '<span class="rz-tab-x" data-x="' + t.id + '">&#10005;</span>';
      var fav = faviconUrl(t.url);
      if (fav) {
        var img = document.createElement('img');
        img.className = 'rz-tab-fav';
        img.alt = '';
        img.src = fav;
        img.addEventListener('error', function () { img.remove(); });
        b.insertBefore(img, b.firstChild);
      }
      b.addEventListener('click', function (e) {
        if (e.target.getAttribute('data-x')) { call('close_tab', t.id); e.stopPropagation(); return; }
        call('switch_tab', t.id);
      });
      // middle-click closes the tab (and shouldn't trigger autoscroll)
      b.addEventListener('mousedown', function (e) { if (e.button === 1) e.preventDefault(); });
      b.addEventListener('auxclick', function (e) {
        if (e.button === 1) { e.preventDefault(); call('close_tab', t.id); }
      });
      list.insertBefore(b, spacer);
    });
    var back = document.getElementById('rz-back'), fwd = document.getElementById('rz-fwd');
    back.style.opacity = state.canBack ? '1' : '0.35';
    fwd.style.opacity = state.canForward ? '1' : '0.35';
    chrome.classList.toggle('rz-private', !!state.private);
  }

  function renderAddr(state) {
    var input = document.getElementById('rz-addr');
    if (!addrFocused && document.activeElement !== input) {
      input.value = state.activeUrl && state.activeUrl.indexOf('rezer://') === 0 ? '' : (state.activeUrl || '');
    }
    var star = document.getElementById('rz-star');
    star.innerHTML = state.bookmarked ? '&#9733;' : '&#9734;';
    star.style.color = state.bookmarked ? 'var(--rz-accent)' : '';
  }

  function renderBookmarks(state) {
    var bar = document.getElementById('rz-bookmarks');
    bar.classList.toggle('rz-hidden', !state.bookmarkBar);
    bar.innerHTML = '';
    (state.bookmarks || []).forEach(function (b) {
      var el = document.createElement('button');
      el.className = 'rz-bm';
      el.textContent = b.title || b.url;
      el.title = b.url;
      el.addEventListener('click', function () { call('open_bookmark', b.url); });
      el.addEventListener('contextmenu', function (e) {
        e.preventDefault();
        // right-click = pin/unpin to new-tab top; manage/remove in Settings
        call('toggle_pin', b.url);
      });
      bar.appendChild(el);
    });
    if (!(state.bookmarks || []).length) {
      var hint = document.createElement('span');
      hint.style.cssText = 'font-size:12px;color:var(--rz-muted);padding:4px 10px;';
      hint.textContent = 'No bookmarks yet — star a page to add one.';
      bar.appendChild(hint);
    }
  }

  function renderMisc(state) {
    luna.classList.toggle('rz-open', !!state.lunaOpen);
  }

  /* ---------- events ---------- */
  document.getElementById('rz-newtab').addEventListener('click', function () { call('new_tab'); });
  // double-click empty tab-strip space opens a new tab (like other browsers)
  document.getElementById('rz-tabs').addEventListener('dblclick', function (e) {
    if (e.target === e.currentTarget || e.target.id === 'rz-tablist' || e.target.id === 'rz-tabspacer') {
      call('new_tab');
    }
  });

  /* Browser keyboard shortcuts, handled in the capture phase so they work
   * no matter where focus is — including while typing in a page input.
   * (The webview hands all keys to the page, so the chrome owns these.) */
  document.addEventListener('keydown', function (e) {
    if (!(e.ctrlKey || e.metaKey)) return;
    var k = e.key;
    if (k === 't' || k === 'T') {
      e.preventDefault(); e.stopPropagation();
      call('new_tab');
    } else if (k === 'w' || k === 'W') {
      e.preventDefault(); e.stopPropagation();
      if (S) call('close_tab', S.activeId);
    } else if (k === 'Tab') {
      e.preventDefault(); e.stopPropagation();
      call('cycle_tab', e.shiftKey ? -1 : 1);
    } else if (k === 'l' || k === 'L') {
      e.preventDefault(); e.stopPropagation();
      var inp = document.getElementById('rz-addr');
      if (inp) { inp.focus(); inp.select(); }
    }
  }, true);
  document.getElementById('rz-back').addEventListener('click', function () { call('go_back'); });
  document.getElementById('rz-fwd').addEventListener('click', function () { call('go_forward'); });
  document.getElementById('rz-reload').addEventListener('click', function () { call('reload'); });
  document.getElementById('rz-star').addEventListener('click', function () { call('toggle_bookmark'); });
  document.getElementById('rz-settings').addEventListener('click', function () { call('open_settings'); });
  document.getElementById('rz-shot').addEventListener('click', function () {
    call('take_screenshot').then(function (r) {
      showToast(r && r.ok ? 'Screenshot saved' : 'Screenshot failed');
    });
  });

  var addr = document.getElementById('rz-addr');
  addr.addEventListener('focus', function () { addrFocused = true; setTimeout(function(){ addr.select(); }, 0); });
  addr.addEventListener('blur', function () {
    addrFocused = false;
    // delay so a suggestion click (mousedown) lands before we hide
    setTimeout(function(){ hideAddrSug(); }, 120);
    if (S) renderAddr(S);
  });
  addr.addEventListener('keydown', function (e) {
    if (addrSugOpen()) {
      if (e.key === 'ArrowDown') { e.preventDefault(); addrSugMove(1); e.stopPropagation(); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); addrSugMove(-1); e.stopPropagation(); return; }
      if (e.key === 'Escape') { hideAddrSug(); e.stopPropagation(); return; }
      if (e.key === 'Enter' && addrSugSel >= 0) {
        e.preventDefault(); e.stopPropagation();
        var u = addrSugItems[addrSugSel].url;
        hideAddrSug(); call('navigate', u); addr.blur();
        return;
      }
    }
    if (e.key === 'Enter') { hideAddrSug(); call('navigate', addr.value); addr.blur(); }
    e.stopPropagation();
  });

  /* ---------- address bar suggestions ---------- */
  var addrSugBox = document.getElementById('rz-suggest');
  var addrSugItems = [], addrSugSel = -1, addrSugTimer = null;
  function addrSugOpen(){ return addrSugBox.classList.contains('rz-show'); }
  function hideAddrSug(){ addrSugBox.classList.remove('rz-show'); addrSugItems = []; addrSugSel = -1; }
  function addrSugMove(d){
    if(!addrSugItems.length) return;
    addrSugSel = (addrSugSel + d + addrSugItems.length) % addrSugItems.length;
    var rows = addrSugBox.querySelectorAll('.rz-sg');
    for(var i=0;i<rows.length;i++) rows[i].classList.toggle('rz-sel', i===addrSugSel);
  }
  function addrSugHost(u){ try { return new URL(u).hostname.replace(/^www\./,''); } catch(e){ return u; } }
  function renderAddrSug(items){
    addrSugItems = items || []; addrSugSel = -1;
    if(!addrSugItems.length){ hideAddrSug(); return; }
    var html = '';
    addrSugItems.forEach(function(it, i){
      var h = addrSugHost(it.url);
      var letter = it.kind === 'search' ? '&#8981;' : esc((h[0]||'?').toUpperCase());
      var sub = it.sub || h;
      html += '<div class="rz-sg" data-i="'+i+'">' +
        '<div class="rz-sg-ic">'+letter+'</div>' +
        '<div class="rz-sg-tx"><div class="rz-sg-ti">'+esc(it.title||h)+'</div>' +
        '<div class="rz-sg-ur">'+esc(sub)+'</div></div></div>';
    });
    addrSugBox.innerHTML = html;
    addrSugBox.classList.add('rz-show');
    var rows = addrSugBox.querySelectorAll('.rz-sg');
    for(var i=0;i<rows.length;i++){
      (function(idx){
        rows[idx].addEventListener('mousedown', function(e){
          e.preventDefault(); e.stopPropagation();
          var u = addrSugItems[idx].url;
          hideAddrSug(); call('navigate', u); addr.blur();
        });
        rows[idx].addEventListener('mousemove', function(){
          addrSugSel = idx;
          for(var j=0;j<rows.length;j++) rows[j].classList.toggle('rz-sel', j===idx);
        });
      })(i);
    }
  }
  function mergeAddrSug(gs){
    // Append Google suggestions behind the history matches, deduped by
    // title/url, capped so the dropdown stays compact.
    if(!gs || !gs.length) return;
    var seen = {};
    addrSugItems.forEach(function(it){
      seen[(it.title||'').toLowerCase()] = 1; seen[it.url] = 1;
    });
    var add = gs.filter(function(g){
      return !seen[(g.title||'').toLowerCase()] && !seen[g.url];
    });
    if(add.length) renderAddrSug(addrSugItems.concat(add).slice(0, 10));
  }
  addr.addEventListener('input', function(){
    clearTimeout(addrSugTimer);
    addrSugTimer = setTimeout(function(){
      var v = addr.value.trim();
      if(!v){ hideAddrSug(); return; }
      // history first (instant, local)...
      call('get_suggestions', v).then(function(items){
        if(addr.value.trim() !== v) return;  // query moved on
        renderAddrSug(items || []);
        // ...then Google suggestions, so recommendations also work with an
        // empty history (fresh install) instead of never appearing at all.
        call('google_suggestions', v).then(function(gs){
          if(addr.value.trim() !== v) return;
          mergeAddrSug(gs || []);
        });
      });
    }, 150);
  });

  // menu
  var menuBtn = document.getElementById('rz-menu-btn');
  var menu = document.getElementById('rz-menu');
  var menuItems = [
    ['New window', 'open_new_window'],
    ['New private window', 'open_private'],
    ['History', 'open_history'],
    ['Screenshot', 'shot'],
    ['Settings', 'open_settings'],
  ];
  menuItems.forEach(function (it) {
    var b = document.createElement('button');
    b.textContent = it[0];
    b.style.cssText = 'display:block;width:100%;text-align:left;border:none;background:none;padding:8px 12px;cursor:pointer;font-size:13px;color:var(--rz-text);border-radius:6px;';
    b.onmouseenter = function(){ b.style.background = 'var(--rz-hover)'; };
    b.onmouseleave = function(){ b.style.background = 'none'; };
    b.addEventListener('click', function () {
      menu.style.display = 'none';
      if (it[1] === 'shot') document.getElementById('rz-shot').click();
      else if (it[1] === 'open_history') call('navigate', 'rezer://history');
      else call(it[1]);
    });
    menu.appendChild(b);
  });
  menuBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
  });
  document.addEventListener('click', function () { menu.style.display = 'none'; });

  /* ---------- Luna ---------- */
  var lunaBtn = document.getElementById('rz-luna-btn');
  lunaBtn.addEventListener('click', function () { call('toggle_luna'); });
  document.getElementById('rz-luna-x').addEventListener('click', function () { call('toggle_luna'); });

  function addMsg(who, text) {
    var box = document.getElementById('rz-luna-msgs');
    var d = document.createElement('div');
    d.className = 'rz-msg rz-' + who;
    d.textContent = text;
    box.appendChild(d);
    box.scrollTop = box.scrollHeight;
  }
  function lunaAsk(prompt) {
    if (!prompt.trim()) return;
    addMsg('user', prompt);
    addMsg('thinking', 'Luna is thinking…');
    call('luna_ask', prompt);
  }
  document.getElementById('rz-luna-send').addEventListener('click', function () {
    var i = document.getElementById('rz-luna-input');
    lunaAsk(i.value); i.value = '';
  });
  document.getElementById('rz-luna-input').addEventListener('keydown', function (e) {
    e.stopPropagation();
    if (e.key === 'Enter') {
      lunaAsk(e.target.value); e.target.value = '';
    }
  });
  document.getElementById('rz-luna-sum').addEventListener('click', function () {
    addMsg('user', 'Summarize this page');
    addMsg('thinking', 'Luna is reading the page…');
    var text = '';
    try { text = document.body.innerText.slice(0, 4000); } catch (e) {}
    call('luna_summarize', text);
  });
  document.getElementById('rz-luna-exp').addEventListener('click', function () {
    var sel = '';
    try { sel = window.getSelection().toString().slice(0, 2000); } catch (e) {}
    if (!sel.trim()) { showToast('Select some text first'); return; }
    addMsg('user', 'Explain: "' + sel.slice(0, 80) + '…"');
    addMsg('thinking', 'Luna is thinking…');
    call('luna_explain', sel);
  });
  // Luna logo — retry a few times; the bridge may lag the injection
  (function pullLogo(tries) {
    var a = api();
    if (a && a.luna_logo) {
      a.luna_logo().then(function (u) {
        if (u) document.getElementById('rz-luna-logo').src = u;
      });
      return;
    }
    if (tries < 20) setTimeout(function () { pullLogo(tries + 1); }, 300);
  })(0);

  /* ---------- password manager ---------- */
  var pendingCreds = null;
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || !form.querySelector) return;
    var pw = form.querySelector('input[type="password"]');
    if (!pw || !pw.value) return;
    var userField = form.querySelector('input[type="text"],input[type="email"],input[name*="user" i],input[name*="login" i],input[name*="email" i]');
    pendingCreds = { u: userField ? userField.value : '', p: pw.value };
    var bar = document.getElementById('rz-pw-prompt');
    call('password_offer', pendingCreds.u, pendingCreds.p).then(function (offer) {
      if (offer) bar.classList.add('rz-show');
      else pendingCreds = null;
    });
  }, true);
  document.getElementById('rz-pw-yes').addEventListener('click', function () {
    if (pendingCreds) call('password_save', pendingCreds.u, pendingCreds.p);
    document.getElementById('rz-pw-prompt').classList.remove('rz-show');
    pendingCreds = null;
    showToast('Password saved');
  });
  document.getElementById('rz-pw-no').addEventListener('click', function () {
    document.getElementById('rz-pw-prompt').classList.remove('rz-show');
    pendingCreds = null;
  });
  // autofill once per page
  var filled = false;
  function tryFill() {
    if (filled) return; filled = true;
    call('password_fill').then(function (creds) {
      if (!creds || !creds.password) return;
      var pw = document.querySelector('input[type="password"]');
      if (pw && !pw.value) {
        pw.value = creds.password;
        pw.dispatchEvent(new Event('input', { bubbles: true }));
        var uf = document.querySelector('input[type="text"],input[type="email"]');
        if (uf && !uf.value && creds.username) {
          uf.value = creds.username;
          uf.dispatchEvent(new Event('input', { bubbles: true }));
        }
        showToast('Password filled');
      }
    });
  }
  setTimeout(tryFill, 1200);

  /* ---------- pollers ---------- */
  var lastHref = location.href, lastTitle = document.title;
  setInterval(function () {
    try {
      if (location.href !== lastHref) {
        lastHref = location.href;
        call('on_url_changed', lastHref);
      }
      if (document.title !== lastTitle) {
        lastTitle = document.title;
        call('on_title', lastTitle);
      }
    } catch (e) {}
  }, 500);

  // initial state pull — retry until the pywebview JS bridge is ready.
  // (The host waits for the bridge before injecting, but on slow machines
  // the bridge can still lag a moment behind the injection.)
  (function pullState(tries) {
    var a = api();
    if (a && a.get_state) {
      a.get_state().then(function (s) { if (s) window.RezerChrome.sync(s); });
      return;
    }
    if (tries < 50) setTimeout(function () { pullState(tries + 1); }, 300);
  })(0);
  padPage();
})();
