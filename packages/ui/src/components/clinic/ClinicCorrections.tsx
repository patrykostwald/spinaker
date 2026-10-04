"use client";

import Link from "next/link";
import { useInfiniteQuery } from "@tanstack/react-query";
import { getClinicCorrections, type ClinicAuthorReply, type WithdrawnDiagnosis } from "../../lib/clinic";
import { formatDateTimePl } from "../../lib/utils";
import { Button } from "../../kit/Button";
import { SectionHeader } from "../../kit/SectionHeader";
import { ClinicNav } from "./ClinicNav";
import { SpinAuthorRow } from "./SpinParts";
import { Loading } from "../../kit/Loading";

const labels = { withdrawal: "Wycofanie", hiding: "Ukrycie prawne", author_reply: "Odpowiedź autora" };

export function ClinicCorrections() {
  const query = useInfiniteQuery({
    queryKey: ["clinic-corrections"], queryFn: ({ pageParam }) => getClinicCorrections(pageParam),
    initialPageParam: 1, getNextPageParam: last => last.next_page ?? undefined,
  });
  const first = query.data?.pages[0];
  const events = query.data?.pages.flatMap(page => page.results) ?? [];
  return <section className="sc-corrections">
    <ClinicNav />
    <SectionHeader variant="page" title="Rejestr korekt" subtitle="Przejrzystość także wtedy, gdy popełniamy błąd." />
    <p className="sc-corrections__lead">Treści AI nie poprawiamy ręcznie. Możemy wycofać całą diagnozę: każde wycofanie jest tu widoczne.
      Publikujemy też informacje o ukryciach prawnych i odpowiedzi autorów wypowiedzi.</p>
    {first ? <>
      <dl className="sc-corrections__counts" aria-label="Liczniki rejestru">
        <div><dt>Wycofane diagnozy</dt><dd>{first.counts.withdrawn.toLocaleString("pl-PL")}<span>z {first.counts.published.toLocaleString("pl-PL")} opublikowanych</span></dd></div>
        <div><dt>Ukrycia prawne</dt><dd>{first.counts.hidden.toLocaleString("pl-PL")}</dd></div>
        <div><dt>Odpowiedzi autorów</dt><dd>{first.counts.replies.toLocaleString("pl-PL")}</dd></div>
      </dl>
      <p className="sc-corrections__note">Liczba opublikowanych obejmuje także diagnozy później wycofane lub ukryte. Zdarzenia pokazujemy od najnowszych.</p>
    </> : null}
    {query.isPending ? <p role="status"><Loading label="Wczytywanie rejestru" /></p> : null}
    {query.isError ? <p role="alert">Nie udało się wczytać rejestru. <Button onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</Button></p> : null}
    {first && !events.length ? <p className="sc-corrections__empty">Na razie nie wycofaliśmy żadnej diagnozy.</p> : null}
    <ol className="sc-corrections__feed" aria-label="Zdarzenia w rejestrze">{events.map(event => <li key={event.id}>
      <div className="sc-corrections__event-meta"><time dateTime={event.date}>{formatDateTimePl(event.date)}</time>
        <span className="sc-corrections__chip" data-type={event.type}>{labels[event.type]}</span></div>
      <div className="sc-corrections__event-body">
        {event.author ? <><h2>{event.author.name}</h2><p className="sc-corrections__note">{event.camp_label}{event.post_date ? <> · wpis z <time dateTime={event.post_date}>{formatDateTimePl(event.post_date)}</time></> : null}</p></> : null}
        <p>{event.notice || (event.type === "withdrawal" ? event.reason : event.type === "author_reply" ? event.reply_excerpt : "Ukryto po zgłoszeniu prawnym")}</p>
        {event.diagnosis_url ? <Link href={event.diagnosis_url}>{event.type === "author_reply" ? "Przeczytaj całą odpowiedź" : "Zobacz informację o diagnozie"} →</Link> : null}
      </div>
    </li>)}</ol>
    {query.hasNextPage ? <Button disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? <Loading inline label="Wczytywanie" /> : "Pokaż wcześniejsze zdarzenia"}</Button> : null}
    <p className="sc-corrections__contact">Chcesz zgłosić błąd lub przesłać odpowiedź? <Link href="/o-nas#kontakt">Skontaktuj się z nami</Link>. <Link href="/metodologia#korekty">Zasady korekt</Link></p>
  </section>;
}

export function AuthorReplies({ replies }: { replies?: ClinicAuthorReply[] }) {
  if (!replies?.length) return null;
  return <section className="sc-author-replies" aria-labelledby="author-replies-title">
    <h2 id="author-replies-title">Odpowiedź autora</h2>
    <p>Stanowisko autora wypowiedzi. Odpowiedź nie zmienia diagnozy AI.</p>
    {replies.map(reply => <article key={reply.id}>
      <p className="sc-corrections__note">Otrzymano: <time dateTime={reply.received_at}>{formatDateTimePl(reply.received_at)}</time> · opublikowano: <time dateTime={reply.published_at}>{formatDateTimePl(reply.published_at)}</time></p>
      <p className="sc-author-replies__body">{reply.body}</p>
      <a href={reply.source_url} target="_blank" rel="noopener noreferrer">Źródło odpowiedzi ↗</a>
    </article>)}
  </section>;
}

export function WithdrawnSpin({ spin }: { spin: WithdrawnDiagnosis }) {
  return <section className="sc-corrections sc-withdrawn">
    <ClinicNav />
    <Link href="/klinika/korekty">← Rejestr korekt</Link>
    <h1>Diagnoza wycofana</h1>
    <div className="sc-withdrawn__notice" role="status">
      <p><strong>Diagnoza wycofana <time dateTime={spin.withdrawn_at}>{formatDateTimePl(spin.withdrawn_at)}</time>:</strong> {spin.withdrawn_reason}</p>
    </div>
    <div className="sc-withdrawn__source">
      <p className="sc-clinic-kicker">{spin.camp_label}</p>
      <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} size="lg" />
      <a href={spin.post.url} target="_blank" rel="noopener noreferrer">Oryginalny wpis na X ↗</a>
    </div>
    <p className="sc-corrections__lead">Wycofaliśmy tę diagnozę. Jej ocena i analiza nie są już publikowane ani uwzględniane w zestawieniach Kliniki.</p>
    <p><Link href="/metodologia#korekty">Jak postępujemy po zgłoszeniu błędu?</Link></p>
    <AuthorReplies replies={spin.author_replies} />
  </section>;
}
