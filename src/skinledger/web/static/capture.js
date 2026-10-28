/* SkinLedger capture page: Camera Kit, photo upload and the local-only preview. */
(function () {
  "use strict";

  var root = document.getElementById("capture-page");
  if (!root) {
    return;
  }

  var personId = root.dataset.personId;
  var allowUpload = root.dataset.allowUpload === "1";
  var maxAnalyses = root.dataset.maxAnalyses;
  var baselineStep = root.dataset.baselineStep || "";
  var languageKey = "skinledger_camera_language";

  var attestation = document.getElementById("attestation");
  var startButton = document.getElementById("start-capture");
  var uploadButton = document.getElementById("send-upload");
  var fileInput = document.getElementById("photo");
  var statusBox = document.getElementById("capture-status-container");
  var help = document.getElementById("camera-help");
  var stepLabel = document.getElementById("baseline-step");
  var doneMessage = document.getElementById("baseline-done");
  var analysesLeftLabel = document.getElementById("analyses-left");
  var languageSelect = document.getElementById("camera-language");
  var preview = document.getElementById("preview");
  var previewImage = document.getElementById("preview-image");
  var overlay = document.getElementById("preview-overlay");
  var maskSelect = document.getElementById("mask-select");

  var MAX_BYTES = 10 * 1024 * 1024;
  var SIZE_MESSAGE =
    "This photo can't be used. Please upload a JPG or PNG under 10 MB, at least 480 px on " +
    "the short side — or use the guided camera. This attempt didn't count toward your limit.";

  var kitReady = false;
  var kitInitTried = false;
  var retriedLowQuality = false;
  var objectUrl = null;
  var pollTimer = null;
  var handledCaptureId = null;

  function loadLanguage() {
    try {
      return window.localStorage.getItem(languageKey) || root.dataset.cameraLanguage || "enu";
    } catch (error) {
      return root.dataset.cameraLanguage || "enu";
    }
  }

  function saveLanguage(value) {
    try {
      window.localStorage.setItem(languageKey, value);
    } catch (error) {
      /* Storage can be unavailable; the selector still works for this page. */
    }
  }

  function updateButtons() {
    var attested = Boolean(attestation && attestation.checked);
    if (startButton) {
      startButton.disabled = !attested || !kitReady;
    }
    if (uploadButton) {
      uploadButton.disabled = !attested;
    }
  }

  function selectTab(name) {
    document.querySelectorAll("[data-tab-button]").forEach(function (button) {
      button.setAttribute(
        "aria-selected",
        button.getAttribute("data-tab-button") === name ? "true" : "false"
      );
    });
    document.querySelectorAll("[data-tab-panel]").forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-tab-panel") !== name;
    });
  }

  document.querySelectorAll("[data-tab-button]").forEach(function (button) {
    button.addEventListener("click", function () {
      selectTab(button.getAttribute("data-tab-button"));
    });
  });

  function revokePreview() {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
  }

  function setPreview(blob) {
    revokePreview();
    objectUrl = URL.createObjectURL(blob);
    previewImage.src = objectUrl;
    overlay.removeAttribute("src");
    overlay.hidden = true;
    preview.hidden = false;
  }

  window.addEventListener("pagehide", revokePreview);
  window.addEventListener("beforeunload", revokePreview);

  function updateCounter(value) {
    if (analysesLeftLabel && value !== null) {
      analysesLeftLabel.textContent = value + " of " + maxAnalyses + " analyses left";
    }
  }

  function showError(message) {
    statusBox.innerHTML = "";
    var paragraph = document.createElement("p");
    paragraph.setAttribute("role", "alert");
    paragraph.textContent = message;
    statusBox.append(paragraph);
  }

  function showMasks(section) {
    var captureId = section.getAttribute("data-capture-id");
    var items = Array.prototype.slice.call(
      section.querySelectorAll("[data-mask-file]")
    );
    maskSelect.innerHTML = "";
    items.forEach(function (item) {
      var option = document.createElement("option");
      var file = item.getAttribute("data-mask-file");
      option.value = "/media/" + encodeURIComponent(captureId) + "/" + encodeURIComponent(file);
      option.textContent = item.getAttribute("data-mask-aspect") || "Mask";
      maskSelect.append(option);
    });
    maskSelect.hidden = items.length === 0;
    overlay.hidden = items.length === 0;
    if (items.length) {
      overlay.src = maskSelect.value;
    }
  }

  function onSuccess(section) {
    showMasks(section);
    var captureId = section.getAttribute("data-capture-id");
    if (captureId === handledCaptureId) {
      return;
    }
    handledCaptureId = captureId;

    if (baselineStep === "1") {
      baselineStep = "2";
      stepLabel.hidden = false;
      stepLabel.textContent = "Analysis 2 of 2 (same place, same light)";
    } else if (baselineStep === "2") {
      baselineStep = "";
      doneMessage.hidden = false;
      stepLabel.textContent = "Baseline complete.";
    }
  }

  function applyStatus(html) {
    var parsed = new DOMParser().parseFromString(html, "text/html");
    var section = parsed.querySelector("#capture-status");
    if (!section) {
      statusBox.innerHTML = html;
      return null;
    }
    statusBox.innerHTML = section.outerHTML;
    var left = section.getAttribute("data-analyses-left");
    if (left !== null) {
      updateCounter(left);
    }
    var state = section.getAttribute("data-status");
    if (state === "success") {
      onSuccess(section);
    }
    return state;
  }

  function stopPolling() {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function watchCapture(captureId) {
    stopPolling();
    var tick = function () {
      fetch("/api/captures/" + encodeURIComponent(captureId) + "/status", {
        headers: { "HX-Request": "true" },
      })
        .then(function (response) {
          if (!response.ok) {
            stopPolling();
            return null;
          }
          return response.text();
        })
        .then(function (html) {
          if (html === null) {
            return;
          }
          var state = applyStatus(html);
          if (state === "success" || state === "error") {
            stopPolling();
          }
        })
        .catch(function () {
          /* Keep the interval running; a transient failure is fine. */
        });
    };
    pollTimer = window.setInterval(tick, 3000);
    tick();
  }

  function extractDetail(text) {
    try {
      var data = JSON.parse(text);
      if (data && typeof data.detail === "string") {
        return data.detail;
      }
    } catch (error) {
      /* The response was an HTML fragment. */
    }
    return "The photo couldn't be analyzed. Please try again.";
  }

  function sendImage(blob, source) {
    var params = new URLSearchParams({
      person_id: personId,
      source: source,
      is_baseline_pair: baselineStep ? "1" : "0",
      attested: "1",
    });
    statusBox.innerHTML = "<p>Uploading…</p>";
    fetch("/api/captures?" + params.toString(), {
      method: "POST",
      body: blob,
      headers: { "Content-Type": blob.type || "image/jpeg" },
    })
      .then(function (response) {
        return response.text().then(function (text) {
          if (!response.ok) {
            showError(extractDetail(text));
            return;
          }
          var state = applyStatus(text);
          var section = statusBox.querySelector("#capture-status");
          if (!section || state === "success" || state === "error") {
            return;
          }
          watchCapture(section.getAttribute("data-capture-id"));
        });
      })
      .catch(function () {
        showError("We couldn't reach SkinLedger. Check your connection and try again.");
      });
  }

  function cameraUnavailable() {
    kitReady = false;
    updateButtons();
    help.textContent = "Guided camera unavailable on this device.";
    if (allowUpload) {
      selectTab("upload");
    }
  }

  function kitLoaded() {
    return (
      typeof YMK !== "undefined" &&
      typeof YMK.isLoaded === "function" &&
      YMK.isLoaded()
    );
  }

  function markReady() {
    kitReady = true;
    updateButtons();
    help.textContent = "Camera ready. Hold still and look at the camera.";
  }

  function onQuality(state) {
    // UNVERIFIED: exact field values of faceQualityChanged; adjust from the console.
    var messages = [];
    if (state && state.hasFace === false) {
      messages.push("Move closer");
    }
    if (state && state.frontal === false) {
      messages.push("Look straight");
    }
    if (
      state &&
      (state.lighting === false || state.lighting === "dark" || state.lighting === "low")
    ) {
      messages.push("Face the light");
    }
    if (state && state.position && ["center", "centered", "ok"].indexOf(state.position) === -1) {
      messages.push("Center your face in the frame");
    }
    help.textContent = messages.length
      ? messages.join(" · ")
      : "Hold still and look at the camera.";
  }

  function onCameraFailed(state) {
    var code = (state && (state.error || state.code || state.error_code)) || "";
    var messages = {
      error_permission_denied: "Allow camera access in your browser settings",
      error_resolution_unsupported: "Your camera resolution isn't supported; try another device",
      error_access_failed: "We couldn't open the camera",
    };
    help.textContent = messages[code] || "We couldn't open the camera";
    var link = document.createElement("a");
    link.href = "#upload";
    link.textContent = "Upload a photo instead";
    link.addEventListener("click", function (event) {
      event.preventDefault();
      if (allowUpload) {
        selectTab("upload");
      }
    });
    help.append(document.createElement("br"), link);
  }

  function onCaptured(state) {
    // UNVERIFIED: phase may bring several images in skincare mode; keep the largest.
    var images = (state && state.images) || [];
    if (!images.length) {
      return;
    }
    var best = images.reduce(function (a, b) {
      var aSize = (a.width || 0) * (a.height || 0);
      var bSize = (b.width || 0) * (b.height || 0);
      return aSize >= bSize ? a : b;
    });
    var blob = best.image;
    try {
      YMK.close();
    } catch (error) {
      /* The kit may already be closed. */
    }
    if (!(blob instanceof Blob)) {
      showError("The camera did not return a photo. Please try again.");
      return;
    }
    setPreview(blob);
    sendImage(blob, "camera_kit");
  }

  function startKit(videoQuality) {
    var config = {
      faceDetectionMode: "skincare",
      imageFormat: "blob",
      language: loadLanguage(),
      qualityLevel: "strict",
      videoQuality: videoQuality,
    };
    try {
      var result = YMK.init(config);
      if (result && typeof result.then === "function") {
        result.then(markReady).catch(cameraUnavailable);
      } else {
        markReady();
      }
    } catch (error) {
      cameraUnavailable();
    }
  }

  function onUnsupportedResolution() {
    if (retriedLowQuality) {
      cameraUnavailable();
      return;
    }
    retriedLowQuality = true;
    help.textContent = "Trying a lower camera resolution…";
    try {
      YMK.close();
    } catch (error) {
      /* The kit may not be open yet. */
    }
    startKit("720p");
    help.textContent = "Switched to 720p because your camera did not support 1080p.";
  }

  function initCameraKit() {
    if (kitInitTried) {
      return;
    }
    kitInitTried = true;
    if (!window.isSecureContext || typeof YMK === "undefined") {
      cameraUnavailable();
      return;
    }
    // UNVERIFIED: exact addEventListener signature; adjust from the browser console.
    YMK.addEventListener("faceQualityChanged", onQuality);
    YMK.addEventListener("faceDetectionCaptured", onCaptured);
    YMK.addEventListener("cameraFailed", onCameraFailed);
    YMK.addEventListener("unsupportedResolution", onUnsupportedResolution);
    startKit("1080p");
  }

  window.SkinLedgerCameraKitReady = initCameraKit;
  if (window.__ymkReady) {
    initCameraKit();
  }
  window.addEventListener("ymk-error", cameraUnavailable);
  window.setTimeout(function () {
    if (!kitReady) {
      cameraUnavailable();
    }
  }, 10000);

  if (attestation) {
    attestation.addEventListener("change", updateButtons);
  }

  if (startButton) {
    startButton.addEventListener("click", function () {
      if (!attestation.checked) {
        return;
      }
      if (!kitLoaded()) {
        cameraUnavailable();
        return;
      }
      try {
        YMK.openCameraKit();
      } catch (error) {
        onCameraFailed({ error_access_failed: true });
      }
    });
  }

  if (languageSelect) {
    languageSelect.value = loadLanguage();
    languageSelect.addEventListener("change", function () {
      saveLanguage(languageSelect.value);
      help.textContent = "Reload the page to apply the new camera language.";
    });
  }

  if (maskSelect) {
    maskSelect.addEventListener("change", function () {
      if (maskSelect.value) {
        overlay.src = maskSelect.value;
      }
    });
  }

  if (uploadButton) {
    uploadButton.addEventListener("click", function () {
      if (!attestation.checked) {
        return;
      }
      var file = fileInput.files && fileInput.files[0];
      if (!file) {
        showError("Choose a photo first.");
        return;
      }
      var allowedType = file.type === "image/jpeg" || file.type === "image/png";
      // UNVERIFIED: iPhone Safari may not convert HEIC for this input; the server then
      // answers unsupported_format with the friendly message.
      if (!allowedType || file.size > MAX_BYTES) {
        showError(SIZE_MESSAGE);
        return;
      }
      setPreview(file);
      sendImage(file, "upload");
    });
  }

  selectTab("guided");
  updateButtons();
})();
