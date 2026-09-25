"use client";

import Link from "next/link";
import type { Party, SpinAuthor, SpinCardData, SpinScale as SpinScaleData, Verdict } from "../../lib/clinic";
import { sharePercent } from "../../lib/clinic";
import { formatDateTimePl } from "../../lib/utils";

/** Plakietka partii po lewej od awatara. Skrót tekstowy zamiast logo — neutralnie i bez praw do znaków. */
export function PartyBadge({ party }: { party: Party | null }) {
  if (!party) return <span className="sc-party sc-party--none" aria-hidden="true" />;
  return <span className="sc-party" title={party.name} aria-label={`Partia: ${party.name}`}>{party.short}</span>;
}

export function SpinAvatar({ author, size = "md" }: { author: SpinAuthor; size?: "md" | "lg" }) {
  const initials = author.name.split(/\s+/).map(part => part[0]).filter(Boolean).slice(0, 2).join("");
  return (
    <span className={`sc-spin-avatar sc-spin-avatar--${size}`}>
      {author.avatar_url
        // eslint-disable-next-line @next/next/no-img-element -- awatar z oficjalnego API X, bez optymalizacji po naszej stronie
        ? <img src={author.avatar_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
        : <span aria-hidden="true">{initials}</span>}
    </span>
  );
}

export function SpinAuthorRow({ author, publishedAt, size = "md" }: { author: SpinAuthor; publishedAt: string; size?: "md" | "lg" }) {
  return (
    <header className="sc-spin-author">
      <PartyBadge party={author.party} />
      <SpinAvatar author={author} size={size} />
      <div className="sc-spin-author__text">
        <p className="sc-spin-author__name">
          {author.figure_id ? <Link href={`/osoby-publiczne/${author.figure_id}`}>{author.name}</Link> : author.name}
        </p>
        <p className="sc-spin-author__meta">
          <a href={author.account_url} target="_blank" rel="noopener noreferrer">@{author.handle}</a>
          {" · "}<time dateTime={publishedAt}>{formatDateTimePl(publishedAt)}</time>
        </p>
      </div>
    </header>
  );
}

export function VerdictTag({ verdict, label }: { verdict: Verdict; label: string }) {
  return <span className="sc-verdict" data-verdict={verdict}>{label}</span>;
}

export function IntensityMeter({ value }: { value: number }) {
  return (
    <span className="sc-intensity" title="Siła spinu według diagnozy (0–100)">
      <span className="sc-intensity__track" aria-hidden="true"><span style={{ width: `${Math.max(2, value)}%` }} /></span>
      <span className="sc-intensity__value">siła {value}/100</span>
    </span>
  );
}

export function AiTag() {
  return <span className="sc-ai-tag" title="Treść przygotowana automatycznie przez AI, zatwierdzona bez edycji">AI</span>;
}

/** Karta: po lewej post (autor, treść, zdjęcie), po prawej diagnoza. */
export function SpinCard({ spin }: { spin: SpinCardData }) {
  const image = spin.post.media.find(item => item.url);
  return (
    <article className="sc-spin-card" data-verdict={spin.verdict} aria-labelledby={`spin-${spin.id}-title`}>
      <div className="sc-spin-card__post">
        <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} />
        <p className="sc-spin-card__text">{spin.post.text}</p>
        {image && (
          // eslint-disable-next-line @next/next/no-img-element -- miniatura z oficjalnego API X
          <img className="sc-spin-card__media" src={image.url} alt={image.alt || "Załącznik do posta"} loading="lazy" referrerPolicy="no-referrer" />
        )}
        <a className="sc-spin-card__source" href={spin.post.url} target="_blank" rel="noopener noreferrer">Post na X ↗</a>
      </div>
      <div className="sc-spin-card__diagnosis">
        <p className="sc-spin-card__verdict"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><IntensityMeter value={spin.intensity} /></p>
        <h3 id={`spin-${spin.id}-title`} className="sc-spin-card__headline"><Link href={`/klinika/${spin.id}`}>{spin.headline}</Link></h3>
        <p className="sc-spin-card__summary">{spin.summary}</p>
        {spin.technique_names.length > 0 && (
          <ul className="sc-spin-techniques" aria-label="Techniki">{spin.technique_names.map(name => <li key={name}>{name}</li>)}</ul>
        )}
        <footer className="sc-spin-card__foot">
          <span aria-label={`Trafna diagnoza: ${spin.opinions.positive}, nietrafna: ${spin.opinions.negative}`}>
            <span aria-hidden="true">▲ {spin.opinions.positive} · ▼ {spin.opinions.negative}</span>
          </span>
          <Link href={`/klinika/${spin.id}`}>Pełna diagnoza →</Link>
        </footer>
      </div>
    </article>
  );
}

/** Waga: udział postów ze spinem po każdej stronie — słupki od środka na zewnątrz, jeden neutralny kolor. */
export function SpinScale({ scale }: { scale: SpinScaleData }) {
  const left = sharePercent(scale.government);
  const right = sharePercent(scale.opposition);
  const diff = left !== null && right !== null ? left - right : null;
  const tilt = !scale.enough_data || diff === null ? 0 : Math.max(-12, Math.min(12, diff / 2));
  const verdict = !scale.enough_data
    ? `Za mało danych — waga pokaże wynik, gdy każda strona będzie miała co najmniej ${scale.min_sample} ocenionych postów.`
    : diff === 0 ? "Obie strony mają taki sam udział spinu."
    : `Więcej spinu: ${diff! > 0 ? "rządzący" : "opozycja"} (o ${Math.abs(diff!)} p.p.).`;
  const side = (camp: "government" | "opposition", share: number | null) => {
    const data = scale[camp];
    return (
      <div className={`sc-scale__side sc-scale__side--${camp}`}>
        <p className="sc-scale__label">{camp === "government" ? "Rządzący" : "Opozycja"}</p>
        <p className="sc-scale__value">{share === null ? "—" : `${share}%`}</p>
        <div className="sc-scale__track" title={`${data.spin} spin, ${data.partial} częściowy, ${data.no_spin} bez spinu`}>
          <span style={{ width: `${share ?? 0}%` }} />
        </div>
        <p className="sc-scale__n">{data.spin + data.partial} ze spinem · {data.assessed} ocenionych</p>
      </div>
    );
  };
  return (
    <section className="sc-scale" aria-labelledby="sc-scale-title">
      <header className="sc-scale__head">
        <h2 id="sc-scale-title">Waga spinu</h2>
        <p>Udział postów ze spinem wśród zatwierdzonych diagnoz z ostatnich {scale.window_days} dni. Porównujemy udział, nie liczbę — strony mają różną liczbę kont.</p>
      </header>
      <div className="sc-scale__body">
        {side("government", left)}
        <svg className="sc-scale__beam" viewBox="0 0 120 64" aria-hidden="true">
          <g style={{ transform: `rotate(${-tilt}deg)`, transformOrigin: "60px 22px" }}>
            <line x1="10" y1="22" x2="110" y2="22" />
            <circle cx="10" cy="22" r="5" /><circle cx="110" cy="22" r="5" />
          </g>
          <path d="M60 22 L48 58 L72 58 Z" />
        </svg>
        {side("opposition", right)}
      </div>
      <p className="sc-scale__verdict">{verdict}</p>
      <table className="sr-only">
        <caption>Waga spinu — dane</caption>
        <thead><tr><th>Strona</th><th>Spin</th><th>Częściowy</th><th>Bez spinu</th><th>Udział</th></tr></thead>
        <tbody>
          {(["government", "opposition"] as const).map(camp => (
            <tr key={camp}><td>{camp === "government" ? "Rządzący" : "Opozycja"}</td><td>{scale[camp].spin}</td><td>{scale[camp].partial}</td><td>{scale[camp].no_spin}</td><td>{sharePercent(scale[camp]) ?? "brak"}%</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
