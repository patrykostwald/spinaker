"use client";

import type { DailyMessage } from "../../lib/clinic";
import { MessageCard } from "../../components/clinic/MessageCard";

export function HomePrzekazDnia({ government, opposition }: { government: DailyMessage | null; opposition: DailyMessage | null }) {
  if (!government && !opposition) return null;
  return <section className="sc-home-section sc-home-przekaz" aria-label="Przekaz dnia">
    <header className="sc-home-section__head"><h2 className="sc-t-title-l">Przekaz dnia</h2></header>
    <div className="sc-message-pair">
      <MessageCard camp="government" message={government} compact />
      <MessageCard camp="opposition" message={opposition} compact />
    </div>
  </section>;
}
