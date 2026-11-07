import type { ThreadElement } from '../../lib/community';
import { ClampedText } from './SocialPrimitives';
import { formatDatePl } from '../../lib/utils';

export function XPostCard({ item }: { item: ThreadElement }) {
  return <div className="sc-x-post-card">
    <header><span className="sc-social-avatar" aria-hidden="true">{(item.source_name || item.x_handle || 'X').charAt(0).toUpperCase()}</span>
      <span><strong>{item.source_name || item.x_handle || 'Wpis na X'}</strong>{item.x_handle && <small>@{item.x_handle}</small>}</span><span className="sc-x-mark" aria-label="X">𝕏</span></header>
    {item.published_date && <time dateTime={item.published_date}>{formatDatePl(item.published_date)}</time>}
    <ClampedText>{item.body || item.title}</ClampedText>
    <a href={item.url} target="_blank" rel="noopener noreferrer">Otwórz na X</a>
    {item.diagnosis_id != null && <a href={`/klinika/${item.diagnosis_id}`}>Zbadane: siła spinu {item.intensity}/100</a>}
  </div>;
}
