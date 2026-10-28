const {test} = require('node:test');
const assert = require('node:assert/strict');
const Request = require('../web/modules/explanation-request.js');

test('late completion cannot replace the latest request', async () => {
  const pending = [];
  global.fetch = (url, options) => new Promise(resolve => pending.push({url, options, resolve}));
  const request = new Request();
  const old = request.fetch('/old');
  const latest = request.fetch('/new');
  assert.equal(pending[0].options.signal.aborted, true);
  pending[1].resolve({ok: true, blob: async () => 'new blob'});
  assert.equal(await latest, 'new blob');
  pending[0].resolve({ok: true, blob: async () => 'old blob'});
  assert.equal(await old, null);
});

test('invalidating a case while reading a body discards its result', async () => {
  let finish;
  global.fetch = async () => ({ok: true, blob: () => new Promise(resolve => { finish = resolve; })});
  const request = new Request();
  const result = request.fetch('/case');
  await new Promise(resolve => setImmediate(resolve));
  request.cancel();
  finish('stale');
  assert.equal(await result, null);
});

test('current server failures reach the user', async () => {
  global.fetch = async () => ({ok: false, json: async () => ({detail: 'Prediction expired'})});
  await assert.rejects(new Request().fetch('/expired'), /Prediction expired/);
});
