/**
 * Jaśniejsze okienko z etykietą u góry (jak blok w odpowiedzi czatu AI) — sama forma, bez przycisku
 * kopiowania. `mode="diagram"` — tekst o stałej szerokości, bez łamania linii; `mode="text"` — akapit.
 */

export function CopyBlock({ label, text, mode = "diagram", caption }: { label: string; text: string; mode?: "diagram" | "text"; caption?: string }) {
  return (
    <figure className="sc-onas-copy" data-mode={mode}>
      <div className="sc-onas-copy__bar">
        <span className="sc-onas-copy__label">{label}</span>
      </div>
      {mode === "diagram" ? (
        <pre className="sc-onas-copy__pre" tabIndex={0} aria-label={caption ?? label}>{text}</pre>
      ) : (
        <p className="sc-onas-copy__text">{text}</p>
      )}
      {caption ? <figcaption className="sc-onas-copy__caption">{caption}</figcaption> : null}
    </figure>
  );
}
