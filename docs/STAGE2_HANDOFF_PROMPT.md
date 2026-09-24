# Stage 2 handoff — prompt for the implementing model

Copy everything below the line into a fresh session of a capable coding model (Claude Opus/Sonnet 5,
GPT-class, …) opened at the repository root on branch `codex/mvp-public-frontend`. The prompt is
self-contained; the referenced documents are in the repository.

Prepared 2026-09-24 by the stage-1 integrator. Stage 1 (design system + showcase) is finished,
built and pushed; this prompt is stage 2 (apply the system to every live surface).

---

## Prompt

You are taking over the front-end redesign of **spin.clinic** — a Polish public archive of
publications (Next.js 14 App Router + React 18, pnpm monorepo, Django backend). Stage 1 is done: a
complete design system lives in `packages/ui/src/kit/` (package subpath `@spin-clinic/ui/kit`,
styles `@spin-clinic/ui/kit/kit.css`) and is demonstrated at `/ui-kit`. Your job is **stage 2**:
rebuild every live page and panel with that system, page by page, without changing the backend and
without inventing content.

### Read first, in this order

1. `docs/UI_KIT.md` — the system as it actually exists: tokens, components, props, motion rules,
   cascade traps, fixture conventions, known limitations (§8) and stage-2 preconditions.
2. `docs/UI_KIT_PLAN.md` — the approved plan. The section «Дизайн страниц и панелей» is the
   per-route specification (desktop > 900px, phone ≤ 480px, tablet takes the desktop structure in two
   columns). The section «Что будет на этапе 2» is your scope. The section «Оживление каждого
   элемента» is the motion spec per element.
3. `docs/BRAND_AND_THEMES.md` — two themes (night/day), black/white with blue accent, Montserrat.
4. `docs/FRONTEND_MVP_DIRECTION.md`, `docs/FRONTEND_HANDOFF.md`, `docs/CLAUDE.md` if present —
   project rules that stay in force (Polish UI, no fake news content, security constraints).
5. The code itself: `packages/ui/src/kit/index.ts` (public exports), `packages/ui/src/kit/kit.css`
   (all component styles, tokens at the top), `packages/ui/src/kit/showcase/sections/*.tsx` (how each
   component is meant to be used).

Run the showcase while you work: `corepack pnpm --filter frontend-spin dev`, then open
`http://localhost:3000/ui-kit`. Compare every page you rebuild against it.

### Non-negotiable rules

- **Backend untouched.** Zero changes under `backend/`. API contracts, enums (including the `pastel`
  theme value) and endpoints stay as they are. X/YouTube/NIM/Groq integrations stay disabled.
- **No fabricated content.** Fixtures only from `packages/ui/src/kit/showcase/fixtures.ts`
  (fictional, `przyklad.invalid`, negative ids, "DEMO" images). Never write plausible-looking
  headlines. Never commit API keys, `.env` files or database data.
- **UI language is Polish.** Copy existing strings verbatim (the footer disclaimer «Zestawienie
  publikacji nie jest potwierdzeniem zawartych w nich twierdzeń» is editorial policy).
- **Only the kit.** New markup uses `.sc-*` classes and `--sc-*` tokens. No Tailwind utility classes
  in kit components or in rebuilt pages (`globals.css` overrides the Tailwind palette — see
  `docs/UI_KIT.md` §5). Transitions only through `useMotionTokens().t(name)`; never literal
  `transition` objects; animate only `transform`/`opacity`; no `will-change`; no `transition: all`.
- **Accessibility floor**: every state reachable by keyboard, readable without colour, 44px touch
  targets, focus ring `--sc-focus`, reduced motion = short fades, never nothing.
- **Amber is banned.** Glow and accents are blue. Hover on cards = blue glow behind the card via
  `--sc-ring`; hover on everything else = text/icon colour change only (no halo, no lift, no shadow).
- **Stage B never moves the grid.** A hovered card grows out of its slot on a layer above; see how
  `NewsCard` does it. Strips with `overflow-x: auto` need the `.sc-strip-bleed` pattern or the
  expanded card gets clipped.
- **Never `router.push` for card → material.** The portal uses `history.pushState`; a real App Router
  navigation unmounts the morph partner. Keep `window.location.search` in every address change.
- Never write `*/` inside a CSS comment in `kit.css` (it broke the build once). Next 14's CSS
  minifier rejects `:is()` / `:has()` — use plain selector lists.
- **Never run `next build` while `next dev` serves the same directory** — both write `.next/` and
  the dev server dies. Stop dev → build → restart.
- Tooling: pnpm is not on PATH on the owner's machine — use `corepack pnpm`. Gates before every
  commit: `corepack pnpm --filter frontend-spin typecheck` and `corepack pnpm --filter frontend-spin build`.
- Do not delete `public/illustrations/pastel/*` or old demo fixtures unless the step below says so.

### What the kit gives you (all exported from `@spin-clinic/ui/kit`)

- `NewsCard` (sizes `mini | compact | medium | large`, six data states, stages A/B built in, opens
  the portal automatically when rendered inside `PortalProvider`; `action` slot outside the link).
- `Button` (variants `primary | secondary | quiet | ghost | danger`, sizes `sm | md | lg`, shapes
  `rounded | pill | icon`, `pressed`, `loading`, `href` → `next/link`).
- `Dropdown` (modes `menu | single | multi`, `presentation: popover | sheet | auto`, full keyboard;
  the panel grows out of the trigger and the trigger becomes the panel's head row).
- Controls: `Checkbox`, `Radio`, `Switch`, `Segmented`, `SearchField`; icons in `kit/icons`.
- Motion primitives: `Morph`, `MorphList`, `MorphIndicator`, `Reveal`, `MorphValue`,
  `SkeletonMorph`, `ReorderableStrips`, `useDragDismiss`, `useScrollLock`, `useModalA11y`.
- Portal: `PortalProvider` (`historyMode: "none" | "query" | "path"`), `PortalLayer`,
  `usePortal`, `usePortalApiOptional`, `MaterialSurface` (`mode: "overlay" | "page"`).
- Navigation: `NavMenu`, `SiteFooter`, `ThemeToggle`; mobile: `useFocalBand`, `FoldedSection`,
  `Carousel`, `BottomSheet`, `CompactHeader`.
- `MotionRoot` is already mounted in `frontend-spin/app/providers.tsx`; Montserrat is already
  loaded in `frontend-spin/app/layout.tsx` as `--font-montserrat` (with `latin-ext`).

If a component is missing something a page needs, extend the kit (new prop, new `.sc-*` block
appended to `kit.css` under a comment `/* === Stage 2: <what> === */`) and show the new state in
the matching showcase section. Do not fork component logic into page files.

### Work plan — one step, one commit, gates green after each

Do the steps in this order. Each step ends with: typecheck + build green, the page checked in the
browser in both themes (`data-theme` on `<html>`), at 375 / 768 / 1280 widths, with keyboard, and
with `prefers-reduced-motion` emulated.

**Step 0 — foundation switch (one commit).**
1. Move `frontend-spin/app/ui-kit/template.tsx` to `frontend-spin/app/template.tsx` (page-enter
   transition for every route; scroll to top with `behavior: "instant"`).
2. Mount `PortalProvider historyMode="path"` and `PortalLayer` in `frontend-spin/app/providers.tsx`
   (with `resolveArticle` backed by the real feed data available on the page, `relatedFor` from
   the material context API already used by `ArticleContext.tsx`).
3. `ThemeSwitcher.tsx` → two options (Ciemny / Jasny) plus «Automatyczny» via `matchMedia`, built on
   the kit's `ThemeToggle`. Migrate a stored `localStorage['spin-theme'] === "pastel"` to `"light"`
   on read. Keep the anti-FOUC script working. The backend enum keeps `pastel`; the UI simply never
   sends it.
4. Fonts: make `body { font-family }` in `globals.css` use `var(--font-montserrat)`; remove the
   `@fontsource/ibm-plex-*` imports and dependencies; verify Polish diacritics render in Montserrat
   (DevTools → Rendered Fonts).
5. Delete the old demo routes `/box-materialu`, `/box-kontekstu`, `/osoby-publiczne/demo` and the
   fixtures `powiekszonyBoxDemo`, `boxKontekstuDemo`, `publicFigureDemo`; the showcase replaces them.

**Step 1 — home `/`** (`PortalHome.tsx`, `NajnowszeWiadomosci`, `TopTenRedakcji`, `TematDnia`,
`DrSpin`, `PrzekazDnia`, `TwojePaski`/`PersonalizedNews`, `Baza`, `MaterialStrip`, `NewsStrip`).
Section order stays as in `docs/BRAND_AND_THEMES.md`. Header = `NavMenu`, footer = `SiteFooter`.
Strips = `NewsCard compact` inside `ReorderableStrips` where the plan says reorderable, with
`.sc-strip-bleed`. TOP 10 = filters (pills, `Dropdown`, `SearchField`) + `medium` cards. Temat dnia
= `large` anchor + timeline of `compact`. Baza = sticky filter column + `medium` grid with
infinite scroll; count via `MorphValue`; filter changes animate via `MorphList`. Phone layout as
specified (carousels with snap, bottom-sheet filters, folded sections, focal band).
Sections that have no data (unpublished thread, missing Przekaz dnia) are not rendered at all.

**Step 2 — search `/search`** (`SearchPageContent.tsx`, `SearchBar.tsx`, `ExternalSearchResults`
stays disabled). Full-width `SearchField`, category pills, results grouped by date with sticky day
headers, `member_votes` block with vote labels in colour **and** text, «Pokaż starsze materiały» as
`Button secondary loading`.

**Step 3 — material `/material/[id]`** (`frontend-spin/app/material/[id]/page.tsx`,
`ArticleModal.tsx`, `ArticleContext.tsx`, `ArticleOpinions.tsx`, `VotingDetails.tsx`). Render
`MaterialSurface mode="page"`; the overlay opened from a card uses the same component. Source name
links to the original (`arrow-up-right`), date `tabular-nums`, actions row, context counters as
pills, related strip, opinions in two columns, `VotingDetails` for votes. Delete `ArticleModal.tsx`
once nothing imports it.

**Step 4 — threads `/thread/[slug]`** (`ThreadCard`, `HorizontalTimeline`, `TimelineGrid`,
`ThreadOpinions`, `ThreadExport`, `ThreadFavoriteButton`, `ShareOnX`). Sponsored thread keeps the
visible «Nitka sponsorowana» label on the thread and on every box. Phone: vertical timeline drawn
as the user scrolls.

**Step 5 — sources `/zrodla`** (`SourcesCatalog`, `SourceCoverage`, `ArchiveProgress`) and public
figures `/osoby-publiczne`, `/osoby-publiczne/[id]` (`PublicFigureDirectory`,
`PublicFigureProfile`, `ProfilPolitykaBox`) — tabs with `MorphIndicator`, no photos, no personal data
beyond confirmed roles. Public reader profile `/profile/[username]`.

**Step 6 — account** `/konto` (`MojeKonto`, `AccountDialog`, `AccountProfile`),
`/konto/nitki/nowa`, `/konto/nitki/[id]` (`MojaNitkaEditor`), `/profile` (settings: role, privacy
switch, theme `Segmented` with three options). Optimistic save with `Reveal` for errors; deletions
collapse via `MorphList`. Phone: bottom tabs instead of the side nav.

**Step 7 — editorial** `/editor` (`ThreadEditor`, `DraftAssistant`, `ImportStatus`),
`/editor/sources` (table → cards on phone, side drawer for «Nowe źródło» via `BottomSheet` on phone),
`/editor/political` (`PoliticalReview`, two-step form, statuses as text pills). Nothing here
publishes automatically and the UI must not promise it. `Dialog.tsx` → replace `<dialog>.showModal()`
with the kit's overlay pattern (`useModalA11y` + `useScrollLock`, AnimatePresence).

**Step 8 — informational pages** `/o-nas`, `/o-projekcie`, `/wsparcie` (support cards only when
the URLs are configured; otherwise honest text), `/dostep`, `/polityka-prywatnosci`,
`/zasady-korzystania`: `65ch` column, sticky table of contents, spring-scrolled anchors,
`PhaseList` timeline drawn on scroll.

**Step 9 — cleanup.** Remove CSS from `globals.css` and `packages/ui/src/components/**` that no
rebuilt page uses any more (measure with a grep of every class name; keep anything still referenced).
Move radii that still live in `globals.css` into components. Update `docs/UI_KIT.md` §8 (limitations
that no longer apply) and `docs/BRAND_AND_THEMES.md` (transition section becomes history). Run the
full check list from `docs/UI_KIT_PLAN.md` → «Проверка», including the 240-card frame measurement
(`makeArticles(240)` on the home grid, Performance panel, scroll + filter change at once) and the
regression proof that `git diff --stat` shows zero changes under `backend/`.

### Two decisions to ask the owner before you need them

1. **Backend for live pages.** Docker is not available on the owner's machine and system Python is
   3.14 while Django needs 3.10–3.13. Without the API, `/`, `/search`, `/zrodla` render empty. Either
   install Python 3.12 with the SQLite profile (see `docs/DEPLOYMENT.md` / `docs/FRONTEND_HANDOFF.md`
   → «Uruchomienie lokalne») or build stage 2 on fixtures and verify against the API later.
2. **Strip order persistence.** `ReorderableStrips` saves to `localStorage` and says so in the UI.
   A profile field would need a backend change, which is out of scope here.

### Definition of done for each page

- Looks like the per-route spec in `docs/UI_KIT_PLAN.md` on desktop and phone, in both themes.
- Every interaction animates through the kit primitives (no instant state jumps); hover/focus/keyboard
  parity; reduced motion gives fades.
- No Tailwind classes, no amber, no borders on cards, no fake content, no backend changes.
- `typecheck` + `build` green; one commit per step with a message that names the route.

Report at the end of each step: what changed, what you could not verify and why, and any kit gap
you had to fill.
