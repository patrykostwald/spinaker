"use client";

import { DiscussionCounts } from "./ClinicDiscussion";

import Link from "next/link";
import { Dialog } from "../Dialog";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Party, SpinAuthor, SpinCardData, SpinScale as SpinScaleData, Verdict } from "../../lib/clinic";
import { sharePercent, techniqueLabel } from "../../lib/clinic";
import { diagnosisPresentation } from "../../lib/diagnosisPresentation";
import { formatDateTimePl } from "../../lib/utils";
import { ShareSpinOnX } from "./ShareSpinOnX";
import { useFeature } from "../../lib/features";

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

export function SpinAuthorRow({ author, publishedAt, size = "md", caption }: {
  author: SpinAuthor; publishedAt: string; size?: "md" | "lg";
  /** Opcjonalny napis nad metką partii w prawym rogu (np. „Opozycja”). */
  caption?: string;
}) {
  return (
    <header className="sc-spin-author">
      <SpinAvatar author={author} size={size} />
      <div className="sc-spin-author__text">
        <p className="sc-spin-author__name">
          {author.figure_id ? <Link href={`/osoby-publiczne/${author.figure_id}`}>{author.name}</Link> : author.name}
          {/* Partia zwykłym tekstem przy nazwisku („Mariusz Błaszczak, PiS”) — decyzja właściciela 29.09. */}
          {author.party?.short ? <span className="sc-spin-author__party-text">, {author.party.short}</span> : null}
        </p>
        <p className="sc-spin-author__meta">
          <a href={author.account_url} target="_blank" rel="noopener noreferrer">@{author.handle}</a>
          {" · "}<time dateTime={publishedAt}>{formatDateTimePl(publishedAt)}</time>
        </p>
      </div>
      {caption ? <span className="sc-spin-author__party"><span className="sc-spin-author__caption">{caption}</span></span> : null}
    </header>
  );
}

export function VerdictTag({ verdict, label }: { verdict: Verdict; label: string }) {
  return <span className="sc-verdict" data-verdict={verdict}>{verdict === "unclear" ? "Nie da się ocenić" : label}</span>;
}

export function IntensityMeter({ value }: { value: number }) {
  return (
    <span className="sc-intensity" data-level={value >= 70 ? "high" : value >= 30 ? "mid" : "low"} title="Siła spinu według diagnozy (0–100): jak mocno wpis opiera się na technikach perswazji">
      <span className="sc-intensity__track" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></span>
      <span className="sc-intensity__value">Siła spinu {value}/100</span>
    </span>
  );
}

export function AiTag() {
  return <span className="sc-ai-tag" title="Treść przygotowana automatycznie przez AI — nikt nie edytuje jej treści; tryb publikacji opisano przy analizie">AI</span>;
}

/**
 * Zwarty wiersz diagnozy — rozmiar boxa z pasków: po lewej miniatura (zdjęcie z wpisu albo awatar autora),
 * po prawej obóz, werdykt, nagłówek diagnozy i autor. Cały wiersz prowadzi do pełnej diagnozy.
 */
export function SpinRow({ spin, withSummary = false, badge, returnTo, onOpen }: { spin: SpinCardData; withSummary?: boolean; withTechniques?: boolean; badge?: string; returnTo?: string; onOpen?: () => void }) {
  const image = spin.post.media.find(item => item.url);
  const href = `/klinika/${spin.id}${returnTo ? `?returnTo=${encodeURIComponent(returnTo)}` : ""}`;
  return (
    <article className="sc-spin-row" data-verdict={spin.verdict} aria-labelledby={`spin-row-${spin.id}`}>
      {/* Siatka 2×2: kto i kiedy obok tytułu, miniatura obok danych diagnozy. */}
      <div className="sc-spin-row__side">
        <span className="sc-spin-row__thumb">
          {image
            // eslint-disable-next-line @next/next/no-img-element -- miniatura z oficjalnego API X
            ? <img src={image.url} alt="" loading="lazy" referrerPolicy="no-referrer" />
            : <SpinAvatar author={spin.author} size="lg" />}
          <span className="sc-spin-row__verdict"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} />{badge ? <span className="sc-spin-row__badge">{badge}</span> : null}</span>
        </span>
        <div className="sc-spin-row__who">
          <p className="sc-spin-row__author">{spin.author.name}</p>
          <p className="sc-spin-row__date"><time dateTime={spin.post.published_at}>{formatDateTimePl(spin.post.published_at)}</time></p>
        </div>
      </div>
      <div className="sc-spin-row__body">
        <h3 id={`spin-row-${spin.id}`} className="sc-spin-row__title"><Link href={href} onClick={onOpen}>{spin.headline}</Link></h3>
        <SpinListMetrics spin={spin} />
        <DiscussionCounts {...spin} />
        {withSummary && spin.summary ? <p className="sc-spin-row__summary">{spin.summary}</p> : null}
      </div>
    </article>
  );
}

/** Te same obliczenia co SpinSummary, w czterech kolumnach pod tytułem. */
export function SpinListMetrics({ spin }: { spin: SpinCardData }) {
  const { checked, claims, council, typeCount, families } = diagnosisPresentation({
    ...spin, techniques: spin.technique_types ?? spin.technique_names.map(name => ({ name })),
  });
  const unverified = claims.find(claim => claim.key === "unverified")?.count ?? 0;
  return <dl className="sc-list-metrics" aria-label="Dane diagnozy">
    <div><dt>Siła spinu</dt><dd className="sc-list-metrics__strength">{spin.intensity}<small>/100</small></dd>
      <span className="sc-list-metrics__track" aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(100, spin.intensity))}%` }} /></span></div>
    <div><dt>Konsylium AI</dt><dd>{council.agreement ?? "—"}</dd><small>ten sam werdykt</small></div>
    <div><dt>Twierdzenia</dt><dd>{checked}</dd><small>{unverified > 0 ? `sprawdzone z ${checked + unverified}` : "sprawdzone"}</small></div>
    <div><dt>Techniki</dt><dd>{typeCount}</dd><small>{techniqueLabel(typeCount)}</small>
      <span className="sc-list-metrics__families">{families.filter(family => family.key !== "inne").map(family =>
        <i key={family.key} data-family={family.key} data-empty={!family.count || undefined} role="img" aria-label={`${family.label}: ${family.count}`} title={`${family.label}: ${family.count}`} />)}</span></div>
  </dl>;
}

/** Karta: po lewej post (autor, treść, zdjęcie), po prawej diagnoza. */
export function SpinCard({ spin }: { spin: SpinCardData }) {
  const ACCOUNTS_ENABLED = useFeature('ACCOUNTS_ENABLED');
  const image = spin.post.media.find(item => item.url);
  return (
    <article className="sc-spin-card" data-verdict={spin.verdict} aria-labelledby={`spin-${spin.id}-title`}>
      <div className="sc-spin-card__post">
        <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} />
        <p className="sc-spin-card__text">{spin.post.text}</p>
        {image && (
          // eslint-disable-next-line @next/next/no-img-element -- miniatura z oficjalnego API X
          <img className="sc-spin-card__media" src={image.url} alt={image.alt || "Załącznik do wpisu"} loading="lazy" referrerPolicy="no-referrer" />
        )}
        <a className="sc-spin-card__source" href={spin.post.url} target="_blank" rel="noopener noreferrer">Wpis na X ↗</a>
      </div>
      <div className="sc-spin-card__diagnosis">
        <p className="sc-spin-card__verdict"><span className="sc-spin-card__camp">{spin.camp_label}</span><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><IntensityMeter value={spin.intensity} /></p>
        <h3 id={`spin-${spin.id}-title`} className="sc-spin-card__headline"><Link href={`/klinika/${spin.id}`}>{spin.headline}</Link></h3>
        <p className="sc-spin-card__summary">{spin.summary}</p>
        {spin.technique_names.length > 0 && (
          <ul className="sc-spin-techniques" aria-label="Techniki">{spin.technique_names.map(name => <li key={name}>{name}</li>)}</ul>
        )}
        <footer className="sc-spin-card__foot">
          {ACCOUNTS_ENABLED ? <DiscussionCounts {...spin} /> : <AiTag />}
          <span className="sc-spin-card__links"><ShareSpinOnX id={spin.id} /><Link href={`/klinika/${spin.id}`}>Pełna diagnoza →</Link></span>
        </footer>
      </div>
    </article>
  );
}

/** Waga — dwie liczby i dwa paski: udział wpisów ze spinem po każdej stronie (jeden neutralny kolor). */
export function SpinScale({ scale }: { scale: SpinScaleData }) {
  const left = sharePercent(scale.government);
  const right = sharePercent(scale.opposition);
  const diff = left !== null && right !== null ? left - right : null;
  const verdict = !scale.enough_data
    ? `Za mało danych — wynik pokażemy, gdy każda strona będzie miała co najmniej ${scale.min_sample} ocenionych wpisów.`
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
            <div key={camp} className="sc-scale__row" data-camp={camp}>
              <span className="sc-scale__label">{camp === "government" ? "Rządzący" : "Opozycja"}</span>
              <span className="sc-scale__track"><span style={{ width: `${share ?? 0}%` }} /></span>
              <strong className="sc-scale__value">{share === null ? "—" : `${share}%`}</strong>
              <span className="sc-scale__n">{data.spin + data.partial}/{data.assessed}</span>
            </div>
          );
        })}
      </div>
      <p className="sc-scale__verdict">{verdict} Porównujemy udział wpisów ze spinem, nie ich liczbę.</p>
    </section>
  );
}

/** „Jak czytać wynik” — krótko, żeby nikt nie czytał 70/100 jako „70% kłamstwa” (audyt 046). */
export function HowToRead({ interview = false }: { interview?: boolean }) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" className="sc-howto-trigger" aria-haspopup="dialog" onClick={() => setOpen(true)}>Jak czytać wynik?</button>
    <Dialog open={open} onClose={() => setOpen(false)} title="Jak czytać wynik?" className="sc-howto-panel">
    <dl>
      <div><dt>Siła spinu 0–100</dt><dd>Jak mocno {interview ? "wypowiedź opiera" : "komunikat opiera"} się na technikach perswazji. To nie procent kłamstwa i nie ocena osoby.</dd></div>
      <div><dt>Konsylium AI</dt><dd>Ile modeli wydało ten sam werdykt co diagnoza końcowa, np. 3/4.</dd></div>
      <div><dt>Twierdzenia</dt><dd>Sprawdzone ze źródłami: potwierdzone, sprzeczne albo wprowadzające w błąd. „Niezweryfikowane” znaczy: bez źródła — nie że to fałsz.</dd></div>
      <div><dt>Techniki</dt><dd>Ile różnych technik wskazano, z dosłownym cytatem, w trzech rodzinach: dane, emocje, spór.</dd></div>
    </dl>
    <Link className="sc-howto-methodology" href="/metodologia">Pełna metodologia →</Link>
    </Dialog>
  </>;
}

/** Stick only when the whole panel fits below the site header. Recheck after images/fonts/layout change. */
export function FitStickyAside({ children, className = "", label }: { children: ReactNode; className?: string; label?: string }) {
  const ref = useRef<HTMLElement>(null);
  const [fits, setFits] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const measure = () => setFits(window.innerWidth >= 1024 && element.getBoundingClientRect().height <= window.innerHeight - 120);
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    window.addEventListener("resize", measure);
    measure();
    return () => { observer.disconnect(); window.removeEventListener("resize", measure); };
  }, []);
  return <aside ref={ref} className={`sc-fit-sticky ${className}`} data-fits={fits || undefined} aria-label={label}>{children}</aside>;
}
