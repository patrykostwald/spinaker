import { InfoPage } from '@spin-clinic/ui/kit';

export const metadata = { title: 'Zasady korzystania · spin.clinic' };

export default function TermsPage() {
  return <InfoPage eyebrow="INFORMACJE" title="Zasady korzystania" lead="spin.clinic porządkuje i łączy odnośniki do materiałów źródłowych. Nie zastępuje publikacji wydawcy ani samodzielnej oceny czytelnika.">
    <section><h2>Materiały i kontekst</h2><p>Box pokazuje materiał, jego źródło, datę i odnośnik do oryginału. Powiązanie po haśle, kategorii, źródle lub czasie jest wskazówką do dalszego czytania, a nie dowodem, że jeden materiał potwierdza drugi. Dr. Spin przedstawia wybór i kolejność materiałów zatwierdzone przez zespół spin.clinic.</p></section>
    <section><h2>Klinika spinu</h2><p>Diagnozy postów polityków przygotowuje automatycznie AI i każda jest tak oznaczona, z nazwą modelu i wersją instrukcji. Zespół może diagnozę zatwierdzić albo odrzucić, ale nie zmienia jej treści. Diagnoza opisuje komunikat — techniki perswazji i zgodność twierdzeń ze źródłami — a nie osobę. Ustalenia o faktach mają linki do źródeł; bez źródła twierdzenie jest oznaczone jako „nie do sprawdzenia”. Zgłoszenia dotyczące diagnoz przyjmujemy pod adresem <a href="mailto:admin@spin.clinic">admin@spin.clinic</a>; po zgłoszeniu prawnym diagnoza może zostać ukryta.</p></section>
    <section><h2>Czego portal nie robi</h2><p>Nie ocenia osób, nie wydaje automatycznych werdyktów „prawda” lub „fałsz”, nie publikuje treści modeli bez decyzji człowieka i nie zastępuje oryginalnej publikacji. Jeśli czegoś nie wiemy, pokazujemy brak danych zamiast dopowiadać.</p></section>
    <section><h2>Źródła i prawa wydawców</h2><p>Szanujemy zasady dostępu do źródeł. Nie obchodzimy blokad, limitów ani płatnych dostępów. Pokazujemy konieczny opis i link do materiału; pełne teksty oraz inne utwory pozostają po stronie wydawcy, chyba że zakres wykorzystania jest wyraźnie dozwolony.</p></section>
    <section><h2>Materiały z platform</h2><p>Wpisy z X mogą służyć jako materiał źródłowy po ręcznym potwierdzeniu konta i przez oficjalne API. W przypadku YouTube wykorzystujemy dozwolone metadane oraz opis filmu, bez automatycznego pobierania transkrypcji.</p></section>
    <section><h2>Konta, komentarze i moderacja</h2><p>Po udostępnieniu funkcji społecznościowych użytkownik odpowiada za własny komentarz i nie może publikować treści bezprawnych, danych prywatnych, spamu ani nękania. Reakcje opisują przydatność materiału w zestawieniu, nie osobę ani prawdziwość twierdzenia. Administrator może ograniczyć widoczność lub usunąć wpis po zgłoszeniu i sprawdzeniu.</p></section>
    <section><h2>Operator serwisu</h2><p>Serwis spin.clinic prowadzi iApply sp. z o.o., pl. Wolności 16, 61-739 Poznań, KRS 0001133291, NIP 7831915094, REGON 529962488. Kontakt: <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>.</p></section>
    <section><h2>Wersja beta</h2><p>Funkcje i zasady są rozwijane etapami. Przed zakończeniem bety opublikujemy wersję końcową wraz z datą wejścia w życie.</p></section>
  </InfoPage>;
}
