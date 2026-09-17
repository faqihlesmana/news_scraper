/* ══════════════════════════════════════════════════════════
   THEME SYSTEM — theme.js
   Manages 6 themes × 2 modes with localStorage persistence
   ══════════════════════════════════════════════════════════ */

const THEMES = [
  {
    id: 'starry',
    label: '🌌 Starry',
    dots: ['#6366f1', '#818cf8', '#fbbf24'],
    bg: '#e8ebff',
    color: '#1e1b4b'
  },
  {
    id: 'note',
    label: '📓 Note',
    dots: ['#7c5c2e', '#c97c2a', '#5a7a9a'],
    bg: '#f5edd8',
    color: '#2c1d0a'
  },
  {
    id: 'classic',
    label: '🏛️ Classic',
    dots: ['#1d4ed8', '#0ea5e9', '#d97706'],
    bg: '#f4f7fb',
    color: '#0f172a'
  },
  {
    id: 'cyber',
    label: '⚡ Cyber',
    dots: ['#00b87a', '#00ff9d', '#ff2d9b'],
    bg: '#e8fdf5',
    color: '#062119'
  },
  {
    id: 'sakura',
    label: '🌸 Sakura',
    dots: ['#e0457a', '#f06292', '#9c6fde'],
    bg: '#fde8ed',
    color: '#3d0c1e'
  },
  {
    id: 'ocean',
    label: '🌊 Ocean',
    dots: ['#0891b2', '#22d3ee', '#6366f1'],
    bg: '#e0f5fc',
    color: '#082f49'
  }
];

/* ── State ── */
let currentTheme = localStorage.getItem('app-theme') || 'starry';
let currentMode  = localStorage.getItem('app-mode')  || 'light';

/* ── Apply to <html> element ── */
function applyTheme(theme, mode) {
  const html = document.documentElement;
  html.setAttribute('data-theme', theme);
  html.setAttribute('data-mode', mode);
  document.body.style.background = '';  // let CSS vars take over
  localStorage.setItem('app-theme', theme);
  localStorage.setItem('app-mode', mode);
  currentTheme = theme;
  currentMode  = mode;
  updatePanel();
  // Notify other scripts (e.g. dashboard.js charts) about the change
  document.dispatchEvent(new CustomEvent('themechange', { detail: { theme, mode } }));
}

/* ── Build Theme Picker HTML ── */
function buildThemePicker() {
  // Wrapper (relative parent)
  const wrapper = document.createElement('div');
  wrapper.style.position = 'relative';

  // Button
  const btn = document.createElement('button');
  btn.className = 'theme-picker-btn';
  btn.id = 'theme-picker-btn';
  btn.title = 'Ganti Tema';
  btn.textContent = '🎨';
  btn.addEventListener('click', togglePanel);

  // Panel
  const panel = document.createElement('div');
  panel.className = 'theme-panel';
  panel.id = 'theme-panel';

  // Title
  const title = document.createElement('div');
  title.className = 'theme-panel-title';
  title.textContent = '🎨 Pilih Tema';
  panel.appendChild(title);

  // Theme grid
  const grid = document.createElement('div');
  grid.className = 'theme-grid';
  grid.id = 'theme-grid';

  THEMES.forEach(t => {
    const swatch = document.createElement('div');
    swatch.className = 'theme-swatch';
    swatch.dataset.themeId = t.id;
    swatch.style.background = t.bg;
    swatch.style.color = t.color;
    swatch.title = t.label;

    const dotsEl = document.createElement('div');
    dotsEl.className = 'swatch-dots';
    t.dots.forEach(c => {
      const d = document.createElement('div');
      d.className = 'swatch-dot';
      d.style.background = c;
      dotsEl.appendChild(d);
    });

    const lbl = document.createElement('div');
    lbl.className = 'swatch-label';
    lbl.textContent = t.label;

    swatch.appendChild(dotsEl);
    swatch.appendChild(lbl);
    swatch.addEventListener('click', () => {
      applyTheme(t.id, currentMode);
    });
    grid.appendChild(swatch);
  });
  panel.appendChild(grid);

  // Mode toggle row
  const modeRow = document.createElement('div');
  modeRow.className = 'mode-toggle-row';

  const modeLbl = document.createElement('div');
  modeLbl.className = 'mode-toggle-label';
  modeLbl.id = 'mode-label';
  modeLbl.textContent = '☀️ Mode Terang';

  const track = document.createElement('div');
  track.className = 'mode-toggle-track';
  track.id = 'mode-track';
  track.addEventListener('click', () => {
    const newMode = currentMode === 'light' ? 'dark' : 'light';
    applyTheme(currentTheme, newMode);
  });

  const thumb = document.createElement('div');
  thumb.className = 'mode-toggle-thumb';
  thumb.id = 'mode-thumb';
  thumb.textContent = '☀️';
  track.appendChild(thumb);

  modeRow.appendChild(modeLbl);
  modeRow.appendChild(track);
  panel.appendChild(modeRow);

  wrapper.appendChild(btn);
  wrapper.appendChild(panel);
  return wrapper;
}

/* ── Update panel UI state ── */
function updatePanel() {
  // Swatches active state
  document.querySelectorAll('.theme-swatch').forEach(sw => {
    sw.classList.toggle('active', sw.dataset.themeId === currentTheme);
  });

  // Mode toggle
  const track = document.getElementById('mode-track');
  const thumb = document.getElementById('mode-thumb');
  const lbl   = document.getElementById('mode-label');
  if (!track) return;

  if (currentMode === 'dark') {
    track.classList.add('dark');
    thumb.textContent = '🌙';
    lbl.textContent   = '🌙 Mode Gelap';
  } else {
    track.classList.remove('dark');
    thumb.textContent = '☀️';
    lbl.textContent   = '☀️ Mode Terang';
  }
}

/* ── Toggle panel open/close ── */
function togglePanel(e) {
  e.stopPropagation();
  const panel = document.getElementById('theme-panel');
  panel.classList.toggle('open');
}

/* ── Close panel when clicking outside ── */
document.addEventListener('click', (e) => {
  const panel = document.getElementById('theme-panel');
  const btn   = document.getElementById('theme-picker-btn');
  if (panel && !panel.contains(e.target) && e.target !== btn) {
    panel.classList.remove('open');
  }
});

/* ── Inject into navbar ── */
function initThemePicker() {
  const navActions = document.querySelector('.nav-actions');
  if (!navActions) return;

  const picker = buildThemePicker();
  // Insert before first child of nav-actions
  navActions.insertBefore(picker, navActions.firstChild);

  // Apply saved theme immediately
  applyTheme(currentTheme, currentMode);
}

/* ── Run on DOM ready ── */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initThemePicker);
} else {
  initThemePicker();
}
