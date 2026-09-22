/* UNMC Data Governance site behaviour.
 *
 * Everything here is an enhancement. With JavaScript off the site still works:
 * every term is listed on the glossary page, every row is a real link, and the
 * theme falls back to the reader's OS preference. Only search and the filter
 * pills stop working, and both say so.
 *
 * No build step, no dependencies -- the site has to open straight out of a
 * downloaded PR-preview artifact over file://.
 */
(function () {
  "use strict";

  var BASE = window.UNMC_DG_BASE || "";
  var THEME_KEY = "unmc-dg-theme";

  /* ---------- Theme ---------- */

  function currentTheme() {
    var explicit = document.documentElement.getAttribute("data-theme");
    if (explicit) return explicit;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function paintToggle() {
    var label = document.querySelector("[data-theme-label]");
    if (!label) return;
    label.innerHTML = currentTheme() === "dark" ? "☀ Light" : "☾ Dark";
  }

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch (e) {
        /* Private browsing, or site data blocked. The theme still applies for
           this page view; it just will not be remembered. */
      }
      paintToggle();
    });
    paintToggle();
  }

  /* ---------- Search index ---------- */

  var index = null;
  var indexPromise = null;

  function loadIndex() {
    if (indexPromise) return indexPromise;
    indexPromise = fetch(BASE + "assets/search-index.json")
      .then(function (r) {
        if (!r.ok) throw new Error("search index unavailable");
        return r.json();
      })
      .then(function (data) {
        index = data.map(function (entry) {
          return Object.assign({}, entry, { haystack: (entry.text || "").toLowerCase() });
        });
        return index;
      })
      .catch(function () {
        index = [];
        return index;
      });
    return indexPromise;
  }

  function score(entry, needle) {
    var title = entry.title.toLowerCase();
    if (title === needle) return 0;
    if (title.indexOf(needle) === 0) return 1;
    var alts = (entry.alt || []).map(function (a) {
      return a.toLowerCase();
    });
    for (var i = 0; i < alts.length; i++) {
      if (alts[i].indexOf(needle) === 0) return 2;
    }
    if (title.indexOf(needle) > -1) return 3;
    if (entry.haystack.indexOf(needle) > -1) return 4;
    return -1;
  }

  function search(query, kind) {
    var needle = query.trim().toLowerCase();
    if (!needle || !index) return [];
    var hits = [];
    for (var i = 0; i < index.length; i++) {
      var entry = index[i];
      if (kind && kind !== "all" && entry.kind !== kind) continue;
      var s = score(entry, needle);
      if (s > -1) hits.push({ entry: entry, score: s });
    }
    hits.sort(function (a, b) {
      return a.score - b.score || a.entry.title.localeCompare(b.entry.title);
    });
    return hits.map(function (h) {
      return h.entry;
    });
  }

  /* ---------- Header type-ahead ---------- */

  var input = document.getElementById("site-search");
  var results = document.getElementById("search-results");

  function closeResults() {
    if (!results) return;
    results.innerHTML = "";
    if (input) input.setAttribute("aria-expanded", "false");
  }

  function renderDropdown(hits, query) {
    if (!results) return;
    if (!query.trim()) {
      closeResults();
      return;
    }
    if (!hits.length) {
      results.innerHTML = '<div class="search__empty">No matches for &ldquo;' + escapeHtml(query) + "&rdquo;</div>";
      input.setAttribute("aria-expanded", "true");
      return;
    }
    var html = hits.slice(0, 8).map(function (entry) {
      return (
        '<a class="search__hit" role="option" href="' + BASE + entry.url + '">' +
        '<div class="search__hit-title">' + escapeHtml(entry.title) + "</div>" +
        '<div class="search__hit-meta">' + escapeHtml(entry.meta || "") + "</div>" +
        "</a>"
      );
    });
    if (hits.length > 8) {
      html.push(
        '<a class="search__hit" role="option" href="' + BASE + "search.html?q=" +
        encodeURIComponent(query) + '"><div class="search__hit-meta">See all ' +
        hits.length + " results &rarr;</div></a>"
      );
    }
    results.innerHTML = html.join("");
    input.setAttribute("aria-expanded", "true");
  }

  if (input) {
    input.addEventListener("focus", loadIndex);
    input.addEventListener("input", function () {
      var query = input.value;
      loadIndex().then(function () {
        renderDropdown(search(query, "all"), query);
      });
    });
    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        input.value = "";
        closeResults();
        input.blur();
        return;
      }
      if (event.key === "Enter") {
        var first = results && results.querySelector(".search__hit");
        if (first) {
          event.preventDefault();
          window.location.href = first.getAttribute("href");
        } else if (input.value.trim()) {
          event.preventDefault();
          window.location.href = BASE + "search.html?q=" + encodeURIComponent(input.value);
        }
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        var hits = results ? Array.prototype.slice.call(results.querySelectorAll(".search__hit")) : [];
        if (!hits.length) return;
        event.preventDefault();
        var current = hits.findIndex(function (h) {
          return h.getAttribute("aria-selected") === "true";
        });
        hits.forEach(function (h) {
          h.removeAttribute("aria-selected");
        });
        var next = event.key === "ArrowDown" ? current + 1 : current - 1;
        if (next < 0) next = hits.length - 1;
        if (next >= hits.length) next = 0;
        hits[next].setAttribute("aria-selected", "true");
        hits[next].scrollIntoView({ block: "nearest" });
      }
    });

    document.addEventListener("click", function (event) {
      if (results && !results.contains(event.target) && event.target !== input) closeResults();
    });

    document.addEventListener("keydown", function (event) {
      var tag = (event.target.tagName || "").toLowerCase();
      if (event.key === "/" && tag !== "input" && tag !== "textarea" && !event.metaKey && !event.ctrlKey) {
        event.preventDefault();
        input.focus();
        input.select();
      }
    });
  }

  /* ---------- Search results page ---------- */

  var pageResults = document.querySelector("[data-search-page-results]");
  if (pageResults) {
    var summary = document.querySelector("[data-search-summary]");
    var heading = document.getElementById("search-heading");
    var kindFilter = "all";

    function queryFromUrl() {
      var match = /[?&]q=([^&]*)/.exec(window.location.search);
      return match ? decodeURIComponent(match[1].replace(/\+/g, " ")) : "";
    }

    function renderPage() {
      var query = input ? input.value : queryFromUrl();
      if (!query.trim()) {
        pageResults.innerHTML = "";
        return;
      }
      var hits = search(query, kindFilter);
      if (heading) heading.textContent = "Results for “" + query + "”";
      if (summary) {
        summary.textContent =
          hits.length + (hits.length === 1 ? " match" : " matches") +
          " across terms, subject areas, and standards · sorted by relevance";
      }
      if (!hits.length) {
        pageResults.innerHTML =
          '<p style="color:var(--ink-2)">Nothing matched. Try a shorter phrase, or browse the ' +
          '<a href="' + BASE + 'glossary.html">full dictionary</a>.</p>';
        return;
      }
      pageResults.innerHTML = hits
        .map(function (entry) {
          return (
            '<div class="result">' +
            '<div class="result__head">' +
            '<span class="badge badge--' + entry.kind + '">' + escapeHtml(entry.kindLabel || entry.kind) + "</span>" +
            '<span class="result__path">' + escapeHtml(entry.path || "") + "</span>" +
            "</div>" +
            '<a class="result__title" href="' + BASE + entry.url + '">' + escapeHtml(entry.title) + "</a>" +
            '<p class="result__snippet">' + escapeHtml((entry.snippet || "").slice(0, 260)) + "</p>" +
            '<div class="result__meta"><span>' + escapeHtml(entry.meta || "") + "</span></div>" +
            "</div>"
          );
        })
        .join("");
    }

    var filterBar = document.querySelector("[data-search-filters]");
    if (filterBar) {
      filterBar.addEventListener("click", function (event) {
        var button = event.target.closest("[data-kind]");
        if (!button) return;
        kindFilter = button.getAttribute("data-kind");
        filterBar.querySelectorAll("[data-kind]").forEach(function (b) {
          b.setAttribute("aria-pressed", String(b === button));
        });
        renderPage();
      });
    }

    var initial = queryFromUrl();
    if (input && initial) input.value = initial;
    loadIndex().then(renderPage);
    if (input) input.addEventListener("input", renderPage);
  }

  /* ---------- Glossary filter pills ---------- */

  var filterBarEl = document.querySelector("[data-filter-bar]");
  if (filterBarEl) {
    var rows = Array.prototype.slice.call(document.querySelectorAll(".term-row[data-area]"));
    var countEl = document.querySelector("[data-term-count]");
    var emptyEl = document.querySelector("[data-empty]");

    filterBarEl.addEventListener("click", function (event) {
      var button = event.target.closest("[data-filter]");
      if (!button) return;
      var filter = button.getAttribute("data-filter");

      filterBarEl.querySelectorAll("[data-filter]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === button));
      });

      var shown = 0;
      rows.forEach(function (row) {
        var visible;
        if (filter === "all") {
          visible = true;
        } else if (filter === "attention") {
          var status = row.getAttribute("data-status");
          visible = status === "draft" || status === "in_review";
        } else {
          visible = "area:" + row.getAttribute("data-area") === filter;
        }
        row.hidden = !visible;
        if (visible) shown++;
      });

      if (countEl) countEl.textContent = shown + (shown === 1 ? " term" : " terms");
      if (emptyEl) emptyEl.hidden = shown !== 0;
    });
  }

  /* ---------- Copy to clipboard ---------- */

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    /* file:// and plain http are not secure contexts, and a steward opening
       the PR-preview artifact out of a downloaded zip is on file://. */
    return new Promise(function (resolve, reject) {
      var scratch = document.createElement("textarea");
      scratch.value = text;
      scratch.setAttribute("readonly", "");
      scratch.style.cssText = "position:fixed;top:-1000px;opacity:0";
      document.body.appendChild(scratch);
      scratch.select();
      var ok = false;
      try {
        ok = document.execCommand("copy");
      } catch (e) {
        ok = false;
      }
      document.body.removeChild(scratch);
      ok ? resolve() : reject(new Error("copy failed"));
    });
  }

  document.querySelectorAll("[data-copy-target]").forEach(function (button) {
    var source = document.getElementById(button.getAttribute("data-copy-target"));
    if (!source) return;

    var resetTimer = null;
    button.addEventListener("click", function () {
      copyText(source.textContent.trim()).then(
        function () {
          button.textContent = "Copied";
          button.setAttribute("data-copied", "");
        },
        function () {
          /* Say so rather than silently doing nothing; the value is on screen
             and can still be selected by hand. */
          button.textContent = "Press Ctrl+C to copy";
          var range = document.createRange();
          range.selectNodeContents(source);
          var selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
        }
      );
      clearTimeout(resetTimer);
      resetTimer = setTimeout(function () {
        button.textContent = button.getAttribute("data-copy-label");
        button.removeAttribute("data-copied");
      }, 2000);
    });
  });

  /* ---------- On-this-page rail ---------- */

  var railLinks = Array.prototype.slice.call(document.querySelectorAll(".toc-rail a[href^='#']"));
  if (railLinks.length && "IntersectionObserver" in window) {
    var targets = railLinks
      .map(function (link) {
        return document.getElementById(link.getAttribute("href").slice(1));
      })
      .filter(Boolean);

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          railLinks.forEach(function (link) {
            link.classList.toggle(
              "is-active",
              link.getAttribute("href") === "#" + entry.target.id
            );
          });
        });
      },
      { rootMargin: "-110px 0px -70% 0px" }
    );
    targets.forEach(function (t) {
      observer.observe(t);
    });
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }
})();
