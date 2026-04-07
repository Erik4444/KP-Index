'use strict';

// ─── Constants ────────────────────────────────────────────────────────────────

const KP_PALETTE = {
  quiet:     '#22c55e',
  unsettled: '#84cc16',
  active:    '#eab308',
  minor:     '#f97316',
  moderate:  '#ef4444',
  strong:    '#dc2626',
  severe:    '#b91c1c',
  extreme:   '#7c3aed',
};

const KP_SCALE = [
  { kpMin: 0, kpMax: 2, label: 'KP 0–2 — Ruhig',             color: 'quiet',     note: 'Kein Polarlicht sichtbar' },
  { kpMin: 3, kpMax: 3, label: 'KP 3 — Unruhig',             color: 'unsettled', note: 'Kein Polarlicht sichtbar' },
  { kpMin: 4, kpMax: 4, label: 'KP 4 — Aktiv',               color: 'active',    note: 'Polarlicht bei sehr hohen Breiten' },
  { kpMin: 5, kpMax: 5, label: 'KP 5 — G1 Kleiner Sturm',    color: 'minor',     note: 'Sichtbar: Nordseeküste (~60°N)' },
  { kpMin: 6, kpMax: 6, label: 'KP 6 — G2 Mäßiger Sturm',   color: 'moderate',  note: 'Sichtbar: Norddeutschland (~55°N)' },
  { kpMin: 7, kpMax: 7, label: 'KP 7 — G3 Starker Sturm',    color: 'strong',    note: 'Sichtbar: Mitteldeutschland (~50°N)' },
  { kpMin: 8, kpMax: 8, label: 'KP 8 — G4 Schwerer Sturm',   color: 'severe',    note: 'Weitverbreitetes Polarlicht in DE' },
  { kpMin: 9, kpMax: 9, label: 'KP 9 — G5 Extremer Sturm',   color: 'extreme',   note: 'Polarlicht überall in Deutschland' },
];

const REFRESH_INTERVAL_S = 180;
const AURORA_ICONS = {
  quiet: '☀', unsettled: '🌤', active: '🌙', minor: '✨',
  moderate: '🌌', strong: '🌟', severe: '💫', extreme: '🌠',
};

// ─── State ────────────────────────────────────────────────────────────────────

let chart = null;
let currentDays = 1;
let countdown = REFRESH_INTERVAL_S;
let countdownTimer = null;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function colorForClass(cls) {
  return KP_PALETTE[cls] ?? KP_PALETTE.quiet;
}

function hexWithAlpha(hex, alpha) {
  // alpha: 0–1 → appended as 2-digit hex
  const a = Math.round(alpha * 255).toString(16).padStart(2, '0');
  return hex + a;
}

function formatTimestamp(isoStr) {
  return new Date(isoStr).toLocaleString('de-DE', {
    timeZone: 'Europe/Berlin',
    day: '2-digit', month: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

function applyColorClass(el, colorClass) {
  Object.keys(KP_PALETTE).forEach(c => el.classList.remove('kp-' + c));
  el.classList.add('kp-' + colorClass);
}

// ─── Scale Grid ───────────────────────────────────────────────────────────────

function buildScaleGrid() {
  const grid = document.getElementById('scale-grid');
  KP_SCALE.forEach(({ label, color, note }) => {
    const item = document.createElement('div');
    item.className = 'scale-item kp-' + color;
    item.innerHTML = `
      <div class="scale-item-title">${label}</div>
      <div class="scale-item-note">${note}</div>
    `;
    grid.appendChild(item);
  });
}

// ─── Current KP ───────────────────────────────────────────────────────────────

async function loadCurrentKp() {
  try {
    const res = await fetch('/api/kp/current');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const { kp, color, storm_label, aurora_visibility, timestamp } = data;

    // Header KP card
    const kpValue = document.getElementById('kp-value');
    const kpBadge = document.getElementById('kp-storm-badge');
    const kpCard  = document.getElementById('current-kp-card');

    kpValue.textContent = kp.toFixed(1);
    kpBadge.textContent = storm_label;
    applyColorClass(kpValue, color);
    applyColorClass(kpBadge, color);
    kpCard.style.boxShadow = `0 0 24px ${hexWithAlpha(colorForClass(color), 0.25)}`;
    kpCard.style.borderColor = hexWithAlpha(colorForClass(color), 0.5);

    // Aurora alert bar
    const alert = document.getElementById('aurora-alert');
    const visMain = document.getElementById('aurora-visibility');
    const visSub  = document.getElementById('last-updated');
    const icon    = alert.querySelector('.aurora-alert-icon');

    visMain.textContent = aurora_visibility;
    visSub.textContent  = `Letzter Messwert: ${formatTimestamp(timestamp)} Uhr`;
    icon.textContent    = AURORA_ICONS[color] ?? '☀';
    applyColorClass(alert, color);

  } catch (err) {
    console.error('Failed to load current KP:', err);
    document.getElementById('aurora-visibility').textContent = 'Fehler beim Laden';
  }
}

// ─── Chart ────────────────────────────────────────────────────────────────────

function buildBarColors(ctx, readings) {
  return readings.map(r => {
    const hex = colorForClass(r.color);
    const grad = ctx.createLinearGradient(0, 0, 0, 280);
    grad.addColorStop(0, hexWithAlpha(hex, 0.85));
    grad.addColorStop(1, hexWithAlpha(hex, 0.15));
    return grad;
  });
}

function renderChart(readings) {
  const canvas = document.getElementById('kp-chart');
  const ctx = canvas.getContext('2d');

  // For large datasets, thin the labels
  const step = readings.length > 60 ? Math.ceil(readings.length / 40) : 1;
  const labels = readings.map((r, i) =>
    i % step === 0 ? formatTimestamp(r.timestamp) : ''
  );

  const values = readings.map(r => r.kp);
  const bgColors = buildBarColors(ctx, readings);
  const borderColors = readings.map(r => colorForClass(r.color));

  if (chart) {
    chart.destroy();
  }

  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'KP-Index',
        data: values,
        backgroundColor: bgColors,
        borderColor: borderColors,
        borderWidth: 1,
        borderRadius: 3,
        borderSkipped: false,
        barPercentage: 0.85,
        categoryPercentage: 0.9,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0d1525',
          borderColor: '#1c2d48',
          borderWidth: 1,
          titleColor: '#6b90b8',
          bodyColor: '#ddeeff',
          padding: 10,
          callbacks: {
            title: items => items[0].label || '',
            label: item => ` KP: ${parseFloat(item.raw).toFixed(2)}`,
          },
        },
        annotation: undefined,
      },
      scales: {
        x: {
          grid: { color: '#1c2d4840', drawTicks: false },
          ticks: {
            color: '#6b90b8',
            font: { size: 11, family: 'Space Grotesk' },
            maxRotation: 35,
            autoSkip: false,
          },
          border: { color: '#1c2d48' },
        },
        y: {
          min: 0,
          max: 9,
          grid: {
            color: (ctx) => {
              // Highlight G1 (5) and G3 (7) lines
              const v = ctx.tick.value;
              if (v === 5) return hexWithAlpha(KP_PALETTE.minor, 0.5);
              if (v === 7) return hexWithAlpha(KP_PALETTE.strong, 0.5);
              return '#1c2d4860';
            },
            lineWidth: (ctx) => (ctx.tick.value === 5 || ctx.tick.value === 7) ? 1.5 : 1,
          },
          ticks: {
            color: '#6b90b8',
            font: { size: 11, family: 'Space Grotesk' },
            stepSize: 1,
            callback: v => {
              if (v === 5) return 'G1 ▶ 5';
              if (v === 7) return 'G3 ▶ 7';
              return v;
            },
          },
          border: { color: '#1c2d48' },
        },
      },
    },
  });
}

async function loadHistory(days) {
  try {
    const res = await fetch(`/api/kp/history?days=${days}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderChart(data.readings);
  } catch (err) {
    console.error('Failed to load history:', err);
  }
}

// ─── Refresh Countdown ────────────────────────────────────────────────────────

function startCountdown() {
  countdown = REFRESH_INTERVAL_S;
  clearInterval(countdownTimer);
  const el = document.getElementById('refresh-countdown');

  countdownTimer = setInterval(() => {
    countdown--;
    const m = Math.floor(countdown / 60);
    const s = countdown % 60;
    el.textContent = m > 0
      ? `Aktualisiert in ${m}:${String(s).padStart(2, '0')} min`
      : `Aktualisiert in ${s}s`;

    if (countdown <= 0) {
      refresh();
    }
  }, 1000);
}

async function refresh() {
  await Promise.all([loadCurrentKp(), loadHistory(currentDays)]);
  startCountdown();
}

// ─── Event Listeners ──────────────────────────────────────────────────────────

document.querySelectorAll('.range-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentDays = parseInt(btn.dataset.days, 10);
    loadHistory(currentDays);
  });
});

// ─── Init ─────────────────────────────────────────────────────────────────────

buildScaleGrid();
loadCurrentKp();
loadHistory(currentDays);
startCountdown();
