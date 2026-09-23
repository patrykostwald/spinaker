"use client";

import { motion, useMotionValueEvent, useVelocity } from "framer-motion";
import { useRef, useState } from "react";
import { project, shouldDismiss } from "../../motion/physics";
import { MorphIndicator } from "../../motion/MorphIndicator";
import { MorphList } from "../../motion/MorphList";
import { MorphValue } from "../../motion/MorphValue";
import { RevealHeight } from "../../motion/Reveal";
import { SkeletonMorph } from "../../motion/SkeletonMorph";
import { useMotionTokens } from "../../motion/useMotionTokens";
import { ReorderableStrips } from "../../ReorderableStrips";
import { useDragDismiss } from "../../portal/useDragDismiss";
import { FIXTURE_STRIPS } from "../fixtures";

export const meta = {
  id: "ruch",
  title: "Ruch",
  lead: "Stend, po którym przyjmowany jest wygląd ruchu: prymitywy z docs/UI_KIT_PLAN.md → «Sprężyny» i «Bryły ruchu» na żywo, sterowane przyciskami, nie łapane przypadkiem.",
};

const WORD_POOL = ["Alfa", "Beta", "Gamma", "Delta", "Epsilon", "Dzeta", "Eta", "Theta", "Jota", "Kappa", "Lambda", "Mi"];

type ListItem = { id: number; label: string };

// R0: чистая функция вместо модульного счётчика — тот рос на каждом SSR-запросе и при
// двойном вызове инициализатора в StrictMode, давая расхождение гидратации (нашёл R6).
function makeItem(id: number): ListItem {
  return { id, label: `${WORD_POOL[id % WORD_POOL.length]} · #${id}` };
}

function shuffle<T>(arr: T[]): T[] {
  const next = arr.slice();
  for (let i = next.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [next[i], next[j]] = [next[j], next[i]];
  }
  return next;
}

export function Section() {
  return (
    <div className="sc-motion-stand">
      <ListDemo />
      <TabsDemo />
      <CounterDemo />
      <SkeletonDemo />
      <AccordionDemo />
      <InterruptDemo />
      <StripsDemo />
      <DragDismissDemo />
    </div>
  );
}

/** Живой список: добавление, удаление, перемешивание, фильтрация — уцелевшие элементы едут. */
function ListDemo() {
  const [items, setItems] = useState<ListItem[]>(() => [1, 2, 3, 4].map(makeItem));
  const [seq, setSeq] = useState(4);
  const [onlyEven, setOnlyEven] = useState(false);
  const visible = onlyEven ? items.filter((item) => item.id % 2 === 0) : items;

  return (
    <div className="sc-motion-block">
      <h3 className="sc-t-title-s">Lista: dodawanie, usuwanie, przetasowanie, filtrowanie</h3>
      <div className="sc-motion-toolbar">
        <button type="button" className="sc-motion-btn" onClick={() => { const id = seq + 1; setSeq(id); setItems((cur) => [...cur, makeItem(id)]); }}>
          Dodaj
        </button>
        <button
          type="button"
          className="sc-motion-btn"
          disabled={items.length === 0}
          onClick={() => setItems((cur) => cur.slice(0, -1))}
        >
          Usuń
        </button>
        <button type="button" className="sc-motion-btn" onClick={() => setItems((cur) => shuffle(cur))}>
          Przetasuj
        </button>
        <label className="sc-showcase__check">
          <input type="checkbox" checked={onlyEven} onChange={(e) => setOnlyEven(e.target.checked)} />
          Filtruj (tylko parzyste id)
        </label>
      </div>
      <MorphList
        id="motion-demo-list"
        as="ul"
        itemAs="li"
        className="sc-motion-list"
        itemClassName="sc-motion-list__item"
        items={visible}
        getKey={(item) => item.id}
        renderItem={(item) => <span>{item.label}</span>}
      />
    </div>
  );
}

/** Табы с общим layoutId-индикатором, который переезжает между позициями. */
function TabsDemo() {
  const TABS = ["Dane", "Ustawienia", "Pomoc"] as const;
  const [active, setActive] = useState<(typeof TABS)[number]>(TABS[0]);

  return (
    <div className="sc-motion-block">
      <h3 className="sc-t-title-s">Zakładki z przemieszczającym się wskaźnikiem</h3>
      <div className="sc-motion-tabs" role="tablist" aria-label="Przykładowe zakładki">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={active === tab}
            className="sc-motion-tabs__tab"
            onClick={() => setActive(tab)}
          >
            <MorphIndicator id="motion-demo-tabs" active={active === tab} variant="pill" />
            <span className="sc-motion-tabs__label">{tab}</span>
          </button>
        ))}
      </div>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "var(--sc-s-3) 0 0" }}>
        Aktywna zakładka: <strong>{active}</strong>
      </p>
    </div>
  );
}

/** Перетекающий счётчик — MorphValue. */
function CounterDemo() {
  const [count, setCount] = useState(0);
  return (
    <div className="sc-motion-block">
      <h3 className="sc-t-title-s">Licznik przetekający między wartościami</h3>
      <div className="sc-motion-toolbar">
        <button type="button" className="sc-motion-btn" onClick={() => setCount((c) => c - 1)}>
          −1
        </button>
        <MorphValue value={count} className="sc-motion-counter" />
        <button type="button" className="sc-motion-btn" onClick={() => setCount((c) => c + 1)}>
          +1
        </button>
        <button type="button" className="sc-motion-btn" onClick={() => setCount((c) => c + 10)}>
          +10
        </button>
      </div>
    </div>
  );
}

/** Скелет → контент по кнопке, без изменения раскладки. */
function SkeletonDemo() {
  const [loading, setLoading] = useState(true);
  return (
    <div className="sc-motion-block">
      <h3 className="sc-t-title-s">Szkielet → treść</h3>
      <button type="button" className="sc-motion-btn" onClick={() => setLoading((v) => !v)} style={{ marginBottom: "var(--sc-s-3)" }}>
        {loading ? "Pokaż treść" : "Pokaż szkielet"}
      </button>
      <SkeletonMorph
        loading={loading}
        skeleton={
          <div className="sc-motion-skeleton-card">
            <div className="sc-skeleton" style={{ height: 18, width: "60%" }} />
            <div className="sc-skeleton" style={{ height: 12, width: "90%", marginTop: 8 }} />
            <div className="sc-skeleton" style={{ height: 12, width: "75%", marginTop: 6 }} />
          </div>
        }
      >
        <div className="sc-motion-skeleton-card">
          <p className="sc-t-title-xs" style={{ margin: 0 }}>Tytuł testowy karty</p>
          <p className="sc-t-body-s sc-text-2" style={{ margin: "6px 0 0" }}>
            Opis testowy, który zajmuje mniej więcej tyle samo miejsca co szkielet powyżej.
          </p>
        </div>
      </SkeletonMorph>
    </div>
  );
}

/** RevealHeight-аккордеон: морфинг высоты, содержимое кросс-фейдит. */
function AccordionDemo() {
  const [open, setOpen] = useState(false);
  return (
    <div className="sc-motion-block">
      <h3 className="sc-t-title-s">Rozwijanie wysokości</h3>
      <button type="button" className="sc-motion-btn" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {open ? "Zwiń" : "Pokaż więcej"}
      </button>
      <RevealHeight when={open} className="sc-motion-accordion">
        <p className="sc-t-body-s sc-text-2" style={{ margin: "var(--sc-s-3) 0 0" }}>
          Treść dodatkowa: wysokość kontenera morfuje sprężyną `expand`, a zawartość wewnątrz przechodzi
          krzyżowym zanikiem — to jedyny dozwolony wyjątek od reguły „tylko transform/opacity”, i to na
          zewnętrznej obwódce, nie na tym akapicie.
        </p>
      </RevealHeight>
    </div>
  );
}

/** Прерываемость: клик по цели B на середине полёта к A должен перенацелить, а не поставить в очередь. */
function InterruptDemo() {
  const m = useMotionTokens();
  const [target, setTarget] = useState<"a" | "b">("a");
  return (
    <div className="sc-motion-block">
      <h3 className="sc-t-title-s">Sprawdzenie przerywalności</h3>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-3)" }}>
        Kliknij drugi przycisk w trakcie lotu kropki — ruch ma się przekierować z bieżącego miejsca, nie zacząć od nowa.
      </p>
      <div className="sc-motion-toolbar">
        <button type="button" className="sc-motion-btn" aria-pressed={target === "a"} onClick={() => setTarget("a")}>
          Cel A
        </button>
        <button type="button" className="sc-motion-btn" aria-pressed={target === "b"} onClick={() => setTarget("b")}>
          Cel B
        </button>
      </div>
      <div className="sc-motion-track">
        <motion.div
          className="sc-motion-track__dot"
          animate={{ x: target === "a" ? 0 : 200 }}
          transition={m.t("move")}
        />
      </div>
    </div>
  );
}

/** Перетаскивание полос — пять FIXTURE_STRIPS, простые sc-плитки вместо NewsCard (её строит R3). */
function StripsDemo() {
  return (
    <div className="sc-motion-block">
      <h3 className="sc-t-title-s">Przeciąganie pasków (myszą, dotykiem, klawiaturą)</h3>
      <ReorderableStrips
        strips={FIXTURE_STRIPS}
        storageKey="sc-strips-order-demo"
        label="Kolejność pasków demonstracyjnych"
        renderStrip={(strip) => (
          <div className="sc-motion-strip-tiles">
            {strip.articles.slice(0, 8).map((article) => (
              <div key={article.id} className="sc-motion-strip-tile">
                <span className="sc-t-caption sc-text-2">{article.source.name}</span>
                <strong className="sc-t-body-s">{article.title.slice(0, 28)}…</strong>
              </div>
            ))}
          </div>
        )}
      />
    </div>
  );
}

/** Стенд useDragDismiss: живой вывод offset, velocity, project(velocity) и решения. */
function DragDismissDemo() {
  const HEIGHT = 320;
  const [status, setStatus] = useState<"idle" | "dismissed">("idle");
  const [lastVelocity, setLastVelocity] = useState(0);
  const scrollerRef = useRef<HTMLDivElement>(null);

  const { y, scrimOpacity, surfaceScale, surfaceRadius, dragProps, startIfAtTop } = useDragDismiss({
    height: HEIGHT,
    onDismiss: (velocity) => {
      setLastVelocity(velocity);
      setStatus("dismissed");
      window.setTimeout(() => {
        y.set(0);
        setStatus("idle");
      }, 900);
    },
  });
  const velocity = useVelocity(y);
  const [readout, setReadout] = useState({ offset: 0, velocity: 0, projected: 0, willDismiss: false });

  useMotionValueEvent(y, "change", (latest) => {
    const v = velocity.get();
    setReadout({
      offset: Math.round(latest),
      velocity: Math.round(v),
      projected: Math.round(project(v, 0.99)),
      willDismiss: shouldDismiss(latest, v, HEIGHT),
    });
  });

  return (
    <div className="sc-motion-block">
      <h3 className="sc-t-title-s">Stend useDragDismiss</h3>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-3)" }}>
        Przeciągnij panel za uchwyt u góry w dół — myszą lub palcem. Decyzję o zamknięciu podejmuje znak
        prędkości, nie osiągnięta pozycja.
      </p>
      <div className="sc-drag-sandbox" style={{ height: HEIGHT + 32 }}>
        <motion.div className="sc-drag-sandbox__scrim" style={{ opacity: scrimOpacity }} aria-hidden="true" />
        <motion.div
          {...dragProps}
          className="sc-drag-sandbox__surface"
          style={{ y, scale: surfaceScale, borderRadius: surfaceRadius, height: HEIGHT }}
        >
          <div
            className="sc-drag-sandbox__handle"
            onPointerDown={(event) => startIfAtTop(event, scrollerRef.current)}
          >
            <span className="sc-drag-sandbox__grip" aria-hidden="true" />
          </div>
          <div ref={scrollerRef} className="sc-drag-sandbox__scroller">
            <p className="sc-t-body-s sc-text-2">
              Ten scroller ma `overscroll-behavior: contain`. Jeśli jest na górze, przeciąganie za uchwyt
              zamyka panel; w przeciwnym razie najpierw przewija treść.
            </p>
          </div>
        </motion.div>
      </div>
      <dl className="sc-drag-sandbox__readout">
        <div>
          <dt className="sc-t-caption sc-text-2">offset</dt>
          <dd className="sc-t-mono">{readout.offset}px</dd>
        </div>
        <div>
          <dt className="sc-t-caption sc-text-2">velocity</dt>
          <dd className="sc-t-mono">{readout.velocity}px/s</dd>
        </div>
        <div>
          <dt className="sc-t-caption sc-text-2">project(velocity)</dt>
          <dd className="sc-t-mono">{readout.projected}px</dd>
        </div>
        <div>
          <dt className="sc-t-caption sc-text-2">decyzja</dt>
          <dd>{readout.willDismiss ? "Zamknij" : "Wróć"}</dd>
        </div>
      </dl>
      {status === "dismissed" && (
        <p className="sc-t-caption" style={{ color: "var(--sc-positive)" }}>
          Zamknięto z prędkością {Math.round(lastVelocity)}px/s (symulacja na witrynie — panel wraca).
        </p>
      )}
    </div>
  );
}
