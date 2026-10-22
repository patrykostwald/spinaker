// Wyłącznie syntetyczne dane, wspólny kontrakt ze zlecenia 104.
const source = { key: 'test', label: 'Rejestr demonstracyjny', license: 'Dane testowe', url: 'https://example.org/zrodlo', retrieved_at: '2026-10-09T08:00:00Z' };
const node = (id, kind, label, level, category, date = null, amount = null, extra = {}) => ({ id, kind, label, short: label.slice(0, 28), level, category, date, amount, currency: amount === null ? null : 'PLN', certainty: 'identifier', source, url: source.url, meta: {}, ...extra });
const nodes = [node('root', 'person', 'Jan Przykładowy', 0, 'polityka'),
  node('organ', 'authority', 'Urząd gminy Przykład', 1, 'polityka'), node('spolka', 'organisation', 'Spółka Przykładowa', 1, 'spolki'),
  node('dotacja', 'grant', 'Program rozwoju', 2, 'dotacje', '2025-03-12', 450000), node('umowa', 'contract', 'Modernizacja budynku', 2, 'zamowienia', '2025-07-18', 1250000),
  node('artykul', 'media', 'Artykuł o inwestycji', 3, 'media', '2025-10-02'), node('odbiorca', 'organisation', 'Odbiorca przykładowy', 3, 'spolki', '2026-01-15'),
  node('diagnoza', 'diagnosis', 'Analiza narracji', 3, 'media', '2026-02-03'),
  node('anon', 'person_anon', 'osoba fizyczna', 3, 'spolki', null),
  node('nazwa', 'organisation', 'Podobna nazwa', 3, 'spolki', '2026-03-01', 0, { certainty: 'name_only' })];
const edge = (id, from, to, label, date_from = null, amount = null, extra = {}) => ({ id, from, to, label, date_from, date_to: null, amount, currency: amount === null ? null : 'PLN', source_key: source.key, certainty: 'identifier', ...extra });
module.exports = { root: { id: 'root', kind: 'person', label: 'Jan Przykładowy', url: '/przeszlosc/osoba/1' }, nodes,
  edges: [edge('e1', 'root', 'spolka', 'Funkcja w podmiocie'), edge('e2', 'root', 'organ', 'Dokument organu'),
    edge('e3', 'organ', 'dotacja', 'Przyznana dotacja', '2025-03-12', 450000), edge('e4', 'spolka', 'umowa', 'Zamówienie', '2025-07-18', 1250000),
    edge('e5', 'umowa', 'odbiorca', 'Odbiorca zamówienia'), edge('e6', 'dotacja', 'artykul', 'Wzmianka w artykule'), edge('e7', 'root', 'diagnoza', 'Diagnoza'),
    edge('e8', 'odbiorca', 'anon', 'Funkcja w podmiocie'), edge('e9', 'spolka', 'nazwa', 'Zgodność nazwy', null, null, { certainty: 'name_only' })],
  categories: ['nieruchomosci', 'spolki', 'dotacje', 'zamowienia', 'polityka', 'orzeczenia'].map((key, i) => ({ key,
    label: ['Nieruchomości', 'Spółki', 'Dotacje i fundusze', 'Zamówienia publiczne', 'Polityka i lobbing', 'Orzeczenia'][i],
    count: [0, 3, 1, 1, 2, 0][i], available: i !== 0 && i !== 5 })),
  timeline: nodes.filter(n => n.date).map(n => ({ date: n.date, node_id: n.id, kind: n.kind, label: n.label, category: n.category })),
  signals: [], limits: { max_nodes: 300, max_edges: 600, truncated: false, grouped: [] },
  legal: { notes: ['Dane demonstracyjne. Powiązanie nie stanowi oceny osoby ani podmiotu.'], narrative: false }, generated_at: '2026-10-09T08:00:00Z' };
