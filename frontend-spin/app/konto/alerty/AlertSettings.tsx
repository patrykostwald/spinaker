'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAccount } from '../../../../packages/ui/src/lib/account';
import { useFollows, accountMessage } from '../../../../packages/ui/src/lib/accountPhase2';
import { apiFetch, apiWrite } from '../../../../packages/ui/src/lib/api';
import { useFeature } from '../../../../packages/ui/src/lib/features';
import './alerts.css';

type Preferences = {
  push_followed: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  wake_person_ids: number[];
};

export function AlertSettings() {
  const account = useAccount(), follows = useFollows(), cache = useQueryClient();
  const pushEnabled = useFeature('PUSH_ENABLED');
  const ownerId = account.data?.user?.id;
  const settings = useQuery({ queryKey: ['notification-settings', ownerId], enabled: Boolean(ownerId), retry: false,
    queryFn: () => apiFetch<Preferences>('/api/account/notification-settings/') });
  const [draft, setDraft] = useState<Preferences | null>(null);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const [device, setDevice] = useState('Sprawdzanie powiadomień na urządzeniu…');
  const [supported, setSupported] = useState(false);
  useEffect(() => {
    setDraft(settings.data ? { ...settings.data, quiet_hours_start: settings.data.quiet_hours_start.slice(0, 5), quiet_hours_end: settings.data.quiet_hours_end.slice(0, 5) } : null);
  }, [settings.data]);
  useEffect(() => {
    let cancelled = false;
    async function check() {
      const available = 'Notification' in window && 'PushManager' in window && 'serviceWorker' in navigator;
      setSupported(available);
      if (!pushEnabled) { setDevice('Powiadomienia push są obecnie wyłączone w serwisie. Ustawienia ciszy możesz zapisać.'); return; }
      if (!available) { setDevice('Ta przeglądarka nie obsługuje powiadomień push. Na iPhonie dodaj aplikację do ekranu początkowego i otwórz ją stamtąd.'); return; }
      if (Notification.permission === 'denied') { setDevice('Powiadomienia są zablokowane. Zmień uprawnienia tej strony w ustawieniach przeglądarki.'); return; }
      try {
        const registration = await navigator.serviceWorker.getRegistration('/');
        const subscription = await registration?.pushManager?.getSubscription();
        if (!cancelled) setDevice(subscription ? 'Urządzenie ma subskrypcję push. W zgodach urządzenia zaznacz temat „Obserwowani”.' : 'To urządzenie nie ma subskrypcji push. Otwórz zgody urządzenia i wybierz temat „Obserwowani”.');
      } catch { if (!cancelled) setDevice('Nie udało się sprawdzić subskrypcji urządzenia. Otwórz zgody urządzenia, aby spróbować ponownie.'); }
    }
    void check();
    window.addEventListener('focus', check);
    return () => { cancelled = true; window.removeEventListener('focus', check); };
  }, [pushEnabled]);
  const people = (follows.data || []).filter(row => row.kind === 'figure').sort((a, b) => a.label.localeCompare(b.label, 'pl'));
  function change(patch: Partial<Preferences>) { setMessage(''); setDraft(current => current ? { ...current, ...patch } : current); }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!draft || busy) return;
    if (draft.quiet_hours_enabled && draft.quiet_hours_start === draft.quiet_hours_end) { setMessage('Wybierz różne godziny początku i końca ciszy.'); return; }
    setBusy(true); setMessage('');
    try {
      await apiWrite('/api/account/notification-settings/', {
        push_followed: draft.push_followed,
        quiet_hours_enabled: draft.quiet_hours_enabled,
        quiet_hours_start: `${draft.quiet_hours_start}:00`, quiet_hours_end: `${draft.quiet_hours_end}:00`,
        wake_person_ids: draft.wake_person_ids.filter(id => people.some(person => person.target_id === id)),
      }, 'PATCH');
      await cache.invalidateQueries({ queryKey: ['notification-settings', ownerId] });
      setMessage('Zapisano ustawienia alertów.');
    } catch (error) { setMessage(accountMessage(error)); }
    finally { setBusy(false); }
  }
  return <div className="sc-alert-settings">
    <a className="sc-alert-back" href="/konto#powiadomienia">← Powiadomienia na koncie</a>
    <header><h1>Ustawienia alertów</h1><p>Wybierz, kiedy mogą przychodzić powiadomienia o obserwowanych osobach.</p></header>
    <div className="sc-alert-device" role="status"><p>{device}</p>{supported && pushEnabled && <a href="#powiadomienia">Zgody i tematy na urządzeniu →</a>}</div>
    {account.isLoading && <p role="status">Wczytywanie konta…</p>}
    {account.isError && <p role="alert">Nie udało się wczytać konta. <button onClick={() => void account.refetch()}>Spróbuj ponownie</button></p>}
    {account.data && !ownerId && <p><a href="/konto">Zaloguj się</a>, aby zmienić ustawienia alertów.</p>}
    {ownerId && (settings.isLoading || follows.isLoading) && <p role="status">Wczytywanie ustawień…</p>}
    {ownerId && (settings.isError || follows.isError) && <p role="alert">Nie udało się wczytać ustawień lub obserwowanych osób. <button onClick={() => { void settings.refetch(); void follows.refetch(); }}>Spróbuj ponownie</button></p>}
    {ownerId && draft && follows.data && !follows.isError && <form onSubmit={save}>
      <fieldset disabled={busy} className="sc-alert-section"><legend>Alerty o osobach</legend>
        <label className="sc-alert-check"><input type="checkbox" checked={draft.push_followed} onChange={event => change({ push_followed: event.target.checked })} />Powiadomienia o obserwowanych</label>
        <p>Wyłączenie zatrzymuje te alerty push na wszystkich Twoich urządzeniach. Tematy i zgodę na urządzeniu ustawiasz osobno.</p>
      </fieldset>
      <fieldset disabled={busy} className="sc-alert-section"><legend>Cisza nocna</legend>
        <label className="sc-alert-check"><input type="checkbox" checked={draft.quiet_hours_enabled} onChange={event => change({ quiet_hours_enabled: event.target.checked })} />Wyciszaj w wybranych godzinach</label>
        <div className="sc-alert-times">
          <label>Od<input type="time" required disabled={!draft.quiet_hours_enabled} value={draft.quiet_hours_start} onChange={event => change({ quiet_hours_start: event.target.value })} /></label>
          <label>Do<input type="time" required disabled={!draft.quiet_hours_enabled} value={draft.quiet_hours_end} onChange={event => change({ quiet_hours_end: event.target.value })} /></label>
        </div>
        <p>Godziny według czasu w Warszawie. Odłożone alerty otrzymasz po zakończeniu ciszy.</p>
      </fieldset>
      <fieldset disabled={busy || !draft.quiet_hours_enabled} className="sc-alert-section"><legend>Budź mnie</legend>
        <p>Te osoby mogą przerwać ciszę nocną. Nadal obowiązują wybrane tryby obserwowania i zgoda na push.</p>
        <div className="sc-alert-people">{people.map(person => <label className="sc-alert-check" key={person.target_id}><input type="checkbox" checked={draft.wake_person_ids.includes(person.target_id)} onChange={event => change({ wake_person_ids: event.target.checked ? [...draft.wake_person_ids, person.target_id] : draft.wake_person_ids.filter(id => id !== person.target_id) })} />{person.label}</label>)}</div>
        {!people.length && <p>Nie obserwujesz jeszcze żadnej osoby publicznej.</p>}
        <a href="/konto#obserwowani">Zarządzaj obserwowanymi →</a>
      </fieldset>
      <div className="sc-alert-save"><button type="submit" disabled={busy}>{busy ? 'Zapisywanie…' : 'Zapisz ustawienia'}</button><p role="status" aria-live="polite">{message}</p></div>
    </form>}
  </div>;
}
