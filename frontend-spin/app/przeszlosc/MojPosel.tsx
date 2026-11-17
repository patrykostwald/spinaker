"use client";
import { useEffect, useState } from 'react';
import './moj-posel.css';

/**
 * „Mój poseł”: okręg wyborczy → posłowie z tego okręgu (oficjalna lista aktywnych posłów Sejmu, news/przeszlosc_moj_posel.py).
 * Brak posła w wyniku znaczy „brak w naszych danych”; poseł bez profilu w rejestrze ma odnośnik do oficjalnej strony Sejmu.
 */
type District = { name: string; mps: number };
type Member = { name: string; club: string; slug: string | null; id: number | null; sejm_id?: number | null; sejm_url: string; deviation_share?: number | null; deviation_votes?: number | null };
type Result = { district: string; total: number; members: Member[] };
const API = '/api/przeszlosc/moj-posel/';

export function MojPosel() {
  const [districts, setDistricts] = useState<District[] | null>(null);
  const [chosen, setChosen] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    fetch(API).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(d => { if (live) setDistricts(d.districts); }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, []);
  useEffect(() => {
    if (!chosen) { setResult(null); return; }
    let live = true;
    setFailed(false);
    fetch(`${API}?okreg=${encodeURIComponent(chosen)}`).then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((d: Result) => { if (live) setResult(d); }).catch(() => { if (live) { setResult(null); setFailed(true); } });
    return () => { live = false; };
  }, [chosen]);
  return <section className="px-sec px-mp" aria-labelledby="mp-h">
    <div className="pt-head__l"><p className="px-kicker">Posłowie</p><h1 id="mp-h">Mój poseł</h1></div>
    <p className="px-mp__lead">Wybierz okręg wyborczy, a pokażemy posłów z tego okręgu. W profilu znajdziesz głosowania, wypowiedzi i odstępstwa od klubu, każde ze źródłem.</p>
    <label className="px-mp__pick">Okręg wyborczy
      <select value={chosen} onChange={e => setChosen(e.target.value)} disabled={!districts}>
        <option value="">{districts ? 'wybierz okręg' : failed ? 'nie udało się pobrać listy' : 'ładowanie…'}</option>
        {districts?.map(d => <option key={d.name} value={d.name}>{d.name} ({d.mps})</option>)}
      </select></label>
    {failed && chosen && <p className="px-msg" role="alert">Nie udało się pobrać posłów. Spróbuj ponownie za chwilę.</p>}
    {result && <div className="px-card px-mp__card">
      <h2 className="px-h3">Okręg {result.district} <small>{result.total}</small></h2>
      <ul className="px-mp__list">
        {result.members.map(m => <li key={m.name}>
          <a href={m.slug ? `/przeszlosc/osoba/${m.slug}` : m.sejm_url} {...(m.slug ? {} : { target: '_blank', rel: 'noopener noreferrer' })}>
            <b>{m.name}</b><span className="px-mp__club">{m.club || 'bez klubu'}</span>
            <small>{m.slug ? 'Profil: głosowania, wypowiedzi, odstępstwa' : 'Brak profilu u nas: strona Sejmu ↗'}
              {m.deviation_share != null && m.deviation_votes ? ` · odstępstwa od klubu (90 dni): ${m.deviation_share.toLocaleString('pl-PL', { maximumFractionDigits: 1 })}% z ${m.deviation_votes} głosów` : ''}</small></a>
        </li>)}
      </ul>
      <p className="px-card__foot">Źródło: oficjalna lista aktywnych posłów (API Sejmu). Brak posła w wyniku znaczy „brak w naszych danych”.</p>
    </div>}
  </section>;
}
