import Link from 'next/link';
import Image from 'next/image';
import type { ThreadDetail } from '../types';
import { EmptyMaterialSlot, MaterialBox } from './MaterialBox';
import { MaterialStrip } from './MaterialStrip';

const PREVIEW_TYPES = ['WYWIAD', 'DOKUMENT URZĘDOWY', 'REPORTAŻ', 'ŚLEDZTWO', 'FILM'];

export function DrSpin({ thread }: { thread: ThreadDetail | null }) {
  const published = thread?.published ? thread : null;
  const anchorArticle = published?.items[0]?.article;
  return (
    <section className="mvp-section mvp-dr-spin" aria-label="Dr Spin">
      <header className="mvp-strip-heading">
        <div>
          <p className="mvp-editorial-kicker">SPIN.CLINIC · REDAKCJA</p>
          <h2>Dr Spin</h2>
        </div>
        <p>{published ? 'Dzisiejsza nitka redakcyjna' : 'Codzienna nitka redakcyjna'}</p>
      </header>
      <div className="mvp-dr-spin-track">
        {published ? (
          <Link href={`/thread/${published.slug}`} className="mvp-dr-spin-anchor">
            <span className="mvp-dr-spin-anchor-media">{anchorArticle?.image_url && <Image unoptimized src={anchorArticle.image_url} alt="" fill sizes="188px" className="mvp-dr-spin-anchor-image" />}</span>
            <span className="mvp-dr-spin-anchor-copy">
              <span>GŁÓWNY MATERIAŁ</span>
              <strong>{anchorArticle?.title ?? published.title}</strong>
              <small>{published.description || 'Otwórz nitkę redakcyjną →'}</small>
            </span>
          </Link>
        ) : (
          <div className="mvp-dr-spin-anchor mvp-dr-spin-anchor-placeholder" role="img" aria-label="Główny materiał Dr Spina — miejsce na post lub materiał otwierający">
            <span className="mvp-dr-spin-anchor-media" aria-hidden="true" />
            <span className="mvp-dr-spin-anchor-copy">
              <span>GŁÓWNY MATERIAŁ</span>
              <strong>POST LUB MATERIAŁ OTWIERAJĄCY</strong>
              <small>Tu Dr Spin krótko wyjaśni, co sprawdzamy i dlaczego.</small>
            </span>
          </div>
        )}
        <MaterialStrip label="Dr Spin — materiały wyjaśniające" height="sm">
          {published && published.items.length > 1
            ? published.items.slice(1, 6).map((item) => <MaterialBox key={item.id} article={item.article} />)
            : PREVIEW_TYPES.map((type, index) => <EmptyMaterialSlot key={type} index={index + 2} label={type} />)}
        </MaterialStrip>
      </div>
    </section>
  );
}
