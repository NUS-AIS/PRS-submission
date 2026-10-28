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
  $('scan-view').after(panel);
  let active = null;
  let generation = 0;
  let downloading = false;

  function controls() {
    opacity.disabled = !active?.has_overlay;
    report.disabled = image.disabled = bundle.disabled = !active || downloading;
  }
  function clear() {
    generation++;
    active = null;
    downloading = false;
    status.textContent = 'Run inference to generate an explanation.';
    controls();
  }
  document.addEventListener('pulmo:invalidate', clear);
  document.addEventListener('pulmo:prediction', event => {
    active = {...event.detail, token: currentCase.token};
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

  const originalShowSlice = showSlice;
  window.showSlice = () => {
    originalShowSlice();
    if (!currentCase || !active || !prediction || active.run_id !== prediction.run_id) return;
    const url = new URL($('scan').src, location.href);
    url.searchParams.set('opacity', opacity.value);
    $('scan').src = url.toString();
  };
  // app.js registered function references before this module was loaded.
  $('slice').oninput = () => showSlice();
  $('overlay').onchange = () => showSlice();
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
      const response = await fetch(`/api/cases/${request.token}/explanation/${kind}?${params}`);
      if (!response.ok) {
        const error = await response.json();
        throw Error(error.detail || 'Download failed.');
      }
      const blob = await response.blob();
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
