// Test działania prototypów (suwak z klawiatury, długość okresu, tabela powiatów, Animacje, karta RCB).
// Użycie: node sprawdz.mjs <bezwzględna ścieżka do docs/teraz-koncepcje>; wymaga pakietu playwright obok skryptu.
import { chromium } from 'playwright';
const kat = process.argv[2];
const b = await chromium.launch({ headless: true });
for (const plik of ['A-rzezba-nocna.html', 'B-makieta-polski.html']) {
  const s = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const bledy = []; s.on('pageerror', e => bledy.push(String(e)));
  await s.goto(`file://${kat}/${plik}`); await s.waitForTimeout(800);
  const t = async () => s.textContent('#tytul-okresu');
  const wynik = { plik, start: await t() };
  await s.focus('#os-suwak'); await s.keyboard.press('ArrowLeft'); await s.keyboard.press('ArrowLeft'); await s.waitForTimeout(200);
  wynik.poStrzalkach = await t();
  await s.click('#os-dlugosc button[data-dni="30"]'); await s.waitForTimeout(200);
  wynik.dni30 = await t();
  wynik.wierszeTabeli = await s.$$eval('#tabela-powiatow tbody tr', r => r.length);
  wynik.brakWTabeli = await s.$$eval('#tabela-powiatow tbody tr', r => r.filter(x => x.textContent.includes('brak w naszych danych')).length);
  wynik.etykietaMapy = (await s.getAttribute('#plotno', 'aria-label')).slice(0, 120);
  await s.click('#przel-ruch'); wynik.animacjePoKliknieciu = await s.getAttribute('#przel-ruch', 'aria-pressed');
  wynik.zapamietane = await s.evaluate(() => localStorage.getItem('teraz-animacje'));
  await s.click('#os-dzis'); await s.click('#os-dlugosc button[data-dni="7"]');
  if (plik.startsWith('B')) {
    await s.click('.rcb__karta[data-id="r2"]'); await s.waitForTimeout(300);
    wynik.ogloszenie = await s.textContent('#ogloszenie');
    wynik.wylaczoneWTabeli = await s.$$eval('#tabela-powiatow tbody tr', r => r.filter(x => x.textContent.includes('wyłączony w treści')).map(x => x.cells[0].textContent));
  }
  wynik.bledy = bledy;
  console.log(JSON.stringify(wynik));
}
await b.close();
