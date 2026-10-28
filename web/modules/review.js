// Member D: cached explanation review; never invokes the prediction endpoint.
(() => {
  'use strict';
  const {parsePositions, metric, rankedRows, query} = PulmoReviewState;
  const node = (tag, text, className) => {
    const result = document.createElement(tag);
    if (text) result.textContent = text;
    if (className) result.className = className;
    return result;
  };
  const section = node('section', '', 'panel review-panel');
  section.setAttribute('aria-label', 'Explanation review');
  section.append(node('h2', 'Explanation Review'));
  section.append(node('p', 'Compare sampled attention, export a complete review, or verify a saved archive.', 'hint'));
  const form = node('div', '', 'review-options');
  const positions = node('input');
  positions.id = 'review-positions';
  positions.placeholder = 'All positions, or e.g. 1,4,8,16';
  positions.maxLength = 512;
  const positionsLabel = node('label', 'Positions to review');
  positionsLabel.htmlFor = positions.id;
  const threshold = node('input');
  threshold.id = 'review-threshold';
  threshold.type = 'number';
  threshold.min = '0';
  threshold.max = '1';
  threshold.step = '.05';
  threshold.value = '.5';
  const thresholdLabel = node('label', 'Attention display threshold');
  thresholdLabel.htmlFor = threshold.id;
  const sort = node('select');
  sort.id = 'review-sort';
  const sortLabel = node('label', 'Statistics order');
  sortLabel.htmlFor = sort.id;
  for (const [value, label] of [['position', 'Sampled position'], ['mass', 'Attention mass']]) {
    const option = node('option', label);
    option.value = value;
    sort.append(option);
  }
  const include = node('input');
  include.type = 'checkbox';
  include.id = 'review-clinical';
  const includeLabel = node('label', ' Include clinical inputs in the exported archive');
  includeLabel.prepend(include);
  form.append(positionsLabel, positions, thresholdLabel, threshold, sortLabel, sort);
  const actions = node('div', '', 'review-actions');
  const refresh = node('button', 'Refresh attention statistics');
  const csv = node('button', 'Export statistics CSV');
  const archive = node('button', 'Export full review ZIP');
  actions.append(refresh, csv, archive);
  const status = node('p', 'Run inference to review its attention.', 'hint');
  status.setAttribute('aria-live', 'polite');
  const summary = node('p', '', 'review-summary');
  const tableWrap = node('div', '', 'table-wrap');
  const table = node('table');
  const caption = node('caption', 'Attention in cropped model-input coordinates');
  const head = node('thead');
  const headerRow = node('tr');
  for (const label of ['Position', 'Status', 'Mean', 'Maximum', 'Above threshold', 'Mass share', 'Entropy']) {
    const cell = node('th', label);
    cell.scope = 'col';
    headerRow.append(cell);
  }
  head.append(headerRow);
  const body = node('tbody');
  table.append(caption, head, body);
  tableWrap.append(table);
  section.append(form, includeLabel, actions, status, summary, tableWrap);
  section.append(node('p', 'Attention is not lesion area or diagnostic confidence. The threshold only changes descriptive statistics. Exports contain CT images; handle them as research data.', 'hint'));
  const verifyHeading = node('h3', 'Verify a saved review');
  const file = node('input');
  file.type = 'file';
  file.accept = '.zip';
  file.id = 'review-verify-file';
  const fileLabel = node('label', 'Choose a full review ZIP');
  fileLabel.htmlFor = file.id;
  const verify = node('button', 'Verify archive integrity');
  verify.disabled = true;
  const verifyStatus = node('p', 'The archive is checked locally by this server; no files are extracted.', 'hint');
  verifyStatus.setAttribute('aria-live', 'polite');
  section.append(verifyHeading, fileLabel, file, verify, verifyStatus);
  document.querySelector('#inference .inference-grid').after(section);

  let active = null;
  let report = null;
  let generation = 0;
  let loading = false;
  let verifying = false;
  let verifyController = null;
  let verifyVersion = 0;
  const request = new ExplanationRequest();
  const download = new ExplanationRequest();
  function controls() {
    for (const button of [refresh, csv, archive]) button.disabled = !active || loading;
    section.setAttribute('aria-busy', String(loading));
  }
  function reset(message) {
    generation++;
    request.cancel();
    download.cancel();
    report = null;
    loading = false;
    body.replaceChildren();
    summary.textContent = '';
    status.textContent = message;
    controls();
  }
  function selection() {
    return parsePositions(positions.value, currentCase?.slices || 16);
  }
  function parameters() {
    if (threshold.value.trim() === '') throw new Error('Enter an attention threshold.');
    return query(active, selection(), Number(threshold.value));
  }
  function render() {
    body.replaceChildren();
    if (!report) return;
    const attention = report.attention;
    summary.textContent = `${attention.selected_positions.length} / ${attention.sampled_positions} positions · ${attention.status} · threshold ${attention.threshold}`;
    for (const row of rankedRows(attention.rows, sort.value)) {
      const tr = node('tr');
      const positionCell = node('td');
      const jump = node('button', String(row.position), 'review-jump');
      jump.setAttribute('aria-label', `View review position ${row.position}`);
      jump.onclick = () => {
        $('slice').value = row.position - 1;
        $('slice').dispatchEvent(new Event('input', {bubbles: true}));
        $('scan-view').scrollIntoView({behavior: 'smooth', block: 'center'});
      };
      positionCell.append(jump);
      tr.append(positionCell, node('td', row.status));
      for (const [key, percent] of [['mean', false], ['maximum', false], ['above_threshold_fraction', true], ['selected_mass_fraction', true], ['entropy', false]]) {
        tr.append(node('td', metric(row[key], percent)));
      }
      body.append(tr);
    }
  }
  async function refreshStatistics() {
    if (!active || loading) return;
    const current = active, version = generation;
    try {
      const params = parameters();
      loading = true;
      controls();
      status.textContent = 'Calculating cached attention statistics…';
      const blob = await request.fetch(`/api/cases/${current.token}/explanation/summary?${params}`);
      if (!blob) return;
      const result = JSON.parse(await blob.text());
      if (version !== generation || current !== active) return;
      report = result;
      render();
      status.textContent = 'Statistics ready. No new inference was performed.';
    } catch (error) {
      if (version === generation) status.textContent = error.message;
    } finally {
      if (version === generation) { loading = false; controls(); }
    }
  }
  async function exportReview(kind) {
    if (!active || loading) return;
    const current = active, version = generation;
    try {
      const params = parameters();
      params.set('include_clinical', String(include.checked));
      params.set('opacity', document.getElementById('explanation-opacity')?.value || '.55');
      loading = true;
      controls();
      status.textContent = 'Building selected-position report…';
      const blob = await download.fetch(`/api/cases/${current.token}/explanation/${kind}?${params}`);
      if (!blob || version !== generation || current !== active) return;
      const url = URL.createObjectURL(blob);
      const anchor = node('a');
      anchor.href = url;
      anchor.download = `pulmo-review-${current.run_id}.${kind === 'statistics' ? 'csv' : 'zip'}`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      status.textContent = kind === 'review' ? 'Review downloaded. Extract it and open index.html to read offline.' : 'Statistics downloaded.';
    } catch (error) {
      if (version === generation) status.textContent = error.message;
    } finally {
      if (version === generation) { loading = false; controls(); }
    }
  }
  document.addEventListener('pulmo:invalidate', () => {
    active = null;
    reset('Prediction changed. Run inference to review its attention.');
  });
  document.addEventListener('pulmo:prediction', event => {
    active = {...event.detail, token: currentCase.token};
    reset('Prediction ready. Refresh statistics or export a review.');
  });
  for (const input of [positions, threshold, include]) {
    input.addEventListener('change', () => reset('Review options changed. Refresh statistics when ready.'));
  }
  sort.onchange = render;
  refresh.onclick = refreshStatistics;
  csv.onclick = () => exportReview('statistics');
  archive.onclick = () => exportReview('review');
  file.onchange = () => {
    verifyVersion++;
    verifyController?.abort();
    verifying = false;
    verify.disabled = !file.files.length;
    verifyStatus.textContent = 'Ready to verify selected archive.';
  };
  verify.onclick = async () => {
    const selected = file.files[0];
    if (!selected || verifying) return;
    if (selected.size > 64 * 1024 * 1024) {
      verifyStatus.textContent = 'Select a ZIP no larger than 64 MB.';
      return;
    }
    const version = verifyVersion;
    verifying = true;
    verify.disabled = true;
    verifyController = new AbortController();
    verifyStatus.textContent = 'Checking archive membership, hashes and report schema…';
    try {
      const response = await fetch('/api/explanation/verify', {
        method: 'POST', body: selected, signal: verifyController.signal,
        headers: {'Content-Type': 'application/zip'},
      });
      const result = await response.json();
      if (version !== verifyVersion) return;
      if (!response.ok) throw new Error(result.detail || 'Verification failed.');
      verifyStatus.textContent = `Integrity verified: ${result.file_count} files, run ${result.run_id}. This does not certify authorship or medical validity.`;
    } catch (error) {
      if (version === verifyVersion && error.name !== 'AbortError') verifyStatus.textContent = error.message;
    } finally {
      if (version === verifyVersion) { verifying = false; verify.disabled = !file.files.length; }
    }
  };
  controls();
})();
