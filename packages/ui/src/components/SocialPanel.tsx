'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useSearchParams } from 'next/navigation';
import { apiFetch, apiWrite, ApiError } from '../lib/api';

type Publication = { id?: number; diagnosis_id?: number; platform: string; url: string; posted_at: string; deleted_at: string | null };
export type SocialMaterial = { id: number; title: string; caption?: string; link?: string; thumbnail?: string; video?: string; remove_required: boolean; posts: Publication[] };
type Task = { id: number; author?: string; content: string; kind: 'task' | 'question'; status: string; answer: string; answered_by: string; created_at: string; answered_at: string | null };
const date = (value: string) => new Date(value).toLocaleString('pl-PL', { timeZone: 'Europe/Warsaw', dateStyle: 'short', timeStyle: 'short' });
const status: Record<string, string> = { new: 'Nowe', progress: 'W toku', done: 'Zrobione' };
const authors: Record<string, string> = { assistant: 'Asystent', owner: 'Właściciel', claude: 'Claude' };
const fail = (error: unknown) => error instanceof Error ? error.message : 'Nie udało się wykonać działania.';

function SocialLogin({ onLogin }: { onLogin: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true); setError('');
    try { await apiWrite('/api/account/login/', { username: data.get('email'), password: data.get('password') }); await onLogin(); }
    catch (e) { setError(fail(e)); }
    finally { setBusy(false); }
  }
  return <form className="sc-social-box sc-social-form" onSubmit={submit}><h2>Zaloguj się do social media</h2><p>Użyj konta przygotowanego dla osoby od publikacji.</p>
    <label>E-mail<input type="email" name="email" autoComplete="username" required /></label>
    <label>Hasło<input type="password" name="password" autoComplete="current-password" required /></label>
    <button disabled={busy}>{busy ? 'Logowanie…' : 'Zaloguj się'}</button>
    <p>Przy pierwszym logowaniu ustaw hasło linkiem z zaproszenia. Jeśli link wygasł, poproś właściciela o nowy.</p>
    {error && <p role="alert">{error}</p>}
  </form>;
}

export function SocialPasswordSetup() {
  const params = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [done, setDone] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true); setMessage('');
    try {
      await apiWrite('/api/social/password/confirm/', { uid: params.get('uid'), token: params.get('token'), password: data.get('password') });
      setDone(true); window.history.replaceState(null, '', '/panel/social/haslo');
    } catch (e) { setMessage(fail(e)); }
    finally { setBusy(false); }
  }
  return <div className="sc-command-panel sc-command-v2 sc-social"><h1>Ustaw hasło</h1>{done ? <div className="sc-social-box"><p>Hasło zapisane.</p><a href="/panel/social">Przejdź do logowania</a></div> :
    <form className="sc-social-box sc-social-form" onSubmit={submit}><label>Nowe hasło<input name="password" type="password" minLength={8} maxLength={256} autoComplete="new-password" required /></label><button disabled={busy}>{busy ? 'Zapisywanie…' : 'Zapisz hasło'}</button>{message && <p role="alert">{message}</p>}</form>}</div>;
}

function MaterialCard({ item, onChange }: { item: SocialMaterial; onChange: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function save(action: string, url?: string) {
    setBusy(true); setMessage('');
    try { await apiWrite(`/api/social/materials/${item.id}/`, { action, url }); await onChange(); setMessage('Zapisano.'); }
    catch (e) { setMessage(fail(e)); }
    finally { setBusy(false); }
  }
  async function copy(value: string) {
    try { await navigator.clipboard.writeText(value); setMessage('Skopiowano.'); }
    catch { setMessage('Nie udało się skopiować. Zaznacz tekst i skopiuj go ręcznie.'); }
  }
  return <article className="sc-social-box sc-social-material" aria-label={`Materiał ${item.id}`}>
    {item.remove_required ? <><div className="sc-social-removal" role="alert"><strong>Usuń film</strong><p>Wpis polityka został usunięty lub materiał wycofano. Usuń film z TikToka i YouTube Shorts.</p></div><h2>{item.title}</h2>
      {item.posts.map(post => <p key={post.platform}><a href={post.url} target="_blank" rel="noopener noreferrer">Otwórz {post.platform === 'tiktok' ? 'TikTok' : 'YouTube Shorts'}</a></p>)}
      <button disabled={busy} onClick={() => void save('removed')}>Usunięte</button></> : <>
      <img className="sc-social-thumbnail" src={item.thumbnail} alt={`Karta diagnozy: ${item.title}`} loading="lazy" />
      <span className="sc-command-eyebrow">Materiał #{item.id} · TikTok i Shorts</span><h2>{item.title}</h2>
      <div className="sc-social-actions"><a className="sc-social-download" href={item.video} download>Pobierz film</a><button onClick={() => void copy(item.caption || '')}>Kopiuj opis</button><button onClick={() => void copy(item.link || '')}>Kopiuj link</button></div>
      <details><summary>Opis i link do diagnozy</summary><p className="sc-social-copy">{item.caption}</p><a href={item.link} target="_blank" rel="noopener noreferrer">{item.link}</a></details>
      {(['tiktok', 'shorts'] as const).map(platform => {
        const post = item.posts.find(row => row.platform === platform);
        const label = platform === 'tiktok' ? 'TikToku' : 'YouTube Shorts';
        return post ? <p key={platform} className="sc-social-posted">✓ Opublikowane na {label} · <a href={post.url} target="_blank" rel="noopener noreferrer">Zobacz post</a></p> :
          <form key={platform} className="sc-social-form" onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); void save(platform, String(data.get('url'))); }}>
            <label>Adres posta na {label}<input name="url" type="url" placeholder={platform === 'tiktok' ? 'https://www.tiktok.com/…' : 'https://www.youtube.com/shorts/…'} required maxLength={500} /></label><button disabled={busy}>Opublikowane na {label}</button></form>;
      })}<button className="sc-social-quiet" disabled={busy} onClick={() => void save('skip')}>Pomiń</button></>}
    {message && <p role="status">{message}</p>}
  </article>;
}

export function SocialInbox({ staff = false }: { staff?: boolean }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const endpoint = staff ? '/api/staff/social/tasks/' : '/api/social/tasks/';
  const refresh = useCallback(async () => {
    try { const data = await apiFetch<{ items: Task[] }>(endpoint); setTasks(data.items); setLoaded(true); setError(''); }
    catch (e) { setError(fail(e)); }
  }, [endpoint]);
  useEffect(() => { void refresh(); }, [refresh]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    setBusy(true); setError('');
    try { await apiWrite(endpoint, { kind: data.get('kind'), content: data.get('content') }); form.reset(); await refresh(); }
    catch (e) { setError(fail(e)); } finally { setBusy(false); }
  }
  return <section id={staff ? 'social-tasks' : undefined} className="sc-social-inbox"><div className="sc-social-actions"><h2>{staff ? 'Zadania od social media' : 'Zadania i pytania'}</h2><button onClick={() => void refresh()}>Odśwież skrzynkę</button></div>
    {!staff && <form className="sc-social-box sc-social-form" onSubmit={submit}><label>Rodzaj<select name="kind"><option value="question">Pytanie do asystenta</option><option value="task">Zadanie dla właściciela / Claude</option></select></label><label>Treść<textarea name="content" required maxLength={4000} rows={4} placeholder="Napisz, w czym potrzebujesz pomocy…" /></label><p>Na pytania odpowiada asystent AI. Zadania trafiają do właściciela. Odpowiedź pojawi się tutaj.</p><button disabled={busy}>{busy ? 'Wysyłanie, czekam na odpowiedź…' : 'Wyślij'}</button></form>}
    {error && <p className="sc-command-error" role="alert">{error}</p>}
    {!loaded && !error && <p role="status">Wczytywanie skrzynki…</p>}
    {loaded && !tasks.length && <p className="sc-social-box">Skrzynka jest pusta.</p>}
    {tasks.map(task => <article className="sc-social-box" key={task.id}><div className="sc-social-actions"><strong>{task.kind === 'question' ? 'Pytanie' : 'Zadanie'}{task.author ? ` · ${task.author}` : ''}</strong><span className="sc-social-tag">{status[task.status]}</span></div><p className="sc-social-copy">{task.content}</p><small>{date(task.created_at)}</small>
      {task.answer && <div className="sc-social-answer"><strong>{authors[task.answered_by]}</strong><p className="sc-social-copy">{task.answer}</p>{task.answered_at && <small>{date(task.answered_at)}</small>}</div>}
      {staff && <TaskReply task={task} onSaved={refresh} />}</article>)}
  </section>;
}

function TaskReply({ task, onSaved }: { task: Task; onSaved: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError('');
    const answer = String(data.get('answer') || '').trim();
    try { await apiWrite(`/api/staff/social/tasks/${task.id}/`, { status: data.get('status'), ...(answer ? { answer, answered_by: data.get('answered_by') } : {}) }, 'PATCH'); await onSaved(); }
    catch (e) { setError(fail(e)); } finally { setBusy(false); }
  }
  return <form className="sc-social-form" onSubmit={submit}><label>Status<select name="status" defaultValue={task.status}>{Object.entries(status).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Odpowiedź<textarea name="answer" maxLength={8000} rows={3} /></label><label>Odpowiedź od<select name="answered_by"><option value="owner">Właściciel</option><option value="claude">Claude</option></select></label><button disabled={busy}>Zapisz odpowiedź / status</button>{error && <p role="alert">{error}</p>}</form>;
}

export function SocialWorkspace({ items, onChange, isStaff = false }: { items: SocialMaterial[]; onChange: () => Promise<void>; isStaff?: boolean }) {
  const [tab, setTab] = useState('queue');
  const [posts, setPosts] = useState<Publication[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (tab === 'published') { setError(''); void apiFetch<{ items: Publication[] }>('/api/social/published/').then(data => setPosts(data.items)).catch(e => setError(fail(e))); }
  }, [tab]);
  return <><div className="sc-social-intro"><p>Gotowe materiały, publikacje i kontakt z zespołem.</p>{isStaff && <a href="/panel">Panel dowodzenia</a>}</div>
    <nav className="sc-social-tabs" aria-label="Widok social media">{[['queue', `Do publikacji (${items.length})`], ['published', 'Opublikowane'], ['tasks', 'Zadania i pytania']].map(([value, label]) => <button key={value} aria-pressed={tab === value} onClick={() => setTab(value)}>{label}</button>)}</nav>
    {tab === 'queue' && <>{items.length ? <div className="sc-social-grid">{items.map(item => <MaterialCard key={item.id} item={item} onChange={onChange} />)}</div> : <div className="sc-social-box"><h2>Wszystko na bieżąco</h2><p>Nie ma teraz materiałów do publikacji. Wróć później lub odśwież kolejkę.</p></div>}</>}
    {tab === 'published' && <section><h2>Ostatnie 50 publikacji</h2>{error && <p role="alert">{error}</p>}{!posts && !error && <p role="status">Wczytywanie…</p>}{posts?.length === 0 && <p>Brak publikacji.</p>}{posts?.map(post => <article className="sc-social-box" key={post.id}><strong>{post.platform === 'tiktok' ? 'TikTok' : 'YouTube Shorts'} · Materiał #{post.diagnosis_id}</strong><p><a href={post.url} target="_blank" rel="noopener noreferrer">Otwórz post</a></p><small>{date(post.posted_at)}{post.deleted_at ? ` · Usunięte: ${date(post.deleted_at)}` : ''}</small></article>)}</section>}
    {tab === 'tasks' && <SocialInbox />}</>;
}

export function SocialPanel() {
  const [data, setData] = useState<{ items: SocialMaterial[]; is_staff: boolean } | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    setBusy(true);
    try { const result = await apiFetch<{ items: SocialMaterial[]; is_staff: boolean }>('/api/social/queue/'); setData(result); setForbidden(false); setError(''); }
    catch (e) { if (e instanceof ApiError && [401, 403].includes(e.status)) { setData(null); setForbidden(true); } else setError(fail(e)); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  async function logout() {
    try { await apiWrite('/api/account/logout/', {}); setData(null); setForbidden(true); }
    catch (e) { setError(fail(e)); }
  }
  return <div className="sc-command-panel sc-command-v2 sc-social"><header className="sc-command-header"><div><span className="sc-command-eyebrow">spin.clinic · publikacje</span><h1>Social media</h1></div><div className="sc-social-actions"><button disabled={busy} onClick={() => void refresh()}>{busy ? 'Odświeżanie…' : 'Odśwież'}</button>{data && <button onClick={() => void logout()}>Wyloguj</button>}</div></header>
    {error && <p className="sc-command-error" role="alert">{error}</p>}
    {forbidden ? <SocialLogin onLogin={refresh} /> : data ? <SocialWorkspace items={data.items} isStaff={data.is_staff} onChange={refresh} /> : <p role="status">Wczytywanie panelu…</p>}
    <p className="sc-command-install">Na telefonie: menu przeglądarki → Dodaj do ekranu głównego. Panel wymaga połączenia z internetem.</p>
  </div>;
}
