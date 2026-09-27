import { Suspense } from 'react';
import { InfoPage } from '@spin-clinic/ui/kit';
import { NewsletterAction } from '../NewsletterAction';

export const metadata = { title: 'Wypisanie z newslettera · spin.clinic', robots: { index: false } };

export default function UnsubscribePage() {
  return <InfoPage eyebrow="NEWSLETTER" title="Wypisanie z newslettera" lead="Jedno kliknięcie i nie wyślemy już żadnej wiadomości na ten adres.">
    <section><Suspense><NewsletterAction mode="unsubscribe" /></Suspense></section>
  </InfoPage>;
}
