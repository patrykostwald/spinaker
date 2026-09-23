export const metadata = { title: 'Prywatność i cookies · spin.clinic' };

export default function PrivacyPage() {
  return <article className="mvp-info-page">
    <header className="mvp-info-hero"><p>INFORMACJE</p><h1>Prywatność i cookies</h1><p>Ta strona opisuje obecny techniczny zakres wersji demonstracyjnej serwisu. Przed publicznym uruchomieniem zostanie uzupełniona o dane administratora i końcową konfigurację usług.</p></header>
    <section><h2>Lokalne ustawienia</h2><p>Przeglądarka może przechowywać wybór motywu oraz lokalnie zapisane widoki Bazy. Służą wyłącznie do działania interfejsu na tym urządzeniu.</p></section>
    <section><h2>Zewnętrzne usługi</h2><p>Po uruchomieniu integracji serwis będzie korzystać z API X i YouTube wyłącznie do pobierania dozwolonych danych. Ostateczna treść dokumentu wskaże aktywne usługi, cel i podstawę przetwarzania.</p></section>
  </article>;
}
