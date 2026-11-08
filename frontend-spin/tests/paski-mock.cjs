const data = {
  youtube: Array.from({ length: 8 }, (_, i) => ({ id: `v${i}`, title: `Posiedzenie komisji - omówienie projektu ustawy i pytania posłów ${i + 1}`, date: '2026-10-09T08:00:00Z', source: i % 2 ? 'Kancelaria Premiera' : 'Sejm RP', url: 'https://www.youtube.com/watch?v=abcdefghijk', image_url: 'https://i.ytimg.com/vi/abcdefghijk/mqdefault.jpg', category: i % 2 ? 'kprm' : 'sejm', category_label: i % 2 ? 'Kancelaria Premiera' : 'Sejm RP' })),
  publiczne: Array.from({ length: 8 }, (_, i) => ({ id: `r${i}`, title: `Projekt ustawy o zmianie zasad finansowania inwestycji publicznych ${i + 1}`, date: '2026-10-08', source: 'Sejm RP', url: 'https://sejm.gov.pl/', category: i % 2 ? 'vote' : 'document', category_label: i % 2 ? 'Głosowanie' : 'Dokument' })),
  media: [], kategorie: { youtube: [{ id: 'sejm', label: 'Sejm RP' }, { id: 'kprm', label: 'Kancelaria Premiera' }], publiczne: [{ id: 'document', label: 'Dokument' }, { id: 'vote', label: 'Głosowanie' }], media: [] }, generated_at: '2026-10-09T08:00:00Z',
};
module.exports = data;
if (require.main === module) require('node:http').createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json');
  if (!req.url.includes('/paski') && !req.url.includes('/start')) res.statusCode = 503;
  res.end(JSON.stringify(req.url.includes('/paski') ? data : req.url.includes('/start') ? { counts: {}, latest: [], topics_enabled: false } : {}));
}).listen(8106, '127.0.0.1', () => console.log('Mock API 8106'));
