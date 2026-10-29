// SkinLedger capture boot. Loaded before capture.js and before the Camera Kit SDK.
// External file (no inline handlers) so the strict CSP needs no 'unsafe-inline'.
(function () {
  "use strict";

  // Queue client logs until capture.js installs the real sender.
  window.__clientLogQueue = [];
  window.__ymkScriptState = "pending";
  window.__ymkScriptLoadedAt = null;
  window.SkinLedgerClientLog = function (level, event, detail) {
    window.__clientLogQueue.push([level, event, detail]);
  };

  // Must exist before the Camera Kit SDK runs. It only registers listeners.
  // The shipped SDK checks `typeof window.ymkAsyncInit === "function"` (lowercase)
  // and calls it once window.YMK exists, so the lowercase name is the one that matters.
  window.ymkAsyncInit = function () {
    window.YMKAsyncInitFired = true;
    window.SkinLedgerClientLog(
      "info",
      "async_init",
      "fired capture_ready=" + Boolean(window.SkinLedgerCameraKitReady)
    );
    if (window.SkinLedgerCameraKitReady) {
      window.SkinLedgerCameraKitReady();
    } else {
      window.__ymkReady = true;
    }
  };
  // Alias for the mixed-case spelling used in the docs and by older SDK builds.
  window.YMKAsyncInit = window.ymkAsyncInit;

  var script = document.createElement("script");
  script.src = "https://plugins-media.makeupar.com/v2.5-camera-kit/sdk.js";
  script.async = true;
  script.addEventListener("load", function () {
    window.__ymkScriptState = "loaded";
    window.__ymkScriptLoadedAt = Date.now();
    window.SkinLedgerClientLog("info", "sdk_load", "script loaded");
    window.dispatchEvent(new Event("ymk-loaded"));
  });
  script.addEventListener("error", function () {
    window.__ymkScriptState = "failed";
    window.SkinLedgerClientLog("error", "sdk_fail", "script failed to load");
    window.dispatchEvent(new Event("ymk-error"));
  });
  document.head.appendChild(script);
})();
