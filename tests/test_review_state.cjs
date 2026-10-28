const test = require('node:test');
const assert = require('node:assert/strict');
const {parsePositions, metric, rankedRows, query} = require('../web/modules/review-state.js');

test('blank selection means all sampled positions in order', () => {
  assert.deepEqual(parsePositions(' ', 3), [1, 2, 3]);
});

test('explicit selection is sorted without altering its membership', () => {
  assert.deepEqual(parsePositions('16, 1,8', 16), [1, 8, 16]);
});

test('bad positions fail before making a request', () => {
  for (const value of ['0', '17', '1,1', '-1', '1.5', '1,', '1e1']) {
    assert.throws(() => parsePositions(value, 16));
  }
});

test('invalid sampled-position counts are rejected', () => {
  for (const count of [0, 129, 1.5, NaN]) assert.throws(() => parsePositions('', count));
});

test('missing and nonfinite attention metrics are not shown as zero', () => {
  for (const value of [null, undefined, NaN, Infinity, '1']) assert.equal(metric(value), '—');
  assert.equal(metric(0), '0.0000');
  assert.equal(metric(.25, true), '25.0%');
});

test('mass sorting is stable on ties and does not mutate source', () => {
  const rows = [{position: 2, sum: 1}, {position: 1, sum: 1}, {position: 3, sum: null}];
  assert.deepEqual(rankedRows(rows, 'mass').map(row => row.position), [1, 2, 3]);
  assert.equal(rows[0].position, 2);
});

test('position sorting ignores mass', () => {
  const rows = [{position: 3, sum: 10}, {position: 1, sum: 1}];
  assert.deepEqual(rankedRows(rows, 'position').map(row => row.position), [1, 3]);
});

test('query binds selection and threshold to exact run', () => {
  const params = query({token: 'case', run_id: 'run'}, [1, 3], .25);
  assert.equal(params.get('run'), 'run');
  assert.equal(params.get('positions'), '1,3');
  assert.equal(params.get('threshold'), '0.25');
});

test('query rejects missing run and nonfinite threshold', () => {
  assert.throws(() => query(null, [1], .5));
  for (const threshold of [NaN, Infinity, -.1, 1.1]) {
    assert.throws(() => query({token: 'case', run_id: 'run'}, [1], threshold));
  }
});
