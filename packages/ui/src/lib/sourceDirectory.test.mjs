import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(new URL('../../../../frontend-spin/package.json', import.meta.url));
const ts = require('typescript');
const code = ts.transpileModule(readFileSync(new URL('./sourceDirectory.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { sourceDirectory, directoryGroup, channelIdentity } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const source = (id, extra = {}) => ({ id, name: 'Podobna nazwa', url: `https://publisher${id}.pl`, source_type: 'rss', ...extra });

test('confirmed YouTube and X identities form one publisher regardless of order or tracking parameters', () => {
  const publisher = source(1, { youtube_url: 'https://www.youtube.com/channel/UC-AbC', x_handle: 'Publisher' });
  const youtube = source(2, { url: 'http://youtube.com/channel/UC-AbC/?feature=shared', is_active: true });
  const x = source(3, { url: 'https://twitter.com/publisher/' });
  const groups = sourceDirectory([youtube, x, publisher]);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].source.id, 1);
  assert.deepEqual(groups[0].members.map(row => row.id), [2, 3, 1]);
});

test('names, shared social domains, ambiguous ownership and unproved aliases never merge', () => {
  const publisher = source(1, { youtube_url: 'https://youtube.com/channel/UC-AbC' });
  const channel = source(2, { url: 'https://youtube.com/@Publisher' });
  assert.equal(sourceDirectory([publisher, channel, source(3)]).length, 3);
  const sameChannel = source(4, { url: publisher.youtube_url });
  assert.equal(sourceDirectory([publisher, source(5, { youtube_url: publisher.youtube_url }), sameChannel]).length, 3);
  assert.notEqual(channelIdentity('https://youtube.com/channel/UC-AbC'), channelIdentity('https://youtube.com/channel/UC-abc'));
  assert.equal(channelIdentity('https://youtube.com.evil.test/channel/UC-AbC'), null);
  assert.equal(channelIdentity('https://youtube.com/watch?v=video'), null);
});

test('classification uses declared groups and exact institutional domains, never name fragments', () => {
  assert.equal(directoryGroup(source(1, { url: 'https://api.sejm.gov.pl/sejm/term10', portal_group: 'media' })), 'publiczne');
  assert.equal(directoryGroup(source(2, { name: 'PAP naukawpolsce.pl' })), 'media');
  assert.equal(directoryGroup(source(3, { portal_group: 'top' })), 'top');
  assert.equal(directoryGroup(source(4, { source_type: 'institution', portal_group: 'top' })), 'publiczne');
  assert.equal(directoryGroup(source(5, { url: 'https://api.sejm.gov.pl.evil.test' })), 'media');
});
