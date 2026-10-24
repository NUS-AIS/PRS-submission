// Clinical form: required markers, unit and missing-value hints, inline field errors.
// Load after app.js and before prediction.js. Uses app.js globals $, api, fields, loaded and the inputs that
// fields() builds (wrapped below, so it runs once /api/overview has loaded). Rules come from /api/clinical.
// Server field errors arrive as the pulmo:field-errors event. Exposes window.ClinicalForm.
(() => {
  'use strict';
  const form = $('clinical-form');
  if (!form || typeof fields !== 'function') return;
  let schema = null;
  const rule = name => schema?.fields.find(f => f.field === name);
  const fusion = () => $('inference-model').value.startsWith('fusion');
  const controls = () => [...form.querySelectorAll('[data-field]')];
  const fmt = x => Number.isInteger(x) ? String(x) : String(+x.toFixed(3));

  // One message line per field, created on first use and placed under the label/input row.
  function line(input, cls) {
    const div = input.closest('.field');
    let p = div.querySelector('.' + cls);
    if (!p) {
      p = document.createElement('p');
      p.className = cls;
      p.id = `${input.id}-${cls}`;
      div.append(p);
    }
    return p;
  }

  function setError(input, message) {
    const p = line(input, 'field-error');
    p.textContent = message || '';
    p.hidden = !message;
    input.setAttribute('aria-invalid', String(!!message));
    const hint = input.closest('.field').querySelector('.field-hint');
    input.setAttribute('aria-describedby', [message && p.id, hint && !hint.hidden && hint.id].filter(Boolean).join(' '));
  }

  // Same rules and wording as pulmo_clinical.validate_clinical, so the page catches mistakes before a request.
  function check(input) {
    const r = rule(input.dataset.field), name = input.dataset.field;
    if (!r || !fusion()) return '';
    if (r.kind !== 'numeric') return input.value === '' ? `Please specify ${name}.` : '';
    if (input.validity.badInput) return `${name} must be a number or left blank.`;
    if (input.value === '') return '';
    const x = Number(input.value);
    if (!Number.isFinite(x) || x < 0) return `${name} must be a non-negative number or left blank.`;
    if (r.max != null && x > r.max) return `${name} must be between 0 and ${r.max}.`;
    return '';
  }

  function hint(input) {
    const r = rule(input.dataset.field), p = line(input, 'field-hint');
    const parts = [];
    if (r?.kind === 'numeric' && input.value === '' && fusion())
      parts.push(`Blank: the model uses the training median ${fmt(r.median)}.`);
    if (r?.unit && r.unit !== 'years') parts.push('Unit not stated in the dataset; use the original PAC569 table units.');
    p.textContent = parts.join(' ');
    p.hidden = !parts.length;
  }

  function sync() {
    const on = fusion();
    form.classList.toggle('fusion', on);
    for (const input of controls()) {
      const r = rule(input.dataset.field);
      input.required = on && !!r?.required;
      input.closest('.field').classList.toggle('required', !!r?.required);
      setError(input, '');
      hint(input);
    }
  }

  function showErrors(errors) {
    const unknown = [];
    let first = null;
    for (const [name, message] of Object.entries(errors || {})) {
      const input = controls().find(e => e.dataset.field === name);
      if (input) { setError(input, message); first ??= input; } else unknown.push(message);
    }
    if (first) first.focus();
    return unknown;
  }

  function wire() {
    for (const input of controls()) {
      input.addEventListener('input', () => { setError(input, check(input)); hint(input); });
      input.addEventListener('blur', () => setError(input, check(input)));
      // reportValidity() in app.js fires `invalid`; show our wording next to the field as well.
      input.addEventListener('invalid', () => setError(input, check(input) || input.validationMessage));
    }
    sync();
  }

  const baseFields = fields;
  window.fields = function () {
    baseFields();
    api('/api/clinical').then(s => { schema = s; wire(); }).catch(e => notice('Clinical field rules unavailable: ' + e.message));
  };
  const baseLoaded = loaded;
  window.loaded = function (c) { baseLoaded(c); if (schema) sync(); };
  $('inference-model').addEventListener('change', () => { if (schema) sync(); });
  document.addEventListener('pulmo:field-errors', e => { if (schema) showErrors(e.detail); });

  window.ClinicalForm = { sync, showErrors, get schema() { return schema; } };
})();
