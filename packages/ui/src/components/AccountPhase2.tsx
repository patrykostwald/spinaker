"use client";
import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, usePortalApi } from '../kit';
import { apiFetch, apiWrite } from '../lib/api';
import { accountEmail, emailVerified, useAccount } from '../lib/account';
import { accountHref, notificationHref, accountMessage, useFollows, useNotifications, type NotificationSettings } from '../lib/accountPhase2';
import { isUnavailable, useSavedTopics } from '../lib/personal';
import { useFeature } from '../lib/features';
import { getPortalConfig } from '../lib/portal';
import { getPublicFigures, usePublicFigure, verifiedXAccount } from '../lib/publicFigures';
import { searchClinicSpins } from '../lib/clinic';
import { formatDateTimePl } from '../lib/utils';
import { PersonalizedNews } from './PersonalizedNews';
import { FollowButton, FollowModeSelect } from './FollowButton';
import { ThemeSwitcher } from './ThemeSwitcher';
import { XAccountSettings } from './XAccountSettings';
import { ProfileEditor, MutedSettings } from './AccountDashboardParts';

export function AccountDataState({ query, empty = 'Ta część będzie dostępna wkrótce.' }: { query: { isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown }; empty?: string }) {
  if (query.isPending) return <div role="status" aria-label="Ładowanie" className="sc-social-skeleton" />;
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
    {follows.isSuccess && !follows.data.length && <p>Obserwuj wybrane osoby i spinki, aby łatwo do nich wracać. <Link href="/osoby-publiczne">Znajdź osobę publiczną</Link>.</p>}
    {(['figure', 'user'] as const).map(kind => {
      const rows = follows.data?.filter(row => row.kind === kind) ?? [];
      return rows.length ? <div key={kind}><h3>{kind === 'figure' ? 'Osoby publiczne' : 'Autorzy spinek'}</h3><ul className="sc-account-rows">{rows.map(row => <li key={row.id}>
        <div><Link className="sc-account-title" href={accountHref(row.url)}>{row.label}</Link>{kind === 'figure' && <><FollowModeSelect follow={row} /><LatestDiagnosis figureId={row.target_id} /></>}</div>
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
    {notifications.isSuccess && !notifications.data?.results?.length && <div className="sc-account-empty"><span aria-hidden="true">○</span><p>Nie masz nowych powiadomień.</p><Button href="/konto#ustawienia">Ustaw powiadomienia</Button></div>}
    <ul className="sc-account-rows">{notifications.data?.results.map(row => <li key={row.id} data-unread={!row.read_at || undefined}>
      <div><p className="sc-f2-muted">{!row.read_at && <strong>Nowe · </strong>}<time dateTime={row.created_at}>{formatDateTimePl(row.created_at)}</time></p><a href={notificationHref(row.url)}>{row.title}</a>
        {row.posts?.map(post => <p key={post.id}>{row.posts!.length > 1 && <a href={notificationHref(post.url)}>{post.title}</a>}{post.score !== null && <a className="sc-follow-diagnosed" href={notificationHref(post.url)}>Zbadane: {post.score}/100</a>}</p>)}
      </div>
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
  return <div className="sc-f2-notice"><p>{accountEmail(account.data) ? 'Potwierdź e-mail, aby publikować spinki. Szkic możesz zapisać już teraz.' : 'Dodaj e-mail w ustawieniach konta i potwierdź go, aby publikować spinki.'}</p>
    {accountEmail(account.data) ? <Button type="button" variant="quiet" loading={pending} onClick={resend}>Wyślij ponownie link potwierdzający</Button> : <Button href="/konto#ustawienia" variant="quiet">Ustaw e-mail</Button>}
    <Button type="button" variant="quiet" disabled={account.isFetching} onClick={() => account.refetch()}>Sprawdź potwierdzenie</Button>
    {message && <p role="status">{message}</p>}
  </div>;
}

export type SettingsPart = 'konto' | 'powiadomienia' | 'prywatnosc';
const PART_TITLE: Record<SettingsPart, string> = { konto: 'Konto', powiadomienia: 'Ustawienia powiadomień', prywatnosc: 'Prywatność i dane' };

export function AccountSettings({ part = 'konto' }: { part?: SettingsPart }) {
  const PUSH_ENABLED = useFeature('PUSH_ENABLED');
  const THREADS_ENABLED = useFeature('THREADS_ENABLED');
  const account = useAccount(); const cache = useQueryClient(); const ownerId = account.data?.user?.id;
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
    event.preventDefault(); const data = new FormData(event.currentTarget); const email = data.get('email'); const password = data.get('password');
    void perform(async () => { await apiWrite('/api/account/me/', { email, password, accepted_terms: data.get('accepted_terms') === 'on' }, 'PATCH'); await cache.invalidateQueries({ queryKey: ['account'] }); }, 'Zapisano adres e-mail. Sprawdź jego potwierdzenie poniżej.');
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
  return <PanelSection id={part} title={PART_TITLE[part]}>
    <div className="sc-f2-settings">
      {part === 'konto' && <><ProfileEditor /><XAccountSettings /><section><h3>Motyw</h3><ThemeSwitcher /></section></>}
      {part === 'powiadomienia' && <section><h3>E-mail i push</h3><AccountDataState query={settings} />
        {settings.data && <>
        {([['service_enabled', 'Powiadomienia serwisowe'], ['social_enabled', 'Powiadomienia społecznościowe']] as const).map(([key, label]) => <label className="sc-f2-check" key={key}><input type="checkbox" checked={settings.data[key]} disabled={pending} onChange={event => { const checked = event.target.checked; void perform(() => updateSettings({ [key]: checked }), 'Zapisano powiadomienia.'); }} />{label}</label>)}<label>Podsumowanie e-mail<select value={settings.data.email_digest} disabled={pending} onChange={event => { const email_digest = event.target.value as NotificationSettings['email_digest']; void perform(() => updateSettings({ email_digest }), 'Zapisano powiadomienia.'); }}>
          <option value="off">Wyłączone</option><option value="daily">Raz dziennie</option><option value="weekly">Raz w tygodniu</option>
        </select></label>
        {PUSH_ENABLED && <><p>Wybierz rodzaje powiadomień push. Wymagają też włączonej subskrypcji na urządzeniu.</p>{([
          ['push_spin_of_day', 'Spin dnia'], ['push_followed', 'Nowości u obserwowanych'], ...(THREADS_ENABLED ? [['push_thread_replies', 'Odpowiedzi w spinkach']] : []),
        ] as [keyof Omit<NotificationSettings, 'email_digest'>, string][]).map(([key, label]) => <label className="sc-f2-check" key={key}><input type="checkbox" checked={settings.data[key]} disabled={pending} onChange={event => { const checked = event.target.checked; void perform(() => updateSettings({ [key]: checked }), 'Zapisano preferencje push.'); }} />{label}</label>)}</>}
        </>}
      </section>}
      {part === 'konto' && <><section><h3>E-mail i bezpieczeństwo</h3>
        <form onSubmit={emailSubmit}><label>Adres e-mail<input key={accountEmail(account.data)} name="email" type="email" autoComplete="email" required defaultValue={accountEmail(account.data)} /></label><p>{emailVerified(account.data) ? 'E-mail potwierdzony.' : 'E-mail nie jest jeszcze potwierdzony.'}</p><label>Aktualne hasło<input name="password" required type="password" autoComplete="current-password" /></label>
          {!account.data?.user?.accepted_terms_version && <label className="sc-f2-check"><input type="checkbox" name="accepted_terms" required />Akceptuję <Link href="/zasady-korzystania">zasady korzystania</Link>.</label>}
          <Button type="submit" variant="secondary" disabled={pending}>Zapisz e-mail</Button></form>
        <VerifyEmailNotice />
        <form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); const element = event.currentTarget; void perform(async () => { await apiWrite('/api/account/password-change/', { current_password: form.get('current_password'), password: form.get('new_password') }); element.reset(); }, 'Hasło zmienione.'); }}>
          <label>Aktualne hasło<input required name="current_password" type="password" autoComplete="current-password" /></label>
          <label>Nowe hasło<input required minLength={8} maxLength={256} name="new_password" type="password" autoComplete="new-password" /></label>
          <Button type="submit" disabled={pending}>Zmień hasło</Button>
        </form>
        <Button disabled={pending} onClick={() => perform(async () => { await apiWrite('/api/account/logout-all/', {}); cache.clear(); window.location.assign('/konto'); }, 'Wylogowano ze wszystkich urządzeń.')}>Wyloguj ze wszystkich urządzeń</Button>
        <Button variant="quiet" disabled={pending || !accountEmail(account.data)} onClick={() => perform(() => apiWrite('/api/account/password-reset/', { email: accountEmail(account.data) }), 'Jeśli adres jest przypisany do konta, otrzymasz link do zmiany hasła.')}>Wyślij link do zmiany hasła</Button>
      </section>
      <section><h3>Aplikacja na telefonie</h3><p>W menu przeglądarki wybierz „Zainstaluj aplikację” lub „Dodaj do ekranu głównego”, jeśli ta opcja jest dostępna. Na iPhonie: Safari → Udostępnij → Do ekranu początkowego.</p></section></>}
      {part === 'prywatnosc' && <><MutedSettings />
      <section><h3>Twoje dane</h3><p>Zbieramy tylko to, co potrzebne do konta: e-mail, nick, Twoje spinki, komentarze i reakcje. Bez śledzenia i reklam.</p>
        <Button variant="quiet" disabled={pending} onClick={() => perform(download, 'Przygotowano plik JSON do pobrania.')}>Pobierz moje dane (JSON)</Button></section>
      <section><h3>Usunięcie konta</h3><p>Konto i treści zostaną usunięte od razu po potwierdzeniu hasłem. To działanie jest nieodwracalne. Przed usunięciem pobierz eksport danych. Historia decyzji moderacji pozostaje bez przypisania do konta. Jeśli logujesz się przez Google, najpierw ustaw hasło przez e-mail.</p>
        {!deleting ? <Button variant="quiet" onClick={() => setDeleting(true)}>Chcę usunąć konto</Button> : <form onSubmit={deleteSubmit}>
          <label>Potwierdź aktualnym hasłem<input required name="password" type="password" autoComplete="current-password" /></label>
          <label>Wpisz USUŃ<input name="confirm" required pattern="USUŃ" autoComplete="off" /></label>
          <div className="sc-f2-actions"><Button type="submit" variant="danger" disabled={pending}>Usuń konto nieodwracalnie</Button><Button variant="quiet" disabled={pending} onClick={() => setDeleting(false)}>Anuluj</Button></div>
        </form>}
        <p><Link href="/polityka-prywatnosci">Polityka prywatności</Link> · <Link href="/zasady-korzystania">Zasady korzystania</Link></p>
      </section></>}
    </div>
    {message && <p role="status" className="sc-f2-notice">{message}</p>}
  </PanelSection>;
}

export function AccountOnboarding({ ownerId }: { ownerId: number }) {
  const [step, setStep] = useState<number | null>(null);
  useEffect(() => { try { setStep(localStorage.getItem(`sc-onboarding-social:${ownerId}`) === 'done' ? null : 0); } catch { setStep(0); } }, [ownerId]);
  function finish() { try { localStorage.setItem(`sc-onboarding-social:${ownerId}`, 'done'); } catch {} setStep(null); }
  if (step === null) return <Button variant="quiet" onClick={() => setStep(0)}>Pierwsze kroki</Button>;
  const steps = [
    ['Oceniaj spinki', 'Trzy znaki pomagają wyrazić ocenę: ✓ zgadzam się, ? mam wątpliwości, ✕ nie zgadzam się.'],
    ['Obserwuj', 'Obserwuj polityków i autorów, aby łatwo wracać do ich treści.'],
    ['Ustaw powiadomienia', 'Powiadomienia serwisowe są włączone. Społecznościowe włączysz w sekcji Powiadomienia.'],
  ];
  return <section className="sc-f2-onboarding" aria-labelledby="onboarding-title"><p className="sc-account-meta">Pierwsze kroki · {step + 1}/3</p><h2 id="onboarding-title">{steps[step][0]}</h2><p>{steps[step][1]}</p>
    <div className="sc-f2-actions">{step > 0 && <Button onClick={() => setStep(step - 1)}>Wstecz</Button>}<Button variant="primary" onClick={() => step === 2 ? finish() : setStep(step + 1)}>{step === 2 ? 'Gotowe' : 'Dalej'}</Button><Button variant="quiet" onClick={finish}>Pomiń</Button></div>
  </section>;
}
