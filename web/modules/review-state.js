// Pure selection and display helpers shared by the browser and Node tests.
(() => {
  'use strict';
  function parsePositions(text, count) {
    if (!Number.isInteger(count) || count < 1 || count > 128) throw new Error('Invalid position count.');
    if (!text.trim()) return Array.from({length: count}, (_, index) => index + 1);
    const parts = text.split(',').map(value => value.trim());
    if (parts.some(value => !/^\d+$/.test(value))) throw new Error('Use comma-separated position numbers.');
    const values = parts.map(Number);
    if (values.some(value => value < 1 || value > count)) throw new Error(`Choose positions from 1 to ${count}.`);
    if (new Set(values).size !== values.length) throw new Error('Select each position only once.');
    return values.sort((a, b) => a - b);
  }
  function metric(value, percent = false) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
    return percent ? `${(value * 100).toFixed(1)}%` : value.toFixed(4);
  }
  function rankedRows(rows, order) {
    const copy = rows.slice();
    if (order === 'mass') return copy.sort((a, b) => (b.sum || 0) - (a.sum || 0) || a.position - b.position);
    return copy.sort((a, b) => a.position - b.position);
  }
  function query(active, positions, threshold) {
    if (!active?.run_id || !active?.token) throw new Error('Run inference first.');
    if (!Number.isFinite(threshold) || threshold < 0 || threshold > 1) throw new Error('Threshold must be between 0 and 1.');
    return new URLSearchParams({run: active.run_id, positions: positions.join(','), threshold});
  }
  const api = {parsePositions, metric, rankedRows, query};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else window.PulmoReviewState = api;
})();
