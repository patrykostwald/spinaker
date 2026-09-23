# UI Kit spin.clinic — справочник

Источник истины — код на коммите `7051357` (`packages/ui/src/kit/**`, `frontend-spin/app/ui-kit/**`).
План — `docs/UI_KIT_PLAN.md`. Там, где код и план расходятся, ниже описан **код**, а расхождение
занесено в список «Расхождения с планом» в конце документа.

## 1. Назначение и изоляция

Библиотека — новый визуальный язык spin.clinic (две темы, чёрный/белый + синий акцент,
Montserrat, «сплошное движение»), построенный **рядом** со старым интерфейсом, а не поверх него.

- **Пространство имён.** Все классы — с префиксом `sc-` (БЭМ-подобно: `sc-card`, `sc-card__media`,
  `sc-card--large`), все переменные — с префиксом `--sc-`. Состояния — `data`-атрибуты
  (`data-size`, `data-state`, `data-stage`), не классы-модификаторы.
- **Точка входа.** `@spin-clinic/ui/kit` — отдельный подпуть `exports` в `packages/ui/package.json`,
  главный barrel (`@spin-clinic/ui`) не трогается:
  ```jsonc
  "exports": {
    ".":            { "types": "./src/index.ts", "default": "./src/index.ts" },
    "./kit":        { "types": "./src/kit/index.ts", "default": "./src/kit/index.ts" },
    "./kit/kit.css": "./src/kit/kit.css"
  }
  ```
  (третья запись, `./kit/kit.css`, — фактическое расширение контракта волны 0, см. «Расхождения»).
- **CSS.** `kit.css` подключается в `frontend-spin/app/layout.tsx` **строкой сразу после**
  `import "./globals.css"` — порядок каскада для этого и держится:
  ```ts
  import "./globals.css";
  // Библиотека нового визуального языка. Обязательно ПОСЛЕ globals.css.
  import "@spin-clinic/ui/kit/kit.css";
  ```
- **Нулевые изменения на этапе 1.** `frontend-spin/app/globals.css`, `packages/ui/src/components/**`
  и `backend/**` не тронуты ни одной строкой. `layout.tsx` подключает `Montserrat` через
  `next/font/google` (`variable: "--font-montserrat"`) и вешает класс переменной на `<html>`, но
  `body { font-family }` в `globals.css` остаётся на IBM Plex — Montserrat работает только там, где
  используется `--sc-font-sans`.
- **Правило компонентов.** Ни одной утилиты Tailwind внутри `kit/**` — иначе элемент возвращается в
  слой перезаписи `globals.css` (строки 27–62) и темится от `--surface`/`--color-primary` вместо
  `--sc-*`. Правило зафиксировано в шапке `kit.css` и держится по всем файлам библиотеки.

## 2. Токены

Объявлены под теми же селекторами `html[data-theme]`, что и старый механизм, плюс локальный
`[data-sc-theme]` — им пользуется только витрина, чтобы показывать обе темы рядом на одной
странице без переключения `html[data-theme]` целиком.

### 2.1 Цвет

| Токен | Ночь (`dark`) | День (`light`/`pastel`) |
|---|---|---|
| `--sc-bg` | `#08090b` | `#ffffff` |
| `--sc-surface` | `#111317` | `#ffffff` |
| `--sc-surface-2` | `#1a1d22` | `#f5f6f8` |
| `--sc-surface-3` | `#22262d` | `#ebedf1` |
| `--sc-chrome` | `rgba(8,9,11,.72)` | `rgba(255,255,255,.72)` |
| `--sc-chrome-menu` | `rgba(26,29,34,.82)` | `rgba(255,255,255,.86)` |
| `--sc-line` | `#262a31` | `#e3e5e9` |
| `--sc-line-strong` | `#363b44` | `#c9cdd4` |
| `--sc-line-hover` | `#3a6fb5` | `#9cc0ee` |
| `--sc-hairline` | `rgba(255,255,255,.08)` | `rgba(0,0,0,.06)` |
| `--sc-text` | `#f5f6f7` | `#0b0c0e` |
| `--sc-text-2` | `#a0a6af` | `#4b5159` |
| `--sc-text-3` | `#868d96` | `#656b73` |
| `--sc-accent` | `#4a9eff` | `#0a62d0` |
| `--sc-accent-hover` | `#6fb2ff` | `#0850ae` |
| `--sc-accent-press` | `#2e86f0` | `#06408c` |
| `--sc-accent-soft` | `rgba(74,158,255,.14)` | `rgba(10,98,208,.08)` |
| `--sc-on-accent` | `#04101f` | `#ffffff` |
| `--sc-focus` | `#6fb2ff` | `#0a62d0` |
| `--sc-live` | `#ff6b6b` | `#c42b2b` |
| `--sc-positive` | `#4ed18a` | `#147a4b` |
| `--sc-warning` | `#f2b441` | `#8a5a00` |
| `--sc-negative` | `#ff6b6b` | `#c42b2b` |
| `--sc-glow` | `rgba(74,158,255,.45)` | `rgba(10,98,208,.28)` |
| `--sc-glow-strong` | `rgba(74,158,255,.66)` | `rgba(10,98,208,.42)` |
| `--sc-glow-ring` | `0 0 0 1px rgba(74,158,255,.55), 0 0 28px 6px var(--sc-glow)` | `0 0 0 1px rgba(10,98,208,.4), 0 0 28px 6px var(--sc-glow)` |
| `--sc-glow-ring-strong` | `0 0 0 1px rgba(74,158,255,.7), 0 0 44px 12px var(--sc-glow-strong)` | `0 0 0 1px rgba(10,98,208,.55), 0 0 44px 12px var(--sc-glow-strong)` |
| `--sc-sheen` | `rgba(255,255,255,.22)` | `rgba(255,255,255,.6)` |

`--sc-glow`/`--sc-glow-ring*` — **синие, не янтарные** (решение владельца 23.09: «янтаря в системе
нет вообще»). Глушение: `--sc-warning` остаётся тёплым тоном (`#f2b441`/`#8a5a00`) — это
семантический цвет предупреждения, не свечение, правило «только синий» на него не распространяется.

Высота (тень) и внутренняя кромка:

| Токен | Ночь | День |
|---|---|---|
| `--sc-e-1` | `0 1px 2px rgba(0,0,0,.28), 0 1px 1px rgba(0,0,0,.2)` | `0 1px 2px rgba(0,0,0,.06), 0 1px 1px rgba(0,0,0,.04)` |
| `--sc-e-2` | `0 2px 6px rgba(0,0,0,.4), 0 8px 20px rgba(0,0,0,.3)` | `0 2px 6px rgba(0,0,0,.08), 0 8px 20px rgba(0,0,0,.06)` |
| `--sc-e-3` | `0 8px 24px rgba(0,0,0,.55), 0 2px 6px rgba(0,0,0,.4)` | `0 8px 24px rgba(0,0,0,.12), 0 2px 6px rgba(0,0,0,.08)` |
| `--sc-e-menu` | `0 12px 32px rgba(0,0,0,.6), 0 2px 8px rgba(0,0,0,.4)` | `0 12px 32px rgba(0,0,0,.18), 0 2px 8px rgba(0,0,0,.1)` |

`--sc-ring: inset 0 0 0 1px var(--sc-hairline)` (одна на обе темы) — внутренняя кромка добавляется
к тени элемента; на картах она обнулена (см. §6.3).

Локальный токен `Button`-варианта `danger`: `--sc-btn-danger-soft` = `rgba(255,107,107,.14)` (ночь) /
`rgba(196,43,43,.1)` (день).

### 2.2 Радиусы, отступы, контейнер

```
--sc-r-xs: 6px    --sc-r-sm: 10px   --sc-r-md: 14px   --sc-r-lg: 18px
--sc-r-xl: 22px   --sc-r-2xl: 28px  --sc-r-pill: 999px

--sc-s-1: 4px   --sc-s-2: 8px   --sc-s-3: 12px  --sc-s-4: 16px  --sc-s-5: 20px
--sc-s-6: 24px  --sc-s-7: 32px  --sc-s-8: 40px  --sc-s-9: 48px  --sc-s-10: 64px  --sc-s-11: 80px

--sc-container: 1280px
--sc-gutter: max(16px, calc((100vw - var(--sc-container)) / 2))
--sc-measure: 65ch
```

### 2.3 Свечение и смягчение

```
--sc-glow-blur: 24px
--sc-glow-spread: 8px
--sc-ease-standard: cubic-bezier(0.16, 1, 0.3, 1)
--sc-ease-exit: cubic-bezier(0.4, 0, 1, 1)
--sc-dur-fast: 120ms
--sc-dur-base: 220ms
--sc-dur-slow: 380ms
```

### 2.4 Типографическая шкала (общая часть, кегль/интерлиньяж/трекинг)

| Токен | Кегль | Интерлиньяж | Трекинг |
|---|---|---|---|
| `display` | `clamp(34px, 3.2vw + 20px, 56px)` | `1.06` | `-0.03em` |
| `title-l` | `26px` | `1.16` | `-0.022em` |
| `title-m` | `20px` | `1.24` | `-0.016em` |
| `title-s` | `16px` | `1.3` | `-0.01em` |
| `title-xs` | `14px` | `1.34` | `-0.006em` |
| `body` | `15px` | `1.6` | `0` |
| `body-s` | `13px` | `1.52` | по теме, см. ниже |
| `meta` | `12px` | `1.4` | по теме, см. ниже |
| `caption` | `11px` | `1.34` | по теме, см. ниже |

Вес и мелкий трекинг **зависят от темы** (оптическая компенсация: светлый текст на тёмном фоне
читается жирнее при одном и том же начертании):

| Токен | Ночь | День |
|---|---|---|
| `--sc-w-display` | `600` | `700` |
| `--sc-w-title` | `500` | `600` |
| `--sc-w-body` | `400` | `400` |
| `--sc-w-meta` | `500` | `500` |
| `--sc-w-caption` | `600` | `600` |
| `--sc-track-meta` | `0.018em` | `0.012em` |
| `--sc-track-caption` | `0.051em` | `0.045em` |
| `--sc-track-body-s` | `0.01em` | `0.004em` |

Класс `.sc-t-mono` (`var(--sc-font-mono)` + `tabular-nums`) — для настоящих идентификаторов; для
всех дат/времени/счётчиков в обычном тексте — `font-variant-numeric: tabular-nums` встроено в
`.sc-t-meta`. `.sc-root` задаёт `font-optical-sizing: auto` глобально.

Шрифт: `--sc-font-sans: var(--font-montserrat, "Montserrat"), system-ui, -apple-system, "Segoe UI",
sans-serif`; `--sc-font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`. Серифного
токена в ките нет вовсе — новый визуальный язык полностью гротескный.

### 2.5 Пружины (`kit/motion/springs.ts`)

Единственный источник имён и значений (все — только пара `bounce` + `duration`,
`restDelta: 0.5, restSpeed: 2`):

| Имя | bounce | duration | Назначение |
|---|---|---|---|
| `ui` | `0.18` | `0.26` | наведение, подсветка, кромка, служебные переходы |
| `press` | `0` | `0.16` | нажатие |
| `move` | `0` | `0.4` | переезд: индикаторы, layout-перестановки |
| `fade` | `0` | `0.25` | только прозрачность |
| `portalIn` | `0.12` | `0.42` | карточка → полный экран |
| `portalOut` | `0` | `0.34` | полный экран → карточка (закрытие не пружинит) |
| `scrim` | `0` | `0.28` | затемнение/обвязка, синхронно с морфингом |
| `sheet` | `0.2` | `0.3` | нижний лист, захват при перетаскивании полос |
| `settle` | `0.25` | `0.38` | возврат после отпускания (с реальной скоростью) |
| `expand` | `0.22` | `0.4` | содержимое, раскрывающееся внутри расширения |
| `collapse` | `0` | `0.26` | сворачивание, без отскока |
| `reduced` | `0` | `0.18` | замена любой пружины при `prefers-reduced-motion` |

`responsive(base, velocityPxPerSec)` — подменяет `duration` в диапазоне `[0.24, 0.46]` в зависимости
от скорости отпускания (`0.46 - v/4000`, зажато сверху/снизу); используется на выходе портала после
перетаскивания.

### 2.6 `useMotionTokens()` — контракт

```ts
type MotionTokens = {
  reduced: boolean;
  t: (name: SpringName, overrides?: Transition) => Transition;
  stagger: number;      // 0.035, при reduced — 0
  staggerCap: number;   // 10, при reduced — 0
  rise: number;         // 8px, при reduced — 0
  scale: (value: number) => number; // тождество при reduced (всегда 1)
  gestures: boolean;    // !reduced — можно ли включать drag
  morph: boolean;       // !reduced — можно ли делить layoutId между открывателем и открытым
};
```

`reduced = ForcedReducedMotionContext ?? useReducedMotion()` — витрина форсирует режим через
контекст (переключатель «Mniej ruchu»), не трогая системную настройку. При `reduced === true`
`t(name, overrides)` возвращает `{ ...springs.reduced, ...overrides, bounce: 0 }` — то есть **всегда**
короткое затухание без отскока, даже если вызывающий передал свой `bounce` в `overrides`.
`MotionRoot` (`frontend-spin/app/providers.tsx`) оборачивает дерево в
`<MotionConfig reducedMotion="user" transition={springs.ui}>` — это подстраховка framer-motion
поверх спроектированной деградации `useMotionTokens`.

### 2.7 `motion/physics.ts` — чистые функции жестов

```ts
project(initialVelocity, decelerationRate = 0.998): number
rubberband(overshoot, dimension, constant = 0.55): number
clamp(value, min, max): number
projectedTarget(current, velocity, snaps): number
shouldDismiss(offset, velocity, dimension): boolean   // VELOCITY_COMMIT=120, DISTANCE_COMMIT=0.22
```

## 3. Компоненты

Каждый раздел — реальные пропсы из TS-типов на `7051357`.

### 3.1 `Button` (`kit/Button.tsx`)

```ts
type ButtonVariant = "primary" | "secondary" | "quiet" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";
type ButtonShape = "rounded" | "pill" | "icon";

type ButtonOwnProps = {
  variant?: ButtonVariant;      // default "secondary"
  size?: ButtonSize;            // default "md"
  pressed?: boolean;            // → aria-pressed
  loading?: boolean;            // default false → aria-busy, ширина не меняется
  iconStart?: ReactNode;
  iconEnd?: ReactNode;
  href?: string;                // рендерится next/link (motion(Link)), а не motion.button
  fullWidth?: boolean;
  onClick?: (event) => void;
};
// shape:"icon" требует aria-label и запрещает children — на уровне типа (union ButtonProps),
// не проверкой в рантайме.
```

Плюс произвольные нативные атрибуты (`id`, `tabIndex`, `title`, `name`, `form`, `value`,
`disabled`, `className`, `style`, `data-*`) и `type` (`button|submit|reset`) для текстового варианта.

Высота/отступы/радиус по `size`: `sm` 32px/12px/`--sc-r-sm`, `md` 40px/16px/`--sc-r-md`,
`lg` 48px/20px/`--sc-r-md`. `shape="icon"` — квадрат без горизонтального паддинга, тот же радиус.
Зона нажатия 44px — псевдоэлемент `::after` с отрицательным `inset` (`::before` занято
`.sc-hoverable`).

Движение: `whileTap={{ scale: m.scale(0.97), transition: m.t("press") }}` — единственная встроенная
анимация. **Никакого `whileHover`, никакого подъёма и свечения** — наведение у кнопки меняет только
цвет/фон через чистый CSS `:hover`/`:focus-visible`/`[data-lit="true"]` по варианту (см. §6.3).
`loading` кросс-фейдит спиннер поверх скрытых (`visibility:hidden`) текста/иконок через
`AnimatePresence` + `fade`, ширина кнопки не меняется. `.sc-btn[aria-pressed="true"]` красит фон/цвет
в акцент независимо от варианта — общий стиль переключателя.

### 3.2 `Dropdown` (`kit/Dropdown.tsx`)

```ts
type DropdownMode = "menu" | "single" | "multi";
type DropdownItem = { value: string; label: string; description?: string; disabled?: boolean };
type DropdownPresentation = "popover" | "sheet" | "auto";
type DropdownAlign = "start" | "end";

type DropdownProps = {
  label: string;
  ariaLabel?: string;
  mode: DropdownMode;
  items: DropdownItem[];
  value?: string | string[];
  onSelect?: (item: DropdownItem) => void;
  onChange?: (value: string | string[]) => void;
  align?: DropdownAlign;              // default "start"
  width?: number | "trigger";
  triggerVariant?: ButtonVariant;     // default "secondary"
  footer?: ReactNode;
  presentation?: DropdownPresentation; // default "popover"
  defaultOpen?: boolean;              // default false
};
```

Клавиатура: `ArrowUp`/`ArrowDown` с заворотом, `Home`/`End`, посимвольный поиск (буфер 250ms),
`Enter`/`Space` активируют текущий пункт. Закрытие — `useDismissable` (клик снаружи, `Escape` с
возвратом фокуса на триггер, `Tab` закрывает без ловушки фокуса). `multi` не закрывается по выбору.
`presentation="sheet"` всегда рендерит `BottomSheet` (`kit/mobile`); `"auto"` переключается на него
ниже `BREAKPOINTS.phone` (480px) через `matchMedia`; список пунктов и клавиатура — **один и тот же**
код для popover и sheet (`renderItemsList()`).

«Один живой элемент»: пока панель закрыта, в кнопке рендерится невидимый `motion.span` с
`layoutId={instanceId-surface}` (тот же радиус `RADIUS.md`); когда панель открывается, ровно она
несёт этот `layoutId` — framer-motion морфит панель из бокса кнопки и обратно при закрытии.
`transform-origin` считается от места триггера (`align`/нижняя треть экрана → `placement:"top"`).
При `m.morph === false` (уменьшенное движение) слой-семя не рендерится, панель просто
затухает/масштабируется через `initial/animate/exit`.

### 3.3 `NewsCard` (`kit/NewsCard.tsx`)

```ts
type NewsCardSize = "mini" | "compact" | "medium" | "large";

type NewsCardProps = {
  article: Article;
  size?: NewsCardSize;                 // default "compact"
  href?: string;                       // default `/material/${article.id}`
  headingLevel?: 2 | 3 | 4;            // default 3
  showCategory?: boolean;              // default true
  showDescription?: boolean;           // default: только medium/large
  layout?: "stack" | "split";          // только large; split эффективен ≥900px, default "stack"
  priority?: boolean;
  eyebrow?: ReactNode;
  action?: ReactNode;                  // вне <Link>, свой узел DOM (избранное и т.п.)
  onOpen?: (article: Article) => void; // без него: внутри PortalProvider — портал (usePortalApiOptional), иначе <Link>
  expandable?: boolean;                // default true — ступень B включена по умолчанию
  className?: string;
};
```

Три ступени в самом компоненте: `rest → a (курсор/фокус, немедленно) → b (400ms намерения,
`PREVIEW_DELAY_MS`, или сразу по фокусу с клавиатуры)`. Разметка (R0, 24.09): корневой
`<article.sc-card-slot>` — место в сетке, на ступени B его высота фиксируется инлайн, поэтому
сетка не двигается; внутри — `<div.sc-card>`, сама карта (фон, радиус, ореол, содержимое).
На ступени B **тот же** `.sc-card` выходит из потока (`position:absolute` внутри слота,
`z-index` над сеткой) и меняет форму через framer-motion `layout` (корень + медиа + заголовок +
мета) на пружине `expand`; ширина — `CARD_SPEC[size].grow`, рост от центра, у края окна — внутрь.
У каждого размера своя форма разворота (mini — шире, строкой; compact/medium — вниз; large — во
все стороны), но набор содержимого один: медиа → заголовок → описание → источник · дата →
сердце (`.sc-card__fav`, если не передан `action`). `large` в покое показывает только бейдж и
заголовок над фото. Уход со ступени B держит слот ещё `COLLAPSE_HOLD_MS` (450 мс), пока карта
сжимается и гаснут описание/сердце. Клик в любое место карты (кроме `action`) открывает портал;
после клика карта сама возвращается в покой, чтобы закрытие вернуло её в состояние «до
разворота».

`data-material-id={article.id}` на слоте — по нему `PortalProvider` находит карту
(`document.querySelector('[data-material-id="…"]')`, бокс для полёта берёт с `.sc-card` внутри —
уже разросшийся, если идёт B) и `useFocalBand` (мобильный слой) находит кандидатов в фокальной
полосе (`data-lit` ставится на слот).

Пустое изображение: `article.image_url?.trim()` — пустая строка никогда не передаётся в `src`
`next/image`; вместо неё — `materialTypeLabel(article.category)` в том же боксе соотношения сторон.
Дата: `<time dateTime>` рендерится только при настоящем ISO (не `null`/`"undated"`/`"unknown"`),
иначе `<span>` с текстом «Data nieustalona»/«Data publikacji nieustalona».

Внутренние подкомпоненты в том же файле: `CardBadge`, `CardMedia`, `CardMeta` (не экспортированы
отдельно — часть реализации `NewsCard`).

### 3.4 Контролы (`kit/Checkbox.tsx`, `Radio.tsx`, `Switch.tsx`, `Segmented.tsx`, `SearchField.tsx`)

```ts
// Checkbox
interface CheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  indeterminate?: boolean;   // визуальный третий стан, не влияет на checked
  disabled?: boolean;
  error?: boolean;
  label: string;
  id?: string; name?: string; className?: string;
}
```
Настоящий `<input type="checkbox">` внутри, зона нажатия 44px (`.sc-checkbox__hit`, `inset:-12px`
на инпуте). Включение: диагональный блик `.sc-sheen` один раз (420ms), коробка «стреляет»
`scale 1→.92→1` (пружина `press`), галочка/минус — `CheckIcon`/`MinusIcon` рисуются штрихом.
Ошибка: одноразовое горизонтальное встряхивание `x:[0,-2,2,-2,0]`.

```ts
// Radio / RadioGroup
interface RadioProps {
  checked: boolean; onChange: () => void;
  disabled?: boolean; error?: boolean; label: string;
  id?: string; name?: string; value?: string;
  groupId?: string;   // задаётся RadioGroup — включает общий layoutId точки
  className?: string;
}
interface RadioGroupProps {
  name: string; value: string; onChange: (value: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean; error?: boolean; legend: string; className?: string;
}
```
В группе точка «переезжает» общим `layoutId={sc-radio-dot-${groupId}}` (пружина `move`) внутри
`LayoutGroup id={sc-radio-group-${name}}`; вне группы — обычное появление `scale 0→1`.

```ts
// Switch
interface SwitchProps {
  checked: boolean; onChange: (checked: boolean) => void;
  disabled?: boolean; error?: boolean; label: string;
  id?: string; name?: string; className?: string;
}
```
Бегунок едет на `move`, попутно растягиваясь `scaleX:[1, scale(1.18), 1]` — подсказка направления.
Дорожка меняет цвет чистым CSS-переходом (не framer). Заблокирован — `opacity:.4`, движение
остаётся.

```ts
// Segmented
interface SegmentedProps {
  name: string; value: string; onChange: (value: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean; label: string; className?: string;
}
```
`role="radiogroup"`, индикатор — общий `layoutId={sc-segmented-indicator-${name}}` внутри
`LayoutGroup id={sc-segmented-${name}}`, весь контрол сжимается `scale .98` при нажатии
(пружина `press`).

```ts
// SearchField
interface SearchFieldProps {
  value: string; onChange: (value: string) => void;
  placeholder?: string; label?: string; disabled?: boolean; error?: boolean;
  resultsCount?: number;  // число рядом с полем — перетекание делает вызывающий через MorphValue
  id?: string; className?: string;
}
```
Инпут получает классы `sc-input sc-search__input`; фактическую стилизацию несёт селектор
`.sc-root input.sc-search__input` (специфичность 0,2,1 — побеждает `input:not([type=checkbox])…`
из `globals.css:319`, единственная настоящая ловушка каскада для текстовых полей). Кнопка очистки
появляется `scale .8→1` через `AnimatePresence`, только когда `value.length > 0`.

### 3.5 Иконки (`kit/icons/*`)

Контракт (`kit/icons/types.ts`):
```ts
type IconSize = 16 | 20 | 24;
interface IconProps { size?: IconSize; className?: string; title?: string }
// title задан → role="img" (видима для AT); иначе aria-hidden (по умолчанию — декоративная).
iconStroke(size): number   // 16 → 1.25, 20/24 → 1.5 (штрих НЕ масштабируется пропорционально)
```

| Иконка | Доп. пропсы | Поведение |
|---|---|---|
| `SearchIcon` | — | — |
| `CloseIcon` | — | вращение 90° при `:hover` (CSS, `.sc-icon--close`) |
| `ChevronDownIcon` | `open?: boolean` | поворот 180° через инлайн `style.transform` (не framer) |
| `ChevronLeftIcon` / `ChevronRightIcon` | — | сдвиг 2px по направлению при `:hover` |
| `ArrowUpRightIcon` | — | диагональный сдвиг 2px при `:hover` |
| `CheckIcon` | `animate?: boolean` (default true) | рисуется штрихом `pathLength 0→1`, ~0.2s |
| `MinusIcon` | `animate?: boolean` (default true) | рост от центра, тот же приём |
| `HeartIcon` | `filled?: boolean` | включение — заливка + одноразовый `scale 1→1.25→1` (чистый CSS keyframe, не framer) |
| `ShareIcon` | — | подъём 1px при `:hover` |
| `GripIcon` | — | — |
| `FilterIcon`, `CalendarIcon`, `ClockIcon`, `GlobeIcon`, `DocumentIcon`, `InfoIcon`, `EditIcon` | — | без анимации |
| `PlayIcon` | — | `scale 1→1.1` при `:hover` |
| `PlusIcon` | `active?: boolean` | поворот 45° (превращается в крестик) |
| `MenuClose` | `open: boolean` | морфинг гамбургер↔крест: три `motion.line`, `y`+`rotate`+`opacity` |
| `ThemeIcon` | `mode: "sun" \| "moon"` | кросс-переход двух `motion.g` (opacity+scale+rotate), НЕ интерполяция `d` |
| `SpinnerIcon` | — | вращение 1s **чистым CSS** (`.sc-icon--spinner`), единственная зацикленная анимация системы |
| `AlertIcon` | — | — |
| `TrashIcon` | — | крышка приподнимается 1px при `:hover` (`.sc-icon__lid`) |
| `EyeIcon` | `visible?: boolean` (default true) | морфинг зачёркивания через `pathLength`, не подмена иконки |

Все иконки, кроме `HeartIcon`/`SpinnerIcon`/`ChevronDownIcon`, анимируются через
`useMotionTokens().t("ui")` — то есть подчиняются глобальному переключателю уменьшенного движения.
`SpinnerIcon` и hover-эффекты в таблице (`--close`, `--chevron-*`, `--arrow`, `--share`, `--play`,
`--trash`) — чистый CSS в `kit.css`, гасится общим килсвитчем `prefers-reduced-motion`.
`[data-sc-icon-demo="true"]` на родителе форсирует те же CSS hover-эффекты без реального курсора —
только для витрины.

### 3.6 Примитивы движения (`kit/motion/*`)

```ts
// Morph.tsx — контейнер с layout, базовый кирпич «сплошной системы движения»
type MorphProps = {
  as?: ElementType;            // default "div"
  layout?: boolean | "position"; // true — полный layout, "position" — дешевле, только позиция
  radius?: number;             // ИНЛАЙНОВО числом на layout-элементе — CSS-радиус растягивается
                                // в эллипс на промежуточных кадрах проекции translate+scale
  children?: ReactNode; className?: string;
} & остальные HTMLMotionProps<"div">;
```

```ts
// MorphList.tsx — коллекции: добавление/удаление/переупорядочивание/фильтрация одним примитивом
type MorphListProps<T> = {
  id: string;                  // id LayoutGroup — несвязанные списки не измеряются вместе
  items: T[];
  getKey: (item: T) => string | number;
  renderItem: (item: T, index: number) => ReactNode;
  as?: "div" | "ul" | "ol"; itemAs?: "div" | "li";
  className?: string;
  itemClassName?: string | ((item: T, index: number) => string | undefined);
};
```
Уцелевшие элементы едут (`layout="position"`, пружина `move`), ушедшие гаснут
(`opacity→0, scale→.96`, `collapse`), пришедшие проявляются через `whileInView`
(`IntersectionObserver`, `once: true`), задержка `min(index, staggerCap) × stagger`.

```ts
// MorphIndicator.tsx — общий layoutId для табов/пилюль/навигации
type MorphIndicatorProps = {
  id: string;        // общий layoutId группы
  active: boolean;   // рендерится ТОЛЬКО у активного элемента
  variant?: "underline" | "pill"; // default "underline"
  className?: string;
};
```

```ts
// Reveal.tsx
type RevealProps = { when: boolean; children: ReactNode; delay?: number; as?: "div"|"span"|"li"; className?: string; };
// вход — opacity+y(rise) на `ui`, выход — collapse без задержки (асимметрия намеренная)

type RevealHeightProps = { when: boolean; children: ReactNode; contentDelay?: number /* default 0.06 */; className?: string; };
// единственное разрешённое исключение из «только transform/opacity»: height на ОБЁРТКЕ
// (overflow:hidden), содержимое внутри — чистый кросс-фейд opacity. Раскрытие — expand,
// сворачивание — collapse (содержимое гаснет первым).
```

```ts
// MorphValue.tsx — числа перетекают, не перескакивают
type MorphValueProps = { value: number; className?: string; format?: (value: number) => string; };
// default format = Math.round(value).toLocaleString("pl-PL"); анимация — MotionValue + animate()
// на пружине move, запись в DOM напрямую (без React-рендера на каждый кадр); класс sc-t-mono.
```

```ts
// SkeletonMorph.tsx
type SkeletonMorphProps = { loading: boolean; skeleton: ReactNode; children: ReactNode; className?: string; };
// оба слоя — в одной ячейке CSS-грида (.sc-skeleton-morph), кросс-фейд на fade, без scale/сдвига.
```

### 3.7 `ReorderableStrips` (`kit/ReorderableStrips.tsx`)

```ts
type ReorderableStrip = { id: string; title: string };
type ReorderableStripsProps<T extends ReorderableStrip> = {
  strips: T[];
  renderStrip: (strip: T) => ReactNode;   // содержимое полосы рисует вызывающий
  storageKey?: string;   // default "sc-strips-order"
  label?: string;        // default "Kolejność pasków"
  onReorder?: (strips: T[]) => void;
  className?: string;
};
```
`Reorder.Group`/`Reorder.Item` (framer-motion) под капотом. Захват только за ручку
(`.sc-strip-handle`): мышь/перо — немедленно, тач — долгое нажатие `LONG_PRESS_MS` (250ms),
отменяется сдвигом пальца >10px. Автопрокрутка у края экрана (`AUTOSCROLL_MARGIN` 96px,
`AUTOSCROLL_MAX_SPEED` 16). Клавиатура: `Space`/`Enter` — взять/положить, `↑`/`↓` — переместить,
`Escape` — отменить (возврат к снапшоту); каждое действие объявляется в `aria-live="polite"`.
Порядок пишется в `localStorage[storageKey]` (гидратация — эффектом после монтирования, чтобы SSR
и клиент совпали); подпись «Kolejność zapisana na tym urządzeniu» — честная оговорка, что порядок
не привязан к аккаунту.

### 3.8 Навигация и футер (`kit/NavMenu.tsx`, `kit/SiteFooter.tsx`, `kit/ThemeToggle.tsx`)

```ts
// NavMenu
type NavItem = { label: string; href: string; current?: boolean; items?: NavItem[] };
type NavMenuProps = {
  items: NavItem[];
  ariaLabel?: string;      // default "Nawigacja główna"
  cta?: ReactNode;
  sticky?: boolean;        // default true
  overflowLabel?: string;  // default "Więcej"
  brand?: ReactNode;
  search?: ReactNode;      // скрывается ниже 768px (контейнерный запрос на самом <nav>)
};
```
Первые `MAX_VISIBLE_ITEMS = 5` пунктов — в ряд, остальные — в дропдаун `overflowLabel` (константа
в коде, не измерение ширины). Активный пункт получает `aria-current="page"` и общий
`MorphIndicator` (`layoutId="sc-navmenu-indicator"`) — переезжает между пунктами на `move`. Нижняя
кромка шапки появляется по 1px-сентинелу (`IntersectionObserver`), не по скролл-листенеру.
Ниже `@container sc-navmenu (max-width: 767px)` — список/поиск/cta скрываются, кнопка меню
(`MenuClose`) раскрывает мобильную панель, которая **вырастает из кнопки** (тот же приём
общего `layoutId`-семени, что у `Dropdown`).

```ts
// NavCategories
type NavCategory = { label: string; href: string; current?: boolean };
type NavCategoriesProps = { items: NavCategory[]; ariaLabel?: string /* default "Kategorie" */ };
```
Горизонтальная лента ссылок (как NEWS/SPORTS/LIFE в референсе) со своим `MorphIndicator`,
прокручивается на телефоне.

```ts
// SiteFooter
type SiteFooterColumn = { title: string; links: { label: string; href: string }[] };
type SiteFooterCta = { eyebrow?: string; label: string; href: string };
type SiteFooterProps = { brand: ReactNode; note?: ReactNode; columns: SiteFooterColumn[]; cta?: SiteFooterCta; bottom?: ReactNode };
```
Каждая колонка — собственный `<nav aria-label={column.title}>` (в отличие от текущего живого
футера с одним неозаглавленным `<nav>`). Сетка колонок — на контейнерных запросах
(`@container sc-footer`, 1 → 2 → 4 колонки), не на ширине окна — работает и внутри узкой рамки
витрины. Колонки появляются каскадом `0.04s` через `whileInView`, один раз.

```ts
// ThemeToggle
type ThemeToggleMode = "night" | "day" | "auto";
type ThemeToggleProps = { className?: string };
```
Построен на `Segmented` (Noc/Dzień/Auto). Пишет **только** `document.documentElement.dataset.theme`
и `style.colorScheme` — никогда `localStorage`, никогда `PATCH /api/account/profile/` (это остаётся
за живым `ThemeSwitcher.tsx`). `auto` честен: следит за `matchMedia('(prefers-color-scheme: dark)')`
живьём. Переключение оборачивается классом `sc-theme-transition` на `<html>` (300ms), который сам
кит гасит при `prefers-reduced-motion`/`prefers-contrast: more`.

### 3.9 Портал (`kit/portal/*`, `kit/MaterialSurface.tsx`)

```ts
// PortalProvider
type PortalHistoryMode = "none" | "query" | "path";
function PortalProvider(props: { children: ReactNode; historyMode?: PortalHistoryMode /* default "none" */ }): JSX.Element;

function usePortal(): {
  active: Article | null; previewing: Article | null;
  isActive: (id: number) => boolean; isPreviewing: (id: number) => boolean;
  open: (article: Article, originEl?: HTMLElement | null) => void;
  close: () => void;
  preview: (article: Article, originEl: HTMLElement) => void;
  endPreview: () => void;
  originRef: RefObject<HTMLElement | null>;
  historyMode: PortalHistoryMode;
};
```
Два раздельных React-контекста внутри (`PortalApiContext` — только стабильные функции,
`PortalEngineContext` — фактическое состояние), чтобы карта, которая лишь **вызывает**
`open`/`preview`, не перерисовывалась при каждом изменении состояния портала. `usePortalApi()`,
`usePortalState()`, `usePortalEngine()` — более узкие хуки для тех, кому не нужен весь `usePortal()`.

```ts
// PortalLayer
type PortalLayerProps = {
  resolveArticle?: (id: number) => Article | null | undefined; // нужен useHistoryPortal
  relatedFor?: (article: Article) => Article[];                // «Powiązane materiały»
};
```
`createPortal` в `document.body`; `<AnimatePresence>` смонтирован **постоянно**, условно только
дочерний элемент. Рисует затемнение (`.sc-portal-scrim`) и поверхность ступени C
(`MaterialSurface`); ступень B живёт в самой `NewsCard` (клона в слое нет с 24.09). Три случая
возврата при `close()` считаются **синхронно** внутри `PortalProvider.close()` (карта на экране /
уехала из вида — `scrollIntoView({behavior:"auto"})` в том же такте / размонтирована). Цель
возврата уходит в поверхность через `custom` у `<AnimatePresence>` (вариант `closed`), а не через
проп `exit`: AnimatePresence отыгрывает выход на элементе из последнего рендера **до** удаления,
когда `engine.exit` ещё `null` — проп `exit` видел бы пустую цель и просто гасил поверхность.

```ts
// useHistoryPortal({ mode, active, onOpen, onClose, resolveArticle }): { requestClose, replaceForRelated }
```
`useHistoryPortal` — `window.history.pushState`/`replaceState`, **никогда `router.push`**
(настоящая навигация App Router размонтировала бы дерево-партнёра морфинга). Адрес всегда
сохраняет `window.location.search`. Режим `query` кладёт `?podglad=<id>`, `path` —
`/material/<id>`.

```ts
// MaterialSurface — общее тело оверлея (mode:"overlay") и страницы /material/[id] (mode:"page")
type MaterialSurfaceProps = {
  mode: "overlay" | "page";
  article: Article; related?: Article[];
  onClose?: () => void; onNavigate?: (article: Article) => void;
  surfaceRef?: Ref<HTMLDivElement>; scrollerRef?: RefObject<HTMLDivElement>;
  layoutId?: string;             // делится с клоном, когда он есть
  useSharedLayout?: boolean;     // true — есть живой клон, framer сам считает проекцию
  fromRect?: MaterialSurfaceRect | null; fromRadius?: number;  // клона не было — ручной FLIP
  exitRect?: MaterialSurfaceRect | null; exitRadius?: number;  // закрытие — ВСЕГДА явный rect
  transition?: Transition; exitTransition?: Transition;
  onSettled?: () => void;
  dragEnabled?: boolean; drag?: DragDismiss;
};
```
Содержимое: медиа 16:9, бейдж категории, заголовок `title-l`, строка источника (**ссылка на
оригинал** с `ArrowUpRightIcon`) + автор + дата/«Data publikacji nieustalona», описание, ряд
действий (`Otwórz źródło` primary, избранное `HeartIcon`, поделиться `ShareIcon` — копия ссылки,
таймаут 1.6s на подтверждение), блок «Powiązane materiały» — лентой `NewsCard[size=compact]`.
`mode="page"` рендерит то же тело без затемнения, без `layoutId`, без блокировки скролла.

Хуки-примитивы портала, используемые и `BottomSheet` (§3.10):

```ts
useScrollLock(active: boolean): void
// useLayoutEffect (не useEffect) — компенсация ширины scrollbar-gutter, гасит scroll-behavior:smooth.

useModalA11y(surfaceRef, active, onEscape): { focusFirst(): void; restoreFocus(originEl): void }
// inert на #main-content и <header> вместо ручной ловушки фокуса; запасная Tab-ловушка;
// Escape перехватывается на capture-фазе.

useDragDismiss({ height, onDismiss }): {
  y, scrimOpacity, surfaceScale, surfaceRadius,   // MotionValue — считаются через useTransform
  dragControls, dragProps, startIfAtTop(event, scrollerEl),
}
// drag="y", решение shouldDismiss() по ЗНАКУ скорости (VELOCITY_COMMIT=120px/s), запасной
// критерий — позиция (DISTANCE_COMMIT=22% высоты). Возврат — пружина settle с передачей
// реальной velocity. startIfAtTop стартует жест только если внутренний скроллер уже вверху.
```

### 3.10 Мобильный слой (`kit/mobile/*`)

```ts
useFocalBand(containerRef, options?: {
  band?: [number, number];       // default [0.35, 0.65]  — экспортируется как FOCAL_BAND
  selector?: string;             // default "[data-material-id]"
  axis?: "y" | "x";              // Carousel использует "x"
  force?: boolean;                // работать и на (hover:hover)and(pointer:fine) — нужно Carousel
  velocityThreshold?: number;    // default 0.55 px/ms
}): string | null   // id (data-material-id) элемента, ближайшего к центру полосы, либо null
```
Один `IntersectionObserver` на инстанс, `rootMargin` сжимает корень до самой полосы; единственный
слушатель скролла в файле только пишет скорость в ref (без чтения геометрии, без `setState`) —
решение «зафиксировать фокус» принимается из этого ref и подавляется выше `velocityThreshold`.
Коммит атрибута `data-lit="true"` идёт напрямую в DOM (не React state на карточку) — тот же
атрибут, которым `.sc-hoverable`/`.sc-card` пользуются для наведения на десктопе.

```ts
type FoldedSectionProps = { title: ReactNode; preview: ReactNode; children: ReactNode; scrollRootRef?: RefObject<HTMLElement | null>; className?: string };
```
Секция загружается свёрнутой (заголовок + `preview`), разворачивается один раз, когда заголовок
пересекает фокальную полосу (`focalBandRootMargin`), через `RevealHeight`. Обратно не сворачивается.

```ts
type CarouselProps = { articles: Article[]; size?: NewsCardSize /* default "medium" */; ariaLabel: string; onPreview?: (article, el) => void; onOpen?: (article) => void; className?: string };
```
`scroll-snap-type: x mandatory`, `useFocalBand(..., { axis:"x", force:true })` определяет
центральный слайд. Драбина касания: тап не по центральному слайду → докрутка к центру; тап по уже
центральному → `onPreview` (ступень B, слой R5); тап по слайду с уже открытым превью → `onOpen`
(ступень C). Карусель никогда сама не меняет свою высоту.

```ts
type BottomSheetProps = { open: boolean; onClose: () => void; title?: ReactNode; children: ReactNode; className?: string; id?: string };
```
Та же физика, что закрытие портала (`useDragDismiss`), `createPortal` в `document.body`,
`AnimatePresence` смонтирован постоянно внутри компонента (вызывающий условит только `open`, не
сам `<BottomSheet>`). `a11y.focusFirst()` — по кадру после открытия.

```ts
type CompactHeaderRenderProps = { compact: boolean };
type CompactHeaderProps = { children: ReactNode | ((state: CompactHeaderRenderProps) => ReactNode); scrollRootRef?: RefObject<HTMLElement | null>; className?: string };
```
Уплотняется по **направлению** прокрутки (вниз → 64→48px, вверх → назад), не по позиции;
`DIRECTION_DEADZONE` 4px гасит микро-дрожание (отскок iOS). `height` — тот же разрешённый
исключением из правила «только transform/opacity», что и `RevealHeight`.

### 3.11 `useDismissable` (`kit/useDismissable.ts`)

```ts
function useDismissable<T extends HTMLElement>(options: {
  open: boolean; onClose: () => void; triggerRef: RefObject<HTMLElement>;
}): RefObject<T>
```
Закрытие по `pointerdown` снаружи панели/триггера, `Escape` (возврат фокуса на триггер), `Tab`
(закрывает панель, но **не** ловит фокус — таб продолжает свой обычный путь).

## 4. Правила движения

**Что анимируется.** Только `transform` и `opacity`. Единственные разрешённые исключения —
`height` на внешней обёртке (`RevealHeight`, `CompactHeader`) и явные числовые
`top/left/width/height/borderRadius` у `MaterialSurface`, когда нет общего `layoutId` для проекции
(см. ниже). `will-change` компоненты не ставят — framer-motion делает это сам.

**Что не анимируется никогда.** `filter`/`backdrop-filter` — не по кадрам (`.sc-chrome` даёт
статичный blur через CSS, включается/выключается мгновенно вокруг морфинга, не «плывёт»).
`transition: all` — нигде, все переходы перечисляют свойства поимённо.

**Уменьшенное движение** (`prefers-reduced-motion` или форс на витрине):
- `useMotionTokens().t()` всегда возвращает `bounce: 0` и короткую `duration` (`springs.reduced`,
  0.18s) независимо от запрошенного имени;
- `rise` → 0 (появление — чистый `opacity`), `stagger`/`staggerCap` → 0 (без каскада),
  `scale()` — тождество (масштабные эффекты выключены), `gestures` → `false` (drag выключен
  полностью: `BottomSheet`, перетаскивание портала, `ReorderableStrips` теряют жест), `morph` →
  `false` (общие `layoutId` между открывателем/открытым не выдаются — см. ниже);
- в CSS — глобальный килсвитч в `kit.css`: `transition-duration`/`animation-duration` → `1ms`,
  `animation-iteration-count` → `1` для всего внутри `.sc-root`; `.sc-hoverable::before`
  переключается на `opacity`-only без `transform`; блик `.sc-sheen` не проигрывается; спиннер
  застывает статичной дугой; смена темы теряет плавный переход цвета.
- **Движение никогда не исчезает полностью** — минимум изменение прозрачности остаётся, чтобы было
  понятно, что состояние изменилось (портал при `morph:false` кросс-фейдит на финальном размере
  0.18s вместо layout-морфинга).

**Правило владения `layoutId`.** Формулировка контракта волны 0 (см. `docs/UI_KIT_PLAN.md` →
«Контракты», «Портал»): «в любой момент у материала ровно один элемент с
`layoutId={sc-card-${id}}`». **Фактическая реализация (24.09):** `NewsCard` не несёт `layoutId`
вообще; ступень B — это та же карта, меняющая форму через `layout` (без общего id), а переход
карта → оверлей и обратно — явный FLIP по измеренным боксам:

- `open()` снимает `getBoundingClientRect()` с `.sc-card` (разросшейся, если идёт B) — оверлей
  анимирует `top/left/width/height/borderRadius` от него к целевому боксу (`fromRect`);
- закрытие идёт к `exit.rect` из трёх случаев возврата (`PortalProvider.close()`), доставленному
  через `custom` у `<AnimatePresence>` (вариант `closed` в `MaterialSurface`).

`useSharedLayout`/`layoutId` в `MaterialSurface` остались как путь «есть живой элемент с тем же
id» и сейчас не задействованы (`viaClone` всегда `false`). Правило дословно выполняется в двух
других местах: `Dropdown` (семя в кнопке ↔ панель, панель растёт из бокса кнопки, а кнопка
становится её верхней строкой `.sc-dropdown__head`) и мобильная панель `NavMenu`.

## 5. Ловушки каскада

Проверено по `frontend-spin/app/globals.css` на `7051357`; каждая строка определяет, как писать
селекторы в `kit.css`:

| Угроза | Селектор в `globals.css` | Специфичность | Что делает `kit.css` |
|---|---|---|---|
| Слой перезаписи Tailwind (строки ~27–62) | `.bg-white`, `.text-slate-*`, `.shadow-sm{box-shadow:none}` | `0,1,0` | Ни одной утилиты Tailwind в компонентах библиотеки — снимает весь слой разом |
| Ранние компонентные классы | `.quiet-button`, `.source-card`, `.material-box` | `0,1,0` | Эти имена не переиспользуются |
| Универсальная рамка | `*, ::before, ::after { border-color: var(--line) }` | `0,0,0` | Каждое правило пишет `border: 1px solid var(--sc-line)` целиком |
| Глобальный переход | `button, a, input { transition: … }` | `0,0,1` | `kit.css` пишет `transition` сокращённо со списком свойств — полностью замещает |
| Глобальное кольцо фокуса | `:focus-visible { outline: … var(--color-primary) }` | `0,1,0` | `.sc-root <тег>:focus-visible` — специфичность `0,2,1`, кольцо синее (`--sc-focus`), не янтарное |
| Стилизация полей ввода | `input:not([type=checkbox])…, select, textarea` (строка 319) | `0,2,1` | Единственная настоящая ловушка: писать `input.sc-search__input` под `.sc-root`, не голый класс |

`kit.css` подключается сразу после `import "./globals.css"` в `layout.tsx` — порядок импортов в
одном модуле App Router сохраняет порядок каскада.

## 6. Конвенции фикстур (`kit/showcase/fixtures.ts`)

- Все данные вымышленные; домен ссылок — `przyklad.invalid` (не резолвится, ничего не запрашивает).
- `id` источников и статей — **отрицательные**, чтобы никогда не совпасть с настоящим `Article`.
- `makeArticle(overrides)` — полный `Article` со всеми обязательными полями. Без явного `id`
  идентификатор считается хэшем `JSON.stringify(overrides)` — детерминирован (сервер/клиент
  совпадают), но при рендере **списка** нужно передавать `id` явно, иначе одинаковые overrides дадут
  одинаковый id.
- `makeArticles(n, seed)` — для лент и замера кадра (`makeArticles(240)`), детерминированный набор.
- `FIXTURE_ARTICLES` — `makeArticles(24, 3)`, набор по умолчанию для разделов витрины.
- `FIXTURE_STRIPS` — 5 полос по 8 карточек (`najnowsze`, `polska`, `gospodarka`, `prawo`, `nauka`).
- `FIXTURE_STATES` — 6 состояний данных карточки (`normal`, `no-image`, `no-date`, `undated`,
  `long-title`, `long-source`).
- Изображения — `demoImage(seed, ratio)`: инлайновый `data:image/svg+xml` градиент со словом DEMO,
  без бинарных файлов в репозитории (работает благодаря `images.unoptimized`).
- `POLISH_SPECIMEN`/`POLISH_LONG_WORDS` — эталонные польские строки с диакритикой и длинными
  составными словами для проверки Montserrat/переносов.
- Заголовки описывают **раскладку**, а не события («Bardzo długi tytuł testowy sprawdzający…»),
  по правилу `docs/FRONTEND_MVP_DIRECTION.md` — никаких правдоподобных новостных заголовков даже
  в демо-данных.

## 7. Витрина `/ui-kit`

`frontend-spin/app/ui-kit/page.tsx` — тонкая серверная страница,
`robots: { index: false, follow: false }`, не связана из живой навигации. Рендерит
`UiKitShowcase` (`kit/showcase/UiKitShowcase.tsx`), которая собирает 13 разделов в порядке:

`Tokeny` → `Typografia` → `Ikony` → `Kontrolki` → `Przyciski` → `Dropdowny` → `Karty` → `Portal` →
`Nawigacja` → `Stopka` → `Telefon` → `Ruch` → `Próba morfingu przez portal`.

Каждый раздел — файл `showcase/sections/<Имя>.tsx`, экспортирующий `meta: {id, title, lead?}` и
`Section()`, независим от других разделов и сам показывает все состояния своего компонента в обеих
темах. Панель управления витриной (`.sc-showcase__banner`) даёт:

- переключатель темы (`Noc`/`Dzień`) — пишет **только** `document.documentElement.dataset.theme`,
  восстанавливает исходное значение при размонтировании (эффект в `UiKitShowcase`), не трогает
  `localStorage` и не шлёт `PATCH`;
- три чекбокса принудительных режимов доступности («Mniej ruchu», «Bez przezroczystości»,
  «Większy kontrast») — пишут `data-sc-force` на корень витрины (`.sc-showcase`) и
  `ForcedReducedMotionContext` для «Mniej ruchu» — тот же путь деградации, что настоящие
  `prefers-*`-медиазапросы в `kit.css`, но без смены системных настроек.

`frontend-spin/app/ui-kit/template.tsx` перемонтируется на каждую навигацию **внутри сегмента**
`/ui-kit` и даёт анимацию входа (`opacity 0→1, y 8→0`, пружина `fade`) без хаков с «замороженным
роутером» (App Router не умеет анимировать выход маршрута) — см. §7 в списке известных ограничений
про то, почему файл не в корне `app/`.

## 8. Известные ограничения и предусловия этапа 2

- **Дропдаун не портализован.** `Dropdown.__panel` — обычный абсолютно позиционированный потомок,
  не рендерится в `PortalLayer`. Внутри контейнера с `overflow-x: auto` (лента карточек и т.п.) он
  будет обрезан, если явно не передать `presentation="sheet"` (или `"auto"` ниже 480px, где он и так
  переключится сам). Портализация дропдауна внутри лент — предусловие этапа 2.
- **`template.tsx` только на `/ui-kit`.** Копия в корень `app/` включила бы анимацию входа на всех
  живых страницах уже сегодня — то самое изменение живого поведения, что отложено до утверждения
  вида (нарушило бы критерий «живые страницы выглядят в точности как раньше»). На этапе 2 файл
  просто переезжает в корень.
- **`pastel` жив.** В `kit.css` тема `pastel` — псевдоним дневного набора токенов
  (`html[data-theme="pastel"]` попадает в тот же блок, что `light`), чтобы новые компоненты не
  выглядели сломанными под старым переключателем. Сам `pastel` остаётся в живом `ThemeSwitcher.tsx`,
  `localStorage['spin-theme']` и в перечислении бэкенда до этапа 2.
- **Живые страницы — всё ещё IBM Plex.** `layout.tsx` подключает Montserrat только как переменную
  шрифта (`--font-montserrat`); `body { font-family }` в `globals.css` не тронут, `@fontsource/ibm-plex-*`
  импорты остаются рядом. Оба механизма шрифтов сосуществуют до этапа 2, когда IBM Plex перестанет
  использоваться.
- **Ленты с `overflow-x: auto` обрезают разросшуюся карту по вертикали** (по спецификации
  `overflow-y` при этом вычисляется в `auto`). Ступень B живёт в самой карте, слоя-клона больше нет,
  поэтому ленте нужен запас: класс `.sc-strip-bleed` (margin/padding наизнанку по 120px) — как в
  витрине «Portal». На этапе 2 это касается `.material-strip`, карусели и «Powiązane materiały».
- **Иконки внутри некоторых компонентов — временные инлайновые SVG.** Помечены `TODO(R1)`/`TODO(R0)`
  в коде, ждут замены на `kit/icons` при следующей правке: спиннер и шеврон/галочка в
  `Button.tsx`/`Dropdown.tsx` (написаны параллельно с волной иконок, до её мержа) и ручка
  перетаскивания в `ReorderableStrips.tsx` (не переключена на уже существующий `kit/icons/GripIcon`).
- **Старые демо-маршруты** (`/box-materialu`, `/box-kontekstu`, `/osoby-publiczne/demo`) не входят в
  этот кит и не тронуты — их роль на этапе 2 полностью берёт витрина.

## 9. Расхождения с планом

Список найден при сверке `docs/UI_KIT_PLAN.md` с кодом на `7051357`. Ничего в коде не менялось для
подготовки этого документа — ниже только описание фактического состояния.

1. **Правило владения `layoutId`** («Контракты» → NewsCard, «Портал» → «`layoutId` выдаётся только
   активной карточке») реализовано не буквально: `NewsCard.tsx` не несёт `layoutId`; переход
   карта→оверлей→карта — явный FLIP по измеренным боксам (`open()`/`close()`), ступень B — та же
   карта с `layout`. Подробности — §4 выше.
2. **Пружина `ui`** в `springs.ts` — `bounce 0.18, duration 0.26`. Обзорная таблица раздела
   «Пружины» плана даёт для строки «наведение, левитация, свечение» `bounce 0, duration 0.30`, а
   отскок `0.18/0.26` вводит только позже, для ступеней A/B карточки конкретно («Три ступени»). В
   коде это единое значение `ui` используется универсально — для наведения на кнопки, пункты
   навигации, ссылки футера, панели дропдауна, — а не только для карточек.
3. **`NewsCardProps`** содержит `layout` (`"stack"|"split"` для `large`) сверх набора, зафиксированного в «Контрактах» волны 0
   (`article, size, href, headingLevel, showCategory, showDescription, eyebrow, action, onOpen,
   priority` + `expandable`). Расширение обосновано в коде и не нарушает изоляцию, но контракт не
   обновлён текстом.
4. **`expandable` по умолчанию `true`**, а не «опция» (комментарий в `NewsCard.tsx`: «ступень B —
   штатное поведение, не опция»). План описывает проп как обычный необязательный булев без указания
   значения по умолчанию.
5. **`usePortal()`** возвращает значительно более широкую форму
   (`{active, previewing, isActive, isPreviewing, open, close, preview, endPreview, originRef,
   historyMode}`), чем контракт волны 0 (`{ active, isActive(id), open(), close(), originRef }`).
6. **`packages/ui/package.json` `exports`** содержит третью запись `"./kit/kit.css"` сверх двух
   (`.`, `./kit`), приведённых в примере контракта; `layout.tsx` импортирует стили именно через этот
   подпуть (`@spin-clinic/ui/kit/kit.css"`), а не относительным путём.
7. **`CARD_SPEC.padding`** (`tokens.ts`: `mini 10, compact 12, medium 14, large 18`) нигде не
   читается компонентами — используются только `.radius`, `.lift`, `.previewScale`. Фактический
   CSS-паддинг карточки берётся из шкалы отступов (`--sc-s-3`=12 для mini/compact,
   `--sc-s-4`=16 для medium, `--sc-s-6`=24 для large) — ближайший шаг сетки 4px, а не число из
   плана дословно.
8. **`ReorderableStrips.tsx`** рисует ручку перетаскивания собственным инлайновым `GripIcon`
   (помечен `TODO(R0)`), хотя `kit/icons/GripIcon` уже существует и экспортируется из `kit/index.ts`
   — тот же паттерн временного инлайна, что у `Button`/`Dropdown`, но не отмеченный в плане отдельно.
