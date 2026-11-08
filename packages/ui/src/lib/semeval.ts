// Odpowiednik backend/news/techniques.py; zgodność sprawdza test_semeval.py.
export const SEMEVAL_MAP: Record<string, string[]> = {
  "Straszenie": [
    "Appeal to Fear/Prejudice"
  ],
  "Przypisywanie sobie zasług": [],
  "Przypisywanie intencji": [
    "Casting Doubt"
  ],
  "Atak na osobę": [
    "Questioning the Reputation"
  ],
  "Fałszywa alternatywa": [
    "False Dilemma/No Choice"
  ],
  "Słomiany człowiek": [
    "Strawman"
  ],
  "Fałszywa analogia i skojarzenie": [
    "Guilt by Association"
  ],
  "Przeinaczenie faktów": [],
  "Sugestia i niedopowiedzenie": [
    "Casting Doubt"
  ],
  "Fałszywa przyczynowość": [
    "Causal Oversimplification"
  ],
  "Liczba bez punktu odniesienia": [],
  "Wybiórcze dane": [],
  "Pominięcie kontekstu": [],
  "Nadmierne uogólnienie": [],
  "Etykietowanie": [
    "Name Calling/Labeling"
  ],
  "My kontra oni": [
    "Flag Waving"
  ],
  "Zmiana tematu": [
    "Red Herring",
    "Whataboutism"
  ],
  "Odwołanie do autorytetu": [
    "Appeal to Authority"
  ],
  "Teza bez dowodu": [],
  "Przesada": [
    "Exaggeration/Minimisation"
  ],
  "Apel do emocji": [
    "Loaded Language",
    "Appeal to Values"
  ],
  "Inne": []
};

export const SEMEVAL_UNRECOGNIZED = [
  "Appeal to Hypocrisy",
  "Appeal to Popularity",
  "Consequential Oversimplification",
  "Slogans",
  "Conversation Killer",
  "Appeal to Time",
  "Obfuscation/Vagueness/Confusion",
  "Repetition"
];
