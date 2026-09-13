export function EmptyNarrativeStrip() {
  return <div className="empty-narrative-strip" aria-label="Pusty układ nitki — bez opublikowanych materiałów">
    <div className="empty-narrative-anchor"><Placeholder main /></div>
    <div className="empty-narrative-track" tabIndex={0} aria-label="Miejsca na kolejne materiały — przewijaj poziomo">
      {[1, 2, 3, 4].map(position => <div className="empty-narrative-item" key={position}><Placeholder /></div>)}
    </div>
  </div>;
}

function Placeholder({ main = false }: { main?: boolean }) {
  return <div className="narrative-placeholder" aria-hidden="true">
    <span>{main ? 'WYDARZENIE GŁÓWNE' : 'KATEGORIA'}</span>
    <div className="placeholder-thumbnail" />
    <div className="placeholder-title-line" />
    <p><span>ŹRÓDŁO</span><span>DATA</span></p>
  </div>;
}
