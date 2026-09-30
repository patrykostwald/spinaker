"use client";
import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, usePortalApi } from '../kit';
import { apiFetch, apiWrite } from '../lib/api';
import { accountEmail, emailVerified, useAccount } from '../lib/account';
import { accountHref, accountMessage, useFollows, useNotifications, type NotificationSettings } from '../lib/accountPhase2';
import { isUnavailable, useSavedTopics } from '../lib/personal';
import { useFeature } from '../lib/features';
import { getPortalConfig } from '../lib/portal';
import { getPublicFigures, usePublicFigure, verifiedXAccount } from '../lib/publicFigures';
import { searchClinicSpins } from '../lib/clinic';
import { formatDateTimePl } from '../lib/utils';
import { PersonalizedNews } from './PersonalizedNews';
import { FollowButton } from './FollowButton';
import { ThemeSwitcher } from './ThemeSwitcher';

export function AccountDataState({ query, empty = 'Ta część będzie dostępna wkrótce.' }: { query: { isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown }; empty?: string }) {
  if (query.isPending) return <p role="status">Ładuję…</p>;
  if (isUnavailable(query.error)) return <p>{empty}</p>;
  if (query.isError) return <p role="alert">Nie udało się pobrać danych. <Button variant="quiet" onClick={() => query.refetch()}>Ponów</Button></p>;
  return null;
}
function PanelSection({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return <section id={id} className="sc-account-section sc-f2-section" aria-labelledby={`${id}-title`}><header><h2 id={`${id}-title`}>{title}</h2></header>{children}</section>;
}
export function AccountNews() {
  const config = useQuery({ queryKey: ['portal-config'], queryFn: getPortalConfig, retry: false, staleTime: 60_000 });
  const portal = usePortalApi();
  return <PanelSection id="wiadomosci" title="Twoje wiadomości">
    <p>Wybierz do pięciu tematów. Zapisane paski czekają na Ciebie po zalogowaniu.</p>
    <AccountDataState query={config} />
    {config.data && <PersonalizedNews categories={config.data.categories} topics={config.data.topics ?? []} sources={config.data.sources ?? []} onSelect={portal.open} />}
  </PanelSection>;
}
function LatestDiagnosis({ figureId }: { figureId: number }) {
  const figure = usePublicFigure(figureId);
  const id = figure.data ? verifiedXAccount(figure.data)?.account_id : undefined;
  const spins = useQuery({ queryKey: ['follow-diagnoses', id], queryFn: () => searchClinicSpins({ account: String(id), sort: 'new' }), enabled: Boolean(id), retry: false, staleTime: 60_000 });
  if (figure.isPending || (id && spins.isPending)) return <p role="status">Sprawdzam najnowsze diagnozy…</p>;
  if (figure.isError || spins.isError) return <p>Diagnozy są chwilowo niedostępne. <Button variant="quiet" onClick={() => { void figure.refetch(); if (id) void spins.refetch(); }}>Ponów</Button></p>;
  if (!id || !spins.data?.results?.length) return <p className="sc-f2-muted">Nie ma jeszcze dostępnych diagnoz wpisów.</p>;
  return <ul>{spins.data.results.slice(0, 2).map(spin => <li key={spin.id}><Link href={`/klinika/${spin.id}`}>{spin.headline}</Link></li>)}</ul>;
}
export function FollowedSection() {
  const THREADS_ENABLED = useFeature('THREADS_ENABLED');
  const follows = useFollows();
  return <PanelSection id="obserwowani" title="Obserwowani">
    <AccountDataState query={follows} />
    {follows.isSuccess && !follows.data.length && <p>Obserwuj wybrane osoby i nitki, aby łatwo do nich wracać. <Link href="/osoby-publiczne">Znajdź osobę publiczną</Link>.</p>}
    {(['figure', 'user', ...(THREADS_ENABLED ? ['thread'] as const : [])] as const).map(kind => {
      const rows = follows.data?.filter(row => row.kind === kind) ?? [];
      return rows.length ? <div key={kind}><h3>{kind === 'figure' ? 'Osoby publiczne' : kind === 'user' ? 'Użytkownicy' : 'Nitki'}</h3><ul className="sc-account-rows">{rows.map(row => <li key={row.id}>
        <div><Link className="sc-account-title" href={accountHref(row.url)}>{row.label}</Link>{kind === 'figure' && <LatestDiagnosis figureId={row.target_id} />}</div>
        <FollowButton kind={row.kind} targetId={row.target_id} label={row.label} />
      </li>)}</ul></div> : null;
    })}
  </PanelSection>;
}
export function NotificationsSection() {
  const notifications = useNotifications(); const cache = useQueryClient();
  const [pending, setPending] = useState(false); const [message, setMessage] = useState('');
  async function read(ids?: number[]) {
    if (pending) return;
    setPending(true); setMessage('');
    try { await apiWrite('/api/account/notifications/read/', ids ? { ids } : { all: true }); await cache.invalidateQueries({ queryKey: ['account-notifications'] }); }
    catch (error) { setMessage(accountMessage(error)); } finally { setPending(false); }
  }
  return <PanelSection id="powiadomienia" title={`Powiadomienia${notifications.data ? ` · ${notifications.data.unread} nieprzeczytanych` : ''}`}>
    <AccountDataState query={notifications} />
    {Boolean(notifications.data?.unread) && <Button variant="quiet" disabled={pending} onClick={() => read()}>Oznacz wszystkie jako przeczytane</Button>}
    {notifications.isSuccess && !notifications.data?.results?.length && <p>Nie masz nowych powiadomień. Tutaj pojawią się informacje o obserwowanych osobach i nitkach.</p>}
    <ul className="sc-account-rows">{notifications.data?.results.map(row => <li key={row.id} data-unread={!row.read_at || undefined}>
      <div><p className="sc-f2-muted">{!row.read_at && <strong>Nowe · </strong>}<time dateTime={row.created_at}>{formatDateTimePl(row.created_at)}</time></p><Link href={accountHref(row.url)}>{row.title}</Link></div>
      {!row.read_at && <Button variant="quiet" disabled={pending} onClick={() => read([row.id])} aria-label={`Oznacz jako przeczytane: ${row.title}`}>Przeczytane</Button>}
    </li>)}</ul>
    {message && <p role="status">{message}</p>}
  </PanelSection>;
}
export function VerifyEmailNotice() {
  const account = useAccount(); const [pending, setPending] = useState(false); const [message, setMessage] = useState('');
  if (emailVerified(account.data)) return null;
  async function resend() {
    setPending(true); setMessage('');
    try { await apiWrite('/api/account/verify-email/resend/', {}); setMessage('Wysłano wiadomość. Sprawdź skrzynkę i folder spam.'); }
    catch (error) { setMessage(accountMessage(error)); } finally { setPending(false); }
  }
  return <div className="sc-f2-notice"><p>{accountEmail(account.data) ? 'Potwierdź e-mail, aby publikować nitki. Szkic możesz zapisać już teraz.' : 'Dodaj e-mail w ustawieniach konta i potwierdź go, aby publikować nitki.'}</p>
    {accountEmail(account.data) ? <Button type="button" variant="quiet" loading={pending} onClick={resend}>Wyślij ponownie link potwierdzający</Button> : <Button href="/konto#ustawienia" variant="quiet">Ustaw e-mail</Button>}
    <Button type="button" variant="quiet" disabled={account.isFetching} onClick={() => account.refetch()}>Sprawdź potwierdzenie</Button>
    {message && <p role="status">{message}</p>}
  </div>;
}

export function AccountSettings() {
  const PUSH_ENABLED = useFeature('PUSH_ENABLED');
  const THREADS_ENABLED = useFeature('THREADS_ENABLED');
  const account = useAccount(); const cache = useQueryClient(); const ownerId = account.data?.user?.id;
  const profile = useQuery({ queryKey: ['account-profile', ownerId], queryFn: () => apiFetch<{ username: string; public_activity: boolean }>('/api/account/profile/'), retry: false, enabled: Boolean(ownerId) });
  const settings = useQuery({ queryKey: ['notification-settings', ownerId], queryFn: () => apiFetch<NotificationSettings>('/api/account/notification-settings/'), retry: false, enabled: Boolean(ownerId) });
  const [pending, setPending] = useState(false); const [message, setMessage] = useState(''); const [deleting, setDeleting] = useState(false);
  async function perform(action: () => Promise<unknown>, success: string) {
    if (pending) return;
    setPending(true); setMessage('');
    try { await action(); setMessage(success); } catch (error) { setMessage(accountMessage(error)); } finally { setPending(false); }
  }
  async function updateSettings(patch: Partial<NotificationSettings>) {
    await apiWrite('/api/account/notification-settings/', patch, 'PATCH');
    await cache.invalidateQueries({ queryKey: ['notification-settings', ownerId] });
  }
  function emailSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const email = new FormData(event.currentTarget).get('email');
    void perform(async () => { await apiWrite('/api/account/me/', { email }, 'PATCH'); await cache.invalidateQueries({ queryKey: ['account'] }); }, 'Zapisano adres e-mail. Sprawdź jego potwierdzenie poniżej.');
  }
  async function download() {
    const data = await apiFetch<unknown>('/api/account/export/');
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'spin-clinic-konto.json'; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function deleteSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    if (data.get('confirm') !== 'USUŃ') return;
    void perform(async () => {
      await apiWrite('/api/account/delete/', { password: data.get('password'), confirm: 'USUŃ' });
      try { localStorage.removeItem(`sc-onboarding:${ownerId}`); } catch {}
      cache.clear(); window.location.assign('/');
    }, 'Usunięto konto.');
  }
  return <PanelSection id="ustawienia" title="Ustawienia">
    <div className="sc-f2-settings">
      <section><h3>Profil publiczny i motyw</h3><AccountDataState query={profile} />
        <p>Komentarze są publiczne. Zbiorczą historię pokazujemy tylko za Twoją zgodą. Ulubione i tematy są prywatne.</p>
        <label className="sc-f2-check"><input type="checkbox" checked={profile.data?.public_activity ?? false} disabled={pending || !profile.isSuccess} onChange={event => { const public_activity = event.target.checked; void perform(async () => {
          await apiWrite('/api/account/profile/', { public_activity }, 'PATCH'); await cache.invalidateQueries({ queryKey: ['account-profile', ownerId] }); cache.removeQueries({ queryKey: ['public-profile'] });
        }, 'Zapisano widoczność profilu.'); }} />Udostępnij historię aktywności</label>
        {profile.data?.public_activity && <Link href={`/profile/${encodeURIComponent(profile.data.username)}`}>Zobacz profil publiczny</Link>}
        <ThemeSwitcher />
      </section>
      <section><h3>Powiadomienia e-mail i push</h3><AccountDataState query={settings} />
        {settings.data && <><label>Podsumowanie e-mail<select value={settings.data.email_digest} disabled={pending} onChange={event => { const email_digest = event.target.value as NotificationSettings['email_digest']; void perform(() => updateSettings({ email_digest }), 'Zapisano powiadomienia.'); }}>
          <option value="off">Wyłączone</option><option value="daily">Raz dziennie</option><option value="weekly">Raz w tygodniu</option>
        </select></label>
        {PUSH_ENABLED && <><p>Wybierz rodzaje powiadomień push. Wymagają też włączonej subskrypcji na urządzeniu.</p>{([
          ['push_spin_of_day', 'Spin dnia'], ['push_followed', 'Nowości u obserwowanych'], ...(THREADS_ENABLED ? [['push_thread_replies', 'Odpowiedzi w nitkach']] : []),
        ] as [keyof Omit<NotificationSettings, 'email_digest'>, string][]).map(([key, label]) => <label className="sc-f2-check" key={key}><input type="checkbox" checked={settings.data[key]} disabled={pending} onChange={event => { const checked = event.target.checked; void perform(() => updateSettings({ [key]: checked }), 'Zapisano preferencje push.'); }} />{label}</label>)}</>}
        </>}
      </section>
      <section><h3>E-mail i bezpieczeństwo</h3>
        <form onSubmit={emailSubmit}><label>Adres e-mail<input key={accountEmail(account.data)} name="email" type="email" autoComplete="email" required defaultValue={accountEmail(account.data)} /></label><p>{emailVerified(account.data) ? 'E-mail potwierdzony.' : 'E-mail nie jest jeszcze potwierdzony.'}</p><Button type="submit" variant="secondary" disabled={pending}>Zapisz e-mail</Button></form>
        <VerifyEmailNotice />
        <Button variant="quiet" disabled={pending || !accountEmail(account.data)} onClick={() => perform(() => apiWrite('/api/account/password-reset/', { email: accountEmail(account.data) }), 'Jeśli adres jest przypisany do konta, otrzymasz link do zmiany hasła.')}>Wyślij link do zmiany hasła</Button>
        <Button variant="quiet" disabled={pending} onClick={() => perform(download, 'Przygotowano plik JSON do pobrania.')}>Pobierz eksport konta (JSON)</Button>
      </section>
      <section><h3>Aplikacja na telefonie</h3><p>W menu przeglądarki wybierz „Zainstaluj aplikację” lub „Dodaj do ekranu głównego”, jeśli ta opcja jest dostępna. Na iPhonie: Safari → Udostępnij → Do ekranu początkowego.</p></section>
      <section><h3>Usunięcie konta</h3><p>To działanie jest nieodwracalne. Przed usunięciem możesz pobrać eksport swoich danych. Operatorem serwisu jest iapply sp. z o.o.</p>
        {!deleting ? <Button variant="quiet" onClick={() => setDeleting(true)}>Chcę usunąć konto</Button> : <form onSubmit={deleteSubmit}>
          <label>Potwierdź aktualnym hasłem<input required name="password" type="password" autoComplete="current-password" /></label>
          <label>Wpisz USUŃ<input name="confirm" required pattern="USUŃ" autoComplete="off" /></label>
          <div className="sc-f2-actions"><Button type="submit" variant="danger" disabled={pending}>Usuń konto nieodwracalnie</Button><Button variant="quiet" disabled={pending} onClick={() => setDeleting(false)}>Anuluj</Button></div>
        </form>}
        <p><Link href="/polityka-prywatnosci">Polityka prywatności</Link> · <Link href="/zasady-korzystania">Zasady korzystania</Link></p>
      </section>
    </div>
    {message && <p role="status" className="sc-f2-notice">{message}</p>}
  </PanelSection>;
}

export function AccountOnboarding({ ownerId }: { ownerId: number }) {
  const [step, setStep] = useState<number | null>(null); const [topic, setTopic] = useState(''); const [search, setSearch] = useState(''); const [term, setTerm] = useState('');
  const [pending, setPending] = useState(false); const [message, setMessage] = useState(''); const topics = useSavedTopics(); const cache = useQueryClient();
  const figures = useQuery({ queryKey: ['onboarding-figures', term], queryFn: () => getPublicFigures(term), enabled: term.length >= 2, retry: false });
  useEffect(() => { try { setStep(localStorage.getItem(`sc-onboarding:${ownerId}`) === 'done' ? null : 1); } catch { setStep(1); } }, [ownerId]);
  function finish() { try { localStorage.setItem(`sc-onboarding:${ownerId}`, 'done'); } catch {} setStep(null); document.getElementById('wiadomosci')?.scrollIntoView(); }
  async function saveTopic(event: FormEvent) {
    event.preventDefault(); if (pending || !topic.trim() || !topics.isSuccess || topics.data.topics.length >= 5) return; setPending(true); setMessage('');
    try { await apiWrite('/api/account/topics/', { label: topic.trim(), query: topic.trim(), categories: [], topics: [], source_ids: [] }); await cache.invalidateQueries({ queryKey: ['account-topics', ownerId] }); setStep(2); }
    catch (error) { setMessage(accountMessage(error)); } finally { setPending(false); }
  }
  if (step === null) return <Button variant="quiet" onClick={() => setStep(1)}>Pokaż pierwsze kroki</Button>;
  return <section className="sc-f2-onboarding" aria-labelledby="onboarding-title"><p className="sc-account-kicker">Pierwsze kroki · {step}/3</p><h2 id="onboarding-title">{step === 1 ? 'Co chcesz śledzić?' : step === 2 ? 'Kogo chcesz obserwować?' : 'Twoje miejsce jest gotowe'}</h2>
    {step === 1 && <><p>Zacznij od jednego tematu: wydarzenia, miejscowości lub zagadnienia. Możesz później zmienić wybór.</p>
      {(topics.data?.topics.length ?? 0) >= 5 ? <p>Masz już pięć pasków. Możesz je zmienić w Twoich wiadomościach.</p> : <form onSubmit={saveTopic}><label>Nazwa i hasło pierwszego paska<input value={topic} maxLength={80} required onChange={event => setTopic(event.target.value)} /></label><Button type="submit" variant="primary" disabled={pending || !topics.isSuccess || !topic.trim()}>Zapisz temat i przejdź dalej</Button></form>}
      <AccountDataState query={topics} />
    </>}
    {step === 2 && <><p>Wybór należy do Ciebie. Obserwowanie nie oznacza poparcia dla osoby.</p><form onSubmit={event => { event.preventDefault(); setTerm(search.trim()); }}><label>Znajdź osobę publiczną<input type="search" value={search} onChange={event => setSearch(event.target.value)} /></label><Button type="submit" variant="quiet" disabled={search.trim().length < 2}>Szukaj</Button></form>
      {term && <AccountDataState query={figures} />}{figures.isSuccess && !figures.data?.results?.length && <p>Nie znaleziono osoby. Spróbuj innego nazwiska.</p>}
      <ul className="sc-account-rows">{figures.data?.results.slice(0, 5).map(figure => <li key={figure.id}><Link href={`/osoby-publiczne/${figure.id}`}>{figure.name}</Link><FollowButton kind="figure" targetId={figure.id} label={figure.name} /></li>)}</ul>
    </>}
    {step === 3 && <p>{topics.data?.topics.length ? `Twój pasek „${topics.data.topics[0].label}” znajdziesz poniżej w Twoich wiadomościach.` : 'Możesz zacząć od przeglądania wiadomości, a własny pasek dodać w dowolnym momencie.'} Ulubione, obserwowani i powiadomienia są zawsze w tym panelu.</p>}
    {message && <p role="status">{message}</p>}
    <div className="sc-f2-actions">{step > 1 && <Button variant="quiet" disabled={pending} onClick={() => setStep(step - 1)}>Wstecz</Button>}{step < 3 && <Button variant={step === 2 ? 'primary' : 'quiet'} disabled={pending} onClick={() => setStep(step + 1)}>{step === 1 ? 'Pomiń ten krok' : 'Dalej'}</Button>}<Button variant={step === 3 ? 'primary' : 'quiet'} disabled={pending} onClick={finish}>{step === 3 ? 'Przejdź do Twoich wiadomości' : 'Pomiń pierwsze kroki'}</Button></div>
    <p className="sc-f2-muted">Pominięcie zapamiętamy na tym urządzeniu. Możesz wrócić do tych kroków.</p>
  </section>;
}
