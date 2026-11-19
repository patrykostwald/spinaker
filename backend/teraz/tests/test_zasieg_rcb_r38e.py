"""Zamykająca recenzja PR #38 (R38d, zlecenie Z6P6): zasięg alertu RCB per województwo i wznowienie archiwum.

Zasady strukturalne rundy: (1) zakres zapisujemy osobno dla każdego województwa (`cale`, `czesc`, `lista`, wyłączenia), front
dopasowuje powiat do zakresu swojego województwa; (2) w etykietach fail-closed; (3) zdaniem odbiorców jest nagłówek alertu albo
zdanie z czasownikiem wysłania, obowiązywania lub obejmowania, sama wzmianka o mieście nie zmienia zasięgu. Zdania poniżej to
zdania recenzenta. Etykiety „Mojego powiatu” sprawdza frontend-spin/tests/147-*.test.cjs na wynikach tego parsera
(plik frontend-spin/tests/147-przeszlosc-teraz-zasieg-rcb.json; ten test pilnuje, żeby zgadzał się z parserem).
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from teraz.api import zasieg_wpisu
from teraz.models import Klasa
from teraz.tests.test_zasieg_rcb import ODBIORCY, POLA, linie_miejsca, wpis_z_api, zapisz_karte, zrodlo_rcb  # noqa: F401
from teraz.tests.test_zrodla import LISTA, SCOPE, karta_rcb, link_rcb, odpowiedz
from teraz.transport import OdpowiedzHTTP
from teraz.zbieranie import Adapter, BladPobrania
from teraz.zrodla import rcb

pytestmark = pytest.mark.django_db
PLIK_FRONTU = Path(__file__).resolve().parents[3] / "frontend-spin/tests/147-przeszlosc-teraz-zasieg-rcb.json"


def parsuj_wszystkie(*akapity):
    html = ('<article class="article-area__article"><h2>Alert RCB</h2><p class="event-date">10.11.2026</p>'
            '<div class="editor-content">' + "".join(f"<p>{akapit}</p>" for akapit in akapity) + "</div></article>")
    return rcb.parsuj_karte(OdpowiedzHTTP(200, {}, html.encode(), "utf-8"), link_rcb("10"))


def parsuj(*akapity):
    return parsuj_wszystkie(*akapity)[0]


def zakresy(alert):
    return [linia for linia in alert["miejsce"].splitlines() if linia.startswith(rcb.PREFIKS_ZAKRES)]


def zasieg_api(alert):
    """To, co zwróci API: `zasieg_wpisu` na polach wpisu z parsera."""
    wpis = SimpleNamespace(pewnosc_lokalizacji=alert["pewnosc_lokalizacji"], miejsce=alert["miejsce"], tresc=alert["tresc"],
                           zrodlo=SimpleNamespace(slug="rcb"))
    return zasieg_wpisu(wpis, alert["teryt"], False)


# --- zdania z fixture frontu: id -> akapity karty (każdy przypadek to zdania recenzenta albo ich bliskie odmiany) ---
PRZYPADKI = {
    "miasto-puck": (ODBIORCY + "w mieście Puck w woj. pomorskim.",),
    "czesc-lubelskiego": (ODBIORCY + "w części woj. lubelskiego.",),
    "powiat-swidnicki-dolnoslaskie": (ODBIORCY + "w powiecie świdnickim w woj. dolnośląskim.",),
    "trzy-zasiegi": (ODBIORCY + "w całym woj. lubelskim, w części woj. podkarpackiego i w powiecie świdnickim w woj. dolnośląskim.",),
    "poludnie-mazowieckie": (ODBIORCY + "wyłącznie na południu woj. mazowieckiego.",),
    "cale-i-punkt-pomocy": (ODBIORCY + "w całym woj. lubelskim.", "Punkty pomocy otwarto w mieście Chełm w woj. lubelskim."),
    "wylaczenie-w-osobnym-zdaniu": (ODBIORCY + "w woj. pomorskim.", "Komunikat nie obowiązuje w powiecie puckim."),
    "wylaczenie-i-drugie-wojewodztwo": (ODBIORCY + "w woj. pomorskim z wyjątkiem powiatu puckiego, a także w woj. zachodniopomorskim.",),
    "odsylacz-w-nawiasie": (ODBIORCY + "w powiatach chełmskim i włodawskim (1) w woj. lubelskim.",),
    "element-nieczytelny": (ODBIORCY + "w powiatach chełmskim i włodawskim 7 w woj. lubelskim.",),
    "zmiana-zasiegu-w-aktualizacji": (
        ODBIORCY + "w powiecie świdnickim w woj. dolnośląskim oraz w powiecie chełmskim w woj. lubelskim.",
        "Aktualizacja 11:00",
        "Od 11:00 alert obejmuje wyłącznie powiat chełmski w woj. lubelskim.",
    ),
}


def przelicz(akapity):
    return [{"miejsce": a["miejsce"], "teryt": a["teryt"], "zasieg": zasieg_api(a)} for a in parsuj_wszystkie(*akapity)]


def test_fixture_frontu_zgadza_sie_z_parserem():
    # front (147-*.test.cjs) czyta `miejsce` zapisane w pliku: nie może się rozjechać z tym, co zwraca parser
    if not PLIK_FRONTU.exists():
        pytest.skip("brak katalogu frontu (obraz backendu)")
    zapisane = json.loads(PLIK_FRONTU.read_text(encoding="utf-8"))["przypadki"]
    assert set(zapisane) == set(PRZYPADKI)
    for ident, akapity in PRZYPADKI.items():
        assert zapisane[ident]["akapity"] == list(akapity), ident
        assert zapisane[ident]["wpisy"] == przelicz(akapity), ident


# --- pkt 1: miasto nie jest powiatem ---
def test_miasto_puck_zostaje_miastem_w_wojewodztwie_z_lista():
    alert = parsuj(ODBIORCY + "w mieście Puck w woj. pomorskim.")
    assert linie_miejsca(alert) == ["pomorskie", "pomorskie: miasto Puck"]
    assert zakresy(alert) == ["zakres: pomorskie: lista"] and alert["teryt"] == ["22"]


# --- pkt 2: zakres per województwo ---
def test_czesc_wojewodztwa_nigdy_nie_jest_calym():
    alert = parsuj(ODBIORCY + "w części woj. lubelskiego.")
    assert zakresy(alert) == ["zakres: lubelskie: czesc"] and zasieg_api(alert) == "przyblizony"


def test_powiat_w_innym_wojewodztwie_nie_robi_z_niego_calego():
    alert = parsuj(ODBIORCY + "w powiecie świdnickim w woj. dolnośląskim.")
    assert zakresy(alert) == ["zakres: dolnośląskie: lista"]


def test_trzy_zasiegi_w_jednym_zdaniu():
    alert = parsuj(ODBIORCY + "w całym woj. lubelskim, w części woj. podkarpackiego i w powiecie świdnickim w woj. dolnośląskim.")
    assert zakresy(alert) == ["zakres: lubelskie: cale", "zakres: podkarpackie: czesc", "zakres: dolnośląskie: lista"]
    assert "dolnośląskie: świdnickim" in alert["miejsce"].splitlines() and alert["teryt"] == ["02", "06", "18"]


@pytest.mark.parametrize("zdanie", [
    "wyłącznie na południu woj. mazowieckiego.",
    "na południu woj. mazowieckiego.",
    "w południowej części woj. mazowieckiego.",
    "w północno-wschodniej części województwa mazowieckiego.",
    "w części woj. mazowieckiego.",
])
def test_kierunek_albo_czesc_przed_nazwa_to_czesc_wojewodztwa(zdanie):
    assert zakresy(parsuj(ODBIORCY + zdanie)) == ["zakres: mazowieckie: czesc"]


def test_czesc_dotyczy_kolejnych_wojewodztw_z_tej_samej_listy_ale_nie_nowej_grupy():
    assert zakresy(parsuj(ODBIORCY + "w części woj. lubelskiego i podkarpackiego.")) == [
        "zakres: lubelskie: czesc", "zakres: podkarpackie: czesc"]
    assert zakresy(parsuj(ODBIORCY + "w części woj. lubelskiego oraz w woj. podkarpackim.")) == [
        "zakres: lubelskie: czesc", "zakres: podkarpackie: cale"]


def test_punkty_listy_po_czesci_wojewodztwa_sa_czescia():
    alert = parsuj(ODBIORCY + "na terenie części województwa:", "- lubelskiego", "- podlaskiego")
    assert zakresy(alert) == ["zakres: lubelskie: czesc", "zakres: podlaskie: czesc"]


def test_jednostki_bez_znanego_wojewodztwa_nie_pozwalaja_na_cale():
    alert = parsuj(ODBIORCY + "w woj. lubelskim, a także w powiatach chełmskim i włodawskim.")
    assert "zakres: lubelskie: cale" not in alert["miejsce"].splitlines()


def test_bez_zawezen_to_cale():
    assert zakresy(parsuj(ODBIORCY + "w woj. łódzkim i świętokrzyskim.")) == ["zakres: łódzkie: cale", "zakres: świętokrzyskie: cale"]
    assert zasieg_api(parsuj(ODBIORCY + "w woj. mazowieckim, kujawsko-pomorskim i zachodniopomorskim.")) == "obszar"


def test_rozne_rodzaje_zakresu_w_kilku_zdaniach_daja_czesc():
    alert = parsuj(ODBIORCY + "w woj. lubelskim.", ODBIORCY + "w powiecie chełmskim w woj. lubelskim.")
    assert zakresy(alert) == ["zakres: lubelskie: czesc"]
    zgodne = parsuj(ODBIORCY + "w powiecie chełmskim w woj. lubelskim.", ODBIORCY + "w powiecie włodawskim w woj. lubelskim.")
    assert zakresy(zgodne) == ["zakres: lubelskie: lista"]


def test_scalanie_zakresow_zachowuje_kolejnosc_i_nie_dubluje():
    assert rcb._scal_zakresy(["lubelskiego", "zakres: lubelskie: cale", "x", "zakres: lubelskie: cale", "zakres: podlaskie: lista"]) == [
        "lubelskiego", "zakres: lubelskie: cale", "x", "zakres: podlaskie: lista"]
    assert rcb._scal_zakresy(["zakres: lubelskie: cale", "zakres: lubelskie: lista"]) == ["zakres: lubelskie: czesc"]


def test_linie_zakresu_nie_dopisuja_kodow_teryt():
    # kod województwa pochodzi z jednostek objętych alertem, nie ze znaczników („zakres:”, „wyłączone:”, „nieustalone:”)
    alert = parsuj(ODBIORCY + "w woj. lubelskim z wyłączeniem powiatu świdnickiego w woj. dolnośląskim.")
    assert alert["teryt"] == ["06"]


# --- pkt 3: punkt pomocy i sąsiednie zdanie nie zawężają zasięgu ---
@pytest.mark.parametrize("dopisek", [
    "Punkty pomocy otwarto w mieście Chełm w woj. lubelskim.",
    "Punkty pomocy otwarto w mieście Chełm.",
    "Szkoła w powiecie włodawskim jest zamknięta.",
    "W części woj. lubelskiego ruch jest utrudniony.",
    "Informacje dla mieszkańców powiatu chełmskiego na stronie gminy.",
])
def test_zdanie_bez_czasownika_odbiorcow_nie_zmienia_zasiegu(client, zrodlo_rcb, zrob_wpis, dopisek):  # noqa: F811
    alert = parsuj(ODBIORCY + "w całym woj. lubelskim.", dopisek)
    assert linie_miejsca(alert) == ["lubelskie"] and zakresy(alert) == ["zakres: lubelskie: cale"]
    assert alert["pewnosc_lokalizacji"] == 1 and zasieg_api(alert) == "obszar"
    wpis = zrob_wpis(zrodlo_rcb, klasa=Klasa.ZWYKLY, link=link_rcb("10"), **{pole: alert[pole] for pole in POLA})
    assert wpis_z_api(client, wpis)["zasieg"] == "obszar"


def test_czasownik_obejmowania_robi_ze_zdania_zdanie_odbiorcow():
    for zdanie in ("Alert obejmuje powiat chełmski w woj. lubelskim.", "Komunikat dotyczy powiatu chełmskiego w woj. lubelskim.",
                   "Alert obowiązuje w powiecie chełmskim w woj. lubelskim.", "Alert został wysłany w powiecie chełmskim w woj. lubelskim."):
        alert = parsuj("Alert RCB został wysłany do odbiorców.", zdanie)
        assert linie_miejsca(alert)[-1].startswith("lubelskie: chełmsk"), zdanie


def test_punkt_listy_to_odbiorcy_tylko_po_naglowku_z_dwukropkiem():
    po_naglowku = parsuj(ODBIORCY + "na terenie części województwa:", "- lubelskiego - powiaty: chełmski, włodawski")
    assert "lubelskie: chełmski" in po_naglowku["miejsce"].splitlines()
    bez_naglowka = parsuj(ODBIORCY + "w woj. lubelskim.", "- Chełm - punkt pomocy w powiecie włodawskim")
    assert linie_miejsca(bez_naglowka) == ["lubelskie"]


# --- pkt 4: wyłączenie przypisane do właściwego członu ---
def test_wylaczenie_w_osobnym_zdaniu_po_alercie_dla_wojewodztwa():
    alert = parsuj(ODBIORCY + "w woj. pomorskim.", "Komunikat nie obowiązuje w powiecie puckim.")
    assert linie_miejsca(alert) == ["pomorskie", "wyłączone: puckim"]
    assert zakresy(alert) == ["zakres: pomorskie: cale"] and alert["teryt"] == ["22"]
    assert zasieg_api(alert) == "przyblizony"


def test_nie_obowiazuje_juz_to_wylaczenie():
    alert = parsuj(ODBIORCY + "w woj. pomorskim.", "Alert nie obowiązuje już w powiecie puckim w woj. pomorskim.")
    assert "wyłączone: pomorskie: puckim" in alert["miejsce"].splitlines()


def test_wylaczenie_nie_obcina_drugiego_wojewodztwa():
    alert = parsuj(ODBIORCY + "w woj. pomorskim z wyjątkiem powiatu puckiego, a także w woj. zachodniopomorskim.")
    assert alert["teryt"] == ["22", "32"]
    assert linie_miejsca(alert) == ["pomorskie", "zachodniopomorskie", "wyłączone: pomorskie: puckiego"]
    assert zakresy(alert) == ["zakres: pomorskie: cale", "zakres: zachodniopomorskie: cale"]


@pytest.mark.parametrize("zdanie", [
    "w woj. pomorskim z wyjątkiem powiatu puckiego oraz w woj. zachodniopomorskim.",
    "w woj. pomorskim poza powiatem puckim i w woj. zachodniopomorskim.",
    "w woj. pomorskim z wyłączeniem powiatu puckiego; obejmuje także woj. zachodniopomorskie.",
])
def test_wylaczenie_konczy_sie_przed_nowym_czlonem(zdanie):
    alert = parsuj(ODBIORCY + zdanie)
    assert alert["teryt"] == ["22", "32"], zdanie
    assert zakresy(alert)[-1] == "zakres: zachodniopomorskie: cale"
    assert any(linia.startswith("wyłączone: pomorskie: pucki") for linia in alert["miejsce"].splitlines())


def test_wylaczenie_z_lista_w_tym_samym_czlonie_nie_jest_ucinane_spojnikiem():
    alert = parsuj(ODBIORCY + "w woj. lubelskim z wyłączeniem powiatów chełmskiego i włodawskiego.")
    assert [linia for linia in alert["miejsce"].splitlines() if linia.startswith("wyłączone")] == [
        "wyłączone: lubelskie: chełmskiego", "wyłączone: lubelskie: włodawskiego"]


# --- pkt 5: odsyłacze i elementy nieczytelne ---
@pytest.mark.parametrize("znak", ["(1)", "[2]", "*", "¹", " (12)"])
def test_odsylacz_przy_nazwie_nie_gubi_elementu(znak):
    alert = parsuj(ODBIORCY + f"w powiatach chełmskim i włodawskim{znak} w woj. lubelskim.")
    assert linie_miejsca(alert) == ["lubelskie", "lubelskie: chełmskim", "lubelskie: włodawskim"]
    assert not [linia for linia in alert["miejsce"].splitlines() if linia.startswith(rcb.PREFIKS_NIEUSTALONE)]


def test_odsylacz_po_pierwszej_nazwie_i_przy_ostatniej():
    alert = parsuj(ODBIORCY + "w powiatach: chełmski (1), włodawski [2], bialski*.")
    assert linie_miejsca(alert) == ["chełmski", "włodawski", "bialski"]


def test_element_ktorego_nie_da_sie_odczytac_daje_znacznik_nieustalone():
    alert = parsuj(ODBIORCY + "w powiatach chełmskim i włodawskim 7 w woj. lubelskim.")
    assert "lubelskie: włodawskim" not in alert["miejsce"].splitlines()
    assert "nieustalone: lubelskie" in alert["miejsce"].splitlines()


def test_nieustalone_bez_znanego_wojewodztwa_jest_globalne():
    alert = parsuj(ODBIORCY + "w powiatach: chełmski, xyz.")
    assert rcb.LINIA_NIEUSTALONE in alert["miejsce"].splitlines()


def test_adres_z_ulica_to_nie_element_nieczytelny():
    alert = parsuj(ODBIORCY + "w powiatach: chełmski, ul. Lubelska 5.")
    assert not [linia for linia in alert["miejsce"].splitlines() if linia.startswith(rcb.PREFIKS_NIEUSTALONE)]


# --- pkt 6: aktualizacja z jawną zmianą zasięgu ---
def test_aktualizacja_wylacznie_zastepuje_wczesniejsza_liste():
    pierwszy, aktualizacja = parsuj_wszystkie(*PRZYPADKI["zmiana-zasiegu-w-aktualizacji"])
    assert "dolnośląskie: świdnickim" in pierwszy["miejsce"].splitlines() and pierwszy["teryt"] == ["02", "06"]
    assert linie_miejsca(aktualizacja) == ["lubelskie", "lubelskie: chełmski"]
    assert zakresy(aktualizacja) == ["zakres: lubelskie: lista"] and aktualizacja["teryt"] == ["06"]
    assert "świdnick" not in aktualizacja["miejsce"]


@pytest.mark.parametrize("zdanie", [
    "Zasięg alertu ogranicza się do powiatu chełmskiego w woj. lubelskim.",
    "Alert obejmuje od teraz wyłącznie powiat chełmski w woj. lubelskim.",
])
def test_inne_sformulowania_zmiany_zasiegu(zdanie):
    _, aktualizacja = parsuj_wszystkie(
        ODBIORCY + "w powiecie świdnickim w woj. dolnośląskim.", "Aktualizacja 11:00", zdanie)
    assert aktualizacja["teryt"] == ["06"] and "świdnick" not in aktualizacja["miejsce"]


def test_kolejna_aktualizacja_bez_zmiany_dziedziczy_nowy_zasieg_nie_pierwotny():
    _, zmiana, nastepna = parsuj_wszystkie(
        ODBIORCY + "w powiecie świdnickim w woj. dolnośląskim.",
        "Aktualizacja 11:00", "Od 11:00 alert obejmuje wyłącznie powiat chełmski w woj. lubelskim.",
        "Aktualizacja 12:00", "Pozostańcie w domach.",
    )
    assert zmiana["teryt"] == nastepna["teryt"] == ["06"] and "świdnick" not in nastepna["miejsce"]


def test_aktualizacja_bez_zmiany_zasiegu_dziedziczy_pierwotny():
    _, aktualizacja = parsuj_wszystkie(
        ODBIORCY + "w powiecie świdnickim w woj. dolnośląskim.", "Aktualizacja 11:00", "Pozostańcie w domach do odwołania.")
    assert aktualizacja["teryt"] == ["02"] and "dolnośląskie: świdnickim" in aktualizacja["miejsce"].splitlines()


def test_aktualizacja_z_wyjatkiem_slowa_wylacznie_poza_zasiegiem_nie_zastepuje():
    # „wyłącznie” w zdaniu bez nowego zasięgu (godziny, pory) niczego nie zmienia
    _, aktualizacja = parsuj_wszystkie(
        ODBIORCY + "w powiecie świdnickim w woj. dolnośląskim.", "Aktualizacja 11:00", "Alert obowiązuje wyłącznie do godziny 18:00.")
    assert aktualizacja["teryt"] == ["02"]


def test_aktualizacja_nie_obowiazuje_juz_oznacza_wypadniety_powiat_jako_wylaczony():
    _, aktualizacja = parsuj_wszystkie(
        ODBIORCY + "w powiecie świdnickim w woj. dolnośląskim oraz w powiecie chełmskim w woj. lubelskim.",
        "Aktualizacja 11:00", "Alert nie obowiązuje już w powiecie świdnickim w woj. dolnośląskim.")
    assert "wyłączone: dolnośląskie: świdnickim" in aktualizacja["miejsce"].splitlines()


# --- pkt 7: archiwum, błąd przejściowy zostawia kartę do ponowienia ---
def zapisz_stara_karte(zrodlo, zrob_wpis, dzien):
    """Karta zapisana parserem sprzed zakresu (v4): tylko woj. lubelskie, bez podkarpackiego."""
    alert = rcb.parsuj_karte(odpowiedz(karta_rcb(dzien)), link_rcb(dzien))[0]
    return zapisz_karte(zrodlo, zrob_wpis, dzien, zewnetrzny_id=alert["zewnetrzny_id"], miejsce="lubelskiego",
                        teryt=["06"], pewnosc_lokalizacji=1)


def blad(kod):
    return BladPobrania("timeout") if kod == "timeout" else (odpowiedz(None, kod), SCOPE)


@pytest.mark.parametrize("kod", [500, 503, 429, "timeout"])
def test_archiwum_przejsciowy_blad_ostatniej_karty_nie_konczy_archiwum(monkeypatch, client, zrodlo_rcb, zrob_wpis, kod):  # noqa: F811
    pierwsza, ostatnia = link_rcb("10"), link_rcb("03")
    wpis = zapisz_stara_karte(zrodlo_rcb, zrob_wpis, "03")
    zrodlo_rcb.stan_adaptera = {"archiwum": {"strona": 1, "stron": 1, "karty": [], "zakonczone": True, "wersja_parsera": "5"}}
    zrodlo_rcb.save(update_fields=["stan_adaptera"])
    monkeypatch.setattr(rcb, "parsuj_liste", lambda odp: ([pierwsza, ostatnia], 1))
    monkeypatch.setattr("teraz.management.commands.teraz_rcb_archiwum.sleep", Mock())
    odpowiedzi = [(odpowiedz(LISTA), SCOPE), (odpowiedz(karta_rcb("10")), SCOPE)]
    pierwszy = Mock(side_effect=[*odpowiedzi, blad(kod)])
    monkeypatch.setattr(Adapter, "pobierz", pierwszy)

    if kod in (429, "timeout"):
        with pytest.raises(CommandError):
            call_command("teraz_rcb_archiwum")
    else:
        call_command("teraz_rcb_archiwum")
    zrodlo_rcb.refresh_from_db()
    archiwum = zrodlo_rcb.stan_adaptera["archiwum"]
    assert not archiwum.get("zakonczone"), "archiwum z kartą do ponowienia nie jest zakończone"
    assert wpis_z_api(client, wpis)["teryt"] == ["06"], "karta nie została pobrana, zostaje stary zasięg"
    assert [w.args[0] for w in pierwszy.call_args_list][-1] == ostatnia

    # kolejne uruchomienie ponawia tylko niepobraną kartę (bez listy i bez pierwszej karty) i dokańcza archiwum
    drugi = Mock(side_effect=[(odpowiedz(karta_rcb("03")), SCOPE)])
    monkeypatch.setattr(Adapter, "pobierz", drugi)
    call_command("teraz_rcb_archiwum")
    assert [w.args[0] for w in drugi.call_args_list] == [ostatnia]
    zrodlo_rcb.refresh_from_db()
    archiwum = zrodlo_rcb.stan_adaptera["archiwum"]
    assert archiwum["zakonczone"] and archiwum["wersja_parsera"] == "6" and not archiwum.get("niepobrane")
    assert wpis_z_api(client, wpis)["teryt"] == ["06", "18"]


def test_archiwum_pomija_karte_z_bledem_trwalym_i_konczy(monkeypatch, zrodlo_rcb):  # noqa: F811
    pierwsza, druga = link_rcb("03"), link_rcb("10")
    zrodlo_rcb.stan_adaptera = {"archiwum": {"strona": 1, "stron": 1, "karty": [pierwsza, druga], "wersja_parsera": "6"}}
    zrodlo_rcb.save(update_fields=["stan_adaptera"])
    monkeypatch.setattr(Adapter, "pobierz", Mock(side_effect=[(odpowiedz(None, 404), SCOPE), (odpowiedz(karta_rcb("10")), SCOPE)]))
    monkeypatch.setattr("teraz.management.commands.teraz_rcb_archiwum.sleep", Mock())
    call_command("teraz_rcb_archiwum", limit=2)
    zrodlo_rcb.refresh_from_db()
    assert zrodlo_rcb.stan_adaptera["archiwum"]["zakonczone"] and not zrodlo_rcb.stan_adaptera["archiwum"].get("niepobrane")


def test_archiwum_karta_z_bledem_przejsciowym_w_srodku_nie_blokuje_reszty(monkeypatch, zrodlo_rcb):  # noqa: F811
    pierwsza, druga, trzecia = link_rcb("03"), link_rcb("09"), link_rcb("10")
    zrodlo_rcb.stan_adaptera = {"archiwum": {"strona": 1, "stron": 1, "karty": [pierwsza, druga, trzecia], "wersja_parsera": "6"}}
    zrodlo_rcb.save(update_fields=["stan_adaptera"])
    pobierz = Mock(side_effect=[(odpowiedz(None, 500), SCOPE), (odpowiedz(karta_rcb("09")), SCOPE), (odpowiedz(karta_rcb("10")), SCOPE)])
    monkeypatch.setattr(Adapter, "pobierz", pobierz)
    monkeypatch.setattr("teraz.management.commands.teraz_rcb_archiwum.sleep", Mock())
    call_command("teraz_rcb_archiwum")
    assert [w.args[0] for w in pobierz.call_args_list] == [pierwsza, druga, trzecia]
    zrodlo_rcb.refresh_from_db()
    archiwum = zrodlo_rcb.stan_adaptera["archiwum"]
    assert not archiwum.get("zakonczone") and archiwum["niepobrane"] == [pierwsza] and archiwum["karty"] == []


def test_archiwum_ponawia_niepobrane_karty_az_do_skutku(monkeypatch, zrodlo_rcb):  # noqa: F811
    karta = link_rcb("03")
    zrodlo_rcb.stan_adaptera = {"archiwum": {"strona": 2, "stron": 1, "karty": [], "niepobrane": [karta], "wersja_parsera": "6"}}
    zrodlo_rcb.save(update_fields=["stan_adaptera"])
    monkeypatch.setattr("teraz.management.commands.teraz_rcb_archiwum.sleep", Mock())
    # druga próba też kończy się błędem 500: niepobrana karta wraca do kolejki "niepobrane", archiwum nadal niezakończone
    monkeypatch.setattr(Adapter, "pobierz", Mock(side_effect=[(odpowiedz(None, 500), SCOPE)]))
    call_command("teraz_rcb_archiwum")
    zrodlo_rcb.refresh_from_db()
    assert zrodlo_rcb.stan_adaptera["archiwum"]["niepobrane"] == [karta] and not zrodlo_rcb.stan_adaptera["archiwum"].get("zakonczone")
    monkeypatch.setattr(Adapter, "pobierz", Mock(side_effect=[(odpowiedz(karta_rcb("03")), SCOPE)]))
    call_command("teraz_rcb_archiwum")
    zrodlo_rcb.refresh_from_db()
    assert zrodlo_rcb.stan_adaptera["archiwum"]["zakonczone"]
