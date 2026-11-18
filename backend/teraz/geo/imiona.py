"""Najpopularniejsze polskie imiona (męskie i żeńskie) do odróżnienia osoby od miejsca.

„Andrzej Kalisz”, „Tomasz Opole”, „Maciej Brzeg”: nazwa gminy bez przyimka, tuż po imieniu, to nazwisko, a nie
miejsce. Lista jest ręczna i krótka (kilkaset imion); formy odmienione powstają regułami (dopełniacz, celownik,
narzędnik, miejscownik, wołacz), bez słownika morfologicznego. Imiona są w mianowniku, z polskimi znakami.

Imion, których odmieniona forma jest zwykłym czasownikiem lub rzeczownikiem, nie ma na liście: „Wit” (czasownik „wita”,
„Wita Kraków: turyści wrócili” to nie imię i nazwisko). Takie imiona są w osobnej, krótkiej liście (`_DWUZNACZNE`,
`jest_imieniem_dwuznacznym`): geokoder bierze je pod uwagę tylko ostrożnie (w środku zdania i gdy w tekście jest też
wyraźne miejsce z przyimkiem: „Zaginięcie Wita Kalisza zgłoszono w Warszawie”).
"""

from __future__ import annotations

from functools import lru_cache

from .fleksja import zloz

_MESKIE = (
    "Adam Adrian Albert Aleksander Alfred Andrzej Antoni Arkadiusz Artur Bartłomiej Bartosz Benedykt Bogdan Bogusław "
    "Bolesław Bronisław Cezary Czesław Damian Daniel Dariusz Dawid Dominik Edmund Edward Emil Eryk Eugeniusz Fabian "
    "Feliks Filip Franciszek Gabriel Gerard Grzegorz Gustaw Henryk Hubert Ignacy Igor Ireneusz Jacek Jakub Jan "
    "Janusz Jarosław Jerzy Joachim Józef Julian Juliusz Kacper Kamil Karol Kazimierz Klaudiusz Konrad Krystian "
    "Krzysztof Ksawery Lech Leon Leszek Lucjan Łukasz Maciej Marcel Marcin Marek Mariusz Marian Mateusz Michał "
    "Mieczysław Mikołaj Mirosław Norbert Olaf Oskar Patryk Paweł Piotr Przemysław Radosław Rafał Remigiusz Robert "
    "Roman Ryszard Sebastian Sławomir Stanisław Stefan Sylwester Szczepan Szymon Tadeusz Teodor Tomasz Tymon "
    "Tymoteusz Waldemar Wacław Wiesław Wiktor Witold Władysław Włodzimierz Wojciech Zbigniew Zdzisław Zenon "
    "Zygmunt Aleks Alan Amadeusz Borys Błażej Cyprian Dorian Emanuel Fryderyk Hieronim Iwan Jeremi Kornel Kryspin "
    "Ludwik Maksymilian Miłosz Natan Nikodem Oliwier Rudolf Samuel Seweryn Tobiasz Walenty Wincenty Wojtek Marcin "
    "Bernard Błażej Dionizy Ernest Erwin Eustachy Gracjan Hilary Ireneusz Jaromir Kajetan Karol Lesław Longin "
    "Lubomir Ludomir Mikołaj Modest Narcyz Olgierd Pankracy Przemek Radomir Ratomir Rościsław Sambor Sergiusz "
    "Sobiesław Świętosław Tytus Walerian Wawrzyniec Wolfgang Zefiryn Zbyszek Zenobiusz Kuba Bartek Darek "
    "Mirek Rysiek Staszek Heniek Kazek Leszek Dominik Konstanty Kosma Lew Maurycy Nestor Oktawian Patrycjusz "
    "Rajmund Rochus Rodryg Sylwiusz Teofil Tristan Urban Wiesław Xawery Zachariasz"
).split()

_ZENSKIE = (
    "Aleksandra Alicja Agata Agnieszka Anna Barbara Beata Bożena Danuta Dorota Edyta Elżbieta Ewa Ewelina Grażyna "
    "Halina Hanna Helena Iwona Izabela Jadwiga Janina Jolanta Joanna Julia Justyna Karolina Katarzyna Kinga Klaudia "
    "Krystyna Laura Lidia Lucyna Magdalena Małgorzata Marta Maria Marianna Marzena Milena Monika Natalia Nina Olga "
    "Oliwia Patrycja Paulina Renata Roksana Sabina Sandra Sylwia Teresa Urszula Wanda Weronika Wiktoria Zofia "
    "Zuzanna Żaneta Amelia Alina Bernadeta Celina Dagmara Emilia Eliza Gabriela Irena Jagoda Kamila Kornelia "
    "Liliana Łucja Maja Malwina Martyna Mirosława Nadzieja Otylia Pelagia Regina Stefania Stanisława Wioletta "
    "Violetta Bogumiła Cecylia Czesława Henryka Ilona Lena Marlena Michalina Melania Róża Rozalia Sonia Tamara "
    "Zdzisława Zenona Władysława Aneta Angelika Anita Apolonia Augustyna Bogna Brygida Dominika Dorota Eleonora "
    "Felicja Franciszka Genowefa Gertruda Honorata Inga Irmina Józefa Judyta Kazimiera Klementyna Konstancja "
    "Leokadia Ludmiła Lilianna Marcelina Maryla Matylda Nela Nikola Olimpia Paula Pola Rita Rut Salomea Sara "
    "Sylwana Tekla Ula Wiesława Wirginia Zyta Bianka Blanka Diana Eugenia Hortensja Iga Jowita Julita Kalina "
    "Karina Larysa Lila Luiza Mariola Oksana Pamela Rebeka Sabrina Aurelia Beatrycze"
).split()


def _formy_meskie(imie: str) -> set[str]:
    n = zloz(imie)
    if n.endswith("a"):  # Kuba, Barnaba: odmiana żeńska
        return _formy_zenskie(imie)
    if n.endswith(("y", "i")):  # Jerzy, Antoni
        rdzen = n[:-1]
        return {n} | {rdzen + k for k in ("ego", "emu", "im", "ym", "m")}
    if n.endswith("ek"):  # Marek - Marka
        rdzen = n[:-2] + "k"
        return {n} | {rdzen + k for k in ("a", "owi", "iem", "u")}
    if n == "pawel":  # ruchome „e”: Paweł - Pawła, Pawłem
        return {n} | {"pawl" + k for k in ("a", "owi", "em", "e")}
    return {n} | {n + k for k in ("a", "owi", "em", "u", "ie", "iem")}


def _formy_zenskie(imie: str) -> set[str]:
    n = zloz(imie)
    if not n.endswith("a"):
        return {n}
    rdzen = n[:-1]
    return {n} | {rdzen + k for k in ("y", "i", "e", "ie", "a", "o")}


_DWUZNACZNE = ("Wit",)


@lru_cache(maxsize=1)
def _dwuznaczne() -> frozenset[str]:
    return frozenset(forma for imie in _DWUZNACZNE for forma in _formy_meskie(imie))


@lru_cache(maxsize=1)
def _wszystkie() -> frozenset[str]:
    formy: set[str] = set()
    for imie in _MESKIE:
        formy |= _formy_meskie(imie)
    for imie in _ZENSKIE:
        formy |= _formy_zenskie(imie)
    return frozenset(f for f in formy if len(f) >= 4)


def jest_imieniem(zlozony: str) -> bool:
    """Czy wyraz (złożony: małe litery bez polskich znaków) jest popularnym imieniem, w dowolnym przypadku."""
    return zlozony in _wszystkie()


def jest_imieniem_dwuznacznym(zlozony: str) -> bool:
    """Czy wyraz (złożony) jest formą imienia, które bywa też zwykłym wyrazem (`_DWUZNACZNE`): „Wit”, „Wita”, „Witem”."""
    return zlozony in _dwuznaczne()
