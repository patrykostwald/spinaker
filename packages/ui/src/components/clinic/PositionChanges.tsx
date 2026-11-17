import type { PositionChange } from "../../lib/clinic";

const day = new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "long", year: "numeric" });
const when = (iso: string) => day.format(new Date(`${iso}T12:00:00`));

/** Zmiana zdania (właściciel 6.10): wcześniejsza wypowiedź tej samej osoby obok obecnej - cytat, data, źródło i jedno neutralne zdanie.
 *  Dwie równe karty w rzędzie (Common Region, Proximity); źródła na dole obu kart w jednej linii. */
export function PositionChanges({ id, block }: { id: number; block?: { items: PositionChange[]; note: string } | null }) {
  if (!block?.items.length) return null;
  return (
    <section className="sc-spin-detail__section sc-position" id={`spin-${id}-zmiana-zdania`} aria-labelledby={`spin-${id}-zmiana-zdania-title`}>
      <h2 id={`spin-${id}-zmiana-zdania-title`}>Zmiana zdania</h2>
      <p className="sc-spin-detail__intro">{block.note}</p>
      <ol className="sc-position__list">
        {block.items.map(item => (
          <li key={`${item.kind}-${item.url}`} className="sc-position__item">
            <div className="sc-position__pair">
              <figure className="sc-position__card" data-side="then">
                <figcaption><span>Wcześniej mówił(a)</span><time dateTime={item.date}>{when(item.date)}</time></figcaption>
                <blockquote>„{item.quote_then}”</blockquote>
                <a href={item.url} target="_blank" rel="noopener noreferrer">{item.kind_label} ↗</a>
              </figure>
              <figure className="sc-position__card" data-side="now">
                <figcaption><span>Teraz</span><time dateTime={item.now_date}>{when(item.now_date)}</time></figcaption>
                <blockquote>„{item.quote_now}”</blockquote>
                <a href={item.now_url} target="_blank" rel="noopener noreferrer">Wpis na X ↗</a>
              </figure>
            </div>
            <p className="sc-position__why">{item.explanation}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
