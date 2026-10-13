"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { SpinMeter } from "./SpinMeter";
import { initials } from "../lib/spinScale";

/**
 * Jeden schemat wiersza list v3 (diagnozy, spinki, przekazy): awatar z inicjałami, rodzaj, tytuł w pełnej długości,
 * meta (autor, data, identyfikator w Geist tabular-nums) i jedna liczba siły po prawej (na telefonie w linii rodzaju).
 */
export function SpinRow({ href, name, avatarUrl, kind, icon, title, meta, value, valueLabel, index = 0, onOpen }: {
  href: string; name: string; avatarUrl?: string | null; kind: ReactNode; icon?: ReactNode; title: string;
  meta: ReactNode[]; value?: number | null; valueLabel?: ReactNode; index?: number; onOpen?: () => void;
}) {
  return <li className="sc-v3-row" style={{ "--d": Math.min(index, 6) } as CSSProperties}>
    <Link href={href} onClick={onOpen}>
      <span className="sc-v3-av" aria-hidden="true">{avatarUrl ? <img src={avatarUrl} alt="" loading="lazy" decoding="async" /> : initials(name)}</span>
      <div style={{ minWidth: 0 }}>
        <p className="sc-v3-row__kind">{icon}<span>{kind}</span></p>
        <h3>{title}</h3>
        <p className="sc-v3-row__meta">{meta.filter(Boolean).map((item, i) => <span key={i}>{item}</span>)}</p>
      </div>
      {typeof value === "number" ? <SpinMeter value={value} bare /> : valueLabel ?? <span />}
    </Link>
  </li>;
}
