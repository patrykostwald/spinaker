"use client";

import Link from "next/link";
import { CAMPS, type MessageDay } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { SectionHeader } from "../../kit/SectionHeader";
import { ClinicNav } from "./ClinicNav";
import { AiTag } from "./SpinParts";
import { MessageCard } from "./MessageCard";

export function MessageDetail({ data }: { data: MessageDay }) {
  return <article className="sc-clinic-archives sc-message-detail">
    <ClinicNav />
    <SectionHeader variant="page" title={`Przekazy dnia: ${formatDatePl(data.day)}`}
      kicker={<AiTag />} subtitle="Syntezy wpisów z oficjalnych kont rządzących i opozycji wraz ze źródłami."
      link={<Link href="/klinika/przekazy">Wszystkie przekazy →</Link>} />
    <MessageDayContent data={data} />
  </article>;
}

export function MessageDayContent({ data }: { data: MessageDay }) {
  return <div className="sc-message-pair">{CAMPS.map(camp =>
    <MessageCard key={camp} camp={camp} day={data.day} message={data[camp]} />
  )}</div>;
}
