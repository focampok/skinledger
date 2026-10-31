// SkinLedger per-aspect timeline. Chart.js 4 is vendored at /static/vendor/;
// this file never talks to a CDN and draws only the stored raw scores.
(function () {
  "use strict";

  var page = document.getElementById("timeline-page");
  if (!page || typeof Chart === "undefined") return;

  var personId = page.getAttribute("data-person-id");
  if (!personId) return;

  var SOURCE_LABELS = {
    camera_kit: "guided camera",
    upload: "upload",
    seed: "simulated history",
    mock: "sample"
  };

  function cssVar(name, fallback) {
    var value = getComputedStyle(document.documentElement).getPropertyValue(name);
    return value && value.trim() ? value.trim() : fallback;
  }

  // P16b-4: chart colours come from the same tokens as the page, so a phone in
  // dark mode gets light text, a light band and readable provenance marks.
  var COLORS = {
    text: cssVar("--sl-body", "#373c44"),
    grid: cssVar("--sl-chart-grid", "rgba(0, 0, 0, 0.08)"),
    real: cssVar("--sl-chart-real", "#1f6f5c"),
    simulated: cssVar("--sl-chart-simulated", "#8a6d3b"),
    sample: cssVar("--sl-chart-sample", "#6b5b95"),
    band: cssVar("--sl-chart-band", "rgba(31, 111, 92, 0.16)"),
    bandUnstable: cssVar("--sl-chart-band-unstable", "rgba(120, 126, 132, 0.22)"),
    product: cssVar("--sl-chart-product", "#646b79"),
    hollow: cssVar("--sl-chart-hollow", "#ffffff")
  };

  var LABEL_STYLES = {
    REAL: { color: COLORS.real, dash: [], hollow: false },
    SIMULATED: { color: COLORS.simulated, dash: [6, 4], hollow: true },
    SAMPLE: { color: COLORS.sample, dash: [2, 3], hollow: true }
  };

  // The axis shows the day only; the tooltip keeps the time of capture.
  function formatTick(iso) {
    var date = new Date(iso);
    if (isNaN(date.getTime())) return String(iso).slice(0, 10);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric"
    });
  }

  function formatFull(iso) {
    var date = new Date(iso);
    if (isNaN(date.getTime())) return String(iso);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function scoreText(value) {
    var number = Number(value);
    return isNaN(number) ? String(value) : number.toFixed(1);
  }

  function dayOf(point) {
    return String(point.t || "").slice(0, 10);
  }

  // Each product gets its own muted line style and a small number, matching
  // the swatches in the shared product key. No names are drawn in the chart.
  var PRODUCT_DASHES = [[], [5, 4], [1, 3], [8, 3]];

  function productMarksFor(points, products) {
    var marks = [];
    (products || []).forEach(function (product, productIndex) {
      if (!product.started_on) return;
      var started = String(product.started_on).slice(0, 10);
      for (var index = 0; index < points.length; index += 1) {
        if (dayOf(points[index]) >= started) {
          marks.push({
            index: index,
            number: productIndex + 1,
            dash: PRODUCT_DASHES[productIndex % PRODUCT_DASHES.length]
          });
          return;
        }
      }
    });
    return marks;
  }

  var productMarks = {
    id: "slProductMarks",
    afterDatasetsDraw: function (chart, args, options) {
      var marks = (options && options.marks) || [];
      if (!marks.length) return;
      var x = chart.scales.x;
      var area = chart.chartArea;
      var ctx = chart.ctx;
      var labels = chart.data.labels || [];
      ctx.save();
      ctx.strokeStyle = COLORS.product;
      ctx.lineWidth = 1.5;
      marks.forEach(function (mark) {
        if (mark.index < 0 || mark.index >= labels.length) return;
        var px = x.getPixelForValue(mark.index);
        ctx.setLineDash(mark.dash || []);
        ctx.beginPath();
        ctx.moveTo(px, area.top);
        ctx.lineTo(px, area.bottom);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = COLORS.product;
        ctx.font = "600 11px system-ui, sans-serif";
        ctx.fillText(String(mark.number), px + 4, area.top + 11);
      });
      ctx.restore();
    }
  };

  Chart.register(productMarks);
  Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = COLORS.text;

  function buildDatasets(aspect, labels) {
    var datasets = [];
    var baseline = aspect.baseline;
    var band = aspect.band;
    var hasBand = baseline !== null && band !== null;

    if (hasBand) {
      var bandValues = labels.map(function () {
        return baseline + band;
      });
      var lowerValues = labels.map(function () {
        return baseline - band;
      });
      var bandColor = aspect.unstable ? COLORS.bandUnstable : COLORS.band;
      datasets.push({
        label: "Band top",
        data: bandValues,
        borderWidth: 0,
        pointRadius: 0,
        backgroundColor: bandColor,
        fill: false,
        tension: 0,
        slKind: "band"
      });
      datasets.push({
        label: "Noise band",
        data: lowerValues,
        borderWidth: 0,
        pointRadius: 0,
        backgroundColor: bandColor,
        fill: "-1",
        tension: 0,
        slKind: "band"
      });
    }

    ["REAL", "SIMULATED", "SAMPLE"].forEach(function (dataLabel) {
      var style = LABEL_STYLES[dataLabel];
      var values = aspect.points.map(function (point) {
        return point.data_label === dataLabel ? point.raw_score : null;
      });
      var present = values.some(function (value) {
        return value !== null;
      });
      if (!present) return;
      datasets.push({
        label: dataLabel,
        data: values,
        borderColor: style.color,
        backgroundColor: style.hollow ? COLORS.hollow : style.color,
        pointBackgroundColor: style.hollow ? COLORS.hollow : style.color,
        pointBorderColor: style.color,
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 5,
        borderWidth: 2,
        borderDash: style.dash,
        tension: 0,
        spanGaps: false,
        slKind: "point"
      });
    });
    return datasets;
  }

  function buildChart(aspect, products) {
    var canvas = document.getElementById("chart-" + aspect.aspect);
    if (!canvas) return;
    var points = aspect.points || [];
    var labels = points.map(function (point) {
      return formatTick(point.t);
    });
    new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: buildDatasets(aspect, labels)
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "nearest", intersect: false },
        scales: {
          x: {
            grid: { display: false },
            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 4 }
          },
          y: {
            beginAtZero: false,
            grid: { color: COLORS.grid }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            filter: function (item) {
              return item.dataset.slKind === "point";
            },
            callbacks: {
              title: function (items) {
                var point = points[items[0].dataIndex];
                return point ? formatFull(point.t) : "";
              },
              label: function (item) {
                var point = points[item.dataIndex];
                if (!point) return "";
                var source = SOURCE_LABELS[point.source] || point.source;
                return (
                  "Score " +
                  scoreText(point.raw_score) +
                  " · " +
                  point.data_label +
                  " · " +
                  source
                );
              }
            }
          },
          slProductMarks: { marks: productMarksFor(points, products) }
        }
      }
    });
  }

  function showChartError() {
    var status = document.getElementById("timeline-chart-status");
    if (status) status.hidden = false;
  }

  // Collapse to the first three cards. Charts are created only for visible
  // cards, and the rest are built when the reader expands the grid.
  var grid = document.getElementById("timeline-grid");
  var controls = document.getElementById("timeline-collapse-controls");
  var toggle = document.getElementById("timeline-toggle");
  var extraCards = document.querySelectorAll(".timeline-card-extra");
  var latestSeries = null;
  var built = {};

  function buildVisible() {
    if (!latestSeries) return;
    (latestSeries.aspects || []).forEach(function (aspect) {
      if (built[aspect.aspect]) return;
      var card = document.querySelector(
        '[data-timeline-aspect="' + aspect.aspect + '"]'
      );
      if (!card || card.offsetParent === null) return;
      buildChart(aspect, latestSeries.products || []);
      built[aspect.aspect] = true;
    });
  }

  if (extraCards.length && grid && controls && toggle) {
    controls.hidden = false;
    grid.classList.add("is-collapsed");
    toggle.setAttribute("aria-expanded", "false");
    toggle.addEventListener("click", function () {
      var collapsed = grid.classList.toggle("is-collapsed");
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      toggle.textContent = collapsed
        ? toggle.getAttribute("data-show-all")
        : toggle.getAttribute("data-show-fewer");
      if (!collapsed) buildVisible();
    });
  }

  function loadSeries() {
    fetch("/api/people/" + encodeURIComponent(personId) + "/series", {
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    })
      .then(function (response) {
        if (!response.ok) throw new Error("series " + response.status);
        return response.json();
      })
      .then(function (series) {
        latestSeries = series;
        buildVisible();
      })
      .catch(showChartError);
  }

  // Wait for the self-hosted Inter face so canvas labels use the same UI font.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(loadSeries);
  } else {
    loadSeries();
  }
})();
