import type { SpinReception } from "../../lib/clinic";

const number = new Intl.NumberFormat("pl-PL");
const fmt = (value: number | null) => (value === null || value === undefined ? "-" : number.format(value));

/** Jak zadziałało (właściciel 6.10): odbiór wpisu dobę później - liczniki, udziały odpowiedzi i werdykt z notą o metodzie.
 *  Jedno wyróżnienie (werdykt, Von Restorff); cztery równe kafelki liczników (Common Region); słupki w jednej siatce,
 *  podpisy i procenty w tych samych kolumnach (wspólne linie). Tylko liczby zbiorcze - bez danych osób prywatnych. */
export function SpinReceptionBlock({ id, block }: { id: number; block?: SpinReception | null }) {
  if (!block) return null;
  const titleId = `spin-${id}-odbior-title`;
  return (
    <section className="sc-spin-detail__section sc-reception" id={`spin-${id}-odbior`} aria-labelledby={titleId}>
      <h2 id={titleId}>Jak zadziałało <span className="sc-reception__when">po {block.hours} h</span></h2>
      {block.verdict ? (
        <p className="sc-reception__verdict" data-verdict={block.verdict.key}>
          <strong>{block.verdict.label}</strong>
          <span>próbka {block.sample} odpowiedzi</span>
        </p>
      ) : null}

      {block.metrics.length ? (
        <ul className="sc-reception__metrics" aria-label="Liczniki wpisu: przy pobraniu i po dobie">
          {block.metrics.map(m => (
            <li key={m.key} className="sc-reception__metric">
              <span className="sc-reception__label">{m.label}</span>
              <strong>{fmt(m.after)}</strong>
              <span className="sc-reception__before">{m.before === null || m.before === undefined ? "bez odczytu przy pobraniu" : `przy pobraniu: ${fmt(m.before)}`}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {block.shares.length ? (
        <div className="sc-reception__group">
          <h3>Odpowiedzi</h3>
          <ul className="sc-reception__bars">
            {block.shares.map(s => (
              <li key={s.key}>
                <span className="sc-reception__label">{s.label}</span>
                <span className="sc-reception__track" aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(100, s.share))}%` }} /></span>
                <span className="sc-reception__pct">{s.share}%</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {block.sentiment.length ? (
        <div className="sc-reception__group">
          <h3>Ton odpowiedzi</h3>
          <div className="sc-reception__tone" role="img" aria-label={block.sentiment.map(t => `${t.label} ${t.share}%`).join(", ")}>
            {block.sentiment.map(t => <i key={t.key} data-tone={t.key} style={{ width: `${t.share}%` }} />)}
          </div>
          <ul className="sc-reception__legend">
            {block.sentiment.map(t => <li key={t.key} data-tone={t.key}><span aria-hidden="true" />{t.label} {t.share}%</li>)}
          </ul>
        </div>
      ) : null}

      {block.phrases.length ? (
        <div className="sc-reception__group">
          <h3>Powtarzane zwroty</h3>
          <ul className="sc-reception__phrases">
            {block.phrases.map(p => <li key={p.text}>„{p.text}” <span>{p.count} odp.</span></li>)}
          </ul>
        </div>
      ) : null}

      {block.figures.length ? (
        <div className="sc-reception__group">
          <h3>Odpowiedzi osób publicznych</h3>
          <ul className="sc-reception__figures">
            {block.figures.map(f => <li key={f.url}><a href={f.url} target="_blank" rel="noopener noreferrer">{f.name} <span>@{f.handle}</span> ↗</a></li>)}
          </ul>
        </div>
      ) : null}

      <p className="sc-reception__note">{block.note}</p>
    </section>
  );
}
