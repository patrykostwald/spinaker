/** Rodzina każdej kategorii techniki (jak backend/news/techniques.py) — gdy odpowiedź API nie ma jeszcze pola scan. */
export const FAMILY_OF: Record<string, string> = {
  "Liczba bez punktu odniesienia": "dane", "Wybiórcze dane": "dane", "Pominięcie kontekstu": "dane", "Przeinaczenie faktów": "dane",
  "Teza bez dowodu": "dane", "Fałszywa przyczynowość": "dane", "Nadmierne uogólnienie": "dane", "Fałszywa analogia i skojarzenie": "dane",
  "Fałszywa alternatywa": "dane", "Odwołanie do autorytetu": "dane",
  "Apel do emocji": "przedstawienie", "Straszenie": "przedstawienie", "Przesada": "przedstawienie", "Etykietowanie": "przedstawienie",
  "My kontra oni": "przedstawienie", "Sugestia i niedopowiedzenie": "przedstawienie",
  "Atak na osobę": "spor", "Przypisywanie intencji": "spor", "Słomiany człowiek": "spor", "Zmiana tematu": "spor", "Przypisywanie sobie zasług": "spor",
};
