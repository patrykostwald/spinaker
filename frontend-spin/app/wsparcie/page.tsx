import { Button, InfoPage } from '@spin-clinic/ui/kit';

export const metadata = { title: 'Wsparcie · spin.clinic' };

function publicSupportUrl(value: string | undefined) {
  try {
    const url = new URL(value || '');
    return url.protocol === 'https:' ? url.toString() : '';
  } catch {
    return '';
  }
}

export default function SupportPage() {
  const buycoffee = publicSupportUrl(process.env.BUYCOFFEE_URL);
  const patronite = publicSupportUrl(process.env.PATRONITE_URL);
  const links = [
    buycoffee && { label: 'Wesprzyj przez BuyCoffee', href: buycoffee },
    patronite && { label: 'Wesprzyj przez Patronite', href: patronite },
  ].filter(Boolean) as { label: string; href: string }[];

  return <InfoPage eyebrow="WSPARCIE" title="Wesprzyj spin.clinic" lead="Dobrowolne wsparcie pomaga rozwijać katalog źródeł, weryfikację dostępu i narzędzia do pracy z kontekstem.">
    <section><h2>Wybierz sposób wsparcia</h2>{links.length ? <><p>Wsparcie obsługują wyłącznie oficjalne serwisy zewnętrzne. spin.clinic nie przetwarza danych płatniczych.</p><div className="sc-info-page__actions">{links.map(link => <Button key={link.href} href={link.href} variant="primary">{link.label}</Button>)}</div></> : <p>Linki do BuyCoffee i Patronite pojawią się tutaj po uruchomieniu oficjalnych profili projektu. Nie pobieramy płatności bezpośrednio w serwisie.</p>}</section>
  </InfoPage>;
}
