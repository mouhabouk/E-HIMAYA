// e-Himaya sign-in (Yamen, 2026-11-08): the language as a gold circle; a press drops the other languages as gold
// circles. Built from Keycloak's own <select id="login-select-toggle">, which stays as it is without JavaScript.
// Under it, a circle of the other colour switches the page between royal blue and royal red, kept on this device.
(function () {
  "use strict";
  var THEME_KEY = "ehimaya-login-colour";
  var root = document.documentElement;

  function storedRed() {
    try {
      return window.localStorage.getItem(THEME_KEY) === "red";
    } catch (e) {
      return false;
    }
  }

  // Before the first paint (this file loads in <head>), so the page never flashes the other colour.
  if (storedRed()) root.classList.add("ehimaya-red");

  var THEME_LABELS = {
    ar: ["اللون الأحمر الملكي", "اللون الأزرق الملكي"],
    fr: ["Rouge royal", "Bleu royal"],
    en: ["Royal red", "Royal blue"],
  };

  function themeButton() {
    var lang = (root.lang || "ar").slice(0, 2);
    var labels = THEME_LABELS[lang] || THEME_LABELS.ar;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "ehimaya-theme";
    function label() {
      var red = root.classList.contains("ehimaya-red");
      var text = red ? labels[1] : labels[0];
      button.setAttribute("aria-label", text);
      button.setAttribute("title", text);
    }
    label();
    button.addEventListener("click", function () {
      var red = root.classList.toggle("ehimaya-red");
      try {
        window.localStorage.setItem(THEME_KEY, red ? "red" : "blue");
      } catch (e) {
        /* private window: the choice lasts for this page only */
      }
      label();
    });
    return button;
  }
  var SHORT = { ar: "ع", fr: "FR", en: "EN" };
  var ORDER = ["ar", "fr", "en"]; // Yamen, 2026-11-08: Arabic, then French, then English

  function code(url) {
    var m = /[?&]kc_locale=([a-zA-Z-]+)/.exec(url);
    return m ? m[1].toLowerCase() : "";
  }

  function circle(tag, lang, label) {
    var el = document.createElement(tag);
    el.className = "ehimaya-lang__circle";
    el.textContent = SHORT[lang] || lang.toUpperCase();
    el.setAttribute("lang", lang);
    el.setAttribute("title", label);
    el.setAttribute("aria-label", label);
    return el;
  }

  function build() {
    var select = document.getElementById("login-select-toggle");
    if (!select || !select.parentNode) return;
    var wrapper = select.parentNode;
    var current = null;
    var others = [];
    Array.prototype.forEach.call(select.options, function (o) {
      var item = { url: o.value, lang: code(o.value), label: o.textContent.trim() };
      if (o.selected) current = item;
      else others.push(item);
    });
    if (!current) current = { url: "", lang: document.documentElement.lang || "ar", label: "" };
    others.sort(function (a, b) {
      return ORDER.indexOf(a.lang) - ORDER.indexOf(b.lang);
    });

    var box = document.createElement("div");
    box.className = "ehimaya-lang";
    var toggle = circle("button", current.lang, current.label);
    toggle.type = "button";
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", "ehimaya-lang-list");
    var list = document.createElement("ul");
    list.id = "ehimaya-lang-list";
    list.className = "ehimaya-lang__list";
    list.hidden = true;
    others.forEach(function (o) {
      var li = document.createElement("li");
      var a = circle("a", o.lang, o.label);
      a.href = o.url;
      li.appendChild(a);
      list.appendChild(li);
    });

    function open(yes) {
      list.hidden = !yes;
      toggle.setAttribute("aria-expanded", yes ? "true" : "false");
      box.classList.toggle("is-open", yes);
    }
    toggle.addEventListener("click", function () {
      open(list.hidden);
    });
    document.addEventListener("click", function (e) {
      if (!box.contains(e.target)) open(false);
    });
    box.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        open(false);
        toggle.focus();
      }
    });

    box.appendChild(toggle);
    box.appendChild(list);
    box.appendChild(themeButton());
    wrapper.style.display = "none";
    wrapper.parentNode.insertBefore(box, wrapper);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
