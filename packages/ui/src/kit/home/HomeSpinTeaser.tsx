"use client";

/**
 * Element „Dr. Spin” na stronie głównej (28.09.2026): jedna całość z trzema oznaczonymi częściami —
 * 1 · Spin dnia (przełącznik Rządzący | Opozycja, pierwsza strona z mocniejszym spinem dnia),
 * 2 · Przekaz dnia i liczby obu stron (ta sama miara),
 * 3 · Wywiady (ocena gościa i warsztatu prowadzącego).
 * Na telefonie długie części są przycięte — rozwija je przycisk albo przytrzymanie palcem.
 */

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, getClinicPage, type Camp, type ClinicPageData } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { useLongPress } from "../../lib/useLongPress";
import { AiTag } from "../../components/clinic/SpinParts";
import { InterviewArchive, InterviewBox, MessageBox } from "../../components/clinic/ClinicExtras";
import { SpinOfDay } from "../../components/clinic/ClinicPage";

/** Godziny generowania przekazu dnia (jak w harmonogramie serwera). */
const MESSAGE_SLOTS: Array<[number, number]> = [[9, 0], [12, 0], [15, 0], [18, 0], [21, 30]];

function nextMessageSlot(now: Date): string {
  const minutes = now.getHours() * 60 + now.getMinutes();
  const next = MESSAGE_SLOTS.find(([hour, minute]) => hour * 60 + minute > minutes) ?? MESSAGE_SLOTS[0];
  return `${next[0]}:${String(next[1]).padStart(2, "0")}`;
}

const WINDOW_NOTE: Record<string, string> = {
  "24h": "najmocniejszy spin tej strony z ostatniej doby",
  "72h": "najmocniejszy spin tej strony z ostatnich trzech dni",
  latest: "ta strona nie ma świeżego spinu — to jej najnowszy",
};

/** Część elementu Dr. Spin: numer, nazwa i jedno zdanie, na co patrzy widz. */
function Part({ index, title, hint, children, id }: { index: number; title: string; hint: string; children: ReactNode; id: string }) {
  return (
    <section className="sc-drspin__part" aria-labelledby={id}>
      <header className="sc-drspin__part-head">
        <p className="sc-drspin__part-label" id={id}><span>{index}</span>{title}</p>
        <p className="sc-drspin__part-hint">{hint}</p>
      </header>
      {children}
    </section>
  );
}

/** Telefon: część przycięta do kilku ekranów — „Rozwiń” albo przytrzymanie palcem. Na komputerze bez zmian. */
function MobileClamp({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const press = useLongPress(() => setOpen(true));
  return (
    <div className="sc-mclamp" data-open={open || undefined} {...(open ? {} : press)}>
      {children}
      {open ? null : <button type="button" className="sc-mclamp__more" onClick={() => setOpen(true)}>{label} ↓</button>}
    </div>
  );
}

function CampNumbers({ stats, camp }: { stats: NonNullable<ClinicPageData["stats"]>; camp: Camp }) {
  const row = stats.by_camp?.[camp];
  if (!row) return null;
  const format = (value: number) => value.toLocaleString("pl-PL");
  return (
    <p className="sc-drspin__numbers">
      <strong>{format(row.read)}</strong> przeczytanych wpisów · <strong>{format(row.diagnosed)}</strong> diagnoz · {format(row.accounts)} kont
    </p>
  );
}

export function HomeSpinTeaser() {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, staleTime: 5 * 60_000 });
  const data = query.data;
  const [slot, setSlot] = useState<string | null>(null);
  const [camp, setCamp] = useState<Camp | null>(null);
  const [interviewOpen, setInterviewOpen] = useState(false);
  const [secondOpen, setSecondOpen] = useState(false);
  useEffect(() => setSlot(nextMessageSlot(new Date())), []);
  const emptyMessage = `Najbliższy przekaz${slot ? ` o ${slot}` : ""} — gdy posty opublikują co najmniej trzy konta tego obozu.`;
  if (!data) return null;

  const byCamp = data.spin_by_camp;
  const active: Camp = camp ?? byCamp?.order?.[0] ?? "government";
  const spin = byCamp?.spins?.[active] ?? null;
  const stats = data.stats;
  const format = (value: number) => value.toLocaleString("pl-PL");

  return (
    <section className="sc-drspin" aria-labelledby="home-drspin-title">
      <header className="sc-drspin__head">
        <div>
          <p className="sc-t-caption sc-text-3 sc-home-kicker">Klinika spinu <AiTag /></p>
          <h2 id="home-drspin-title" className="sc-t-title-l sc-home-section__title">Dr. Spin</h2>
        </div>
        <Link className="sc-home-spin__open" href="/klinika">Otwórz Klinikę spinu →</Link>
      </header>

      <Part index={1} id="drspin-part-1" title="Spin dnia" hint="Najmocniejszy spin dnia każdej strony — przełącz, żeby zobaczyć drugą. Ta sama miara dla obu.">
        <div className="sc-drspin__tabs" role="tablist" aria-label="Strona">
          {(byCamp?.order ?? CAMPS).map((key) => (
            <button key={key} type="button" role="tab" aria-selected={key === active} className="sc-drspin__tab" data-camp={key}
              onClick={() => setCamp(key)}>
              {CAMP_LABELS[key]}
              {byCamp?.spins?.[key] ? <small>{byCamp.spins[key]!.intensity}/100</small> : null}
            </button>
          ))}
        </div>
        {spin ? (
          <div className="sc-clinic-sotd sc-home-spin__sotd" role="tabpanel">
            {spin.window && spin.window !== "today" ? <p className="sc-drspin__window">{WINDOW_NOTE[spin.window]}{spin.window === "latest" && spin.post.published_at ? ` (${formatDatePl(spin.post.published_at)})` : ""}.</p> : null}
            <SpinOfDay key={spin.id} spin={spin} />
          </div>
        ) : (
          <p className="sc-t-body-s sc-text-2 sc-home-spin__empty">
            {CAMP_LABELS[active]}: jeszcze bez diagnozy. Strażnik przegląda każdy nowy post z oficjalnych kont, a te warte sprawdzenia bada Dr. Spin — rządzący i opozycja według tych samych zasad.
          </p>
        )}
      </Part>

      <Part index={2} id="drspin-part-2" title="Przekaz dnia i liczby" hint="Co każda strona chciała dziś przekazać (z co najmniej trzech kont) i ile jej wpisów przeczytaliśmy.">
        <div className="sc-clinic-split sc-home-spin__messages">
          {CAMPS.map((key) => (
            <div key={key} className="sc-drspin__side">
              <MessageBox camp={key} message={data.messages[key]} emptyText={emptyMessage} />
              {stats ? <CampNumbers stats={stats} camp={key} /> : null}
            </div>
          ))}
        </div>
        {stats ? (
          <p className="sc-drspin__total">
            Razem <strong>{format(stats.read.total)}</strong> przeczytanych wpisów · ta sama miara dla obu stron ·{" "}
            <Link href="/o-nas#konsylium">jak to liczymy →</Link>
          </p>
        ) : null}
      </Part>

      {data.interview ? (
        <Part index={3} id="drspin-part-3" title="Wywiady" hint="Najgłośniejsza rozmowa z politykiem z poprzedniego dnia — ocena gościa i warsztatu prowadzącego.">
          <MobileClamp label="Rozwiń wywiad">
            <p className="sc-drspin__meta">
              {data.interview.channel} · {formatDatePl(data.interview.day)} ·{" "}
              <button type="button" className="sc-home-interview__more" onClick={() => setInterviewOpen(true)} aria-haspopup="dialog">Pełna analiza ze źródłami →</button>
            </p>
            <InterviewBox interview={data.interview} open={interviewOpen} onOpenChange={setInterviewOpen} hideMore />
            {data.interview_second ? (
              <>
                <p className="sc-drspin__meta">
                  {data.interview_second.channel} · {formatDatePl(data.interview_second.day)} ·{" "}
                  <button type="button" className="sc-home-interview__more" onClick={() => setSecondOpen(true)} aria-haspopup="dialog">Pełna analiza ze źródłami →</button>
                </p>
                <InterviewBox interview={data.interview_second} open={secondOpen} onOpenChange={setSecondOpen} hideMore />
              </>
            ) : null}
          </MobileClamp>
          {data.interview_archive?.length ? <div className="sc-home-interview__archive"><InterviewArchive items={data.interview_archive.slice(0, 3)} /></div> : null}
        </Part>
      ) : null}
    </section>
  );
}
