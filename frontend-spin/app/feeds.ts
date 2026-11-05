import { RSS_FEEDS } from '@spin-clinic/ui';

/** `alternates.types` z kanałami RSS: strony z własnym `alternates` (canonical) nie dziedziczą ich z layoutu. */
export const RSS_ALTERNATE_TYPES = { 'application/rss+xml': RSS_FEEDS.map(feed => ({ url: feed.href, title: `spin.clinic: ${feed.label.toLowerCase()}` })) };
