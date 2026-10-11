"use client";
import { nb } from './ui';

/**
 * F9: przybornik odnośników zewnętrznych przy podmiocie i osobie. Same odnośniki do oficjalnych stron;
 * nic stąd nie wysyła danych (wyszukiwarki rejestrów nie przyjmują wypełnienia, więc podajemy, co wpisać).
 */
type Tool = { label: string; href: string; hint: string };

export function companyTools(c: { krs: string; nip?: string; regon?: string }): Tool[] {
  const krs = c.krs ? `KRS ${c.krs}` : '';
  const nip = c.nip ? `NIP ${c.nip}` : '';
  const both = [krs, nip].filter(Boolean).join(' lub ') || 'numer z odpisu';
  return [
    { label: 'Wyszukiwarka KRS (MS)', href: 'https://wyszukiwarka-krs.ms.gov.pl/', hint: `wpisz ${krs || both}` },
    { label: 'Odpis aktualny (API MS)', href: c.krs ? `https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/${c.krs}?rejestr=P&format=json` : 'https://api-krs.ms.gov.pl/', hint: 'urzędowy odpis w JSON' },
    { label: 'eKRS', href: 'https://ekrs.ms.gov.pl/', hint: 'portal dokumentów i wpisów' },
    { label: 'Sprawozdania finansowe (RDF)', href: 'https://rdf-przegladarka.ms.gov.pl/', hint: `wpisz ${krs || both}` },
    { label: 'CEIDG', href: 'https://aplikacja.ceidg.gov.pl/ceidg/ceidg.public.ui/search.aspx', hint: `wpisz ${nip || 'NIP'}` },
    { label: 'Biała lista VAT', href: 'https://www.podatki.gov.pl/wykaz-podatnikow-vat-wyszukiwarka/', hint: `wpisz ${nip || 'NIP'}` },
    { label: 'Krajowy Rejestr Zadłużonych', href: 'https://krz.ms.gov.pl/', hint: `wpisz ${krs || nip || 'nazwę'}` },
    { label: 'Monitor Sądowy i Gospodarczy', href: 'https://ems.ms.gov.pl/', hint: 'ogłoszenia o spółce' },
    { label: 'e-Zamówienia (BZP)', href: 'https://ezamowienia.gov.pl/mp-client/search/list', hint: `wpisz ${nip || 'nazwę'}` },
    { label: 'TED (UE)', href: 'https://ted.europa.eu/pl/', hint: 'zamówienia powyżej progów UE' },
    { label: 'Internet Archive (Wayback)', href: 'https://web.archive.org/', hint: 'wpisz adres strony spółki' },
    ...(c.krs ? [{ label: 'rejestr.io (nieurzędowy)', href: `https://rejestr.io/krs/${Number(c.krs)}`, hint: 'dodatkowy podgląd powiązań' }] : []),
  ];
}

export function personTools(p: { name: string }): Tool[] {
  const q = encodeURIComponent(`"${p.name}"`);
  return [
    { label: 'Google News', href: `https://news.google.com/search?q=${q}`, hint: 'otwiera wyszukiwanie nazwiska u Google' },
    { label: 'Internet Archive (Wayback)', href: 'https://web.archive.org/', hint: 'wpisz adres strony do sprawdzenia' },
    { label: 'Wyszukiwarka KRS (MS)', href: 'https://wyszukiwarka-krs.ms.gov.pl/', hint: 'po numerze KRS spółki z listy' },
    { label: 'CEIDG', href: 'https://aplikacja.ceidg.gov.pl/ceidg/ceidg.public.ui/search.aspx', hint: 'własna działalność gospodarcza' },
    { label: 'Krajowy Rejestr Zadłużonych', href: 'https://krz.ms.gov.pl/', hint: 'postępowania upadłościowe' },
    { label: 'Monitor Sądowy i Gospodarczy', href: 'https://ems.ms.gov.pl/', hint: 'ogłoszenia sądowe' },
    { label: 'Portal Orzeczeń', href: 'https://orzeczenia.ms.gov.pl/', hint: 'wyroki sądów powszechnych' },
    { label: 'Centralny Rejestr Umów', href: 'https://www.crur.gov.pl/', hint: 'umowy jednostek publicznych' },
    { label: 'e-Zamówienia (BZP)', href: 'https://ezamowienia.gov.pl/mp-client/search/list', hint: 'zamówienia publiczne' },
  ];
}

export function Przybornik({ tools, id, title = 'Przybornik: oficjalne rejestry' }: { tools: Tool[]; id: string; title?: string }) {
  return <section className="px-card px-tools" aria-labelledby={id}>
    <h3 id={id} className="px-h3">{title} <small>{tools.length}</small></h3>
    <ul className="px-tools__list">{tools.map(t => <li key={t.label}>
      <a href={t.href} target="_blank" rel="noopener noreferrer"><b>{t.label} ↗</b><small>{t.hint}</small></a></li>)}</ul>
    <p className="px-note">{nb('Same odnośniki do zewnętrznych stron. Nie wysyłamy tam żadnych danych; po otwarciu przepisz numer ze strony.')}</p>
  </section>;
}
