import { Button, InfoPage } from '@spin-clinic/ui/kit';

export const metadata = {
  title: 'Nitki — spin.clinic',
  description: 'Nitki kontekstowe użytkowników: własne zestawienia materiałów z bazy spin.clinic. Wersja publiczna w fazie II.',
};

export default function ThreadsRoute() {
  return <InfoPage eyebrow="NITKI · FAZA II" title="Nitki kontekstowe czytelników" lead="Tu będą publiczne nitki kontekstowe użytkowników: jeden materiał na początku, a za nim — w kolejności publikacji — to, co go dopełnia, potwierdza albo podważa.">
    <section><h2>Co działa już dziś</h2><p>Po zalogowaniu możesz ułożyć własną, prywatną nitkę z materiałów z naszej bazy: wybierasz materiał otwierający, dokładasz kolejne i dopisujesz krótkie komentarze.</p><div className="sc-info-page__actions"><Button href="/konto/nitki/nowa" variant="primary">Ułóż swoją nitkę</Button></div></section>
    <section><h2>Co dojdzie w fazie II</h2><p>Publikowanie nitek dla innych, reakcje i komentarze z moderacją oraz dodawanie materiałów spoza bazy przez link. Z linku zapiszemy tylko tytuł, adres i nazwę źródła — bez kopiowania treści ani zdjęć. Jeśli ten sam materiał doda kilka osób, powstanie jeden box, bez duplikatów.</p></section>
    <section><h2>Dlaczego nie od razu</h2><p>Nitka ma sens, gdy baza jest pełna. Najpierw rozbudowujemy katalog źródeł i zbieramy zgody wydawców — dzięki temu nitki będą się składać głównie z materiałów, które już mamy i możemy pokazać.</p></section>
  </InfoPage>;
}
