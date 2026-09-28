import { InfoPage } from '@spin-clinic/ui/kit';
import { NewsletterSignup } from '@spin-clinic/ui';

export const metadata = { title: 'Newsletter · spin.clinic' };

export default function NewsletterPage() {
  return <InfoPage eyebrow="NEWSLETTER" title="Powiadomienie o starcie" lead="Zostaw e-mail, a napiszemy, gdy wystartuje pełna wersja spin.clinic. Zapis potwierdzasz linkiem z maila; wypiszesz się jednym kliknięciem.">
    <NewsletterSignup source="newsletter" />
    <section><h2>Co dostaniesz</h2><p>Wiadomość o starcie pełnej wersji i — rzadko — o najważniejszych nowościach: nowych funkcjach Kliniki, raportach Dr. Spina, zbiórce. Bez reklam i bez przekazywania adresu innym firmom.</p></section>
    <section><h2>Twoje dane</h2><p>Przechowujemy tylko adres e-mail, datę zapisu i potwierdzenia oraz wersję zgody. Administrator: iapply sp. z o.o. Szczegóły w <a href="/polityka-prywatnosci">polityce prywatności</a>.</p></section>
  </InfoPage>;
}
