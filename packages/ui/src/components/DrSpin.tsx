import Image from 'next/image';
import Link from 'next/link';
import type { ThreadDetail } from '../types';
import { NewsCard } from '../kit/NewsCard';
import { ThreadFavoriteButton } from './ThreadFavoriteButton';

/** Only an actually published thread may appear as Dr Spin content. */
export function DrSpin({ thread }: { thread: ThreadDetail | null }) {
  const published = thread?.published ? thread : null;
  if (!published) return null;
  const anchorArticle = published.items[0]?.article;
  return (
    <section className="mvp-section mvp-dr-spin" aria-label="Dr Spin">
      <header className="mvp-strip-heading">
        <div><p className="mvp-editorial-kicker">SPIN.CLINIC · REDAKCJA</p><h2>Dr Spin</h2></div>
        <div className="mvp-dr-spin-actions"><p>Dzisiejsza nitka redakcyjna</p><ThreadFavoriteButton thread={published} /></div>
      </header>
      <div className="mvp-dr-spin-track">
        <Link href={`/thread/${published.slug}`} className="mvp-dr-spin-anchor">
          <span className="mvp-dr-spin-anchor-media">{anchorArticle?.image_url && <Image unoptimized src={anchorArticle.image_url} alt="" fill sizes="188px" className="mvp-dr-spin-anchor-image" />}</span>
          <span className="mvp-dr-spin-anchor-copy"><span>GŁÓWNY MATERIAŁ</span><strong>{anchorArticle?.title ?? published.title}</strong><small>{published.description || 'Otwórz nitkę redakcyjną →'}</small></span>
        </Link>
        {published.items.length > 1 ? <div className="news-strip-track sc-strip-bleed" aria-label="Dr Spin — materiały wyjaśniające">
          {published.items.slice(1, 6).map((item) => <div key={item.id} className="news-strip-item"><NewsCard article={item.article} size="compact" /></div>)}
        </div> : null}
      </div>
    </section>
  );
}
