// SkinLedger "Copy list": plain JS, no dependency, no network.
(function () {
  "use strict";

  var button = document.getElementById("copy-list");
  var list = document.getElementById("shopping-list");
  if (!button || !list) return;

  button.addEventListener("click", function () {
    var names = [];
    list.querySelectorAll('input[type="checkbox"]:checked').forEach(function (input) {
      var value = input.getAttribute("value");
      if (value) names.push(value);
    });
    if (!names.length) {
      window.alert(button.getAttribute("data-empty") || "");
      return;
    }
    var copied = button.getAttribute("data-copied") || button.textContent;
    var confirm = function () {
      var original = button.textContent;
      button.textContent = copied;
      window.setTimeout(function () {
        button.textContent = original;
      }, 2000);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(names.join("\n")).then(confirm).catch(function () {});
    }
  });
})();
