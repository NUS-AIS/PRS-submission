// CT viewer: upload stages, retry, scan-quality panel, slice errors and keyboard browsing.
// Load after app.js. Uses its globals $, busy, currentCase, notice, setBusy, loaded, invalidate and
// showSlice (loaded/showSlice are wrapped). Exposes window.CTViewer for the other page modules.
(() => {
  'use strict';
  const LIMIT = 200 * 1024 * 1024;
  const STAGES = [['upload', 'Upload'], ['process', 'Preprocess'], ['ready', 'Ready']];
  const panel = document.querySelector('#inference .viewer');
  if (!panel || typeof loaded !== 'function') return;

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  const mb = n => (n / 1024 / 1024).toFixed(1) + ' MB';
  const join = (xs, digits) => xs.map(x => digits === undefined ? x : Number(x).toFixed(digits)).join(' × ');

  // ---- DOM: stage strip + status under the title, error box on the slice, quality panel under the caption.
  const strip = el('ol', 'ct-stages');
  strip.setAttribute('aria-label', 'CT loading stages');
  strip.append(...STAGES.map(([id, label]) => { const li = el('li', '', label); li.dataset.stage = id; return li; }));
  const status = el('p', 'ct-status');
  status.setAttribute('aria-live', 'polite');
  const retry = el('button', 'ct-retry', 'Retry upload');
  const another = el('button', '', 'Choose another file');
  const actions = el('div', 'ct-actions');
  actions.append(retry, another);
  const box = el('div', 'ct-loading');
  box.hidden = true;
  box.append(strip, status, actions);
  panel.querySelector('.panel-title').after(box);

  const view = $('scan-view'), scan = $('scan'), slider = $('slice');
  view.tabIndex = 0;
  view.setAttribute('aria-label', 'CT slices. Arrow keys browse, Page Up/Down jump 4, Home/End go to the ends.');
  const sliceError = el('div', 'ct-slice-error');
  sliceError.setAttribute('role', 'alert');
  sliceError.hidden = true;
  const sliceText = el('span'), sliceRetry = el('button', '', 'Reload slice');
  sliceError.append(sliceText, sliceRetry);
  scan.after(sliceError);
  view.append(el('small', 'ct-keys', '←/→ slice · PgUp/PgDn ±4 · Home/End'));

  const quality = el('details', 'ct-quality');
  quality.hidden = true;
  const summary = el('summary', '', 'Scan quality '), badge = el('span', 'ct-badge');
  summary.append(badge);
  const facts = el('dl'), warnings = el('ul', 'ct-warnings'), note = el('p', 'hint');
  quality.append(summary, facts, warnings, note);
  panel.querySelector('.viewer-caption').after(quality);

  // ---- Stage strip. Upload shows real bytes sent; preprocessing has no measurable progress, so no percentage.
  let pending = null, stage = null, current = null;

  function setStage(name, message, failed = false) {
    stage = name;
    box.hidden = !name;
    box.classList.toggle('failed', failed);
    const at = STAGES.findIndex(([id]) => id === name);
    strip.querySelectorAll('li').forEach((li, i) => {
      li.className = i < at || (name === 'ready' && i === at) ? 'done' : i === at ? (failed ? 'failed' : 'active') : '';
    });
    status.setAttribute('role', failed ? 'alert' : 'status');
    status.textContent = message || '';
    actions.hidden = !failed;
  }

  function send(file) {
    return new Promise((resolve, reject) => {
      const x = new XMLHttpRequest();
      x.open('POST', '/api/upload?filename=' + encodeURIComponent(file.name));
      x.setRequestHeader('Content-Type', 'application/octet-stream');
      x.responseType = 'json';
      x.upload.onprogress = e => {
        if (e.lengthComputable) setStage('upload', `Sending ${file.name}: ${mb(e.loaded)} of ${mb(e.total)}`);
      };
      x.upload.onload = () => setStage('process', 'Validating the volume, then lung window, crop and 16 axial samples…');
      x.onload = () => {
        if (x.status === 200) return resolve(x.response);
        const body = x.response && typeof x.response.detail === 'string' ? x.response : { detail: `Server returned HTTP ${x.status}.` };
        reject({ ...body, status: x.status });
      };
      x.onerror = () => reject({ detail: 'Network error: the server could not be reached.', status: 0 });
      x.send(file);
    });
  }

  function fail(err, file) {
    setStage(stage || 'upload', err.detail, true);
    // Validation rejections repeat on resend; only network/server failures are worth retrying as-is.
    pending = file && (err.status === 0 || err.status >= 500) ? file : null;
    retry.hidden = !pending;
    $('case-label').textContent = 'No CT loaded';
  }

  async function upload(file) {
    if (!file || busy) return;
    notice();
    const problem = !/\.nii(\.gz)?$/i.test(file.name) ? 'Please choose a .nii or .nii.gz CT volume.'
      : file.size > LIMIT ? 'Upload limit is 200 MB.' : file.size === 0 ? 'The selected file is empty.' : '';
    stage = 'upload';
    if (problem) return fail({ detail: problem });
    invalidate();
    currentCase = null;
    clear();
    $('case-label').textContent = `Uploading ${file.name}…`;
    $('scan-view').hidden = true;
    $('scan-empty').hidden = false;
    setStage('upload', `Sending ${file.name} (${mb(file.size)})…`);
    setBusy(true, 'Uploading and preprocessing CT…');
    try {
      loaded(await send(file));
      setBusy(false, 'CT ready. Choose a model and run inference.');
    } catch (err) {
      setBusy(false, 'Upload failed.');
      fail(err, file);
    }
  }

  retry.onclick = () => upload(pending);
  another.onclick = () => $('file').click();
  $('file').onchange = e => { upload(e.target.files[0]); e.target.value = ''; };
  const drop = $('scan-empty');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); upload(e.dataTransfer.files[0]); };
  $('load-demo').addEventListener('click', () => { if ($('demo').value) setStage(null); });

  // ---- Quality panel. Demo stacks were preprocessed offline, so the server sends quality: null.
  function row(label, value) { facts.append(el('dt', '', label), el('dd', '', value)); }

  function clear() {
    quality.hidden = true;
    facts.replaceChildren();
    warnings.replaceChildren();
    current = null;
  }

  function render(c) {
    clear();
    current = c;
    const q = c.quality;
    quality.hidden = false;
    row('Source', c.source || 'Unknown');
    if (!q) {
      badge.textContent = 'offline';
      badge.className = 'ct-badge';
      note.textContent = 'Preprocessed offline with the training pipeline; the source volume and its metadata are not shipped with demo cases.';
      quality.open = false;
      return;
    }
    const lo = q.sampled_slices[0], hi = q.sampled_slices[q.sampled_slices.length - 1];
    row('Original shape', join(q.original_shape) + ' voxels');
    row('Voxel spacing', join(q.original_spacing_mm, 2) + ' mm');
    row('Orientation', `${q.orientation} → RAS`);
    row('Intensity range', `${q.intensity_range_hu[0]} to ${q.intensity_range_hu[1]} HU`);
    row('Pipeline', `${q.pipeline} · window ${q.window_hu[0]} to ${q.window_hu[1]} HU`);
    row('Lung crop', `x ${q.crop.x0}, y ${q.crop.y0}, ${q.crop.side} px square`);
    row('Axial samples', `${q.samples} of ${q.ras_shape[2]} slices (RAS z ${lo}–${hi})`);
    row('Model input', join(q.output_shape) + ' · uint8');
    warnings.replaceChildren(...q.warnings.map(w => el('li', '', w.detail)));
    badge.textContent = q.warnings.length ? `${q.warnings.length} warning${q.warnings.length > 1 ? 's' : ''}` : 'checks passed';
    badge.className = 'ct-badge' + (q.warnings.length ? ' warn' : ' ok');
    note.textContent = q.hu_check;
    quality.open = q.warnings.length > 0;
  }

  // ---- Slices: label with the source-file slice, explain failed loads, keyboard browsing.
  function label() {
    const q = current?.quality, i = Number(slider.value);
    if (q) $('slice-label').textContent = `Slice ${i + 1} / ${q.samples} · source z ${q.original_slices[i]}`;
  }

  const appLoaded = loaded, appShow = showSlice;
  loaded = c => { appLoaded(c); render(c); setStage('ready', `${c.name} is ready.`); label(); };
  showSlice = () => { sliceError.hidden = true; appShow(); label(); };
  slider.addEventListener('input', () => { sliceError.hidden = true; label(); });

  scan.addEventListener('load', () => { sliceError.hidden = true; scan.classList.remove('ct-broken'); });
  scan.addEventListener('error', async () => {
    if (!currentCase || !scan.getAttribute('src')) return;
    const src = scan.src;
    sliceText.textContent = `Slice ${Number(slider.value) + 1} could not be loaded.`;
    sliceError.hidden = false;
    scan.classList.add('ct-broken');
    try {
      const body = await (await fetch(src)).json();
      if (scan.src === src && typeof body.detail === 'string') sliceText.textContent += ' ' + body.detail;
    } catch { /* keep the generic message */ }
  });
  sliceRetry.onclick = () => { if (currentCase) scan.src = scan.src.replace(/&retry=\d+$/, '') + '&retry=' + Date.now(); };

  view.addEventListener('keydown', e => {
    if (e.target === slider || !currentCase) return;
    const i = Number(slider.value), last = Number(slider.max);
    const next = { ArrowLeft: i - 1, ArrowDown: i - 1, ArrowRight: i + 1, ArrowUp: i + 1,
                   PageDown: i - 4, PageUp: i + 4, Home: 0, End: last }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    slider.value = Math.max(0, Math.min(last, next));
    slider.dispatchEvent(new Event('input'));
  });

  window.CTViewer = { upload, render, clear, setStage, get current() { return current; } };
})();
