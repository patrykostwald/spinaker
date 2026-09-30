import type { Source } from '../types';

/** Match only a stored, confirmed social identity; never infer ownership from names. */
export function channelIdentity(value: string): string | null {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    const host = url.hostname.toLowerCase().replace(/^www\./, '');
    const path = url.pathname.replace(/\/+$/, '');
    if (['x.com', 'twitter.com'].includes(host) && /^\/[\w]{1,15}$/.test(path)) return `x:${path.toLowerCase()}`;
    if (['youtube.com', 'm.youtube.com'].includes(host) && /^\/(channel\/[^/]+|@[^/]+)$/.test(path)) {
      return `youtube:${path.startsWith('/@') ? path.toLowerCase() : path}`;
    }
  } catch { /* Missing or invalid URL provides no identity. */ }
  return null;
}

export function sourceDirectory(sources: Source[]) {
  const publishers = sources.filter(source => !channelIdentity(source.url));
  const owners = new Map<string, Source[]>();
  for (const source of publishers) {
    for (const url of [source.youtube_url, source.x_handle ? `https://x.com/${source.x_handle}` : '']) {
      const identity = channelIdentity(url || '');
      if (identity) owners.set(identity, [...(owners.get(identity) ?? []), source]);
    }
  }
  const groups = new Map<number, { source: Source; members: Source[] }>();
  for (const source of sources) {
    const identity = channelIdentity(source.url);
    const matches = identity ? owners.get(identity) : undefined;
    // Ambiguous ownership is not sufficient evidence to merge records.
    const owner = matches?.length === 1 ? matches[0] : source;
    const group = groups.get(owner.id) ?? { source: owner, members: [] };
    group.members.push(source);
    groups.set(owner.id, group);
  }
  return [...groups.values()];
}

export function directoryGroup(source: Source): 'top' | 'media' | 'publiczne' {
  let host = '';
  try { host = new URL(source.url).hostname.toLowerCase().replace(/^www\./, ''); } catch { /* No domain. */ }
  // Explicit institutional domains also cover API feeds typed as RSS.
  if (source.source_type === 'institution' || ['sejm.gov.pl', 'api.sejm.gov.pl'].includes(host)) return 'publiczne';
  return source.portal_group ?? 'media';
}
