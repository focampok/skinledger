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
  var attestationHint = document.getElementById("attestation-hint");
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
  var listenersRegistered = false;
  var initCalled = false;
  var retriedLowQuality = false;
  var videoQuality = "1080p";
  var asyncInitTimer = null;
  var asyncInitFallback = false;
  var lastLoadingBucket = -1;
  var objectUrl = null;
  var pollTimer = null;
  var handledCaptureId = null;
  var lastQualityLog = 0;

  function errorText(error) {
    if (error && typeof error.message === "string") {
      return error.message;
    }
    if (typeof error === "string") {
      return error;
    }
    return "non-error value";
  }

  function shortUserAgent() {
    return String(navigator.userAgent || "")
      .replace(/\s+/g, " ")
      .slice(0, 120);
  }

  function clientLog(level, event, detail) {
    try {
      fetch("/api/client-log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level: level, event: event, detail: detail || "" }),
        keepalive: true,
      }).catch(function () {
        /* Event logging must never break the capture flow. */
      });
    } catch (error) {
      /* Event logging must never break the capture flow. */
    }
  }

  // Install the real sender and flush anything the template logged before this file ran.
  var queuedLogs = window.__clientLogQueue || [];
  window.__clientLogQueue = [];
  window.SkinLedgerClientLog = clientLog;
  queuedLogs.forEach(function (item) {
    clientLog(item[0], item[1], item[2]);
  });

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
    if (attestationHint) {
      attestationHint.hidden = attested;
    }
    if (!kitReady && help && !help.textContent) {
      help.textContent = "Guided camera is still loading…";
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
      clientLog("debug", "fetch_start", "endpoint=status capture_id=" + captureId);
      fetch("/api/captures/" + encodeURIComponent(captureId) + "/status", {
        headers: { "HX-Request": "true" },
      })
        .then(function (response) {
          if (!response.ok) {
            clientLog(
              "warning",
              "fetch_response",
              "endpoint=status capture_id=" + captureId + " status=" + response.status
            );
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
            clientLog(
              "info",
              "fetch_response",
              "endpoint=status capture_id=" + captureId + " state=" + state
            );
            stopPolling();
          }
        })
        .catch(function (error) {
          clientLog(
            "warning",
            "fetch_error",
            "endpoint=status message=" + errorText(error)
          );
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
    clientLog(
      "info",
      "fetch_start",
      "endpoint=/api/captures source=" + source + " bytes=" + blob.size
    );
    fetch("/api/captures?" + params.toString(), {
      method: "POST",
      body: blob,
      headers: { "Content-Type": blob.type || "image/jpeg" },
    })
      .then(function (response) {
        clientLog(
          "info",
          "fetch_response",
          "endpoint=/api/captures source=" + source + " status=" + response.status
        );
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
      .catch(function (error) {
        clientLog(
          "error",
          "fetch_error",
          "endpoint=/api/captures message=" + errorText(error)
        );
        showError("We couldn't reach SkinLedger. Check your connection and try again.");
      });
  }

  function cameraUnavailable(message, reason, switchToUpload) {
    if (help) {
      help.textContent = message || "Guided camera unavailable on this device.";
    }
    clientLog("warning", "camera_unavailable", "reason=" + (reason || "unknown"));
    updateButtons();
    if (allowUpload && switchToUpload !== false) {
      selectTab("upload");
    }
  }

  function kitIsReady() {
    return (
      typeof YMK !== "undefined" &&
      Boolean(window.YMKAsyncInitFired || asyncInitFallback)
    );
  }

  function logLifecycle(name, detail) {
    clientLog("info", name, detail || "");
  }

  function onOpened() {
    logLifecycle("opened", "event=opened");
    if (help) {
      help.textContent = "Camera open. Hold still and look at the camera.";
    }
  }

  function onLoading(state) {
    var progress = state;
    if (state && typeof state === "object") {
      progress = state.progress;
      if (progress === undefined) {
        progress = state.percent;
      }
      if (progress === undefined) {
        progress = state.value;
      }
    }
    var numeric = Number(progress);
    if (!isFinite(numeric)) {
      logLifecycle("loading", "event=loading progress=unknown");
      return;
    }
    // Log only when the progress crosses a 25% bucket.
    var bucket = Math.floor(numeric / 25) * 25;
    if (bucket === lastLoadingBucket) {
      return;
    }
    lastLoadingBucket = bucket;
    logLifecycle("loading", "event=loading progress=" + bucket);
  }

  function onLoaded() {
    lastLoadingBucket = -1;
    logLifecycle("loaded", "event=loaded");
    if (help) {
      help.textContent = "Camera ready. Hold still and look at the camera.";
    }
  }

  function onClosed() {
    logLifecycle("closed", "event=closed");
    if (help) {
      help.textContent = "Camera closed.";
    }
  }

  function onFaceDetectionStarted() {
    logLifecycle("face_detection_started", "event=faceDetectionStarted");
    if (help) {
      help.textContent = "Hold still and look at the camera.";
    }
  }

  function onCameraOpened() {
    logLifecycle("camera_opened", "event=cameraOpened");
  }

  function onCameraClosed() {
    logLifecycle("camera_closed", "event=cameraClosed");
  }

  function onQuality(state) {
    var now = Date.now();
    if (now - lastQualityLog >= 2000) {
      lastQualityLog = now;
      clientLog(
        "info",
        "face_quality_changed",
        "event=faceQualityChanged" +
          " has_face=" + (state && state.hasFace) +
          " frontal=" + (state && state.frontal) +
          " lighting=" + (state && state.lighting) +
          " position=" + (state && state.position)
      );
    }
    var messages = [];
    if (state) {
      if (state.position === "toosmall") {
        messages.push("Move closer");
      } else if (state.position === "outofboundary" || state.position === "notgood") {
        messages.push("Center your face");
      }
      if (state.frontal === "notgood") {
        messages.push("Look straight");
      }
      if (state.lighting === "notgood") {
        messages.push("Face the light");
      }
      if (state.hasFace === false && !messages.length) {
        messages.push("Center your face");
      }
    }
    if (help) {
      help.textContent = messages.length
        ? messages.join(" · ")
        : "Hold still and look at the camera.";
    }
  }

  function onCameraFailed(state) {
    var code = (state && (state.error || state.code || state.error_code)) || "";
    clientLog(
      "warning",
      "camera_failed",
      "event=cameraFailed code=" + (code || "unknown")
    );
    var messages = {
      error_permission_denied: "Allow camera access in your browser settings",
      error_resolution_unsupported: "Your camera resolution isn't supported; try another device",
      error_access_failed: "We couldn't open the camera",
    };
    if (help) {
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
  }

  function handleCapturedImage(image) {
    if (image instanceof Blob) {
      setPreview(image);
      sendImage(image, "camera_kit");
      return;
    }
    if (typeof image === "string") {
      fetch(image)
        .then(function (response) {
          if (!response.ok) {
            throw new Error("image fetch failed");
          }
          return response.blob();
        })
        .then(function (blob) {
          setPreview(blob);
          sendImage(blob, "camera_kit");
        })
        .catch(function (error) {
          clientLog("error", "capture_image", "fetch_failed " + errorText(error));
          showError("The camera did not return a photo. Please try again.");
        });
      return;
    }
    showError("The camera did not return a photo. Please try again.");
  }

  function onCaptured(state) {
    // UNVERIFIED: skincare mode may return more than one image; keep the largest.
    var images = (state && state.images) || [];
    clientLog(
      "info",
      "face_detection_captured",
      "event=faceDetectionCaptured images=" + images.length
    );
    if (!images.length) {
      return;
    }
    var best = images.reduce(function (a, b) {
      var aSize = (a.width || 0) * (a.height || 0);
      var bSize = (b.width || 0) * (b.height || 0);
      return aSize >= bSize ? a : b;
    });
    try {
      YMK.close();
    } catch (error) {
      /* The kit may already be closed. */
    }
    handleCapturedImage(best.image);
  }

  function initKit(quality) {
    var config = {
      faceDetectionMode: "skincare",
      imageFormat: "blob",
      language: loadLanguage(),
      qualityLevel: "strict",
      videoQuality: quality,
    };
    clientLog("info", "init", "call quality=" + quality);
    var result;
    try {
      result = YMK.init(config);
    } catch (error) {
      clientLog("error", "init", "exception " + errorText(error));
      cameraUnavailable("Guided camera unavailable on this device.", "init_exception");
      return false;
    }
    initCalled = true;
    // UNVERIFIED: whether init returns a promise; opening never waits for it.
    if (result && typeof result.then === "function") {
      result
        .then(function () {
          clientLog("info", "init", "resolved quality=" + quality);
        })
        .catch(function (error) {
          clientLog("error", "init", "rejected " + errorText(error));
        });
    } else {
      clientLog("info", "init", "returned synchronously");
    }
    return true;
  }

  function openKit() {
    try {
      clientLog("info", "open_camera_kit", "called");
      YMK.openCameraKit();
      clientLog("info", "open_camera_kit", "returned");
    } catch (error) {
      clientLog("error", "open_camera_kit", "exception " + errorText(error));
      onCameraFailed({ error_access_failed: true });
    }
  }

  function onUnsupportedResolution() {
    clientLog("warning", "unsupported_resolution", "event=unsupportedResolution");
    if (retriedLowQuality) {
      cameraUnavailable("Guided camera unavailable on this device.", "resolution_unsupported");
      return;
    }
    retriedLowQuality = true;
    videoQuality = "720p";
    initCalled = false;
    if (help) {
      help.textContent = "Trying a lower camera resolution…";
    }
    try {
      YMK.close();
    } catch (error) {
      /* The kit may not be open yet. */
    }
    if (initKit(videoQuality)) {
      openKit();
    }
  }

  function startAsyncInitWatch() {
    if (window.YMKAsyncInitFired || asyncInitTimer !== null) {
      return;
    }
    asyncInitTimer = window.setTimeout(function () {
      asyncInitTimer = null;
      if (window.YMKAsyncInitFired) {
        return;
      }
      var hasYmk = typeof YMK !== "undefined";
      clientLog(
        "error",
        "async_init_missing",
        "sdk=" + (window.__ymkScriptState || "pending") + " has_ymk=" + hasYmk
      );
      if (hasYmk) {
        // The global exists even though the callback never ran: the kit is usable.
        asyncInitFallback = true;
        clientLog(
          "info",
          "async_init_fallback",
          "sdk=" + (window.__ymkScriptState || "pending")
        );
        registerCameraKit();
        return;
      }
      cameraUnavailable("Guided camera unavailable on this device.", "async_init_missing");
    }, 10000);
  }

  function registerCameraKit() {
    if (listenersRegistered) {
      return;
    }
    listenersRegistered = true;
    if (asyncInitTimer !== null) {
      window.clearTimeout(asyncInitTimer);
      asyncInitTimer = null;
    }
    if (typeof YMK === "undefined") {
      clientLog("error", "async_init_missing", "has_ymk=false");
      cameraUnavailable("Guided camera unavailable on this device.", "sdk_missing");
      return;
    }
    if (!window.isSecureContext) {
      cameraUnavailable("Guided camera unavailable on this device.", "insecure_context");
      return;
    }
    YMK.addEventListener("opened", onOpened);
    YMK.addEventListener("loading", onLoading);
    YMK.addEventListener("loaded", onLoaded);
    YMK.addEventListener("closed", onClosed);
    YMK.addEventListener("faceDetectionStarted", onFaceDetectionStarted);
    YMK.addEventListener("cameraOpened", onCameraOpened);
    YMK.addEventListener("cameraClosed", onCameraClosed);
    YMK.addEventListener("cameraFailed", onCameraFailed);
    YMK.addEventListener("unsupportedResolution", onUnsupportedResolution);
    YMK.addEventListener("faceQualityChanged", onQuality);
    YMK.addEventListener("faceDetectionCaptured", onCaptured);

    kitReady = kitIsReady();
    updateButtons();
    if (help && !help.textContent) {
      help.textContent = "Camera ready. Tick the checkbox, then start.";
    }
    clientLog(
      "info",
      "kit_ready",
      "sdk=" + (window.__ymkScriptState || "pending") +
        " secure=" + Boolean(window.isSecureContext)
    );
  }

  window.SkinLedgerCameraKitReady = registerCameraKit;
  if (window.__ymkReady || window.YMKAsyncInitFired) {
    registerCameraKit();
  }
  window.addEventListener("ymk-loaded", startAsyncInitWatch);
  window.addEventListener("ymk-error", function () {
    // The boot script already logged sdk_fail; explain it on screen too.
    cameraUnavailable("Guided camera unavailable on this device.", "sdk_failed");
  });
  if (window.__ymkScriptState === "failed" && !window.YMKAsyncInitFired) {
    // The script failed before this listener existed.
    cameraUnavailable("Guided camera unavailable on this device.", "sdk_failed");
  }
  if (window.__ymkScriptState === "loaded" && !window.YMKAsyncInitFired) {
    startAsyncInitWatch();
  }

  if (attestation) {
    attestation.addEventListener("change", updateButtons);
  }

  if (startButton) {
    startButton.addEventListener("click", function () {
      var attested = Boolean(attestation && attestation.checked);
      clientLog(
        "info",
        "button_click",
        "button=start_capture attested=" + attested +
          " kit_ready=" + kitReady +
          " initialized=" + initCalled
      );
      if (!attested || !kitReady) {
        updateButtons();
        return;
      }
      if (!initCalled && !initKit(videoQuality)) {
        return;
      }
      openKit();
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
      var attested = Boolean(attestation && attestation.checked);
      clientLog("info", "button_click", "button=send_upload attested=" + attested);
      if (!attested) {
        showError("Tick the 18+ checkbox above first.");
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

  window.addEventListener("error", function (event) {
    // Message and position only: never image data or blob contents.
    clientLog(
      "error",
      "error",
      "message=" + errorText(event.error || event.message) +
        " line=" + (event.lineno || 0) +
        " col=" + (event.colno || 0)
    );
  });

  window.addEventListener("unhandledrejection", function (event) {
    clientLog(
      "error",
      "error",
      "unhandled_rejection message=" + errorText(event.reason)
    );
  });

  clientLog(
    "info",
    "page_load",
    "has_ymk=" + (typeof YMK !== "undefined") +
      " sdk=" + (window.__ymkScriptState || "pending") +
      " async_init=" + Boolean(window.YMKAsyncInitFired) +
      " ua=" + shortUserAgent()
  );

  selectTab("guided");
  updateButtons();
})();
