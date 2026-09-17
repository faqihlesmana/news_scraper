/* ─────────────────────────────────────────────────────────
   dashboard.js – Pohuwato News Scraper Dashboard
   ───────────────────────────────────────────────────────── */

function getClientId() {
  let cid = localStorage.getItem('news_app_client_id');
  if (!cid) {
    cid = 'c_' + Math.random().toString(36).substring(2) + Date.now().toString(36);
    localStorage.setItem('news_app_client_id', cid);
  }
  return cid;
}

const API = {
  stats:        () => fetch('/api/stats').then(r => r.json()),
  news:         (params) => fetch('/api/news?' + new URLSearchParams(params), {
                  headers: { 'X-Client-ID': getClientId() }
                }).then(r => r.json()),
  article:      (id) => fetch(`/api/news/${id}`).then(r => r.json()),
  sources:      () => fetch('/api/sources').then(r => r.json()),
  categories:   () => fetch('/api/categories').then(r => r.json()),
  ollamaStatus: () => fetch('/api/ollama/status').then(r => r.json()),
  startScrape:  (opts) => fetch('/api/scrape', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(opts)
  }).then(r => r.json()),
  scrapeStatus: () => fetch('/api/scrape/status').then(r => r.json()),
};


/* ── State ── */
let state = {
  page: 1, perPage: 20,
  search: '', source: '', category: '', expCategory: '',
  feedbackFilter: '', quarter: '',
  startDate: '', endDate: '',
  totalArticles: 0, totalPages: 1,
  sourceChart: null, categoryChart: null,
  scraping: false,
  statusInterval: null,
  hideIrrelevant: false,
  _allIrrelevantArticles: [], // cache for irrelevant modal
};

/* ── DOM Refs ── */
const $ = id => document.getElementById(id);

/* ─────────────────────────────────────────────────────────
   INIT
   ───────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initFilters();
  loadStats();
  loadNews();
  checkScrapeStatus();
  checkOllamaStatus();
  state.statusInterval = setInterval(checkScrapeStatus, 5000);
  setInterval(checkOllamaStatus, 30000); // cek Ollama tiap 30 detik
});

/* ─────────────────────────────────────────────────────────
   STATS
   ───────────────────────────────────────────────────────── */
async function loadStats() {
  try {
    const data = await API.stats();
    $('stat-total').textContent   = data.total.toLocaleString();
    $('stat-today').textContent   = data.today.toLocaleString();
    $('stat-sources').textContent = data.per_source.length;
    $('stat-cats').textContent    = data.per_category.length;

    state._lastStatsData = data;
    renderSourceChart(data.per_source);
    renderCategoryChart(data.per_category);
    renderRecentLogs(data.recent_logs);
  } catch(e) {
    console.error('Stats error:', e);
  }
}

/* ── Charts ── */
const CHART_COLORS_EMERALD = [
  '#10b981','#059669','#34d399','#6ee7b7',
  '#f59e0b','#d97706','#fbbf24','#fde68a',
  '#3b82f6','#2563eb','#60a5fa','#93c5fd',
];

/* Read CSS variable from :root (updates per theme/mode) */
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || null;
}
function getChartTextColor()  { return cssVar('--text-muted')   || '#9ca3af'; }
function getChartGridColor()  { return cssVar('--border')       || '#f1f5f9'; }
function getChartCardBg()     { return cssVar('--bg-card')      || '#ffffff'; }
function getChartPrimaryText(){ return cssVar('--text-primary')  || '#111827'; }
function getChartSecText()    { return cssVar('--text-secondary')|| '#374151'; }

/* Re-render both charts whenever theme changes */
document.addEventListener('themechange', () => {
  if (state._lastStatsData) {
    renderSourceChart(state._lastStatsData.per_source);
    renderCategoryChart(state._lastStatsData.per_category);
  }
});

function renderSourceChart(data) {
  const ctx = $('chart-sources').getContext('2d');
  if (state.sourceChart) state.sourceChart.destroy();
  const textColor = getChartTextColor();
  const gridColor = getChartGridColor();
  const bgCard    = getChartCardBg();
  const ttTitle   = getChartPrimaryText();
  const ttBody    = getChartSecText();
  state.sourceChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.name.replace('Pohuwato','').trim()),
      datasets: [{
        data: data.map(d => d.count),
        backgroundColor: CHART_COLORS_EMERALD,
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: bgCard,
          borderColor: gridColor,
          borderWidth: 1,
          titleColor: ttTitle,
          bodyColor: ttBody,
          callbacks: {
            label: ctx => ` ${ctx.parsed.y} artikel`
          }
        }
      },
      scales: {
        x: {
          ticks: { color: textColor, font: { size: 10 } },
          grid: { display: false },
          border: { display: false },
        },
        y: {
          ticks: { color: textColor, font: { size: 10 } },
          grid: { color: gridColor },
          border: { display: false },
        }
      }
    }
  });
}

function renderCategoryChart(data) {
  const ctx = $('chart-categories').getContext('2d');
  if (state.categoryChart) state.categoryChart.destroy();
  const filtered   = data.slice(0, 8);
  const textColor  = getChartTextColor();
  const gridColor  = getChartGridColor();
  const bgCard     = getChartCardBg();
  const ttTitle    = getChartPrimaryText();
  const ttBody     = getChartSecText();
  state.categoryChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: filtered.map(d => d.name),
      datasets: [{
        data: filtered.map(d => d.count),
        backgroundColor: CHART_COLORS_EMERALD,
        borderColor: bgCard,
        borderWidth: 3,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true,
      cutout: '68%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: textColor,
            font: { size: 10 },
            padding: 12,
            boxWidth: 10,
            usePointStyle: true,
          }
        },
        tooltip: {
          backgroundColor: bgCard,
          borderColor: gridColor,
          borderWidth: 1,
          titleColor: ttTitle,
          bodyColor: ttBody,
          callbacks: { label: ctx => ` ${ctx.parsed} artikel` }
        }
      }
    }
  });
}

function renderRecentLogs(logs) {
  const el = $('recent-logs');
  if (!logs || !logs.length) {
    el.innerHTML = '<p style="color:var(--text-muted);font-size:12px;text-align:center;padding:16px">Belum ada log scraping</p>';
    return;
  }
  el.innerHTML = logs.slice(0, 8).map(l => `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);">
      <div>
        <span style="font-size:12px;font-weight:600;color:var(--text-primary)">${escHtml(l.name || l.source_slug)}</span>
        <span style="font-size:11px;color:var(--text-muted);margin-left:8px">${formatDate(l.run_at)}</span>
      </div>
      <div style="display:flex;gap:6px;font-size:11px">
        <span style="color:var(--emerald)">+${l.articles_new}</span>
        <span style="color:var(--text-muted)">skip ${l.articles_skip}</span>
        <span class="${l.status==='success'?'source-badge':'category-badge uncategorized'}" style="padding:2px 8px">${l.status}</span>
      </div>
    </div>
  `).join('');
}

/* ─────────────────────────────────────────────────────────
   FILTERS
   ───────────────────────────────────────────────────────── */
async function initFilters() {
  // Populate source filter
  const sources = await API.sources().catch(() => []);
  const sourceSel = $('filter-source');
  sources.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.slug;
    opt.textContent = s.name;
    sourceSel.appendChild(opt);
  });

  // Populate category filter (Lapangan Usaha) - Sorted by PDRB Code (A-R-U)
  const categories = await API.categories().catch(() => []);
  const catSel = $('filter-category');
  catSel.innerHTML = '<option value="">Lapus (Semua)</option>';
  
  // Defined PDRB keys in official sector order
  Object.keys(PDRB_MAP).forEach(c => {
    const info = PDRB_MAP[c];
    const code = info ? info.code : '—';
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = `[${code}] ${c}`;
    catSel.appendChild(opt);
  });

  // Any extra categories from DB not in PDRB_MAP
  categories.forEach(c => {
    if (!PDRB_MAP[c] && c !== 'Belum Dikategorikan') {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = `[—] ${c}`;
      catSel.appendChild(opt);
    }
  });

  // Populate PDRB Pengeluaran filter - Sorted by PDRB Code (KRT, LNPRT, etc.)
  const expCatSel = $('filter-exp-category');
  if (expCatSel) {
    expCatSel.innerHTML = '<option value="">Pengeluaran (Semua)</option>';
    Object.keys(PDRB_EXP_MAP).forEach(e => {
      const info = PDRB_EXP_MAP[e];
      const code = info ? info.code : '—';
      const opt = document.createElement('option');
      opt.value = e;
      opt.textContent = `[${code}] ${e}`;
      expCatSel.appendChild(opt);
    });

    expCatSel.addEventListener('change', ev => {
      state.expCategory = ev.target.value;
      state.page = 1;
      loadNews();
    });
  }

  // Feedback Filter
  const fbSel = $('filter-feedback');
  if (fbSel) {
    fbSel.addEventListener('change', e => {
      state.feedbackFilter = e.target.value;
      state.page = 1;
      loadNews();
    });
  }

  // Quarter Filter (Triwulan)
  const qSel = $('filter-quarter');
  if (qSel) {
    qSel.addEventListener('change', e => {
      const q = e.target.value;
      state.quarter = q;
      const year = new Date().getFullYear();

      if (q === 'Q1') {
        state.startDate = `${year}-01-01`;
        state.endDate   = `${year}-03-31`;
      } else if (q === 'Q2') {
        state.startDate = `${year}-04-01`;
        state.endDate   = `${year}-06-30`;
      } else if (q === 'Q3') {
        state.startDate = `${year}-07-01`;
        state.endDate   = `${year}-09-30`;
      } else if (q === 'Q4') {
        state.startDate = `${year}-10-01`;
        state.endDate   = `${year}-12-31`;
      } else {
        state.startDate = '';
        state.endDate   = '';
      }

      // Sync date inputs inside popover
      if ($('filter-start-date')) $('filter-start-date').value = state.startDate;
      if ($('filter-end-date'))   $('filter-end-date').value   = state.endDate;
      updateDateLabel();

      state.page = 1;
      loadNews();
    });
  }

  // Date Popover Toggle & Controls
  const toggleBtn = $('btn-toggle-date-popover');
  const popover   = $('date-popover');
  if (toggleBtn && popover) {
    toggleBtn.addEventListener('click', e => {
      e.stopPropagation();
      popover.classList.toggle('open');
    });

    document.addEventListener('click', e => {
      if (!popover.contains(e.target) && !toggleBtn.contains(e.target)) {
        popover.classList.remove('open');
      }
    });

    $('btn-apply-date').addEventListener('click', () => {
      state.startDate = $('filter-start-date').value;
      state.endDate   = $('filter-end-date').value;
      if (qSel) qSel.value = ''; // clear quarter if custom date set
      state.quarter = '';
      updateDateLabel();
      popover.classList.remove('open');
      state.page = 1;
      loadNews();
    });

    $('btn-clear-date').addEventListener('click', () => {
      state.startDate = '';
      state.endDate   = '';
      state.quarter   = '';
      if ($('filter-start-date')) $('filter-start-date').value = '';
      if ($('filter-end-date'))   $('filter-end-date').value   = '';
      if (qSel) qSel.value = '';
      updateDateLabel();
      popover.classList.remove('open');
      state.page = 1;
      loadNews();
    });
  }

  function updateDateLabel() {
    const label = $('date-popover-label');
    if (!label) return;
    if (state.quarter) {
      label.textContent = `Triwulan ${state.quarter.replace('Q','')}`;
    } else if (state.startDate || state.endDate) {
      const s = state.startDate ? formatDateShort(state.startDate) : '…';
      const e = state.endDate ? formatDateShort(state.endDate) : '…';
      label.textContent = `${s} - ${e}`;
    } else {
      label.textContent = 'Rentang Tanggal';
    }
  }

  function formatDateShort(str) {
    try {
      const d = new Date(str);
      return `${d.getDate()}/${d.getMonth()+1}`;
    } catch { return str; }
  }

  // Events
  let searchTimer;
  $('search-input').addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.search = e.target.value;
      state.page = 1;
      loadNews();
    }, 350);
  });

  sourceSel.addEventListener('change', e => {
    state.source = e.target.value;
    state.page = 1;
    loadNews();
  });

  catSel.addEventListener('change', e => {
    state.category = e.target.value;
    state.page = 1;
    loadNews();
  });

  $('btn-reset-filter').addEventListener('click', () => {
    state.search = ''; state.source = ''; state.category = ''; state.expCategory = '';
    state.feedbackFilter = ''; state.quarter = '';
    state.startDate = ''; state.endDate = '';
    state.page = 1;
    $('search-input').value = '';
    sourceSel.value = '';
    catSel.value = '';
    if (expCatSel) expCatSel.value = '';
    if (fbSel) fbSel.value = '';
    if (qSel) qSel.value = '';
    if ($('filter-start-date')) $('filter-start-date').value = '';
    if ($('filter-end-date'))   $('filter-end-date').value   = '';
    updateDateLabel();
    loadNews();
  });
}

/* ─────────────────────────────────────────────────────────
   NEWS TABLE
   ───────────────────────────────────────────────────────── */
async function loadNews() {
  showTableLoading();
  try {
    const params = {
      page: state.page,
      per_page: state.perPage,
      search: state.search,
      source: state.source,
      category: state.category,
      exp_category: state.expCategory,
      start_date: state.startDate,
      end_date: state.endDate,
    };
    if (state.hideIrrelevant) params.hide_irrelevant = '1';

    const data = await API.news(params);
    state.totalArticles = data.total;
    state.totalPages    = data.pages;
    renderTable(data.articles);
    renderPagination(data);
  } catch(e) {
    console.error('News error:', e);
    $('news-tbody').innerHTML = `<tr><td colspan="7" class="empty-state"><div class="empty-state-icon">⚠️</div><h3>Gagal memuat data</h3><p>${e.message}</p></td></tr>`;
  }
}


/* ── PDRB Sector Color & Code Helper ── */
const PDRB_MAP = {
  'Pertanian, Kehutanan & Perikanan':                     { code: 'A', class: 'cat-a' },
  'Pertambangan & Penggalian':                            { code: 'B', class: 'cat-b' },
  'Industri Pengolahan':                                  { code: 'C', class: 'cat-c' },
  'Pengadaan Listrik & Gas':                              { code: 'D', class: 'cat-d' },
  'Pengadaan Air, Pengelolaan Sampah & Daur Ulang':       { code: 'E', class: 'cat-e' },
  'Konstruksi':                                           { code: 'F', class: 'cat-f' },
  'Perdagangan Besar, Eceran & Reparasi':                 { code: 'G', class: 'cat-g' },
  'Transportasi & Pergudangan':                           { code: 'H', class: 'cat-h' },
  'Penyediaan Akomodasi & Makan Minum':                   { code: 'I', class: 'cat-i' },
  'Informasi & Komunikasi':                               { code: 'J', class: 'cat-j' },
  'Jasa Keuangan & Asuransi':                             { code: 'K', class: 'cat-k' },
  'Real Estate':                                          { code: 'L', class: 'cat-l' },
  'Jasa Perusahaan':                                      { code: 'M-N', class: 'cat-mn' },
  'Administrasi Pemerintahan, Pertahanan & Sosial Wajib': { code: 'O', class: 'cat-o' },
  'Jasa Pendidikan':                                      { code: 'P', class: 'cat-p' },
  'Jasa Kesehatan & Kegiatan Sosial':                     { code: 'Q', class: 'cat-q' },
  'Jasa Lainnya':                                         { code: 'R-U', class: 'cat-rstu' },
  'Tidak Relevan':                                        { code: '—', class: 'uncategorized' },
};

const PDRB_EXP_MAP = {
  'Konsumsi Rumah Tangga': { class: 'exp-rt',  code: 'KRT' },
  'Konsumsi LNPRT':       { class: 'exp-ln',  code: 'LNPRT' },
  'Konsumsi Pemerintah':  { class: 'exp-pem', code: 'KPem' },
  'PMTB':                 { class: 'exp-pmtb', code: 'PMTB' },
  'Perubahan Inventori':  { class: 'exp-inv', code: 'INV' },
  'Ekspor':               { class: 'exp-eks', code: 'EKS' },
  'Impor':                { class: 'exp-imp', code: 'IMP' },
  'Tidak Relevan':        { class: 'uncategorized', code: '—' },
};

function getSubcategoryBadgeInfo(category, subcategory) {
  if (!category || category === 'Tidak Relevan' || category === 'Belum Dikategori') {
    return { text: subcategory || 'Tidak Relevan', class: 'uncategorized' };
  }
  const info = PDRB_MAP[category];
  const textDisplay = subcategory || category;
  return {
    text: textDisplay,
    class: info ? info.class : 'uncategorized'
  };
}

function getExpBadgeInfo(exp_category, exp_subcategory) {
  if (!exp_category || exp_category === 'Tidak Relevan' || exp_category === 'Belum Dikategori') {
    return { text: exp_subcategory || 'Tidak Relevan', class: 'uncategorized', code: '—' };
  }
  const info = PDRB_EXP_MAP[exp_category];
  const code = info ? info.code : '—';
  const textDisplay = exp_subcategory || exp_category;
  return {
    text: `${code} · ${textDisplay}`,
    class: info ? info.class : 'uncategorized',
    code: code
  };
}

function renderTable(articles) {
  const tbody = $('news-tbody');

  let filteredArticles = articles;
  if (state.feedbackFilter) {
    filteredArticles = articles.filter(a => {
      const fb = a.feedback || {};
      if (state.feedbackFilter === 'none') return fb.user_flag === null || fb.user_flag === undefined;
      if (state.feedbackFilter === 'sip') return fb.user_flag === 0;
      if (state.feedbackFilter === 'gasip') return fb.user_flag === 1;
      return true;
    });
  }

  if (!filteredArticles.length) {
    tbody.innerHTML = `
      <tr><td colspan="7">
        <div class="empty-state">
          <div class="empty-state-icon">💭</div>
          <h3>Tidak ada berita ditemukan</h3>
          <p>Coba ubah filter pencarian atau feedback</p>
        </div>
      </td></tr>`;
    return;
  }

  tbody.innerHTML = filteredArticles.map(a => {
    const badge    = getSubcategoryBadgeInfo(a.category, a.subcategory);
    const expBadge = getExpBadgeInfo(a.exp_category, a.exp_subcategory);
    const fb       = a.feedback || { sip: 0, gasip: 0, user_flag: null, user_count: 0 };
    const isSip    = fb.user_flag === 0;
    const isGaSip  = fb.user_flag === 1;
    const hasCorrection = (fb.gasip > 0 || isGaSip);
    const correctedDot  = hasCorrection ? `<span class="corrected-dot" title="Kategori telah dikoreksi pengguna">●</span> ` : '';
    const correctedClass = hasCorrection ? 'is-corrected' : '';
    const safeTitle = escHtml((a.title || '').replace(/'/g, '\u2019'));

    return `
    <tr onclick="openArticle(${a.id})" data-title="${safeTitle}">
      <td class="td-title" title="${escHtml(a.title || '—')}">${escHtml(truncateText(a.title || '—', 70))}</td>
      <td class="td-source">
        <span class="source-badge">📰 ${escHtml(shortName(a.source_media))}</span>
      </td>
      <td>
        <span class="category-badge ${badge.class} ${correctedClass}" title="${hasCorrection ? '✏️ Kategori telah dikoreksi pengguna' : 'Sektor PDRB Usaha: ' + escHtml(a.category || '—')}">
          ${correctedDot}${escHtml(badge.text)}
        </span>
      </td>
      <td>
        <span class="exp-badge ${expBadge.class} ${correctedClass}" title="${hasCorrection ? '✏️ Kategori telah dikoreksi pengguna' : 'Sektor PDRB Pengeluaran: ' + escHtml(a.exp_category || '—')}">
          ${correctedDot}${escHtml(expBadge.text)}
        </span>
      </td>
      <td class="td-date">${formatDate(a.published_at)}</td>
      <td>
        <div class="feedback-group" onclick="event.stopPropagation()">
          <button class="feedback-btn ${isSip ? 'fb-active-sip' : ''}" onclick="submitFeedback(${a.id}, 0)" title="Sip (Kategori Benar)">👍</button>
          <button class="feedback-btn ${isGaSip ? 'fb-active-gasip' : ''}" onclick="openFeedbackModal(${a.id}, '${safeTitle}')" title="Ga Sip (Kategori Salah)">👎</button>
        </div>
      </td>
      <td>
        <button onclick="copyArticleUrl('${escHtml(a.url)}', event)" class="btn btn-ghost btn-sm btn-icon" title="Salin Link Berita">📋</button>
      </td>
    </tr>
    `;
  }).join('');
}

function showTableLoading() {
  $('news-tbody').innerHTML = Array(8).fill(`
    <tr>
      ${Array(7).fill('<td><div class="skeleton" style="height:14px;border-radius:4px"></div></td>').join('')}
    </tr>
  `).join('');
}

/* ─────────────────────────────────────────────────────────
   PAGINATION
   ───────────────────────────────────────────────────────── */
function renderPagination(data) {
  const { total, page, per_page, pages } = data;
  const start = (page - 1) * per_page + 1;
  const end   = Math.min(page * per_page, total);

  $('pagination-info').textContent = total
    ? `Menampilkan ${start}–${end} dari ${total.toLocaleString()} berita`
    : 'Tidak ada berita';

  const ctrl = $('pagination-controls');
  ctrl.innerHTML = '';

  const addBtn = (label, pg, disabled = false) => {
    const btn = document.createElement('button');
    btn.className = 'page-btn' + (pg === page ? ' active' : '');
    btn.textContent = label;
    btn.disabled = disabled;
    if (!disabled) btn.addEventListener('click', () => { state.page = pg; loadNews(); });
    ctrl.appendChild(btn);
  };

  addBtn('«', 1, page === 1);
  addBtn('‹', page - 1, page === 1);

  // window of pages
  let start_pg = Math.max(1, page - 2);
  let end_pg   = Math.min(pages, page + 2);
  for (let p = start_pg; p <= end_pg; p++) addBtn(p, p);

  addBtn('›', page + 1, page === pages);
  addBtn('»', pages, page === pages);
}

/* ─────────────────────────────────────────────────────────
   ARTICLE DETAIL MODAL
   ───────────────────────────────────────────────────────── */
async function openArticle(id) {
  const overlay = $('article-modal');
  overlay.classList.add('open');
  $('modal-title').textContent    = 'Memuat…';
  $('modal-content-body').textContent = '';
  $('modal-meta').innerHTML       = '';
  $('modal-link').href            = '#';

  try {
    const a = await API.article(id);
    $('modal-title').textContent = a.title || 'Tanpa Judul';
    $('modal-link').href         = a.url;

    const catBadge = getSubcategoryBadgeInfo(a.category, a.subcategory);
    const expBadge = getExpBadgeInfo(a.exp_category, a.exp_subcategory);
    $('modal-meta').innerHTML = `
      <span>📰 ${escHtml(a.source_media || '—')}</span>
      <span>✍️ ${escHtml(a.author || '—')}</span>
      <span>📅 ${formatDate(a.published_at)}</span>
      <span class="category-badge ${catBadge.class}" title="Sektor PDRB Usaha: ${escHtml(a.category || '—')}">🏬 ${escHtml(catBadge.text)}</span>
      <span class="exp-badge ${expBadge.class}" title="Sektor PDRB Pengeluaran: ${escHtml(a.exp_category || '—')}">💰 ${escHtml(expBadge.text)}</span>
      ${a.confidence != null ? `<span style="font-size:11px;color:var(--text-muted)">🎯 ${Math.round(a.confidence*100)}% confidence</span>` : ''}
    `;

    // Ringkasan Ollama
    const summaryEl = $('modal-summary');
    if (summaryEl) {
      if (a.summary) {
        summaryEl.innerHTML = `
          <div style="background:rgba(16,185,129,0.08);border-left:3px solid var(--emerald);padding:10px 14px;border-radius:0 8px 8px 0;margin-bottom:16px">
            <div style="font-size:10px;font-weight:700;color:var(--emerald);letter-spacing:1px;margin-bottom:4px">✨ RINGKASAN AI</div>
            <div style="font-size:13px;line-height:1.6;color:var(--text-secondary)">${escHtml(a.summary)}</div>
          </div>`;
        summaryEl.style.display = '';
      } else {
        summaryEl.style.display = 'none';
      }
    }

    $('modal-content-body').textContent = a.content || 'Konten tidak tersedia.';

    // Tags
    let tags = [];
    try { tags = JSON.parse(a.tags || '[]'); } catch(e) {}
    const tagsEl = $('modal-tags');
    if (tags.length) {
      tagsEl.innerHTML = `<div class="tags-wrapper">${tags.map(t => `<span class="tag">${escHtml(t)}</span>`).join('')}</div>`;
      tagsEl.style.display = '';
    } else {
      tagsEl.style.display = 'none';
    }
  } catch(e) {
    $('modal-title').textContent = 'Gagal memuat artikel';
  }
}

function closeArticle() {
  $('article-modal').classList.remove('open');
}

/* ─────────────────────────────────────────────────────────
   SCRAPE MODAL
   ───────────────────────────────────────────────────────── */
let scrapeGemini = false;

function openScrapeModal() {
  $('scrape-modal').classList.add('open');
}

function closeScrapeModal() {
  $('scrape-modal').classList.remove('open');
}

function toggleGemini(el) {
  scrapeGemini = !scrapeGemini;
  el.classList.toggle('on', scrapeGemini);
}

async function startScrape() {
  if (state.scraping) return;

  // Collect selected sources
  const checked = document.querySelectorAll('.source-checkbox:checked');
  const slugs = checked.length ? Array.from(checked).map(c => c.value) : null;
  const pages = parseInt($('pages-range').value);

  closeScrapeModal();

  try {
    const res = await API.startScrape({ sources: slugs, use_ai: true, gemini: scrapeGemini, pages });
    showToast(res.message || 'Scraping dimulai', 'success');
    state.scraping = true;
    updateScrapeBtn();
  } catch(e) {
    showToast('Gagal memulai scraping: ' + e.message, 'error');
  }
}

async function checkScrapeStatus() {
  try {
    const res = await API.scrapeStatus();
    const wasRunning = state.scraping;
    state.scraping = res.running;
    updateScrapeBtn();

    // If just finished
    if (wasRunning && !res.running) {
      showToast('✅ Scraping selesai!', 'success');
      loadStats();
      loadNews();
    }
  } catch(e) {}
}

async function checkOllamaStatus() {
  try {
    const res = await API.ollamaStatus();
    const el = $('ollama-status');
    if (!el) return;
    if (res.cloud_mode) {
      el.innerHTML = `<span style="color:#10b981">● Cloud Mode</span> <span style="font-size:10px;color:var(--text-muted)">(Supabase + Gemini)</span>`;
    } else if (res.running && res.model_ready) {
      el.innerHTML = `<span style="color:#10b981">● Ollama Ready</span> <span style="font-size:10px;color:var(--text-muted)">(${res.configured_model})</span>`;
    } else if (res.running && !res.model_ready) {
      el.innerHTML = `<span style="color:#f59e0b">● Ollama Running</span> <span style="font-size:10px;color:var(--text-muted)">model ${res.configured_model} belum di-pull</span>`;
    } else {
      el.innerHTML = `<span style="color:#ef4444">● Ollama Offline</span> <span style="font-size:10px;color:var(--text-muted)">jalankan: ollama serve</span>`;
    }
  } catch(e) {}
}

function updateScrapeBtn() {
  const btn  = $('btn-scrape');
  const dot  = $('scrape-dot');
  if (state.scraping) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner">⏳</span> Sedang Scraping…`;
    dot.classList.add('running');
  } else {
    btn.disabled = false;
    btn.innerHTML = `⚡ Scrape Sekarang`;
    dot.classList.remove('running');
  }
}

/* ─────────────────────────────────────────────────────────
   RANGE INPUT LIVE VALUE
   ───────────────────────────────────────────────────────── */
document.addEventListener('input', e => {
  if (e.target.id === 'pages-range') {
    $('pages-val').textContent = e.target.value;
  }
});

/* ─────────────────────────────────────────────────────────
   TOAST
   ───────────────────────────────────────────────────────── */
function showToast(msg, type = 'success') {
  const container = $('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type === 'error' ? 'error' : ''}`;
  toast.innerHTML = `
    <span style="font-size:16px">${type === 'error' ? '❌' : '✅'}</span>
    <span class="toast-text">${escHtml(msg)}</span>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.25s ease forwards';
    setTimeout(() => toast.remove(), 260);
  }, 3500);
}

/* ─────────────────────────────────────────────────────────
   HELPERS
   ───────────────────────────────────────────────────────── */
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(str) {
  if (!str) return '—';
  try {
    const d = new Date(str);
    if (isNaN(d)) return str;
    return d.toLocaleDateString('id-ID', { day:'numeric', month:'short', year:'numeric' });
  } catch { return str; }
}

function truncateText(str, maxLen = 70) {
  if (!str) return '—';
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 3) + '...';
}

function shortName(name) {
  if (!name) return '—';
  const shorts = {
    'Pemerintah Daerah':     'PemDa',
    'Tribunnews Pohuwato':   'Tribun',
    'Cara Pandang Pohuwato': 'CaraPandang',
    'Beritabaru Pohuwato':   'Beritabaru',
    'Antaranews Pohuwato':   'Antara',
    'Gorontalo Post':        'GoPost',
    'Seputar Pohuwato':      'Seputar',
  };
  return shorts[name] || name;
}

/* Close modals on overlay click */
document.addEventListener('click', e => {
  if (e.target.id === 'article-modal') closeArticle();
  if (e.target.id === 'scrape-modal') closeScrapeModal();
  if (e.target.id === 'feedback-modal') closeFeedbackModal();
  if (e.target.id === 'irrelevant-modal') closeIrrelevantModal();
});

/* ESC to close */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeArticle(); closeScrapeModal(); closeFeedbackModal(); closeIrrelevantModal(); }
});

/* ─────────────────────────────────────────────────────────
   HIDE / VIEW IRRELEVANT FEATURES
   ───────────────────────────────────────────────────────── */

function toggleHideIrrelevant() {
  state.hideIrrelevant = !state.hideIrrelevant;
  const btn = $('btn-hide-irrelevant');
  if (state.hideIrrelevant) {
    btn.classList.add('btn-active-red');
    btn.innerHTML = '\u2705 Tampilkan Tidak Relevan';
  } else {
    btn.classList.remove('btn-active-red');
    btn.innerHTML = '\ud83d\udeab Sembunyikan Tidak Relevan';
  }
  state.page = 1;
  loadNews();
}

function openIrrelevantModal() {
  // Reset cache so it's filled fresh from current page
  state._allIrrelevantArticles = [];
  $('irrelevant-modal').classList.add('open');
  $('irrelevant-modal-list').innerHTML = '<div style="text-align:center;padding:32px;color:var(--text-muted)">Memuat…</div>';
  $('irrelevant-search').value = '';
  $('irrelevant-filter-type').value = '';
  loadIrrelevantArticles();
}

async function loadIrrelevantArticles() {
  try {
    // Fetch all pages of irrelevant articles by filtering by category=Tidak Relevan
    // We fetch directly via category filter
    const [luData, peData] = await Promise.all([
      fetch('/api/news?' + new URLSearchParams({
        category: 'Tidak Relevan',
        per_page: 500,
        page: 1,
        start_date: state.startDate,
        end_date: state.endDate,
      }), { headers: { 'X-Client-ID': getClientId() } }).then(r => r.json()),
      fetch('/api/news?' + new URLSearchParams({
        exp_category: 'Tidak Relevan',
        per_page: 500,
        page: 1,
        start_date: state.startDate,
        end_date: state.endDate,
      }), { headers: { 'X-Client-ID': getClientId() } }).then(r => r.json()),
    ]);

    // Merge and deduplicate by id, tag each with irrelevance type
    const luIds = new Set((luData.articles || []).map(a => a.id));
    const peIds = new Set((peData.articles || []).map(a => a.id));
    const allById = {};
    (luData.articles || []).forEach(a => { allById[a.id] = { ...a, _irrType: 'lu' }; });
    (peData.articles || []).forEach(a => {
      if (allById[a.id]) {
        allById[a.id]._irrType = 'both';
      } else {
        allById[a.id] = { ...a, _irrType: 'pe' };
      }
    });

    state._allIrrelevantArticles = Object.values(allById);
    // Update button count
    const totalIrrEl = $('irrelevant-total-count');
    if (totalIrrEl) totalIrrEl.textContent = state._allIrrelevantArticles.length;

    renderIrrelevantList(state._allIrrelevantArticles);
  } catch (e) {
    $('irrelevant-modal-list').innerHTML = '<div style="color:#ef4444;padding:20px">Gagal memuat data.</div>';
  }
}

function filterIrrelevantList() {
  const q = ($('irrelevant-search').value || '').toLowerCase();
  const type = $('irrelevant-filter-type').value;
  const filtered = state._allIrrelevantArticles.filter(a => {
    const matchQ = !q || (a.title || '').toLowerCase().includes(q);
    const matchType = !type || a._irrType === type;
    return matchQ && matchType;
  });
  renderIrrelevantList(filtered);
}

function renderIrrelevantList(articles) {
  const el = $('irrelevant-modal-list');
  const countEl = $('irrelevant-modal-count');
  if (countEl) countEl.textContent = `${articles.length} berita`;

  if (!articles.length) {
    el.innerHTML = `<div style="text-align:center;padding:32px">
      <div style="font-size:32px;margin-bottom:8px">🎉</div>
      <div style="color:var(--text-muted);font-size:13px">Tidak ada berita tidak relevan ditemukan</div>
    </div>`;
    return;
  }

  const typeLabel = { lu: '🏤 Lapus', pe: '💰 PE', both: '🚨 Keduanya' };
  const typeClass = { lu: 'category-badge uncategorized', pe: 'exp-badge uncategorized', both: 'category-badge uncategorized' };

  el.innerHTML = articles.map(a => `
    <div onclick="closeIrrelevantModal();openArticle(${a.id})" style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);cursor:pointer;transition:background .15s" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">
      <div style="flex:1;min-width:0">
        <div style="font-size:13px;font-weight:500;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:4px">${escHtml(a.title || '—')}</div>
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
          <span class="source-badge" style="font-size:10px">📰 ${escHtml(shortName(a.source_media))}</span>
          <span style="font-size:10px;color:var(--text-muted)">${formatDate(a.published_at)}</span>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0">
        <span class="${typeClass[a._irrType]}" style="font-size:10px;white-space:nowrap">${typeLabel[a._irrType]} Tidak Relevan</span>
        <button onclick="event.stopPropagation();copyArticleUrl('${escHtml(a.url)}', event)" class="btn btn-ghost btn-sm btn-icon" style="font-size:10px;padding:2px 6px" title="Salin link">📋</button>
      </div>
    </div>
  `).join('');
}

function closeIrrelevantModal() {
  $('irrelevant-modal').classList.remove('open');
}

/* Refresh stats button */
$('btn-refresh').addEventListener('click', () => {
  loadStats();
  loadNews();
  showToast('Data diperbarui');
});

function exportExcel() {
  const params = new URLSearchParams();
  if (state.search) params.append('search', state.search);
  if (state.source) params.append('source', state.source);
  if (state.category) params.append('category', state.category);
  if (state.expCategory) params.append('exp_category', state.expCategory);
  if (state.startDate) params.append('start_date', state.startDate);
  if (state.endDate) params.append('end_date', state.endDate);

  showToast('Membuat file Excel...', 'success');
  window.location.href = '/api/export/excel?' + params.toString();
}

/* ───────────────────────────────────────────────────────────
   COPY LINK
   ─────────────────────────────────────────────────────────── */
function copyArticleLink() {
  const link = $('modal-link').href;
  if (!link || link === '#') return;
  navigator.clipboard.writeText(link).then(() => {
    showToast('📋 Link berhasil disalin!', 'success');
  }).catch(() => {
    // fallback
    const ta = document.createElement('textarea');
    ta.value = link;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    showToast('📋 Link berhasil disalin!', 'success');
  });
}

/* ───────────────────────────────────────────────────────────
   FEEDBACK SYSTEM
   ─────────────────────────────────────────────────────────── */

/* Sub-category data for LU */
const LU_SUBCATEGORIES = {
  'Pertanian, Kehutanan & Perikanan':                     ['Tanaman Pangan', 'Hortikultura', 'Perkebunan', 'Peternakan', 'Kehutanan & Penebangan Kayu', 'Perikanan', 'Umum'],
  'Pertambangan & Penggalian':                            ['Minyak, Gas & Panas Bumi', 'Batubara & Lignit', 'Bijih Logam', 'Penggalian Lainnya', 'Umum'],
  'Industri Pengolahan':                                  ['Makanan & Minuman', 'Tekstil & Pakaian', 'Kayu & Rotan', 'Kimia & Farmasi', 'Logam Dasar', 'Mesin & Peralatan', 'Umum'],
  'Pengadaan Listrik & Gas':                              ['Ketenagalistrikan', 'Pengadaan Gas', 'Umum'],
  'Pengadaan Air, Pengelolaan Sampah & Daur Ulang':       ['Pengadaan Air', 'Pengelolaan Sampah', 'Daur Ulang', 'Umum'],
  'Konstruksi':                                           ['Bangunan Gedung', 'Bangunan Sipil', 'Jalan & Jembatan', 'Instalasi', 'Umum'],
  'Perdagangan Besar, Eceran & Reparasi':                 ['Perdagangan Besar', 'Perdagangan Eceran', 'Reparasi Kendaraan', 'Umum'],
  'Transportasi & Pergudangan':                           ['Angkutan Darat', 'Angkutan Laut', 'Angkutan Udara', 'Pergudangan & Penunjang', 'Umum'],
  'Penyediaan Akomodasi & Makan Minum':                   ['Hotel & Penginapan', 'Restoran & Rumah Makan', 'Katering', 'Umum'],
  'Informasi & Komunikasi':                               ['Telekomunikasi', 'Penyiaran & Konten', 'Teknologi Informasi', 'Umum'],
  'Jasa Keuangan & Asuransi':                             ['Perbankan', 'Asuransi & Dana Pensiun', 'Pasar Modal', 'Jasa Keuangan Lainnya', 'Umum'],
  'Real Estate':                                          ['Real Estate', 'Umum'],
  'Jasa Perusahaan':                                      ['Konsultan & Manajemen', 'Jasa Teknis', 'Umum'],
  'Administrasi Pemerintahan, Pertahanan & Sosial Wajib': ['Pemerintah Pusat', 'Pemerintah Daerah', 'Pertahanan & Keamanan', 'Jaminan Sosial', 'Umum'],
  'Jasa Pendidikan':                                      ['Pendidikan Dasar', 'Pendidikan Menengah', 'Pendidikan Tinggi', 'Pendidikan Lainnya', 'Umum'],
  'Jasa Kesehatan & Kegiatan Sosial':                     ['Rumah Sakit & Klinik', 'Puskesmas & Posyandu', 'Farmasi', 'Kegiatan Sosial', 'Umum'],
  'Jasa Lainnya':                                         ['Seni & Hiburan', 'Olahraga & Rekreasi', 'Jasa Perorangan', 'Organisasi Kemasyarakatan', 'Umum'],
  'Tidak Relevan':                                              ['Tidak Relevan'],
};

/* Sub-category data for PE */
const PE_SUBCATEGORIES = {
  'Konsumsi Rumah Tangga': ['Makanan & Minuman', 'Non-Makanan', 'Perumahan & Utilitas', 'Kesehatan RT', 'Pendidikan RT', 'Transportasi & Komunikasi', 'Umum'],
  'Konsumsi LNPRT':       ['Kegiatan Sosial', 'Pendidikan Non-Profit', 'Kesehatan Non-Profit', 'Umum'],
  'Konsumsi Pemerintah':  ['Belanja Pegawai', 'Belanja Barang & Jasa', 'Subsidi & Bantuan', 'Umum'],
  'PMTB':                 ['Bangunan', 'Mesin & Peralatan', 'Kendaraan', 'Peralatan TIK', 'Budidaya Tanaman', 'Umum'],
  'Perubahan Inventori':  ['Perubahan Inventori', 'Umum'],
  'Ekspor':               ['Ekspor Barang', 'Ekspor Jasa', 'Umum'],
  'Impor':                ['Impor Barang', 'Impor Jasa', 'Umum'],
  'Tidak Relevan':              ['Tidak Relevan'],
};

let feedbackArticleId = null;

function copyArticleUrl(url, event) {
  if (event) event.stopPropagation();
  if (!url) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(() => {
      showToast('📋 Link berita berhasil disalin!', 'success');
    }).catch(() => {
      fallbackCopy(url);
    });
  } else {
    fallbackCopy(url);
  }
}

function fallbackCopy(url) {
  const ta = document.createElement('textarea');
  ta.value = url;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  ta.remove();
  showToast('📋 Link berita berhasil disalin!', 'success');
}

async function submitFeedback(articleId, flag, recData = {}) {
  try {
    const res = await fetch(`/api/news/${articleId}/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Client-ID': getClientId()
      },
      body: JSON.stringify({
        flag: flag,
        ...recData
      })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      showToast(`⚠️ ${data.error || 'Gagal mengirim feedback'}`, 'warning');
      return false;
    }

    if (flag === 0) {
      showToast('👍 Feedback Sip (Kategori Benar) tersimpan!', 'success');
    } else {
      showToast('👎 Feedback Ga Sip (Kategori Salah) tersimpan!', 'success');
    }
    loadNews();
    return true;
  } catch (err) {
    console.error('Feedback error:', err);
    showToast('⚠️ Gagal terhubung ke server', 'warning');
    return false;
  }
}

function openFeedbackModal(articleId, title) {
  feedbackArticleId = articleId;
  $('feedback-article-title').textContent = title || `Artikel #${articleId}`;
  $('feedback-modal').classList.add('open');

  // Populate LU sectors
  const luSel = $('fb-lu-sector');
  luSel.innerHTML = '<option value="">— Pilih Sektor —</option>';
  Object.keys(LU_SUBCATEGORIES).forEach(s => {
    const info = PDRB_MAP[s];
    const code = info ? info.code : '—';
    luSel.innerHTML += `<option value="${escHtml(s)}">${code} – ${escHtml(s)}</option>`;
  });
  $('fb-lu-sub').innerHTML = '<option value="">— Pilih sub-kategori —</option>';

  // Populate PE sectors
  const peSel = $('fb-pe-sector');
  peSel.innerHTML = '<option value="">— Pilih Sektor —</option>';
  Object.keys(PE_SUBCATEGORIES).forEach(s => {
    const info = PDRB_EXP_MAP[s];
    const code = info ? info.code : '—';
    peSel.innerHTML += `<option value="${escHtml(s)}">${code} – ${escHtml(s)}</option>`;
  });
  $('fb-pe-sub').innerHTML = '<option value="">— Pilih sub-kategori —</option>';

  // Reset tabs to LU
  switchFeedbackTab('lu');
}

function closeFeedbackModal() {
  $('feedback-modal').classList.remove('open');
  feedbackArticleId = null;
}

function switchFeedbackTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  $(`tab-${tab}`).classList.add('active');
}

function onFbLuSectorChange() {
  const sector = $('fb-lu-sector').value;
  const subSel = $('fb-lu-sub');
  subSel.innerHTML = '<option value="">— Pilih sub-kategori —</option>';
  if (sector && LU_SUBCATEGORIES[sector]) {
    LU_SUBCATEGORIES[sector].forEach(s => {
      subSel.innerHTML += `<option value="${escHtml(s)}">${escHtml(s)}</option>`;
    });
  }
}

function onFbPeSectorChange() {
  const sector = $('fb-pe-sector').value;
  const subSel = $('fb-pe-sub');
  subSel.innerHTML = '<option value="">— Pilih sub-kategori —</option>';
  if (sector && PE_SUBCATEGORIES[sector]) {
    PE_SUBCATEGORIES[sector].forEach(s => {
      subSel.innerHTML += `<option value="${escHtml(s)}">${escHtml(s)}</option>`;
    });
  }
}

async function submitFeedbackCorrection() {
  if (!feedbackArticleId) return;

  const luSector = $('fb-lu-sector').value;
  const luSub    = $('fb-lu-sub').value;
  const peSector = $('fb-pe-sector').value;
  const peSub    = $('fb-pe-sub').value;

  if (!luSector && !peSector) {
    showToast('⚠️ Pilih minimal satu sektor untuk koreksi', 'warning');
    return;
  }

  const recData = {};
  if (luSector) {
    recData.rec_category = luSector;
    recData.rec_subcategory = luSub || 'Umum';
  }
  if (peSector) {
    recData.rec_exp_category = peSector;
    recData.rec_exp_subcategory = peSub || 'Umum';
  }

  const ok = await submitFeedback(feedbackArticleId, 1, recData);
  if (ok) {
    closeFeedbackModal();
  }
}

