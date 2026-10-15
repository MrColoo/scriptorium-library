// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Profile pictures: square-crop and downscale in the browser, then post as a data URI.
(function () {
  "use strict";
  var CWA = window.CWA;
  var i18n = document.getElementById("avatar-i18n");
  if (!CWA || !i18n) return;
  var T = JSON.parse(i18n.textContent);
  var SIZE = 256;
  var MAX_INPUT = 10 * 1024 * 1024;

  function render(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onerror = function () { reject(new Error(T.read)); };
      reader.onload = function () {
        var img = new Image();
        img.onload = function () {
          var side = Math.min(img.naturalWidth, img.naturalHeight);
          var canvas = document.createElement("canvas");
          canvas.width = canvas.height = Math.min(SIZE, side);
          var ctx = canvas.getContext("2d");
          ctx.imageSmoothingQuality = "high";
          ctx.drawImage(img, (img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2, side, side, 0, 0, canvas.width, canvas.height);
          resolve(canvas.toDataURL("image/jpeg", 0.88));
        };
        img.onerror = function () { reject(new Error(T.read)); };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-avatar-card]"), function (card) {
    var form = card.querySelector("[data-avatar-form]");
    var file = card.querySelector("[data-avatar-file]");
    var data = form.querySelector("input[name='image_data']");
    var save = card.querySelector("[data-avatar-save]");
    var cancel = card.querySelector("[data-avatar-cancel]");
    var pick = card.querySelector("[data-avatar-pick]");
    var remove = card.querySelector("[data-avatar-remove]");
    var avatar = card.querySelector(".avatar");
    var original = avatar.cloneNode(true);

    function editing(on) {
      save.hidden = cancel.hidden = !on;
      pick.hidden = on;
      if (remove) remove.hidden = on;
    }
    file.addEventListener("change", function () {
      var f = file.files[0];
      if (!f) return;
      if (!/^image\/(png|jpeg|webp)$/.test(f.type)) { CWA.toast(T.type, "error"); file.value = ""; return; }
      if (f.size > MAX_INPUT) { CWA.toast(T.size, "error"); file.value = ""; return; }
      render(f).then(function (uri) {
        data.value = uri;
        var img = document.createElement("img");
        img.src = uri;
        img.alt = "";
        avatar.textContent = "";
        avatar.appendChild(img);
        editing(true);
        save.focus();
      }).catch(function (err) { CWA.toast(err.message, "error"); });
    });
    cancel.addEventListener("click", function () {
      data.value = "";
      file.value = "";
      avatar.replaceWith(original);
      avatar = original;
      original = avatar.cloneNode(true);
      editing(false);
    });
  });
})();
