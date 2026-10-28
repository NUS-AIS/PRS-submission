// Member D: uses B's prediction lifecycle and the existing shared CT viewer.
(() => {
  'use strict';
  const element = (tag, text) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    return node;
  };
  const panel = element('section');
  panel.className = 'explanation-controls';
  panel.setAttribute('aria-label', 'Explanation controls');
  const enabledLabel = element('label', ' Compute Grad-CAM on next prediction');
  const enabled = element('input');
  enabled.type = 'checkbox';
  enabled.id = 'compute-explanation';
  enabled.checked = true;
  enabledLabel.prepend(enabled);
  const opacityLabel = element('label', 'Heatmap opacity ');
  const amount = element('output', '55%');
  const opacity = element('input');
  opacity.id = 'explanation-opacity';
  opacity.type = 'range';
  opacity.min = '0';
  opacity.max = '1';
  opacity.step = '.05';
  opacity.value = '.55';
  opacityLabel.htmlFor = opacity.id;
  opacityLabel.append(amount);
  const status = element('p', 'Run inference to generate an explanation.');
  status.setAttribute('aria-live', 'polite');
  const downloads = element('div');
  const report = element('button', 'Download explanation JSON');
  const image = element('button', 'Download selected PNG');
  const bundle = element('button', 'Download explanation ZIP');
  downloads.append(report, image, bundle);
  panel.append(enabledLabel, opacityLabel, opacity, status, downloads);
  const gallery = element('div');
  gallery.className = 'explanation-gallery';
  gallery.setAttribute('aria-label', 'Sampled position previews');
  panel.append(gallery);
  $('scan-view').after(panel);
  const sliceRequest = new ExplanationRequest();
  const downloadRequest = new ExplanationRequest();
  let displayedURL = null;
  let active = null;
  let generation = 0;
  let downloading = false;

  function controls() {
    opacity.disabled = !active?.has_overlay;
    report.disabled = image.disabled = bundle.disabled = !active || downloading;
  }
  function clear() {
    generation++;
    sliceRequest.cancel();
    downloadRequest.cancel();
    if (displayedURL) { URL.revokeObjectURL(displayedURL); displayedURL = null; }
    active = null;
    gallery.replaceChildren();
    downloading = false;
    status.textContent = 'Run inference to generate an explanation.';
    controls();
  }
  document.addEventListener('pulmo:invalidate', clear);
  document.addEventListener('pulmo:prediction', event => {
    active = {...event.detail, token: currentCase.token};
    queueMicrotask(() => { if (active) refreshGallery(); });
    const state = active.explanation_status;
    status.textContent = state === 'zero_signal'
      ? 'No positive Grad-CAM signal. This does not mean no disease.'
      : active.has_overlay
        ? 'Predicted-class attention; not a lesion boundary.'
        : 'Explanation was not requested. Enable it and rerun to obtain a heatmap.';
    const diagnostic = active.explanation_diagnostics;
    if (diagnostic?.gradcam_ms != null) {
      status.textContent += ` Grad-CAM: ${diagnostic.gradcam_ms.toFixed(1)} ms · target: ${active.predicted_class}.`;
    }
    controls();
  });
  enabled.addEventListener('change', () => {
    if (busy) return;
    invalidate();
  });

  function refreshGallery() {
    gallery.replaceChildren();
    if (!active) return;
    const count = currentCase.slices || 16;
    for (let index = 0; index < count; index++) {
      const button = element('button');
      button.type = 'button';
      button.setAttribute('aria-label', `Show sampled position ${index + 1}`);
      button.setAttribute('aria-pressed', String(index === Number($('slice').value)));
      const thumb = element('img');
      thumb.alt = `Sampled position ${index + 1}`;
      thumb.loading = 'lazy';
      const params = new URLSearchParams({run: active.run_id, index,
        overlay: String(active.has_overlay && $('overlay').checked), opacity: opacity.value});
      thumb.src = `/api/cases/${active.token}/explanation/image?${params}`;
      thumb.onerror = () => { thumb.hidden = true; button.title = 'Preview unavailable. Rerun if this case expired.'; };
      button.append(thumb, element('span', String(index + 1)));
      button.onclick = () => {
        $('slice').value = index;
        $('slice').dispatchEvent(new Event('input', {bubbles: true}));
      };
      gallery.append(button);
    }
  }
  function highlightPosition() {
    [...gallery.children].forEach((button, index) =>
      button.setAttribute('aria-pressed', String(index === Number($('slice').value))));
  }
  const originalShowSlice = showSlice;
  window.showSlice = async () => {
    sliceRequest.cancel();
    highlightPosition();
    if (!currentCase || !active || !prediction || active.run_id !== prediction.run_id) {
      $('scan').hidden = false;
      originalShowSlice();
      return;
    }
    const version = generation;
    const index = $('slice').value;
    $('slice-label').textContent = `Slice ${Number(index) + 1} / ${currentCase.slices || 16}`;
    const params = new URLSearchParams({run: active.run_id, index,
      overlay: String($('overlay').checked), opacity: opacity.value});
    $('scan').hidden = true;
    try {
      const blob = await sliceRequest.fetch(`/api/cases/${active.token}/explanation/image?${params}`);
      if (!blob || version !== generation) return;
      if (displayedURL) URL.revokeObjectURL(displayedURL);
      displayedURL = URL.createObjectURL(blob);
      $('scan').src = displayedURL;
      $('scan').hidden = false;
    } catch (error) {
      if (version === generation) status.textContent = `${error.message} Change position or rerun to retry.`;
    }
  };
  // app.js registered function references before this module was loaded.
  $('slice').oninput = () => showSlice();
  $('overlay').onchange = () => { showSlice(); refreshGallery(); };
  opacity.onchange = refreshGallery;
  opacity.oninput = () => {
    amount.textContent = `${Math.round(Number(opacity.value) * 100)}%`;
    showSlice();
  };
  const originalBusy = setBusy;
  window.setBusy = (value, message = '') => {
    originalBusy(value, message);
    enabled.disabled = value;
  };

  async function download(kind) {
    if (!active || downloading) return;
    const request = active, version = generation;
    const params = new URLSearchParams({
      run: request.run_id, index: $('slice').value,
      opacity: opacity.value, overlay: String($('overlay').checked),
    });
    downloading = true;
    controls();
    try {
      const blob = await downloadRequest.fetch(`/api/cases/${request.token}/explanation/${kind}?${params}`);
      if (!blob) return;
      // A case/input change while fetching must not download an obsolete report.
      if (version !== generation || active !== request) return;
      const url = URL.createObjectURL(blob);
      const link = element('a');
      link.href = url;
      link.download = `pulmo-${request.run_id}.${{report: 'json', image: 'png', bundle: 'zip'}[kind]}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      status.textContent = 'Download ready. Report and image refer to this prediction.';
    } catch (error) {
      if (version === generation) status.textContent = error.message;
    } finally {
      if (version === generation) { downloading = false; controls(); }
    }
  }
  report.onclick = () => download('report');
  image.onclick = () => download('image');
  bundle.onclick = () => download('bundle');
  controls();
})();
