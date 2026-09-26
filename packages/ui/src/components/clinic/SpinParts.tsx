"use client";

import Link from "next/link";
import type { Party, SpinAuthor, SpinCardData, SpinScale as SpinScaleData, Verdict } from "../../lib/clinic";
import { sharePercent } from "../../lib/clinic";
import { formatDateTimePl } from "../../lib/utils";
import { ShareSpinOnX } from "./ShareSpinOnX";
import { ACCOUNTS_ENABLED } from "../../lib/features";

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

/**
 * Zwarty wiersz diagnozy — rozmiar boxa z pasków: po lewej miniatura (zdjęcie z posta albo awatar autora),
 * po prawej obóz, werdykt, nagłówek diagnozy i autor. Cały wiersz prowadzi do pełnej diagnozy.
 */
export function SpinRow({ spin, withSummary = false }: { spin: SpinCardData; withSummary?: boolean }) {
  const image = spin.post.media.find(item => item.url);
  return (
    <article className="sc-spin-row" data-verdict={spin.verdict} aria-labelledby={`spin-row-${spin.id}`}>
      <span className="sc-spin-row__thumb">
        {image
          // eslint-disable-next-line @next/next/no-img-element -- miniatura z oficjalnego API X
          ? <img src={image.url} alt="" loading="lazy" referrerPolicy="no-referrer" />
          : <SpinAvatar author={spin.author} size="lg" />}
        <PartyBadge party={spin.author.party} />
      </span>
      <div className="sc-spin-row__body">
        <p className="sc-spin-row__meta"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><IntensityMeter value={spin.intensity} /></p>
        <h3 id={`spin-row-${spin.id}`} className="sc-spin-row__title"><Link href={`/klinika/${spin.id}`}>{spin.headline}</Link></h3>
        {withSummary && spin.summary ? <p className="sc-spin-row__summary">{spin.summary}</p> : null}
        <p className="sc-spin-row__author">{spin.author.name} · @{spin.author.handle} · <time dateTime={spin.post.published_at}>{formatDateTimePl(spin.post.published_at)}</time></p>
      </div>
    </article>
  );
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
        <p className="sc-spin-card__verdict"><span className="sc-spin-card__camp">{spin.camp_label}</span><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><IntensityMeter value={spin.intensity} /></p>
        <h3 id={`spin-${spin.id}-title`} className="sc-spin-card__headline"><Link href={`/klinika/${spin.id}`}>{spin.headline}</Link></h3>
        <p className="sc-spin-card__summary">{spin.summary}</p>
        {spin.technique_names.length > 0 && (
          <ul className="sc-spin-techniques" aria-label="Techniki">{spin.technique_names.map(name => <li key={name}>{name}</li>)}</ul>
        )}
        <footer className="sc-spin-card__foot">
          {ACCOUNTS_ENABLED ? <span aria-label={`Trafna diagnoza: ${spin.opinions.positive}, nietrafna: ${spin.opinions.negative}`}>
            <span aria-hidden="true">▲ {spin.opinions.positive} · ▼ {spin.opinions.negative}</span>
          </span> : <AiTag />}
          <span className="sc-spin-card__links"><ShareSpinOnX id={spin.id} /><Link href={`/klinika/${spin.id}`}>Pełna diagnoza →</Link></span>
        </footer>
      </div>
    </article>
  );
}

/** Waga — dwie liczby i dwa paski: udział postów ze spinem po każdej stronie (jeden neutralny kolor). */
export function SpinScale({ scale }: { scale: SpinScaleData }) {
  const left = sharePercent(scale.government);
  const right = sharePercent(scale.opposition);
  const diff = left !== null && right !== null ? left - right : null;
  const verdict = !scale.enough_data
    ? `Za mało danych — wynik pokażemy, gdy każda strona będzie miała co najmniej ${scale.min_sample} ocenionych postów.`
    : diff === 0 ? "Obie strony mają taki sam udział spinu."
    : `Więcej spinu: ${diff! > 0 ? "rządzący" : "opozycja"} (o ${Math.abs(diff!)} p.p.).`;
  return (
    <section className="sc-scale" aria-labelledby="sc-scale-title">
      <h2 id="sc-scale-title" className="sc-scale__title">Waga spinu · {scale.window_days} dni</h2>
      <div className="sc-scale__rows">
        {(["government", "opposition"] as const).map(camp => {
          const share = camp === "government" ? left : right;
          const data = scale[camp];
          return (
            <div key={camp} className="sc-scale__row">
              <span className="sc-scale__label">{camp === "government" ? "Rządzący" : "Opozycja"}</span>
              <span className="sc-scale__track"><span style={{ width: `${share ?? 0}%` }} /></span>
              <strong className="sc-scale__value">{share === null ? "—" : `${share}%`}</strong>
              <span className="sc-scale__n">{data.spin + data.partial}/{data.assessed}</span>
            </div>
          );
        })}
      </div>
      <p className="sc-scale__verdict">{verdict} Porównujemy udział postów ze spinem, nie ich liczbę.</p>
    </section>
  );
}
