/**
 * app.js — Crypto Volatility Dashboard
 * Talks to the Flask REST API at /api/*, renders Chart.js charts,
 * and handles the prediction form.
 */

'use strict';

// ── Config ─────────────────────────────────────────────────────────────────────
const API_BASE = '';   // same origin (Flask serves frontend too)
let mainChart = null;

// ── Utility ────────────────────────────────────────────────────────────────────

function fmt(n, dec = 4) {
  if (n == null) return '—';
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(2) + 'K';
  return Number(n).toFixed(dec);
}

function fmtPct(n) {
  return (n * 100).toFixed(3) + '%';
}

function toast(msg, type = 'info') {
  const wrap = document.getElementById('toastWrap');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 3700);
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ── Bootstrap ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initSummary();
  initCoinSelect();
  initPredictForm();
  document.getElementById('loadCoinBtn').addEventListener('click', loadCoin);
});

// ── Market Summary ─────────────────────────────────────────────────────────────

async function initSummary() {
  try {
    const res = await fetch(`${API_BASE}/api/summary`);
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();

    // Hero stats
    setEl('hStatCryptos', data.total_cryptos);
    setEl('hStatVol', fmtPct(data.market_avg_volatility));

    // Summary cards
    setEl('sumCryptos', data.total_cryptos);
    setEl('sumMostVol', data.top_volatile[0]?.symbol ?? '—');
    setEl('sumLeastVol', data.least_volatile[0]?.symbol ?? '—');
    setEl('sumAvgVol', fmtPct(data.market_avg_volatility));

    // Rankings
    renderRanking('volatileList', data.top_volatile, false);
    renderRanking('stableList', data.least_volatile, true);

  } catch (err) {
    console.error('Summary error:', err);
    toast('⚠️ Could not load market summary. Is the server running?', 'error');
    document.getElementById('volatileList').innerHTML =
      '<div style="color:var(--text-muted);font-size:0.85rem;padding:20px;text-align:center">Server offline</div>';
    document.getElementById('stableList').innerHTML =
      '<div style="color:var(--text-muted);font-size:0.85rem;padding:20px;text-align:center">Server offline</div>';
  }
}

function renderRanking(containerId, items, isSafe) {
  const container = document.getElementById(containerId);
  if (!items || items.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted);padding:12px">No data</div>';
    return;
  }
  container.innerHTML = '';
  items.forEach((item, i) => {
    const row = document.createElement('div');
    row.className = 'coin-row';
    row.innerHTML = `
      <div>
        <div class="coin-name">${item.symbol}</div>
        <div class="coin-sym">Rank #${i + 1}</div>
      </div>
      <span class="vol-badge ${isSafe ? 'safe' : ''}">${fmtPct(item.avg_volatility)}</span>
    `;
    container.appendChild(row);
  });
}

// ── Coin Select Dropdown ───────────────────────────────────────────────────────

async function initCoinSelect() {
  try {
    const res = await fetch(`${API_BASE}/api/cryptos`);
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();

    const select = document.getElementById('coinSelect');
    data.cryptos.forEach(coin => {
      const opt = document.createElement('option');
      opt.value = coin.symbol;
      opt.textContent = coin.symbol;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error('Coin list error:', err);
    toast('⚠️ Could not load crypto list.', 'error');
  }
}

// ── Load Coin Chart ────────────────────────────────────────────────────────────

async function loadCoin() {
  const symbol = document.getElementById('coinSelect').value;
  const n = parseInt(document.getElementById('periodSelect').value, 10);

  if (!symbol) {
    toast('Please select a cryptocurrency first.', 'error');
    return;
  }

  const btn = document.getElementById('loadCoinBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Loading…';

  document.getElementById('chartPlaceholder').style.display = 'none';
  document.getElementById('chartSection').style.display = 'none';

  try {
    const res = await fetch(`${API_BASE}/api/volatility/${encodeURIComponent(symbol)}?n=${n}`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();

    renderChart(symbol, data.data);
    updateCoinStats(data.data);

    document.getElementById('chartSection').style.display = 'block';
    document.getElementById('chartTitle').textContent = `${symbol} — ${n}-Day Analysis`;
  } catch (err) {
    console.error('Coin load error:', err);
    toast(`Failed to load data for ${symbol}.`, 'error');
    document.getElementById('chartPlaceholder').style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Analyse →';
  }
}

function renderChart(symbol, rows) {
  const labels = rows.map(r => r.date);
  const closes = rows.map(r => r.close);
  const vols = rows.map(r => r.volatility_14d);

  if (mainChart) {
    mainChart.destroy();
    mainChart = null;
  }

  const ctx = document.getElementById('mainChart').getContext('2d');

  mainChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Close Price',
          data: closes,
          yAxisID: 'yPrice',
          borderColor: '#06b6d4',
          backgroundColor: 'rgba(6,182,212,0.07)',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.3,
        },
        {
          label: '14-Day Volatility',
          data: vols,
          yAxisID: 'yVol',
          borderColor: '#8b5cf6',
          backgroundColor: 'rgba(139,92,246,0.07)',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: { color: '#94a3b8', font: { family: 'Outfit', size: 12 } },
        },
        tooltip: {
          backgroundColor: 'rgba(5,8,22,0.95)',
          borderColor: 'rgba(255,255,255,0.08)',
          borderWidth: 1,
          titleColor: '#f1f5f9',
          bodyColor: '#94a3b8',
          callbacks: {
            label: ctx => {
              if (ctx.dataset.yAxisID === 'yPrice') {
                return ` Price: $${fmt(ctx.parsed.y, 4)}`;
              }
              return ` Volatility: ${fmtPct(ctx.parsed.y)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: {
            color: '#475569',
            maxTicksLimit: 10,
            font: { family: 'Outfit', size: 11 },
          },
        },
        yPrice: {
          type: 'linear',
          position: 'left',
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: {
            color: '#06b6d4',
            font: { family: 'Outfit', size: 11 },
            callback: v => '$' + fmt(v, 2),
          },
        },
        yVol: {
          type: 'linear',
          position: 'right',
          grid: { drawOnChartArea: false },
          ticks: {
            color: '#8b5cf6',
            font: { family: 'Outfit', size: 11 },
            callback: v => fmtPct(v),
          },
        },
      },
    },
  });
}

function updateCoinStats(rows) {
  if (!rows || rows.length === 0) return;
  const last = rows[rows.length - 1];
  setEl('statClose', '$' + fmt(last.close, 4));
  setEl('statVol', fmtPct(last.volatility_14d));
  setEl('statDate', last.date);
}

// ── Prediction Form ────────────────────────────────────────────────────────────

function initPredictForm() {
  document.getElementById('predictBtn').addEventListener('click', async () => {
    const fields = ['pOpen', 'pHigh', 'pLow', 'pClose', 'pVolume', 'pMarketcap'];
    const vals = fields.map(id => parseFloat(document.getElementById(id).value));

    if (vals.some(v => isNaN(v) || v < 0)) {
      toast('Please fill in all fields with valid positive numbers.', 'error');
      return;
    }
    const [open, high, low, close, volume, marketcap] = vals;

    if (high < low) { toast('High must be ≥ Low.', 'error'); return; }

    const btn = document.getElementById('predictBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Predicting…';

    try {
      const res = await fetch(`${API_BASE}/api/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ open, high, low, close, volume, marketcap }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || res.statusText);
      }
      const data = await res.json();
      showPredResult(data);
      toast('✅ Prediction complete!', 'success');
    } catch (err) {
      console.error('Predict error:', err);
      toast(`Prediction failed: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '🤖 Predict Volatility';
    }
  });
}

function showPredResult(data) {
  const box = document.getElementById('predResult');
  setEl('predVal', fmtPct(data.predicted_volatility));

  const levelEl = document.getElementById('predLevel');
  levelEl.textContent = data.volatility_level;
  levelEl.className = `pred-level ${data.volatility_level}`;

  setEl('predInterp', data.interpretation);
  box.classList.add('visible');
  box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
