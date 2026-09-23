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

  return <article className="mvp-info-page mvp-support-page">
    <header className="mvp-info-hero"><p>WSPARCIE</p><h1>Wesprzyj spin.clinic</h1><p>Dobrowolne wsparcie pomaga rozwijać katalog źródeł, weryfikację dostępu i narzędzia redakcyjne.</p></header>
    <section><h2>Wybierz sposób wsparcia</h2>{links.length ? <><p>Wsparcie obsługują wyłącznie oficjalne serwisy zewnętrzne. spin.clinic nie przetwarza danych płatniczych.</p><div className="mvp-support-links">{links.map(link => <a key={link.href} href={link.href} target="_blank" rel="noreferrer">{link.label} ↗</a>)}</div></> : <p>Linki do BuyCoffee i Patronite pojawią się tutaj po uruchomieniu oficjalnych profili projektu. Nie pobieramy płatności bezpośrednio w serwisie.</p>}</section>
  </article>;
}
