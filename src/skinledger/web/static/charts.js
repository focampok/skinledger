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

  var COLORS = {
    real: "#1f6f5c",
    simulated: "#8a6d3b",
    sample: "#6b5b95",
    band: "rgba(31, 111, 92, 0.16)",
    bandUnstable: "rgba(120, 126, 132, 0.22)"
  };

  var LABEL_STYLES = {
    REAL: { color: COLORS.real, dash: [], hollow: false },
    SIMULATED: { color: COLORS.simulated, dash: [6, 4], hollow: true },
    SAMPLE: { color: COLORS.sample, dash: [2, 3], hollow: true }
  };

  function formatDate(iso) {
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

  function productMarksFor(points, products) {
    var marks = [];
    (products || []).forEach(function (product) {
      if (!product.started_on) return;
      var started = String(product.started_on).slice(0, 10);
      for (var index = 0; index < points.length; index += 1) {
        if (dayOf(points[index]) >= started) {
          marks.push({
            index: index,
            label: String(product.name || "Product").slice(0, 16)
          });
          return;
        }
      }
    });
    return marks;
  }

  // Vertical marks at each product start; no annotation plugin is needed.
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
      ctx.strokeStyle = "rgba(31, 111, 92, 0.55)";
      ctx.fillStyle = "rgba(31, 111, 92, 0.85)";
      ctx.lineWidth = 1;
      ctx.font = "10px system-ui, sans-serif";
      ctx.setLineDash([3, 3]);
      marks.forEach(function (mark) {
        if (mark.index < 0 || mark.index >= labels.length) return;
        var px = x.getPixelForValue(mark.index);
        ctx.beginPath();
        ctx.moveTo(px, area.top);
        ctx.lineTo(px, area.bottom);
        ctx.stroke();
        ctx.fillText(mark.label, px + 3, area.top + 10);
      });
      ctx.restore();
    }
  };

  Chart.register(productMarks);
  Chart.defaults.font.family = "system-ui, sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.color = "#3c4043";

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
        backgroundColor: style.hollow ? "#ffffff" : style.color,
        pointBackgroundColor: style.hollow ? "#ffffff" : style.color,
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
      return formatDate(point.t);
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
            grid: { color: "rgba(0, 0, 0, 0.06)" }
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
                return point ? formatDate(point.t) : "";
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

  fetch("/api/people/" + encodeURIComponent(personId) + "/series", {
    headers: { Accept: "application/json" },
    credentials: "same-origin"
  })
    .then(function (response) {
      if (!response.ok) throw new Error("series " + response.status);
      return response.json();
    })
    .then(function (series) {
      (series.aspects || []).forEach(function (aspect) {
        buildChart(aspect, series.products || []);
      });
    })
    .catch(showChartError);
})();
