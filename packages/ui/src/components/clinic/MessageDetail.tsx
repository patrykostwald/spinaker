import Link from "next/link";
import { CAMPS, CAMP_LABELS, type MessageDay } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { SectionHeader } from "../../kit/SectionHeader";
import { ClinicNav } from "./ClinicNav";
import { AiTag } from "./SpinParts";

export function MessageDetail({ data }: { data: MessageDay }) {
  return <article className="sc-clinic-archives sc-message-detail">
    <ClinicNav />
    <SectionHeader variant="page" title={`Przekazy dnia: ${formatDatePl(data.day)}`}
      kicker={<AiTag />} subtitle="Syntezy wpisów z oficjalnych kont rządzących i opozycji wraz ze źródłami."
      link={<Link href="/klinika/przekazy">Wszystkie przekazy →</Link>} />
    <nav className="sc-message-detail__anchors" aria-label="Strony przekazu">
      <a href="#rzadzacy">Rządzący</a><a href="#opozycja">Opozycja</a>
    </nav>
    {CAMPS.map(camp => {
      const message = data[camp];
      const anchor = camp === "government" ? "rzadzacy" : "opozycja";
      return <section key={camp} id={anchor} className="sc-message-detail__camp" aria-labelledby={`${anchor}-title`}>
        <SectionHeader titleId={`${anchor}-title`} title={CAMP_LABELS[camp]} />
        {message ? <>
          <dl className="sc-message-detail__meta">
            <div><dt>Dzień przekazu</dt><dd><time dateTime={message.day}>{formatDatePl(message.day)}</time></dd></div>
            <div><dt>Materiał</dt><dd>{message.posts_count} wpisów z kont tej strony</dd></div>
            <div><dt>Zakres publikacji źródeł</dt><dd>{message.scope?.date_from && message.scope.date_to
              ? <>{formatDateTimePl(message.scope.date_from)} – {formatDateTimePl(message.scope.date_to)}</>
              : "Brak zapisanych dat źródeł"}</dd></div>
            {message.created_at ? <div><dt>Przygotowano</dt><dd>{formatDateTimePl(message.created_at)}</dd></div> : null}
            {message.reviewed_at ? <div><dt>Zatwierdzono</dt><dd>{formatDateTimePl(message.reviewed_at)}</dd></div> : null}
            <div><dt>Model</dt><dd>{message.model || "Nie zapisano nazwy modelu"}</dd></div>
          </dl>
          <p className="sc-message-detail__lead">{message.message}</p>
          {message.analysis?.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>)}
          {message.themes.length ? <ul className="sc-spin-techniques" aria-label="Główne hasła">{message.themes.map(theme => <li key={theme}>{theme}</li>)}</ul> : null}
          <h3>Źródła — wpisy ({message.posts?.length ?? 0})</h3>
          {message.posts?.length ? <ol className="sc-message-detail__sources">{message.posts.map(post => <li key={post.url}>
            <a href={post.url} target="_blank" rel="noopener noreferrer"><strong>{post.author}</strong> @{post.handle} ↗</a>
            <time dateTime={post.published_at}>{formatDateTimePl(post.published_at)}</time>
            {post.available === false ? <p>Wpis jest niedostępny.</p> : <p>{post.text}</p>}
          </li>)}</ol> : <p>Brak zapisanych wpisów źródłowych.</p>}
        </> : <p>Brak opublikowanego przekazu tej strony w tym dniu.</p>}
      </section>;
    })}
  </article>;
}
