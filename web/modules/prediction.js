// Prediction: structured API errors, the "inputs used" summary and prediction lifecycle events.
// Load after app.js and clinical-form.js. Replaces the global api() so failures keep `code`, `status` and
// `fieldErrors`, and wraps invalidate() so any case, model or input change also clears the summary.
// Events on document for other modules (the explanation viewer subscribes to these):
//   pulmo:prediction  detail = predict response (has run_id)  ·  pulmo:invalidate  ·  pulmo:field-errors
(() => {
  'use strict';
  if (typeof api !== 'function' || typeof invalidate !== 'function') return;
  const emit = (name, detail) => document.dispatchEvent(new CustomEvent('pulmo:' + name, { detail }));
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };

  window.api = async function (path, options = {}) {
    const predicting = path.startsWith('/api/predict');
    const r = await fetch(path, options);
    if (!r.ok) {
      let body;
      try { body = await r.json(); } catch { body = { detail: r.statusText }; }
      const err = new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail));
      Object.assign(err, { status: r.status, code: body.code, fieldErrors: body.field_errors || {} });
      if (predicting && body.code === 'invalid_clinical') emit('field-errors', err.fieldErrors);
      throw err;
    }
    const data = await r.json();
    if (predicting) { render(data); emit('prediction', data); }
    return data;
  };

  const box = el('section', 'input-summary');
  box.hidden = true;
  box.setAttribute('aria-label', 'Inputs used by the model');
  $('probabilities').after(box);

  function shown(f) {
    if (f.used === null || f.used === undefined) return '—';
    if (f.kind === 'categorical') return { M: 'Male', F: 'Female' }[f.used] || f.used;
    if (f.kind === 'binary') {
      const test = /Glucan|Antigen/.test(f.field);
      return f.used ? (test ? 'Positive' : 'Yes') : (test ? 'Negative' : 'No');
    }
    return String(+Number(f.used).toFixed(3));
  }

  function render(result) {
    const inputs = result.inputs;
    box.replaceChildren(el('h3', '', 'Inputs used by the model'));
    box.hidden = !inputs;
    if (!inputs) return;
    if (!inputs.used) { box.append(el('p', 'hint', inputs.note)); return; }
    const table = el('table'), body = el('tbody');
    table.append(el('thead'), body);
    table.tHead.append(el('tr'));
    for (const h of ['Field', 'Value used', 'Source']) table.tHead.rows[0].append(el('th', '', h));
    for (const f of inputs.fields) {
      const tr = el('tr', f.source === 'user input' ? '' : 'imputed');
      const src = el('td');
      src.append(el('span', 'source', f.source === 'user input' ? 'Entered' : 'Training median'));
      tr.append(el('td', '', fieldLabels[f.field] || f.field), el('td', '', shown(f)), src);
      body.append(tr);
    }
    const p = inputs.preprocessing, notes = el('p', 'hint');
    const n = inputs.imputed.length;
    notes.textContent = (n ? `${n} blank numeric field${n > 1 ? 's' : ''} filled with the training median. ` : 'All fields entered. ')
      + `Medians and scaling fitted on ${p.train_rows} training rows only · ${p.split_file} ${p.split_sha256}.`
      + (inputs.ignored_fields.length ? ` Ignored unknown fields: ${inputs.ignored_fields.join(', ')}.` : '');
    box.append(table, notes);
  }

  const baseInvalidate = invalidate;
  window.invalidate = function () {
    baseInvalidate();
    box.hidden = true;
    box.replaceChildren();
    if (!busy) $('progress').textContent = '';  // drop "Inference complete" once the result is gone
    emit('invalidate');
  };

  window.Prediction = { render };
})();
