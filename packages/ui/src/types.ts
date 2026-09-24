export type Source = {
  id: number;
  name: string;
  url: string;
  source_type: string;
  is_active?: boolean;
  catalog_stage?: 'candidate' | 'configured' | 'excluded';
};

export type Article = {
  reference_only?: boolean;
  tags?: string[];
  content_status?: string;
  id: number;
  title: string;
  url: string;
  published_date: string | null;
  date_precision: 'time' | 'day';
  official?: { provider: string; api_url: string; fetched_at: string; date_label: string; status: string; document_type: string; attachments: {name: string; url: string}[] } | null;
  voting?: {
    term: number; sitting: number; number: number; motion: string; kind: string;
    counts: Record<string, number | string>; options: unknown[];
    matching_ballots: Ballot[]; matching_ballots_count: number; ballots_url: string;
  } | null;
  evidence_links?: { phrase: string; source_url: string; explanation: string }[];
  category: string;
  image_url: string;
  discovered_at: string | null;
  ingestion_method: string;
  category_reviewed: boolean;
  evidence_note: string;
  author: string;
  description: string;
  source: Source;
};

export type Ballot = { mp_id: number; name: string; club: string; vote: string; list_votes: Record<string, string> };

export type TimelineResponse = {
  direct_results?: Article[];
  query_intent?: 'member_votes';
  total: number;
  returned: number;
  truncated: boolean;
  page: number;
  next_page: number | null;
  timeline: Record<string, Article[]>;
};

export type ThreadItem = {
  is_sponsored?: boolean;
  sponsor_name?: string;
  sponsorship_label?: string;
  author_role?: 'editor' | 'journalist' | 'reader';
  id: number;
  position: number;
  editorial_note: string;
  author_name?: string;
  article: Article;
};

export type ThreadListItem = {
  is_sponsored?: boolean;
  sponsor_name?: string;
  sponsorship_label?: string;
  author_name?: string;
  author_role?: 'editor' | 'journalist' | 'reader';
  editorial_slot?: '' | 'government' | 'opposition';
  id: number;
  title: string;
  slug: string;
  thread_type: "factcheck" | "context" | "sponsored";
  is_featured: boolean;
  updated_at: string;
  items: ThreadItem[];
  published: boolean;
  item_count: number;
  description: string;
  image_url: string;
  views_count: number;
  created_at: string;
};

export type ThreadDetail = ThreadListItem & {
  items: ThreadItem[];
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type SiteConfig = {
  name: string;
  domain: string;
  tagline: string;
  primaryColor: string;
};
