"""
可视化模块 - 生成单页 HTML 仪表盘
功能：
  1. 一级菜单：个股 / ETF
  2. ETF 二级菜单：按类别筛选
  3. 每个标的独立走势页面（IV Rank + IV30 图表）
"""

import json
import os
import sqlite3
import pandas as pd
from config import DB_PATH, CHART_OUTPUT


# ── 数据加载 ─────────────────────────────────────────────────

def load_etf_map():
    """从 etf_watchlist.json 构建 {ticker: category} 映射"""
    etf_file = os.path.join(os.path.dirname(__file__), "etf_watchlist.json")
    if not os.path.exists(etf_file):
        return {}, {}
    with open(etf_file) as f:
        data = json.load(f)["etfs"]
    mapping = {}
    for cat, tickers in data.items():
        for t in tickers:
            mapping[t] = cat
    return mapping, data


def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT symbol, date, iv_pct, iv_percentile, iv30 FROM iv_history ORDER BY symbol, date",
        conn,
        parse_dates=["date"],
    )
    conn.close()
    return df


def build_embed_data(df, etf_map):
    tickers = {}
    for symbol, grp in df.groupby("symbol"):
        grp = grp.sort_values("date")
        dates        = grp["date"].dt.strftime("%Y-%m-%d").tolist()
        iv_ranks     = grp["iv_pct"].round(1).tolist()
        iv_pcts      = grp["iv_percentile"].round(1).fillna(-1).tolist() if "iv_percentile" in grp.columns else []
        iv30s        = grp["iv30"].round(1).fillna(0).tolist() if "iv30" in grp.columns else []

        latest_rank  = iv_ranks[-1] if iv_ranks else None
        latest_pct   = iv_pcts[-1]  if iv_pcts and iv_pcts[-1] >= 0 else None
        prev_rank    = iv_ranks[-2] if len(iv_ranks) >= 2 else None
        change       = round(latest_rank - prev_rank, 1) if (latest_rank is not None and prev_rank is not None) else None
        latest_date  = dates[-1] if dates else None

        tickers[symbol] = {
            "dates":      dates,
            "iv_ranks":   iv_ranks,
            "iv_pcts":    [v if v >= 0 else None for v in iv_pcts],
            "iv30s":      iv30s,
            "latest":     latest_rank,
            "latest_pct": latest_pct,
            "change":     change,
            "date":       latest_date,
            "category":   etf_map.get(symbol, None),  # None=个股，否则为 ETF 类别
        }
    return tickers


# ── HTML 模板 ────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IV Rank 追踪器</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f6fa; color: #2d3436; }

  /* ── 顶栏 ── */
  .topbar { background: #fff; border-bottom: 1px solid #e0e0e0;
            padding: 14px 24px; display: flex; align-items: center; gap: 16px;
            position: sticky; top: 0; z-index: 100; }
  .topbar h1 { font-size: 18px; font-weight: 700; color: #2d3436; white-space: nowrap; }
  .search-wrap { flex: 1; max-width: 400px; position: relative; }
  .search-wrap input {
    width: 100%; padding: 8px 12px 8px 36px; border: 1px solid #ddd;
    border-radius: 8px; font-size: 14px; outline: none; transition: border .2s;
  }
  .search-wrap input:focus { border-color: #6c5ce7; }
  .search-wrap::before { content: '🔍'; position: absolute; left: 10px; top: 8px; font-size: 14px; }
  .topbar .meta { font-size: 12px; color: #999; margin-left: auto; white-space: nowrap; }

  /* ── 一级导航 ── */
  .nav-bar { background: #fff; border-bottom: 1px solid #e0e0e0;
             padding: 0 24px; display: flex; gap: 4px; position: sticky; top: 53px; z-index: 99; }
  .nav-tab { padding: 11px 22px; font-size: 14px; font-weight: 600;
             border: none; background: none; cursor: pointer;
             border-bottom: 3px solid transparent; color: #666;
             transition: all .15s; }
  .nav-tab.active { color: #6c5ce7; border-bottom-color: #6c5ce7; }
  .nav-tab:hover:not(.active) { color: #2d3436; background: #f8f8f8; }

  /* ── 二级导航（ETF类别）── */
  .sub-nav { background: #fafbff; border-bottom: 1px solid #e8eaf0;
             padding: 8px 24px; display: flex; gap: 6px; flex-wrap: wrap;
             position: sticky; top: 100px; z-index: 98; }
  .sub-tab { padding: 5px 14px; font-size: 13px; border-radius: 20px;
             border: 1.5px solid #e0e0e0; background: #fff;
             cursor: pointer; transition: all .15s; color: #555; white-space: nowrap; }
  .sub-tab.active { background: #6c5ce7; color: #fff; border-color: #6c5ce7; }
  .sub-tab:hover:not(.active) { border-color: #6c5ce7; color: #6c5ce7; }

  /* ── 仪表盘 ── */
  #view-dashboard { padding: 20px 24px; }
  .stats-row { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat-card { background: #fff; border-radius: 10px; padding: 14px 20px;
               box-shadow: 0 1px 4px rgba(0,0,0,.07); min-width: 120px; }
  .stat-card .val { font-size: 26px; font-weight: 700; }
  .stat-card .lbl { font-size: 12px; color: #999; margin-top: 2px; }

  table { width: 100%; border-collapse: collapse; background: #fff;
          border-radius: 10px; overflow: hidden;
          box-shadow: 0 1px 4px rgba(0,0,0,.07); }
  thead { background: #f8f9fa; }
  th { padding: 10px 14px; text-align: left; font-size: 12px; color: #666;
       text-transform: uppercase; letter-spacing: .5px; cursor: pointer;
       user-select: none; white-space: nowrap; }
  th:hover { background: #eee; }
  th.sorted-asc::after  { content: ' ▲'; }
  th.sorted-desc::after { content: ' ▼'; }
  td { padding: 10px 14px; font-size: 14px; border-top: 1px solid #f0f0f0; }
  tr:hover td { background: #fafbff; cursor: pointer; }
  .mini-bar-wrap { display:flex; align-items:center; gap:6px; }
  .mini-bar { height:6px; border-radius:3px; background:#e0e0e0; width:80px; flex-shrink:0; }
  .mini-bar-fill { height:100%; border-radius:3px; }

  .iv-badge { display: inline-block; padding: 3px 10px; border-radius: 20px;
              font-size: 13px; font-weight: 600; }
  .iv-low  { background: #dbeafe; color: #1d4ed8; }
  .iv-mid  { background: #dcfce7; color: #15803d; }
  .iv-high { background: #fef3c7; color: #b45309; }
  .iv-peak { background: #fee2e2; color: #b91c1c; }

  .cat-badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
               font-size: 11px; background: #ede9fe; color: #6c5ce7;
               margin-left: 6px; vertical-align: middle; }

  .change-up   { color: #e53e3e; font-size: 12px; }
  .change-down { color: #38a169; font-size: 12px; }
  .change-flat { color: #999;    font-size: 12px; }

  /* ── 详情页 ── */
  #view-detail { display: none; padding: 20px 24px; }
  .back-btn { background: none; border: 1px solid #ddd; border-radius: 8px;
              padding: 7px 14px; font-size: 13px; cursor: pointer; margin-bottom: 16px;
              display: inline-flex; align-items: center; gap: 6px; }
  .back-btn:hover { background: #f0f0f0; }

  .detail-header { display: flex; align-items: flex-start; gap: 24px;
                   margin-bottom: 20px; flex-wrap: wrap; }
  .detail-title h2 { font-size: 32px; font-weight: 700; }
  .detail-title .subtitle { font-size: 13px; color: #999; margin-top: 2px; }
  .detail-kpis { display: flex; gap: 12px; flex-wrap: wrap; }
  .kpi { background: #fff; border-radius: 10px; padding: 12px 18px;
         box-shadow: 0 1px 4px rgba(0,0,0,.07); }
  .kpi .k-val { font-size: 24px; font-weight: 700; }
  .kpi .k-lbl { font-size: 11px; color: #999; margin-top: 2px; }

  /* ── 数据按钮 ── */
  .data-tabs { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  .data-tab { padding: 8px 18px; border-radius: 8px; border: 1.5px solid #ddd;
              font-size: 13px; font-weight: 500; cursor: pointer;
              transition: all .15s; background: #fff; }
  .data-tab.active { background: #6c5ce7; color: #fff; border-color: #6c5ce7; }
  .data-tab.ready:not(.active):hover { border-color: #6c5ce7; color: #6c5ce7; }
  .data-tab.reserved { color: #bbb; cursor: not-allowed; position: relative; }
  .data-tab.reserved::after { content: '即将推出'; font-size: 10px;
    background: #f0f0f0; color: #999; padding: 1px 5px; border-radius: 4px;
    margin-left: 6px; vertical-align: middle; }

  .chart-container { background: #fff; border-radius: 10px;
                     box-shadow: 0 1px 4px rgba(0,0,0,.07); padding: 16px;
                     margin-bottom: 16px; }
  #detail-chart { width: 100%; height: 400px; }

  .coming-soon-box { background: #fff; border-radius: 10px;
                     box-shadow: 0 1px 4px rgba(0,0,0,.07);
                     padding: 60px 20px; text-align: center; color: #bbb;
                     font-size: 15px; display: none; }
  .coming-soon-box .icon { font-size: 40px; margin-bottom: 10px; }

  .no-result { text-align: center; padding: 40px; color: #aaa; font-size: 15px; }
  @media(max-width:600px) { .topbar { flex-wrap: wrap; } }
</style>
</head>
<body>

<!-- 顶栏 -->
<div class="topbar">
  <h1>📈 IV Rank 追踪器</h1>
  <div class="search-wrap" id="search-area">
    <input type="text" id="search-input" placeholder="搜索标的，如 AAPL..." oninput="onSearch(this.value)">
  </div>
  <div class="meta" id="topbar-meta"></div>
</div>

<!-- 一级导航 -->
<div class="nav-bar">
  <button class="nav-tab active" id="nav-stock" onclick="switchMode('stock')">个股</button>
  <button class="nav-tab"        id="nav-etf"   onclick="switchMode('etf')">ETF</button>
</div>

<!-- 二级导航（ETF类别，初始隐藏）-->
<div class="sub-nav" id="sub-nav" style="display:none"></div>

<!-- 仪表盘视图 -->
<div id="view-dashboard">
  <div class="stats-row" id="stats-row"></div>
  <div id="no-result" class="no-result" style="display:none">未找到匹配的标的</div>
  <table id="main-table">
    <thead>
      <tr id="table-head">
        <th onclick="sortTable('symbol')">标的</th>
        <th onclick="sortTable('latest')">IV Rank</th>
        <th onclick="sortTable('latest_pct')">IV Percentile</th>
        <th onclick="sortTable('iv30')">IV30</th>
        <th onclick="sortTable('change')">Rank 日变化</th>
        <th onclick="sortTable('date')">更新日期</th>
      </tr>
    </thead>
    <tbody id="table-body"></tbody>
  </table>
</div>

<!-- 详情视图 -->
<div id="view-detail">
  <button class="back-btn" onclick="showDashboard()">← 返回列表</button>

  <div class="detail-header">
    <div class="detail-title">
      <h2 id="d-symbol"></h2>
      <div class="subtitle" id="d-date"></div>
    </div>
    <div class="detail-kpis" id="d-kpis"></div>
  </div>

  <div class="data-tabs">
    <button class="data-tab ready active" id="tab-ivrank" onclick="switchTab('ivrank')">IV Rank</button>
    <button class="data-tab ready"        id="tab-ivpct"  onclick="switchTab('ivpct')">IV Percentile</button>
    <button class="data-tab ready"        id="tab-iv30"   onclick="switchTab('iv30')">IV30 走势</button>
    <button class="data-tab reserved"     id="tab-price"  onclick="showReserved()">股价走势</button>
    <button class="data-tab reserved"     id="tab-volume" onclick="showReserved()">成交量</button>
    <button class="data-tab reserved"     id="tab-pcr"    onclick="showReserved()">P/C 比率</button>
    <button class="data-tab reserved"     id="tab-custom" onclick="showReserved()">自定义</button>
  </div>

  <div class="chart-container" id="chart-box">
    <div id="detail-chart"></div>
  </div>
  <div class="coming-soon-box" id="coming-soon-box">
    <div class="icon">🚧</div>
    该功能数据采集开发中，敬请期待
  </div>
</div>

<script>
// ── 内嵌数据 ────────────────────────────────────────────────
const DATA     = __DATA_JSON__;
const ETF_CATS = __ETF_CATS_JSON__;

const CAT_LABELS = {
  '宽基指数':     '宽基指数',
  '板块_SPDR':    '板块 SPDR',
  '板块_行业':    '行业板块',
  '固定收益':     '固定收益',
  '大宗商品':     '大宗商品',
  '杠杆_反向':    '杠杆/反向',
  '国际_新兴市场': '国际/新兴',
  '主题_创新':    '主题/创新',
};

// ── 状态 ─────────────────────────────────────────────────────
let currentMode   = 'stock';   // 'stock' | 'etf'
let currentEtfCat = 'all';     // 'all' | category key
let sortKey = 'latest', sortDir = -1;
let currentTicker = null;
let allRows = [];
let searchQuery = '';

// ── 初始化 ───────────────────────────────────────────────────
window.onload = function() {
  allRows = Object.entries(DATA).map(([sym, d]) => ({
    symbol:     sym,
    latest:     d.latest,
    latest_pct: d.latest_pct,
    iv30:       d.iv30s.length ? d.iv30s[d.iv30s.length - 1] : null,
    change:     d.change,
    date:       d.date,
    category:   d.category,
  }));

  buildSubNav();
  renderAll();

  const total = allRows.length;
  const latest_date = allRows.reduce((a, b) => (b.date > a ? b.date : a), '');
  document.getElementById('topbar-meta').textContent =
    `${total} 个标的 · 最近更新 ${latest_date}`;
};

// ── 二级导航构建 ─────────────────────────────────────────────
function buildSubNav() {
  const nav = document.getElementById('sub-nav');
  const cats = Object.keys(ETF_CATS);
  const btns = cats.map(cat => {
    const label = CAT_LABELS[cat] || cat;
    const count = ETF_CATS[cat].length;
    return `<button class="sub-tab" id="sub-${CSS.escape(cat)}" onclick="switchEtfCat('${cat}')">${label} <span style="opacity:.6;font-size:11px">${count}</span></button>`;
  }).join('');
  nav.innerHTML = `<button class="sub-tab active" id="sub-all" onclick="switchEtfCat('all')">全部</button>${btns}`;
}

// ── 模式切换 ─────────────────────────────────────────────────
function switchMode(mode) {
  currentMode = mode;
  searchQuery = '';
  document.getElementById('search-input').value = '';
  document.getElementById('nav-stock').classList.toggle('active', mode === 'stock');
  document.getElementById('nav-etf').classList.toggle('active',   mode === 'etf');
  document.getElementById('sub-nav').style.display = mode === 'etf' ? 'flex' : 'none';

  // ETF 模式时，表头加"类别"列
  const headRow = document.getElementById('table-head');
  if (mode === 'etf') {
    headRow.innerHTML = `
      <th onclick="sortTable('symbol')">标的</th>
      <th onclick="sortTable('category')">类别</th>
      <th onclick="sortTable('latest')">IV Rank</th>
      <th onclick="sortTable('latest_pct')">IV Percentile</th>
      <th onclick="sortTable('iv30')">IV30</th>
      <th onclick="sortTable('change')">Rank 日变化</th>
      <th onclick="sortTable('date')">更新日期</th>`;
  } else {
    headRow.innerHTML = `
      <th onclick="sortTable('symbol')">标的</th>
      <th onclick="sortTable('latest')">IV Rank</th>
      <th onclick="sortTable('latest_pct')">IV Percentile</th>
      <th onclick="sortTable('iv30')">IV30</th>
      <th onclick="sortTable('change')">Rank 日变化</th>
      <th onclick="sortTable('date')">更新日期</th>`;
  }
  renderAll();
}

function switchEtfCat(cat) {
  currentEtfCat = cat;
  document.querySelectorAll('.sub-tab').forEach(el => el.classList.remove('active'));
  const el = document.getElementById('sub-' + CSS.escape(cat));
  if (el) el.classList.add('active');
  renderAll();
}

// ── 可见行过滤 ───────────────────────────────────────────────
function getVisibleRows() {
  let rows;
  if (currentMode === 'stock') {
    rows = allRows.filter(r => !r.category);
  } else if (currentEtfCat === 'all') {
    rows = allRows.filter(r => !!r.category);
  } else {
    rows = allRows.filter(r => r.category === currentEtfCat);
  }
  if (searchQuery) {
    rows = rows.filter(r => r.symbol.includes(searchQuery));
  }
  return rows;
}

function renderAll() {
  const rows = getVisibleRows();
  renderStats(rows);
  renderTable(rows);
}

// ── 统计卡片 ─────────────────────────────────────────────────
function renderStats(rows) {
  const vals = rows.map(r => r.latest).filter(v => v !== null);
  const pcts = rows.map(r => r.latest_pct).filter(v => v !== null);
  const high = vals.filter(v => v >= 75).length;
  const low  = vals.filter(v => v < 25).length;
  const avgRank = vals.length ? (vals.reduce((a,b)=>a+b,0)/vals.length).toFixed(1) : '-';
  const avgPct  = pcts.length ? (pcts.reduce((a,b)=>a+b,0)/pcts.length).toFixed(1) : '-';

  document.getElementById('stats-row').innerHTML = `
    <div class="stat-card"><div class="val">${vals.length}</div><div class="lbl">追踪标的数</div></div>
    <div class="stat-card"><div class="val" style="color:#e53e3e">${high}</div><div class="lbl">IV Rank ≥75%</div></div>
    <div class="stat-card"><div class="val" style="color:#1d4ed8">${low}</div><div class="lbl">IV Rank &lt;25%</div></div>
    <div class="stat-card"><div class="val">${avgRank}%</div><div class="lbl">平均 IV Rank</div></div>
    <div class="stat-card"><div class="val">${avgPct}%</div><div class="lbl">平均 IV Percentile</div></div>
  `;
}

// ── 表格渲染 ─────────────────────────────────────────────────
function ivClass(v) {
  if (v === null) return '';
  if (v < 25)  return 'iv-low';
  if (v < 50)  return 'iv-mid';
  if (v < 75)  return 'iv-high';
  return 'iv-peak';
}

function renderTable(rows) {
  const sorted = [...rows].sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (sortKey === 'symbol' || sortKey === 'category') {
      va = va || ''; vb = vb || '';
      return sortDir * va.localeCompare(vb);
    }
    if (va === null) return 1; if (vb === null) return -1;
    return sortDir * (vb - va);
  });

  const tbody = document.getElementById('table-body');
  if (!sorted.length) {
    document.getElementById('no-result').style.display = 'block';
    tbody.innerHTML = '';
    return;
  }
  document.getElementById('no-result').style.display = 'none';

  tbody.innerHTML = sorted.map(r => {
    const iv    = r.latest     !== null ? r.latest.toFixed(1)     : '-';
    const ivpct = r.latest_pct !== null ? r.latest_pct.toFixed(1) : '-';
    const iv30  = r.iv30       !== null ? r.iv30.toFixed(1) + '%' : '-';

    const pctBar = r.latest_pct !== null
      ? `<div class="mini-bar-wrap">
           <div class="mini-bar"><div class="mini-bar-fill" style="width:${r.latest_pct}%;background:${barColor(r.latest_pct)}"></div></div>
           <span>${ivpct}%</span>
         </div>`
      : '-';

    const chg = r.change !== null
      ? `<span class="${r.change > 0 ? 'change-up' : r.change < 0 ? 'change-down' : 'change-flat'}">
           ${r.change > 0 ? '▲' : r.change < 0 ? '▼' : '—'} ${Math.abs(r.change).toFixed(1)}
         </span>`
      : '<span class="change-flat">—</span>';

    const catCell = currentMode === 'etf'
      ? `<td><span class="cat-badge">${CAT_LABELS[r.category] || r.category || ''}</span></td>`
      : '';

    return `<tr onclick="showDetail('${r.symbol}')">
      <td><strong>${r.symbol}</strong></td>
      ${catCell}
      <td><span class="iv-badge ${ivClass(r.latest)}">${iv}%</span></td>
      <td>${pctBar}</td>
      <td>${iv30}</td>
      <td>${chg}</td>
      <td style="color:#999;font-size:12px">${r.date || '-'}</td>
    </tr>`;
  }).join('');
}

function barColor(v) {
  if (v < 25)  return '#4e9af1';
  if (v < 50)  return '#2ecc71';
  if (v < 75)  return '#f39c12';
  return '#e74c3c';
}

function sortTable(key) {
  if (sortKey === key) { sortDir *= -1; }
  else { sortKey = key; sortDir = -1; }
  renderAll();
}

// ── 搜索 ─────────────────────────────────────────────────────
function onSearch(q) {
  searchQuery = q.trim().toUpperCase();
  // 搜索时跨越个股/ETF边界
  if (searchQuery) {
    const matched = allRows.filter(r => r.symbol.includes(searchQuery));
    renderStats(matched);
    renderTable(matched);
  } else {
    renderAll();
  }
}

// ── 详情视图 ─────────────────────────────────────────────────
function showDetail(symbol) {
  currentTicker = symbol;
  const d = DATA[symbol];
  if (!d) return;

  document.getElementById('view-dashboard').style.display = 'none';
  document.getElementById('view-detail').style.display    = 'block';
  document.getElementById('search-area').style.display   = 'none';

  const catLabel = d.category ? (CAT_LABELS[d.category] || d.category) : null;
  document.getElementById('d-symbol').innerHTML =
    symbol + (catLabel ? `<span class="cat-badge" style="font-size:14px">${catLabel}</span>` : '');
  document.getElementById('d-date').textContent =
    d.date ? `最近更新：${d.date}` : '';

  const iv_rank = d.latest     !== null ? d.latest.toFixed(1)     + '%' : '-';
  const iv_pct  = d.latest_pct !== null ? d.latest_pct.toFixed(1) + '%' : '-';
  const iv30    = d.iv30s.length ? d.iv30s[d.iv30s.length-1].toFixed(1) + '%' : '-';
  const chgText = d.change !== null
    ? (d.change > 0 ? '▲ ' : d.change < 0 ? '▼ ' : '') + Math.abs(d.change).toFixed(1) + '%'
    : '-';
  const chgColor = d.change > 0 ? '#e53e3e' : d.change < 0 ? '#38a169' : '#999';

  document.getElementById('d-kpis').innerHTML = `
    <div class="kpi">
      <div class="k-val"><span class="iv-badge ${ivClass(d.latest)}">${iv_rank}</span></div>
      <div class="k-lbl">IV Rank</div>
    </div>
    <div class="kpi">
      <div class="k-val"><span class="iv-badge ${ivClass(d.latest_pct)}">${iv_pct}</span></div>
      <div class="k-lbl">IV Percentile</div>
    </div>
    <div class="kpi">
      <div class="k-val">${iv30}</div>
      <div class="k-lbl">IV30</div>
    </div>
    <div class="kpi">
      <div class="k-val" style="color:${chgColor}">${chgText}</div>
      <div class="k-lbl">Rank 日变化</div>
    </div>
  `;

  switchTab('ivrank');
  const hasPct = d.iv_pcts && d.iv_pcts.some(v => v !== null);
  document.getElementById('tab-ivpct').classList.toggle('reserved', !hasPct);
  document.getElementById('tab-ivpct').classList.toggle('ready',    hasPct);
  document.getElementById('tab-ivpct').setAttribute('onclick', hasPct ? "switchTab('ivpct')" : "showReserved()");
}

function showDashboard() {
  document.getElementById('view-dashboard').style.display = 'block';
  document.getElementById('view-detail').style.display    = 'none';
  document.getElementById('search-area').style.display   = 'block';
  Plotly.purge('detail-chart');
}

// ── 图表 Tab 切换 ─────────────────────────────────────────────
function switchTab(tab) {
  ['ivrank','ivpct','iv30','price','volume','pcr','custom'].forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (el) el.classList.remove('active');
  });
  const el = document.getElementById('tab-' + tab);
  if (el) el.classList.add('active');

  document.getElementById('chart-box').style.display       = 'block';
  document.getElementById('coming-soon-box').style.display = 'none';

  if      (tab === 'ivrank') renderIVRankChart();
  else if (tab === 'ivpct')  renderIVPercentileChart();
  else if (tab === 'iv30')   renderIV30Chart();
}

function showReserved() {
  ['ivrank','ivpct','iv30'].forEach(t => {
    document.getElementById('tab-' + t).classList.remove('active');
  });
  document.getElementById('chart-box').style.display       = 'none';
  document.getElementById('coming-soon-box').style.display = 'block';
}

function renderIVRankChart() {
  const d = DATA[currentTicker];
  if (!d) return;
  const trace = {
    x: d.dates, y: d.iv_ranks,
    type: 'scatter', mode: d.dates.length > 1 ? 'lines+markers' : 'markers',
    name: 'IV Rank',
    line: { color: '#6c5ce7', width: 2.5 },
    marker: { size: 6, color: '#6c5ce7' },
    hovertemplate: '<b>%{x}</b><br>IV Rank: %{y:.1f}%<extra></extra>',
  };
  const shapes = [
    { type:'line', x0:0, x1:1, xref:'paper', y0:75, y1:75,
      line:{color:'rgba(231,76,60,0.4)', width:1.5, dash:'dash'} },
    { type:'line', x0:0, x1:1, xref:'paper', y0:50, y1:50,
      line:{color:'rgba(243,156,18,0.4)', width:1.5, dash:'dot'} },
    { type:'line', x0:0, x1:1, xref:'paper', y0:25, y1:25,
      line:{color:'rgba(78,154,241,0.4)', width:1.5, dash:'dash'} },
  ];
  const layout = {
    margin: { t:20, r:60, b:50, l:55 },
    xaxis: { showgrid:true, gridcolor:'#f0f0f0',
             rangeselector: { buttons: [
               {count:1,label:'1月',step:'month',stepmode:'backward'},
               {count:3,label:'3月',step:'month',stepmode:'backward'},
               {count:6,label:'6月',step:'month',stepmode:'backward'},
               {step:'all',label:'全部'}
             ]},
             rangeslider: {visible:true, thickness:0.06} },
    yaxis: { title:'IV Rank (%)', range:[0,100], showgrid:true,
             gridcolor:'#f0f0f0', ticksuffix:'%' },
    shapes, annotations: [
      { xref:'paper', x:1.01, y:75, text:'高位', showarrow:false,
        font:{size:11, color:'rgba(231,76,60,0.7)'}, xanchor:'left' },
      { xref:'paper', x:1.01, y:25, text:'低位', showarrow:false,
        font:{size:11, color:'rgba(78,154,241,0.7)'}, xanchor:'left' },
    ],
    plot_bgcolor:'#fff', paper_bgcolor:'#fff',
    font: { family:'-apple-system, sans-serif', size:12 },
    hovermode: 'x unified',
  };
  Plotly.newPlot('detail-chart', [trace], layout, {responsive:true, displayModeBar:false});
}

function renderIVPercentileChart() {
  const d = DATA[currentTicker];
  if (!d || !d.iv_pcts || !d.iv_pcts.some(v => v !== null)) {
    document.getElementById('chart-box').style.display       = 'none';
    document.getElementById('coming-soon-box').style.display = 'block';
    return;
  }
  const trace = {
    x: d.dates, y: d.iv_pcts,
    type: 'scatter', mode: d.dates.length > 1 ? 'lines+markers' : 'markers',
    name: 'IV Percentile',
    line: { color: '#e17055', width: 2.5 },
    marker: { size: 6, color: '#e17055' },
    connectgaps: true,
    hovertemplate: '<b>%{x}</b><br>IV Percentile: %{y:.1f}%<extra></extra>',
  };
  const shapes = [
    { type:'line', x0:0, x1:1, xref:'paper', y0:75, y1:75,
      line:{color:'rgba(231,76,60,0.4)', width:1.5, dash:'dash'} },
    { type:'line', x0:0, x1:1, xref:'paper', y0:50, y1:50,
      line:{color:'rgba(243,156,18,0.4)', width:1.5, dash:'dot'} },
    { type:'line', x0:0, x1:1, xref:'paper', y0:25, y1:25,
      line:{color:'rgba(78,154,241,0.4)', width:1.5, dash:'dash'} },
  ];
  const layout = {
    margin: { t:20, r:60, b:50, l:55 },
    xaxis: { showgrid:true, gridcolor:'#f0f0f0',
             rangeselector: { buttons: [
               {count:1,label:'1月',step:'month',stepmode:'backward'},
               {count:3,label:'3月',step:'month',stepmode:'backward'},
               {count:6,label:'6月',step:'month',stepmode:'backward'},
               {step:'all',label:'全部'}
             ]},
             rangeslider: {visible:true, thickness:0.06} },
    yaxis: { title:'IV Percentile (%)', range:[0,100], showgrid:true,
             gridcolor:'#f0f0f0', ticksuffix:'%' },
    shapes, annotations: [
      { xref:'paper', x:1.01, y:75, text:'高位', showarrow:false,
        font:{size:11, color:'rgba(231,76,60,0.7)'}, xanchor:'left' },
      { xref:'paper', x:1.01, y:25, text:'低位', showarrow:false,
        font:{size:11, color:'rgba(78,154,241,0.7)'}, xanchor:'left' },
    ],
    plot_bgcolor:'#fff', paper_bgcolor:'#fff',
    font: { family:'-apple-system, sans-serif', size:12 },
    hovermode: 'x unified',
  };
  Plotly.newPlot('detail-chart', [trace], layout, {responsive:true, displayModeBar:false});
}

function renderIV30Chart() {
  const d = DATA[currentTicker];
  if (!d || !d.iv30s.length) {
    document.getElementById('chart-box').style.display       = 'none';
    document.getElementById('coming-soon-box').style.display = 'block';
    return;
  }
  const trace = {
    x: d.dates, y: d.iv30s,
    type: 'scatter', mode: d.dates.length > 1 ? 'lines+markers' : 'markers',
    name: 'IV30',
    line: { color: '#00b894', width: 2.5 },
    marker: { size: 6, color: '#00b894' },
    hovertemplate: '<b>%{x}</b><br>IV30: %{y:.1f}%<extra></extra>',
  };
  const layout = {
    margin: { t:20, r:20, b:50, l:55 },
    xaxis: { showgrid:true, gridcolor:'#f0f0f0',
             rangeslider: {visible:true, thickness:0.06} },
    yaxis: { title:'30日隐含波动率 (%)', showgrid:true,
             gridcolor:'#f0f0f0', ticksuffix:'%' },
    plot_bgcolor:'#fff', paper_bgcolor:'#fff',
    font: { family:'-apple-system, sans-serif', size:12 },
    hovermode: 'x unified',
  };
  Plotly.newPlot('detail-chart', [trace], layout, {responsive:true, displayModeBar:false});
}
</script>
</body>
</html>
"""


# ── 生成 HTML ────────────────────────────────────────────────

def generate_chart():
    df = load_data()
    if df.empty:
        print("数据库暂无数据，请先运行 python3 scraper.py")
        return

    etf_map, etf_cats = load_etf_map()
    embed_data  = build_embed_data(df, etf_map)
    data_json   = json.dumps(embed_data, ensure_ascii=False)
    etf_cats_json = json.dumps(etf_cats, ensure_ascii=False)

    html = HTML_TEMPLATE.replace("__DATA_JSON__",     data_json)
    html = html.replace(         "__ETF_CATS_JSON__", etf_cats_json)

    with open(CHART_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    stock_cnt = sum(1 for d in embed_data.values() if not d["category"])
    etf_cnt   = sum(1 for d in embed_data.values() if d["category"])
    print(f"\n图表已生成: {CHART_OUTPUT}")
    print(f"个股: {stock_cnt}  ETF: {etf_cnt}  合计: {len(embed_data)}")

    rows = [
        (sym, d["latest"], d["latest_pct"], d["change"])
        for sym, d in embed_data.items()
        if d["latest"] is not None
    ]
    rows.sort(key=lambda x: x[1], reverse=True)
    print("\n── 最新 IV Rank 排行（前15）──────────────────────────────────")
    print(f"  {'标的':<8}  {'IV Rank':>8}  {'IV Percentile':>14}  日变化")
    print("  " + "─" * 50)
    for sym, iv, pct, chg in rows[:15]:
        pct_str = f"{pct:6.1f}%" if pct is not None else "    N/A"
        chg_str = f"{chg:+.1f}" if chg is not None else "  -"
        print(f"  {sym:<8}  {iv:7.1f}%  {pct_str:>14}  {chg_str}")


if __name__ == "__main__":
    generate_chart()
