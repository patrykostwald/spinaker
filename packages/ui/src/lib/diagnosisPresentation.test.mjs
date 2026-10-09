import assert from "node:assert/strict";
import { after, test } from "node:test";
import { mkdtempSync, readFileSync, writeFileSync, unlinkSync, rmdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRequire } from "node:module";
const require = createRequire(new URL("../../../../frontend-spin/package.json", import.meta.url));
const ts = require("typescript");

// Brak runnera TS: kompilujemy prawdziwe moduły istniejącym TypeScriptem i używamy node --test.
const compiled = mkdtempSync(join(tmpdir(), "spin-d1-test-"));
const modules = ["techniqueFamilies", "diagnosisPresentation", "utils", "clinicPeriod", "typography", "api", "clinicReports"];
writeFileSync(join(compiled, "package.json"), '{"type":"commonjs"}');
for (const name of modules) {
  const source = readFileSync(new URL(`./${name}.ts`, import.meta.url), "utf8");
  writeFileSync(join(compiled, `${name}.js`), ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText);
}
const { diagnosisPresentation } = require(join(compiled, "diagnosisPresentation.js"));
const { clinicPeriodLabel } = require(join(compiled, "clinicPeriod.js"));
const { reportWeekLabel, reportPublicationLabel } = require(join(compiled, "clinicReports.js"));
after(() => {
  for (const name of [...modules.map(name => `${name}.js`), "package.json"]) unlinkSync(join(compiled, name));
  rmdirSync(compiled);
});

function checkTotal(result, expected) {
  assert.equal(result.typeCount, expected);
  assert.equal(result.families.reduce((sum, family) => sum + family.count, 0), expected);
}

// Przypadki odtwarzające kształt problemów 1041/1060 z audytu, nie kopie danych produkcyjnych.
test("1041: pełna lista wygrywa z uciętym scan i sprzecznymi agregatami rodzin", () => {
  const techniques = ["Teza bez dowodu", ...Array.from({ length: 6 }, (_, index) => `Historyczna technika ${index}`)].map(name => ({ name }));
  const result = diagnosisPresentation({ id: 1041, techniques, scan: {
    techniques: techniques.slice(0, 6), families: { dane: { technique_types: 20 } },
  } });
  checkTotal(result, 7);
  assert.equal(result.families.find(f => f.key === "dane").count, 1);
  assert.equal(result.families.find(f => f.key === "inne").count, 6);
  assert.equal(result.familyMax, 6);
  assert.equal(result.techniques.at(-1).name, "Historyczna technika 5");
});

test("1060: statusy są jawne, brak źródeł nie zamienia twierdzenia w opinię", () => {
  const claims = ["supported", "misleading", "contradicted", "unverified", "opinion"].map(assessment => ({ claim: "To samo zdanie", assessment, sources: [] }));
  claims.push({ ...claims[3] });
  const result = diagnosisPresentation({ id: 1060, claims, scan: { claims: { opinions: 9, checked: 0 } } });
  assert.deepEqual(Object.fromEntries(result.claims.map(c => [c.key, c.count])), {
    supported: 1, misleading: 1, contradicted: 1, unverified: 2, opinion: 1,
  });
  assert.equal(result.checked, 3);
  assert.equal(result.claimSquares.length, 6); // zapisane pozycje, nie unikalne zdania
});

test("wywiad z 7 kategoriami: licznik, tabela i rodziny liczą te same typy", () => {
  const categories = ["Teza bez dowodu", "Wybiórcze dane", "Przesada", "Straszenie", "Atak na osobę", "Zmiana tematu", "Inne"];
  const techniques = categories.map((category, index) => ({ category, name: `Opis ${index}`, seconds: index * 60 }));
  const result = diagnosisPresentation({ techniques: [...techniques, { ...techniques[0], name: "Drugi cytat" }] });
  checkTotal(result, 7);
  assert.deepEqual(result.families.map(f => f.count), [2, 2, 2, 1]);
  assert.equal(result.techniques.length, 8); // zachowujemy wszystkie cytaty w uzasadnieniu
});

test("scan jako fallback: kategoria jest kluczem nawet przy innej nazwie widocznej", () => {
  const result = diagnosisPresentation({ scan: { techniques: [
    { category: "Słomiany człowiek", name: "Zniekształcenie cudzego stanowiska" },
    { category: "Słomiany człowiek", name: "Drugi opis" },
  ] } });
  checkTotal(result, 1);
  assert.equal(result.types[0].family, "spor");
  assert.equal(result.families.some(f => f.key === "inne"), false);
});

test("nieznana rodzina pozostaje widoczna jako Inne; puste dane nie wymyślają wyniku", () => {
  const result = diagnosisPresentation({ techniques: [{ name: "Historyczna", family: "nowa" }] });
  checkTotal(result, 1);
  assert.equal(result.types[0].family, "inne");
  const empty = diagnosisPresentation({});
  checkTotal(empty, 0);
  assert.equal(empty.checked, 0);
  assert.equal(empty.council.agreement, null);
});

test("2/3: trzy odpowiedzi, czwarty model bez odpowiedzi poza rozbieżnością", () => {
  const members = [
    { model: "A", verdict: "spin", intensity: 60 },
    { model: "B", verdict: "spin", intensity: 0 },
    { model: "C", verdict: "partial", intensity: 40 },
    { model: "D", verdict: null, intensity: null, status: "brak odpowiedzi" },
  ];
  const result = diagnosisPresentation({ council: { members }, scan: { council: { votes: members.slice(0, 3), verdict_agreement: "3/3" } } });
  assert.equal(result.council.agreement, "2/3");
  assert.equal(result.council.disagreementCount, 1);
  assert.equal(result.council.missing.length, 1);
  assert.equal(result.council.responses[1].intensity, 0);
});

test("werdykt bez liczby nadal jest odpowiedzią; unclear jest werdyktem", () => {
  const result = diagnosisPresentation({ scan: { council: { votes: [
    { model: "A", verdict: "unclear", intensity: null },
    { model: "B", verdict: "spin", intensity: 40 },
    { model: "C", verdict: null, intensity: 0 },
  ] } } });
  assert.equal(result.council.agreement, "1/2");
  assert.equal(result.council.missing.length, 1);
});

test("jawny brak odpowiedzi i pusty skład nie pokazują zgodności", () => {
  const result = diagnosisPresentation({ council: { members: [{ model: "A", verdict: "spin", intensity: 50, status: "brak odpowiedzi" }] } });
  assert.equal(result.council.agreement, null);
  assert.equal(result.council.disagreementCount, 0);
  assert.equal(result.council.missing.length, 1);
});

test("data zestawienia pochodzi z serwera, niezależnie od pobrania", () => {
  const period = { since: "2026-09-21", generated_at: "2026-09-27T18:00:00Z" };
  assert.equal(clinicPeriodLabel(period, 1), clinicPeriodLabel(period, Date.now()));
  assert.match(clinicPeriodLabel(period, 1), /^od 21 września 2026 · stan na /);
  assert.match(clinicPeriodLabel(period, 1), /20:00/);
});

test("starsze API: brak dowolnego pola oznacza Pobrano, nigdy stan na", () => {
  for (const period of [undefined, {}, { since: "2026-09-21" }, { generated_at: "2026-09-27T18:00:00Z" }]) {
    assert.match(clinicPeriodLabel(period, Date.parse("2026-09-28T10:10:00Z")), /^Pobrano /);
  }
});

test("daty raportu są polskie, bez sekund, także przy zmianie roku", () => {
  assert.equal(reportWeekLabel("2026-09-21", "2026-09-27"), "21–27 września 2026");
  assert.equal(reportWeekLabel("2026-12-28", "2027-01-03"), "28 grudnia 2026 – 3 stycznia 2027");
  assert.equal(reportPublicationLabel("2026-09-27T18:00:00Z"), "27 września, 20:00");
});

test("zgodność liczona względem końcowego werdyktu (audyt 046)", () => {
  const members = [{ model: "a", verdict: "unclear", intensity: 20 }, { model: "b", verdict: "unclear", intensity: 30 }, { model: "c", verdict: "spin", intensity: 70 }];
  assert.equal(diagnosisPresentation({ verdict: "spin", council: { members } }).council.agreement, "1/3");
  assert.equal(diagnosisPresentation({ council: { members } }).council.agreement, "2/3");
});

test("064: lekki payload listy daje te same liczby co detal", () => {
  const detail = {
    verdict: "partial",
    techniques: [{ name: "Opis", category: "Teza bez dowodu" }, { name: "Drugi cytat", category: "Teza bez dowodu" }, { name: "Straszenie" }],
    claims: [{ assessment: "supported", sources: [{ url: "https://example.org" }] }, { assessment: "unverified" }],
    council: { members: [{ model: "A", verdict: "partial" }, { model: "B", verdict: "spin" }, { model: "C", verdict: null, status: "brak odpowiedzi" }] },
  };
  const list = { ...detail, claims: detail.claims.map(({ assessment }) => ({ assessment })) };
  const summary = input => {
    const value = diagnosisPresentation(input);
    return { checked: value.checked, claims: value.claims, agreement: value.council.agreement,
      count: value.typeCount, families: value.families.map(({ key, count }) => ({ key, count })) };
  };
  assert.deepEqual(summary(list), summary(detail));
  assert.equal(summary(list).agreement, "1/2");
  assert.equal(summary(list).count, 2);
});
