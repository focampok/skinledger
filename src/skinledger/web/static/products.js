// Product form: live target counter and a hard client-side cap at four.
(function () {
  "use strict";

  var form = document.querySelector(".product-form");
  if (!form) return;

  var boxes = Array.prototype.slice.call(
    form.querySelectorAll('input[name="target_aspects"]')
  );
  var counter = form.querySelector("#target-count");
  var max = Number(form.getAttribute("data-max-targets")) || 4;
  var template = form.getAttribute("data-count-template") || "{count} of {max} selected";

  function update() {
    var checked = boxes.filter(function (box) {
      return box.checked;
    }).length;
    if (counter) {
      counter.textContent = template
        .replace("{count}", checked)
        .replace("{max}", max);
    }
    boxes.forEach(function (box) {
      box.disabled = checked >= max && !box.checked;
    });
  }

  boxes.forEach(function (box) {
    box.addEventListener("change", update);
  });
  update();
})();
