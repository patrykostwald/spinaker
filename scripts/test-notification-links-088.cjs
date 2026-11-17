const assert = require('node:assert/strict');
const fs = require('fs');
const vm = require('vm');
const handlers = {}, opened = [];
vm.runInNewContext(fs.readFileSync('frontend-spin/public/sw.js', 'utf8'), {
  URL, self: { location: { origin: 'https://spin.clinic' }, addEventListener: (name, fn) => handlers[name] = fn,
    clients: { matchAll: async () => [], openWindow: async url => opened.push(url) } },
});
(async () => {
  for (const [input, expected] of [
    ['/klinika/12', 'https://spin.clinic/klinika/12'],
    ['https://x.com/FixtureOnly/status/123', 'https://x.com/FixtureOnly/status/123'],
    ['https://x.com.evil.test/FixtureOnly/status/123', 'https://spin.clinic/'],
    ['https://x.com@evil.test/FixtureOnly/status/123', 'https://spin.clinic/'],
    ['https://x.com/FixtureOnly/status/123?redirect=evil', 'https://spin.clinic/'],
    ['javascript:alert(1)', 'https://spin.clinic/'],
  ]) {
    let pending;
    handlers.notificationclick({ notification: { close() {}, data: { url: input } }, waitUntil: value => pending = value });
    await pending;
    assert.equal(opened.at(-1), expected);
  }
  console.log('6 notification link checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
