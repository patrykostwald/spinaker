import type { ThreadDetail } from '../types';
import { Button } from '../kit';

function Column({ title, thread }: { title: string; thread: ThreadDetail | null }) {
  const published = thread?.published ? thread : null;
  return (
    <div className="sc-daily-message-column">
      <p className="sc-daily-message-label">{title}</p>
      {published ? (
        <Button href={`/thread/${published.slug}`} variant="quiet">{published.title} ↗</Button>
      ) : (
        <p className="sc-daily-message-empty">W przygotowaniu</p>
      )}
    </div>
  );
}

export function PrzekazDnia({ government, opposition }: { government: ThreadDetail | null; opposition: ThreadDetail | null }) {
  if (!government?.published && !opposition?.published) return null;
  return (
    <section className="sc-daily-message" aria-label="Przekaz dnia">
      <header><h2>Przekaz dnia</h2></header>
      <div className="sc-daily-message-grid">
        <Column title="Rządzący" thread={government} />
        <Column title="Opozycja" thread={opposition} />
      </div>
    </section>
  );
}
