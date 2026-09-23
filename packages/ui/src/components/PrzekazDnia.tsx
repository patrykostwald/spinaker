import Link from 'next/link';
import type { ThreadDetail } from '../types';

function Column({ title, thread }: { title: string; thread: ThreadDetail | null }) {
  const published = thread?.published ? thread : null;
  return (
    <div className="mvp-przekaz-column">
      <p className="mvp-przekaz-label">{title}</p>
      {published ? (
        <Link href={`/thread/${published.slug}`} className="mvp-przekaz-link">{published.title} ↗</Link>
      ) : (
        <p className="mvp-przekaz-empty">W przygotowaniu</p>
      )}
    </div>
  );
}

export function PrzekazDnia({ government, opposition }: { government: ThreadDetail | null; opposition: ThreadDetail | null }) {
  if (!government?.published && !opposition?.published) return null;
  return (
    <section className="mvp-section mvp-przekaz-dnia" aria-label="Przekaz dnia">
      <header className="mvp-strip-heading"><h2>Przekaz dnia</h2></header>
      <div className="mvp-przekaz-grid">
        <Column title="Rządzący" thread={government} />
        <Column title="Opozycja" thread={opposition} />
      </div>
    </section>
  );
}
