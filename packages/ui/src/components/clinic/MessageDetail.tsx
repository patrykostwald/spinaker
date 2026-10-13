"use client";

import Link from "next/link";
import { CAMPS, type MessageDay } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { PageHeaderV3 } from "../../kit/PageHeaderV3";
import { ClinicNav } from "./ClinicNav";
import { MessageCard } from "./MessageCard";

export function MessageDetail({ data }: { data: MessageDay }) {
  return <article className="sc-v3 sc-v3-page sc-message-detail">
    <PageHeaderV3 nav={<ClinicNav />} kicker={<><span className="sc-v3-tag" data-tone="accent" title="Wygenerowane z udziałem AI">AI</span> <span className="sc-v3-tag">BETA</span> Przekaz dnia · Dr. Spin (AI)</>}
      title={`Przekazy dnia: ${formatDatePl(data.day).replace(/ /g, "\u00A0")}`}
      sub="Syntezy wpisów z oficjalnych kont rządzących i opozycji wraz ze źródłami. Ta sama miara dla obu stron."
      actions={<Link className="sc-v3-lnk" href="/klinika/przekazy">Wszystkie przekazy <span className="sc-v3-ar" aria-hidden="true">→</span></Link>} />
    <MessageDayContent data={data} />
  </article>;
}

/** Para kart Rządzący / Opozycja o równej wysokości (te same elementy na tej samej wysokości). */
export function MessageDayContent({ data, compact = false }: { data: MessageDay; compact?: boolean }) {
  return <div className="sc-v3-msgs">{CAMPS.map(camp =>
    <MessageCard key={camp} camp={camp} day={data.day} message={data[camp]} compact={compact} />
  )}</div>;
}
