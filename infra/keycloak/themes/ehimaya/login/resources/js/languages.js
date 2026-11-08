// e-Himaya sign-in (Yamen, 2026-11-08): the language as a gold circle; a press drops the other languages as gold
// circles. Built from Keycloak's own <select id="login-select-toggle">, which stays as it is without JavaScript.
(function () {
  "use strict";
  var SHORT = { ar: "ع", fr: "FR", en: "EN" };

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
    wrapper.style.display = "none";
    wrapper.parentNode.insertBefore(box, wrapper);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
