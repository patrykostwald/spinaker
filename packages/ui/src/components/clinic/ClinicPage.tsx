"use client";

import { useState } from "react";
import Link from "next/link";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Button, Segmented } from "../../kit";
import { CAMPS, CAMP_LABELS, getClinicAccounts, getClinicPage, getClinicSpins, type Camp, type DailyMessage } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { AiTag, IntensityMeter, SpinAuthorRow, SpinCard, SpinScale, VerdictTag } from "./SpinParts";

function MessageBox({ camp, message }: { camp: Camp; message: DailyMessage | null }) {
  return (
    <article className="sc-clinic-message" data-camp={camp}>
      <p className="sc-clinic-kicker">{CAMP_LABELS[camp]} · przekaz dnia <AiTag /></p>
      {message ? <>
        <p className="sc-clinic-message__text">{message.message}</p>
        {message.themes.length > 0 && <ul className="sc-spin-techniques" aria-label="Główne hasła">{message.themes.map(theme => <li key={theme}>{theme}</li>)}</ul>}
        <p className="sc-clinic-message__meta">{formatDatePl(message.day)} · na podstawie {message.posts_count} postów</p>
      </> : <p className="sc-clinic-empty">Przekaz dnia pojawi się, gdy Dr. Spin przeanalizuje posty z tego dnia.</p>}
    </article>
  );
}

function CampColumn({ camp, initial }: { camp: Camp; initial: import("../../lib/clinic").SpinCardData[] }) {
  const more = useInfiniteQuery({
    queryKey: ["clinic-spins", camp],
    queryFn: ({ pageParam }) => getClinicSpins(camp, pageParam),
    initialPageParam: 2,
    getNextPageParam: last => last.next_page ?? undefined,
    enabled: false,
  });
  const extra = more.data?.pages.flatMap(page => page.results) ?? [];
  const cards = [...initial, ...extra.filter(card => !initial.some(item => item.id === card.id))];
  const canLoad = initial.length >= 12 && (!more.data || more.hasNextPage);
  return (
    <section className="sc-clinic-column" data-camp={camp} aria-labelledby={`clinic-${camp}`}>
      <h2 id={`clinic-${camp}`} className="sc-clinic-column__title">{CAMP_LABELS[camp]}</h2>
      {cards.length ? cards.map(spin => <SpinCard key={spin.id} spin={spin} />)
        : <p className="sc-clinic-empty">Brak zatwierdzonych diagnoz. Pojawią się tu, gdy konta tej strony coś opublikują.</p>}
      {canLoad && <Button variant="quiet" loading={more.isFetching} onClick={() => (more.data ? more.fetchNextPage() : more.refetch())}>Pokaż wcześniejsze</Button>}
    </section>
  );
}

function AccountsList() {
  const [open, setOpen] = useState(false);
  const query = useQuery({ queryKey: ["clinic-accounts"], queryFn: getClinicAccounts, enabled: open });
  return (
    <details className="sc-clinic-accounts" onToggle={event => setOpen((event.target as HTMLDetailsElement).open)}>
      <summary>Z jakich kont czytamy</summary>
      <p>Czytamy wyłącznie konta, które zespół potwierdził oficjalnym dowodem (strona instytucji, profil w Sejmie). Podział na rządzących i opozycję wynika z przynależności klubowej.</p>
      {query.isLoading && <p>Ładowanie…</p>}
      {query.data && <div className="sc-clinic-accounts__grid">{CAMPS.map(camp => (
        <section key={camp}>
          <h3>{CAMP_LABELS[camp]}</h3>
          <ul>{query.data.results.filter(item => item.camp === camp).map(item => (
            <li key={item.handle}>
              <a href={item.url} target="_blank" rel="noopener noreferrer">@{item.handle}</a>
              {" — "}{item.figure_id ? <Link href={`/osoby-publiczne/${item.figure_id}`}>{item.figure_name}</Link> : item.display_name}
              {item.party ? ` · ${item.party.short}` : ""}
            </li>
          ))}</ul>
        </section>
      ))}</div>}
    </details>
  );
}

export function ClinicPage() {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, refetchInterval: 5 * 60_000 });
  const [side, setSide] = useState<Camp>("government");
  const data = query.data;
  return (
    <div className="sc-clinic">
      <header className="sc-clinic-head">
        <p className="sc-clinic-kicker">Klinika spinu</p>
        <h1>Diagnozy przekazów polityków</h1>
        <p className="sc-clinic-lead">
          Każdy nowy post z kont, które czytamy, trafia do Dr. Spina. AI rozkłada go na czynniki pierwsze i stawia diagnozę —
          według tych samych zasad dla każdej strony. Oceniamy komunikat, nie człowieka.
        </p>
        <p className="sc-clinic-notice"><AiTag /> {data?.notice ?? "Diagnozy przygotowuje AI automatycznie. Człowiek może je tylko zatwierdzić albo odrzucić — nie zmienia ich treści."} <Link href="/o-nas#klinika">Jak to działa</Link></p>
      </header>

      {query.isError && <p role="alert" className="sc-clinic-empty">Nie udało się pobrać Kliniki. <Button size="sm" variant="quiet" onClick={() => query.refetch()}>Ponów</Button></p>}
      {query.isLoading && <p className="sc-clinic-empty">Ładowanie diagnoz…</p>}

      {data && <>
        <SpinScale scale={data.scale} />

        <section className="sc-clinic-split" aria-label="Przekazy dnia">
          {CAMPS.map(camp => <MessageBox key={camp} camp={camp} message={data.messages[camp]} />)}
        </section>

        <section className="sc-clinic-sotd" aria-labelledby="sotd-title">
          <p className="sc-clinic-kicker">Spin dnia</p>
          {data.spin_of_day ? <div className="sc-clinic-sotd__body">
            <div className="sc-clinic-sotd__post">
              <SpinAuthorRow author={data.spin_of_day.author} publishedAt={data.spin_of_day.post.published_at} size="lg" />
              <p className="sc-clinic-sotd__camp">{data.spin_of_day.camp_label}</p>
              <blockquote>{data.spin_of_day.post.text}</blockquote>
              <a href={data.spin_of_day.post.url} target="_blank" rel="noopener noreferrer">Post na X ↗</a>
            </div>
            <div className="sc-clinic-sotd__diagnosis">
              <p className="sc-spin-card__verdict"><VerdictTag verdict={data.spin_of_day.verdict} label={data.spin_of_day.verdict_label} /><IntensityMeter value={data.spin_of_day.intensity} /></p>
              <h2 id="sotd-title"><Link href={`/klinika/${data.spin_of_day.id}`}>{data.spin_of_day.headline}</Link></h2>
              {data.spin_of_day.analysis.split(/\n{2,}/).slice(0, 3).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
              <Link className="sc-clinic-sotd__more" href={`/klinika/${data.spin_of_day.id}`}>Pełna diagnoza, źródła i komentarze →</Link>
            </div>
          </div> : <p className="sc-clinic-empty" id="sotd-title">Spin dnia to diagnoza z najwyższą siłą spinu z ostatniej doby. Pojawi się po pierwszych zatwierdzonych diagnozach.</p>}
        </section>

        <Segmented className="sc-clinic-switch" name="clinic-side" label="Strona" value={side} onChange={value => setSide(value as Camp)}
          options={CAMPS.map(camp => ({ value: camp, label: CAMP_LABELS[camp] }))} />
        <div className="sc-clinic-split sc-clinic-columns" data-side={side}>
          {CAMPS.map(camp => <CampColumn key={camp} camp={camp} initial={data.columns[camp]} />)}
        </div>

        <p className="sc-clinic-roadmap">
          Dziś diagnoza to tekst ze źródłami z wyszukiwania. W miarę rozbudowy naszej bazy dowodami będą boxy z materiałami źródłowymi —
          tak jak w nitkach kontekstowych.
        </p>
        <AccountsList />
      </>}
    </div>
  );
}
