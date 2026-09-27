import { Suspense } from 'react';
import { InfoPage } from '@spin-clinic/ui/kit';
import { NewsletterAction } from '../NewsletterAction';

export const metadata = { title: 'Potwierdzenie zapisu · spin.clinic', robots: { index: false } };

export default function ConfirmPage() {
  return <InfoPage eyebrow="NEWSLETTER" title="Potwierdzenie zapisu" lead="Sprawdzamy link z maila i dopisujemy Cię do listy powiadomień o starcie.">
    <section><Suspense><NewsletterAction mode="confirm" /></Suspense></section>
  </InfoPage>;
}
