"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../kit";
import { getClinicQueue, reviewDailyMessage, reviewSpin } from "../../lib/clinic";
import { useAccount } from "../../lib/account";
import { SpinDiagnosisBody } from "./SpinDetail";
import { SpinAuthorRow } from "./SpinParts";

/** Kolejka zatwierdzania. Tylko dwie decyzje — treści nie da się tu zmienić. */
export function ClinicQueue() {
  const account = useAccount();
  const isStaff = Boolean(account.data?.user?.is_staff);
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["clinic-queue"], queryFn: getClinicQueue, enabled: isStaff, refetchInterval: 60_000 });
  const [busy, setBusy] = useState<string>("");
  const [error, setError] = useState("");

  async function decide(kind: "spin" | "message", id: number, decision: "approve" | "reject") {
    setBusy(`${kind}-${id}`); setError("");
    try {
      await (kind === "spin" ? reviewSpin(id, decision) : reviewDailyMessage(id, decision));
      await cache.invalidateQueries({ queryKey: ["clinic-queue"] });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się zapisać decyzji.");
    } finally { setBusy(""); }
  }

  if (account.isLoading) return <div className="sc-clinic"><p className="sc-clinic-empty">Ładowanie…</p></div>;
  if (!isStaff) return <div className="sc-clinic"><p className="sc-clinic-empty">Kolejka Kliniki jest dostępna tylko dla zespołu. <Link href="/konto">Zaloguj się</Link></p></div>;
  const data = query.data;
  const buttons = (kind: "spin" | "message", id: number) => (
    <div className="sc-clinic-queue__actions">
      <Button variant="primary" size="sm" loading={busy === `${kind}-${id}`} disabled={Boolean(busy)} onClick={() => decide(kind, id, "approve")}>Zatwierdź</Button>
      <Button variant="quiet" size="sm" disabled={Boolean(busy)} onClick={() => decide(kind, id, "reject")}>Odrzuć</Button>
    </div>
  );
  return (
    <div className="sc-clinic sc-clinic-queue">
      <header className="sc-clinic-head">
        <p className="sc-clinic-kicker">Klinika · kolejka</p>
        <h1>Do zatwierdzenia</h1>
        <p className="sc-clinic-lead">Zatwierdzasz albo odrzucasz — treści diagnozy nie da się zmienić. Odrzucona diagnoza nie jest publikowana.</p>
        {data && <p className="sc-clinic-notice">Czeka {data.counts.pending} · zatwierdzone {data.counts.approved} · odrzucone {data.counts.rejected} · bez treści do oceny {data.counts.not_applicable}
          {Object.keys(data.counts.failed).length > 0 && ` · błędy: ${Object.entries(data.counts.failed).map(([code, n]) => `${code} ${n}`).join(", ")}`}
          {data.counts.suggestions > 0 && <> · <a href="/admin/news/xaccountsuggestion/">sugestie kont X: {data.counts.suggestions}</a></>}</p>}
      </header>
      {error && <p role="alert" className="sc-clinic-empty">{error}</p>}
      {data?.messages.map(message => (
        <article key={`m-${message.id}`} className="sc-clinic-queue__item">
          <p className="sc-clinic-kicker">Przekaz dnia · {message.camp_label} · {message.day} · {message.posts_count} postów</p>
          <p className="sc-clinic-message__text">{message.message}</p>
          <p>{message.themes.join(" · ")}</p>
          {buttons("message", message.id)}
        </article>
      ))}
      {data?.diagnoses.map(spin => (
        <article key={spin.id} className="sc-clinic-queue__item sc-spin-detail__grid">
          <aside className="sc-spin-detail__post">
            <p className="sc-clinic-kicker">{spin.camp_label}</p>
            <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} />
            <p className="sc-spin-card__text sc-spin-card__text--full">{spin.post.text}</p>
            <a className="sc-spin-card__source" href={spin.post.url} target="_blank" rel="noopener noreferrer">Post na X ↗</a>
          </aside>
          <div className="sc-spin-detail__diagnosis"><SpinDiagnosisBody spin={spin} />{buttons("spin", spin.id)}</div>
        </article>
      ))}
      {data && !data.diagnoses.length && !data.messages.length && <p className="sc-clinic-empty">Kolejka jest pusta.</p>}
    </div>
  );
}
