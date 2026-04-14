/* ── main.js — Polaris Obfuscator Frontend ──────────────────────────────── */

const $ = id => document.getElementById(id);

// ── Elements ─────────────────────────────────────────────────────────────────
const dropZone     = $('dropZone');
const fileInput    = $('fileInput');
const fileChosen   = $('fileChosen');
const submitBtn    = $('submitBtn');
const uploadError  = $('uploadError');
const uploadCard   = $('uploadCard');
const progressCard = $('progressCard');
const progressTitle= $('progressTitle');
const resultsSection = $('resultsSection');
const resetBtn     = $('resetBtn');

// ── Drag-and-drop ─────────────────────────────────────────────────────────────
['dragenter','dragover'].forEach(evt =>
  dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.add('drag-over'); })
);
['dragleave','drop'].forEach(evt =>
  dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.remove('drag-over'); })
);
dropZone.addEventListener('drop', e => {
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

function setFile(file) {
  const ok = /\.(c|cpp|cc|cxx)$/i.test(file.name);
  if (!ok) { showError('Only .c and .cpp files are accepted.'); return; }
  hideError();
  fileChosen.textContent = `📄 ${file.name}  (${fmtBytes(file.size)})`;
  fileChosen.hidden = false;
  submitBtn.disabled = false;
  submitBtn.dataset.file = file.name;
  // Stash file reference on input so FormData works
  const dt = new DataTransfer();
  dt.items.add(file);
  fileInput.files = dt.files;
}

// ── Passes helper ──────────────────────────────────────────────────────────────
function getPassesString() {
  return [...document.querySelectorAll('.pass-chip input:checked')]
    .map(cb => cb.value).join(',');
}

// ── Upload + poll ──────────────────────────────────────────────────────────────
submitBtn.addEventListener('click', async () => {
  if (!fileInput.files[0]) { showError('Please choose a file first.'); return; }
  const passes = getPassesString();
  if (!passes) { showError('Select at least one obfuscation pass.'); return; }

  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('passes', passes);

  uploadCard.hidden = true;
  progressCard.hidden = false;
  resultsSection.hidden = true;

  try {
    const res = await fetch('/upload', { method: 'POST', body: fd });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.error || `HTTP ${res.status}`);
    }
    const { job_id } = await res.json();
    await pollJob(job_id);
  } catch (err) {
    showError(err.message);
    uploadCard.hidden = false;
    progressCard.hidden = true;
  }
});

// Status → display label map
const STATUS_LABELS = {
  queued:       'Waiting in queue…',
  ai_enhancing: 'Gemini is annotating your source…',
  compiling:    'Polaris is compiling & obfuscating…',
  done:         'Done! Building report…',
  error:        'Pipeline encountered an error.',
};
const STATUS_STEPS = ['queued','ai_enhancing','compiling','done'];

async function pollJob(jobId) {
  while (true) {
    const res  = await fetch(`/status/${jobId}`);
    const data = await res.json();
    const st     = data.status;
    const detail = data.detail || '';

    // Show label + live detail sub-text
    progressTitle.textContent = (STATUS_LABELS[st] || st);
    let detailEl = $('progressDetail');
    if (!detailEl) {
      detailEl = document.createElement('p');
      detailEl.id = 'progressDetail';
      detailEl.style.cssText = 'font-size:0.78rem;color:var(--text-muted);margin-top:0.5rem;font-family:var(--mono);';
      progressCard.querySelector('.progress-steps').before(detailEl);
    }
    detailEl.textContent = detail;

    STATUS_STEPS.forEach((s, i) => {
      const el = $(`step-${s}`);
      if (!el) return;
      const idx = STATUS_STEPS.indexOf(st);
      if (i < idx)        { el.className = 'step done';   }
      else if (i === idx) { el.className = 'step active'; }
      else                { el.className = 'step'; }
    });

    if (st === 'error') {
      // Show error inline without fetching report
      progressCard.hidden = true;
      showError(`Pipeline error: ${detail || 'unknown error'}`);
      uploadCard.hidden = false;
      return;
    }

    if (st === 'done') {
      const rRes = await fetch(`/report/${jobId}`);
      const report = await rRes.json();
      progressCard.hidden = true;
      renderReport(report, jobId);
      return;
    }

    await sleep(1500);
  }
}

// ── Render report ──────────────────────────────────────────────────────────────
function renderReport(report, jobId) {
  resultsSection.hidden = false;

  // Verdict banner
  const banner = $('verdictBanner');
  const verdict = report.verdict;
  banner.className = `verdict-banner ${verdict === 'PASS' ? 'pass' : verdict === 'FAIL' ? 'fail' : 'err'}`;
  $('verdictIcon').textContent = verdict === 'PASS' ? '✅' : verdict === 'FAIL' ? '❌' : '⚠️';
  $('verdictTitle').textContent = verdict === 'PASS'
    ? 'PASS — Semantics Preserved'
    : verdict === 'FAIL' ? 'FAIL — Output Mismatch' : 'ERROR';
  $('verdictDetail').textContent = report.verdict_detail || report.error || '';

  // Metrics table
  const m   = report.metrics || {};
  const pm  = m.plain || {};
  const om  = m.obfuscated || {};
  const rat = m.ratios || {};

  const rows = [
    ['Binary Size',        pm.size_human,    om.size_human,    rat.size,         true],
    ['Instructions',       pm.instructions,  om.instructions,  ratio(pm.instructions, om.instructions), true],
    ['Branch / Call Sites',pm.branches,      om.branches,      ratio(pm.branches, om.branches), true],
    ['Functions (nm)',     pm.functions,     om.functions,     '—',              false],
    ['.text Entropy',      pm.entropy ?? '—',om.entropy ?? '—',
      rat.entropy_delta != null ? `+${rat.entropy_delta}` : '—', false],
    ['Strings Visible',
      pm.strings_visible ? '🟡 Yes' : '🟢 Hidden',
      om.strings_visible ? '🔴 Yes' : '🟢 Hidden',
      '—', false],
  ];

  const tbody = $('metricsTable').querySelector('tbody');
  tbody.innerHTML = rows.map(([label, pv, ov, r, highlight]) => `
    <tr>
      <td>${label}</td>
      <td>${pv}</td>
      <td>${ov}</td>
      <td class="${highlight ? 'ratio-up' : ''}">${r}</td>
    </tr>`).join('');

  $('passesUsedLine').innerHTML =
    `Passes: <span>${report.passes_used || m.passes_used || '—'}</span>`;

  // Download
  $('dlName').textContent = `obfuscated_binary  (${report.original_filename || ''})`;
  $('dlMeta').textContent = om.size_human ? `${om.size_human} · obfuscated ELF` : '';
  $('dlBtn').href = `/download/${jobId}`;

  // Entropy bars
  const maxEnt = 8;
  const pe = pm.entropy || 0, oe = om.entropy || 0;
  $('plainBar').style.width = `${Math.min((pe / maxEnt) * 100, 100)}%`;
  $('obfuBar').style.width  = `${Math.min((oe / maxEnt) * 100, 100)}%`;
  $('entropyVals').textContent = `${pe} → ${oe} bits`;

  // Outputs
  const outMatch = report.outputs?.match;
  const matchBadge = $('outputMatchBadge');
  matchBadge.textContent = outMatch ? 'Outputs Match' : 'Outputs Differ';
  matchBadge.className   = `output-match-badge ${outMatch ? 'badge-match' : 'badge-diff'}`;
  $('plainOutput').textContent = report.outputs?.plain  || '(no output)';
  $('obfuOutput').textContent  = report.outputs?.obfuscated || '(no output)';

  // Source code tabs
  $('origCode').textContent = report.ai?.original_source || '(unavailable)';
  $('aiCode').textContent   = report.ai?.enhanced_source || '(unavailable)';
}

// ── Tabs ───────────────────────────────────────────────────────────────────────
document.addEventListener('click', e => {
  const tab = e.target.closest('.tab[data-pane]');
  if (!tab) return;
  const bar  = tab.closest('.tab-bar');
  const card = tab.closest('.card');
  bar.querySelectorAll('.tab').forEach(t => {
    t.classList.remove('active'); t.setAttribute('aria-selected','false');
  });
  card.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  tab.classList.add('active'); tab.setAttribute('aria-selected','true');
  const pane = document.getElementById(tab.dataset.pane);
  if (pane) pane.classList.add('active');
});

// ── Reset ──────────────────────────────────────────────────────────────────────
resetBtn.addEventListener('click', () => {
  resultsSection.hidden = true;
  progressCard.hidden   = true;
  uploadCard.hidden     = false;
  fileInput.value       = '';
  fileChosen.hidden     = true;
  submitBtn.disabled    = true;
  hideError();
});

// ── Helpers ────────────────────────────────────────────────────────────────────
function showError(msg) {
  uploadError.textContent = msg;
  uploadError.hidden = false;
}
function hideError() {
  uploadError.hidden = true;
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function fmtBytes(n) {
  if (n < 1024)       return `${n} B`;
  if (n < 1048576)    return `${(n/1024).toFixed(1)} KB`;
  return `${(n/1048576).toFixed(1)} MB`;
}
function ratio(a, b) {
  if (!a || !b) return '—';
  return `${(b/a).toFixed(2)}×`;
}