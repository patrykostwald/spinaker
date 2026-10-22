/* Run against the offline dev server; all API requests are fulfilled locally.
 * Uses an already installed Playwright: PLAYWRIGHT_MODULE=/path/to/playwright.
 */
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.VERIFY_ORIGIN || 'http://localhost:3088';
const output = path.resolve('reports/088-layout');
fs.mkdirSync(output, { recursive: true });
// Isolated route for the actual FollowButton; remove it after verification.
const fixturePage = path.resolve('frontend-spin/app/check-follow-088/page.tsx');
const ownsFixture = !fs.existsSync(fixturePage);
if (ownsFixture) {
  fs.mkdirSync(path.dirname(fixturePage), { recursive: true });
  fs.writeFileSync(fixturePage, `'use client';
import { FollowButton } from '../../../packages/ui/src/components/FollowButton';
export default function Check() { return <main className="sc-account sc-f2"><h1>Anna Testowa</h1><FollowButton kind="figure" targetId={2} label="Anna Testowa" /></main>; }
`);
}

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const results = [];
  try {
    for (const width of [320, 390, 1024, 1440]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 } });
      const page = await context.newPage();
      page.setDefaultTimeout(30000);
      const errors = [], writes = [];
      let follows = [{ id: 1, kind: 'figure', target_id: 1, label: 'Agnieszka Testowa-Kowalska', mode: 'diagnoses', url: '/osoby-publiczne/1' }];
      page.on('pageerror', error => errors.push(error.stack));
      await context.route('**/*', async route => {
        const req = route.request(), url = new URL(req.url());
        if (url.origin !== origin) return route.abort();
        if (!url.pathname.startsWith('/api/')) return route.continue();
        const p = url.pathname, method = req.method();
        let body = {};
        if (p === '/api/account/me/') body = { authenticated: true, user: { id: 88, username: 'czytelnik', email_verified: true, is_staff: false }, csrfToken: 'fixture' };
        else if (p === '/api/auth/csrf/') body = { csrfToken: 'fixture' };
        else if (p === '/api/account/profile/') body = { id: 88, username: 'czytelnik', bio: '', theme_preference: 'dark', date_joined: '2026-10-03T10:00:00Z', public_activity: true, counts: { threads: 0, ratings: 0, comments: 0 } };
        else if (p === '/api/account/follows/' && method === 'POST') {
          const input = req.postDataJSON(); writes.push(input);
          body = { id: 2, label: 'Anna Testowa', url: '/osoby-publiczne/2', ...input };
          follows.push(body);
        } else if (p === '/api/account/follows/2/' && method === 'PATCH') {
          const input = req.postDataJSON(); writes.push(input);
          Object.assign(follows[1], input); body = follows[1];
        } else if (p === '/api/account/follows/') body = follows;
        else if (p === '/api/account/notifications/') body = { unread: 1, results: [{ id: 1, kind: 'followed_post', title: 'Testowa: 3 nowe wpisy', url: 'https://x.com/FixtureOnly/status/123', created_at: '2026-10-03T10:00:00Z', read_at: null, posts: [
          { id: 1, title: 'Pierwszy wpis testowy', url: '/klinika/12', score: 74 },
          { id: 2, title: 'Drugi wpis testowy', url: 'https://x.com/FixtureOnly/status/123', score: null },
          { id: 3, title: 'Trzeci wpis testowy', url: '/klinika/13', score: 20 },
        ] }] };
        else if (p.startsWith('/api/public-figures/')) body = { id: 1, name: 'Anna Testowa', x_account: null };
        else if (p === '/api/account/settings/notifications/') body = { service_enabled: true, social_enabled: false };
        else body = { results: [], next_page: null, count: 0, categories: [], topics: [], sources: [] };
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
      });
      await page.goto(`${origin}/check-follow-088`, { waitUntil: 'networkidle' });
      assert.deepEqual(errors, []);
      await page.getByRole('button', { name: 'Obserwuj: Anna Testowa', exact: true }).click();
      assert.equal(await page.getByRole('radio').count(), 3);
      assert.equal(await page.getByRole('radio', { name: 'Diagnozy', exact: true }).isChecked(), true);
      for (const label of await page.locator('.sc-follow-mode-box label').all()) {
        const box = await label.boundingBox(); assert.ok(box.height >= 44 && box.height < 60);
      }
      await page.screenshot({ path: path.join(output, `chooser-${width}.png`), fullPage: true });
      await page.getByRole('radio', { name: 'Każdy wpis', exact: true }).check();
      await page.getByRole('button', { name: 'Zapisz', exact: true }).click();
      await page.getByText('Dodano do obserwowanych.', { exact: true }).waitFor();
      assert.equal(writes[0].mode, 'posts');
      await page.goto(`${origin}/konto#obserwowani`, { waitUntil: 'networkidle' });
      const select = page.getByRole('combobox', { name: 'Powiadomienia: Anna Testowa', exact: true });
      assert.equal(await select.inputValue(), 'posts');
      await select.selectOption('strong_spin');
      await page.getByText('Zapisano tryb.', { exact: true }).waitFor();
      assert.equal(writes.at(-1).mode, 'strong_spin');
      await page.screenshot({ path: path.join(output, `followed-${width}.png`), fullPage: true });
      await page.getByRole('navigation', { name: 'Sekcje konta' }).getByRole('link', { name: 'Powiadomienia', exact: true }).click();
      await page.getByText('Zbadane: 74/100', { exact: true }).waitFor();
      assert.equal(await page.getByText('Drugi wpis testowy', { exact: true }).getAttribute('href'), 'https://x.com/FixtureOnly/status/123');
      await page.screenshot({ path: path.join(output, `notifications-${width}.png`), fullPage: true });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      assert.equal(overflow, false, `Horizontal overflow at ${width}`);
      assert.equal(await page.locator('[data-nextjs-dialog]').count(), 0);
      assert.deepEqual(errors, []);
      results.push({ width, picker: 'passed', modeChange: 'passed', diagnosisBadge: 'passed', xLink: 'passed', overflow, errors });
      await context.close();
    }
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results));
  } finally {
    await browser.close();
    if (ownsFixture) {
      fs.unlinkSync(fixturePage); fs.rmdirSync(path.dirname(fixturePage));
      fs.rmSync(path.resolve('frontend-spin/.next/types/app/check-follow-088/page.ts'), { force: true });
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
