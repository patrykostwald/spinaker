"use client";
import { useState, type FormEvent } from 'react';
import { OBJECTION_SENT, RELATIONS, noticeLine, noticeSections, objectionBody, objectionError, objectionUrl, type PrivacyNotice, type Relation } from './informacja-dane';
import './informacja.css';

/**
 * Klauzula informacyjna RODO art. 14 w stopce profilu osoby i na stronie "Jak to działa" (decyzja właściciela 13.10,
 * API-v3 sekcja 0, flaga backendu PRZESZLOSC_PRIVACY_NOTICE_ENABLED). Domyślnie zwinięta: widać jedną linię
 * (tytuł, wersja, data, status "szkic do prawnika") i "Rozwiń". Formularz sprzeciwu: powód, e-mail do potwierdzenia,
 * kogo dotyczy; POST na objection_url z kontraktu -> 202 i link potwierdzający w e-mailu. Brak danych = nic nie renderuje.
 */
export function InformacjaODanych({ notice, id = 'informacja-o-danych' }: { notice: PrivacyNotice | null | undefined; id?: string }) {
  const sections = noticeSections(notice);
  const url = objectionUrl(notice);
  const [form, setForm] = useState(false);
  const [reason, setReason] = useState('');
  const [contact, setContact] = useState('');
  const [relation, setRelation] = useState<Relation | ''>('');
  const [state, setState] = useState<{ k: 'idle' | 'sending' | 'sent' | 'error'; msg?: string }>({ k: 'idle' });
  if (!notice || (!sections.length && !notice.title)) return null;

  async function send(event: FormEvent) {
    event.preventDefault();
    const err = objectionError(reason, contact, relation);
    if (err) { setState({ k: 'error', msg: err }); return; }
    setState({ k: 'sending' });
    try {
      const csrf = await (await fetch('/api/auth/csrf/', { credentials: 'include', cache: 'no-store' })).json().catch(() => ({}));
      const r = await fetch(url!, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', ...(csrf?.csrfToken ? { 'X-CSRFToken': csrf.csrfToken } : {}) },
        body: JSON.stringify(objectionBody(reason, contact, relation as Relation)) });
      if (r.status !== 202 && !r.ok) throw new Error('Nie udało się wysłać. Spróbuj za chwilę.');
      // kontrakt (3. recenzja): zawsze 202 z tą samą treścią - komunikat neutralny, bez informacji, czy osoba istnieje
      setState({ k: 'sent', msg: OBJECTION_SENT });
    } catch (e) { setState({ k: 'error', msg: e instanceof Error && e.message !== 'Failed to fetch' ? e.message : 'Nie udało się wysłać. Spróbuj za chwilę.' }); }
  }

  return <details className="pt-info" id={id}>
    <summary><span className="pt-info__line">{noticeLine(notice)}</span><span className="pt-info__more" aria-hidden="true">Rozwiń</span></summary>
    <div className="pt-info__body">
      {sections.map((s, i) => <section key={i}>{s.heading ? <h4>{s.heading}</h4> : null}<p>{s.text}</p></section>)}
      {notice.contact ? <p className="pt-info__contact">Kontakt w sprawie danych: <a href={`mailto:${notice.contact}`}>{notice.contact}</a></p> : null}
      {url ? <div className="pt-info__obj">
        {!form ? <button type="button" className="pt-info__btn" aria-expanded={false} onClick={() => setForm(true)}>Zgłoś sprzeciw</button> :
        state.k === 'sent' ? <p role="status" className="pt-info__ok">{state.msg}</p> :
        <form onSubmit={send} noValidate aria-label="Sprzeciw wobec przetwarzania danych">
          <label>Powód sprzeciwu
            <textarea required minLength={20} maxLength={2000} rows={4} value={reason} onChange={e => setReason(e.target.value)} /></label>
          <label>E-mail (wyślemy link do potwierdzenia)
            <input type="email" required maxLength={254} autoComplete="email" value={contact} onChange={e => setContact(e.target.value)} /></label>
          <fieldset><legend>Kogo dotyczy sprzeciw</legend>
            {RELATIONS.map(([k, l]) => <label key={k} className="pt-info__radio"><input type="radio" name={`${id}-rel`} value={k} checked={relation === k} onChange={() => setRelation(k)} />{l}</label>)}
          </fieldset>
          {state.k === 'error' ? <p role="alert" className="pt-info__err">{state.msg}</p> : null}
          <div className="pt-info__act"><button type="submit" className="pt-info__btn" disabled={state.k === 'sending'} aria-busy={state.k === 'sending'}>Wyślij sprzeciw</button>
            <button type="button" className="pt-info__ghost" onClick={() => setForm(false)}>Anuluj</button></div>
        </form>}
      </div> : null}
    </div>
  </details>;
}
