// Dane syntetyczne wyłącznie do lokalnych testów. Żadnych ocen rzeczywistych osób.
const spin = (id, camp, intensity) => ({
  id, status: 'approved', camp, camp_label: camp === 'government' ? 'Rządzący' : 'Opozycja', intensity,
  verdict: 'partial', verdict_label: 'Częściowy spin', headline: 'Przykład testowy: teza wymaga kontekstu',
  summary: 'Materiał demonstracyjny do oceny układu. Analiza oddziela argument od sposobu przedstawienia danych.',
  author: { name: id === 109 ? 'Aleksandra Testowa-Dwuczłonowa z bardzo długim nazwiskiem' : 'Osoba testowa', handle: 'test', avatar_url: '', account_url: '', figure_id: null, role_title: '', party: null },
  post: { id: String(id), url: 'https://example.invalid/post', text: 'Syntetyczny wpis testowy. Nie jest wypowiedzią rzeczywistej osoby.', published_at: '2026-10-09T08:00:00Z', media: [], likes: 0, reposts: 0 },
  opinions: { positive: 0, negative: 0 }, comment_count: 0, technique_names: [], techniques: [], claims: [],
  analysis: 'Przykładowa analiza służy wyłącznie sprawdzeniu szerokości kolumny i sekcji Dyskusja.', limitations: 'Dane syntetyczne.', model: 'fixture', prompt_version: 'test', created_at: '2026-10-09T08:00:00Z', reviewed_at: null, notice: 'Dane testowe, nie diagnoza polityka.',
});
const spins = [spin(109, 'government', 24), spin(110, 'opposition', 52), spin(111, 'government', 78), spin(112, 'opposition', 18)];
const interview = { id: 109, day: '2026-10-08', title: 'Rozmowa testowa', headline: 'Przykład testowy: pytania i odpowiedzi', summary: 'Demonstracja analizy rozmowy. Oceny gościa i prowadzącego są prezentowane osobno.', channel: 'Kanał testowy', guest_name: 'Gość testowy', guest_role: '', host_name: 'Prowadzący testowy', url: '', video_id: '', thumbnail_url: '', overall: '', guest: { verdict: 'partial', verdict_label: 'Częściowy spin', intensity: 52, summary: 'Dane testowe', techniques: [], claims: [] }, host: { summary: 'Dane testowe', notes: [] }, limitations: 'Dane syntetyczne.', model: 'fixture', diagnosed_at: null };
const page = { generated_at: '2026-10-09T08:00:00Z', since: '2026-10-01', notice: 'Fixture', stats: Object.fromEntries(['read','screened','rejected','diagnosed','spins'].map((key, i) => [key, { total: 320 + i, today: [128, 42, 12, 16, 4][i] }])), accounts_count: 12,
  messages: Object.fromEntries(['government','opposition'].map(camp => [camp, { day: '2026-10-09', camp, message: 'Przykładowy przekaz do testu układu. To fikcyjna treść, nie relacja z wydarzeń politycznych.', thesis: 'Przykładowy przekaz do testu układu. To fikcyjna treść, nie relacja z wydarzeń politycznych.', themes: [], posts_count: 12, model: 'fixture' }])),
  columns: { government: spins.filter(s => s.camp === 'government'), opposition: spins.filter(s => s.camp === 'opposition') }, interview, message_history: { government: [], opposition: [] }, spin_of_day: null, latest_spin: null, scale: { window_days: 7, government: {}, opposition: {} },
};
function response(path) {
  if (path === '/api/clinic/') return page;
  if (path === '/api/auth/csrf/') return { csrfToken: 'test-only' };
  if (path.includes('/deleted/')) return { week_by_camp: { government:0, opposition:0 }, top_deleters:[], items:[], days:7 };
  if (path === '/api/clinic/stats/') return { generated_at: page.generated_at, since: page.since, totals: page.stats, accounts: [], window: { days: 7, date_from: '2026-10-03', date_to: '2026-10-09' }, daily: Array.from({length:7}, (_,i) => ({date:`2026-10-0${i+3}`,by_camp:{government:{diagnosed:i+1},opposition:{diagnosed:7-i}}})) };
  if (path.includes('/comments/')) return { results: [], count: 0, next_page: null };
  if (/\/spins\/\d+\/$/.test(path)) return spins.find(s => path.includes(`/${s.id}/`)) || spins[0];
  if (/\/interviews\/\d+\/$/.test(path)) return interview;
  if (path.includes('/opinions/')) return { counts: { positive: 0, negative: 0 }, mine: null };
  if (path.includes('/account/me/')) return { authenticated: false };
  if (path.includes('/newsletter/')) return { detail: 'Sprawdź skrzynkę i potwierdź zapis. To test - nie wysłano e-maila.' };
  if (path.includes('/spins/')) return { results: spins, count: spins.length, next_page: null };
  return { results: [], count: 0, next_page: null };
}
module.exports = { page, spins, interview, response };
