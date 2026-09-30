import { InfoPage } from '@spin-clinic/ui/kit';
import { NewsletterSignup } from '@spin-clinic/ui';

export const metadata = { title: 'Newsletter · spin.clinic' };

export default function NewsletterPage() {
  return <InfoPage eyebrow="NEWSLETTER" title="Powiadomienie o starcie" lead="Zostaw e-mail, a napiszemy, gdy wystartuje pełna wersja spin.clinic. Zapis potwierdzasz linkiem z maila; wypiszesz się jednym kliknięciem.">
    <NewsletterSignup source="newsletter" />
    <section><h2>Co dostaniesz</h2><p>Wiadomość o starcie pełnej wersji i — rzadko — o najważniejszych nowościach: nowych funkcjach Kliniki, raportach Dr. Spina, zbiórce. Bez reklam. Nie sprzedajemy adresów ani nie udostępniamy ich innym podmiotom do ich własnego marketingu.</p></section>
    <section><h2>Twoje dane</h2><p>Przechowujemy adres e-mail, status zapisu, daty zapisu, potwierdzenia i ewentualnej rezygnacji, miejsce zapisu na stronie oraz wersję zgody. Wiadomości wysyłamy przez dostawcę poczty obsługującego skrzynkę spin.clinic. Administrator: iapply sp. z o.o. Szczegóły w <a href="/polityka-prywatnosci">polityce prywatności</a>.</p></section>
  </InfoPage>;
}
