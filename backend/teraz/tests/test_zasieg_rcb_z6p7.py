"""Zlecenie Z6P7: reszta zasięgu RCB po scaleniu #38 (lista Z6P7 z recenzji R38e i R38g).

Zasada strukturalna: parser nigdy nie zawęża ani nie poszerza zasięgu na podstawie zdania, którego nie rozpoznał w pełni.
Zdanie z jednostką lub województwem, ale bez czasownika albo nagłówka odbiorców, nie zmienia zasięgu; gdy mogło zmienić znaczenie
wcześniejszego zasięgu (wyłączenie, „już tylko”), zasięg dostaje znacznik `nieustalone` i zostaje przybliżony. Zdania poniżej
to zdania z listy Z6P7; te same przypadki (z regeneracją) są w fixture frontu 147-*.json (test_zasieg_rcb_r38e.py).
"""
import pytest
from django.core.management import call_command  # noqa: F401
from django.utils import timezone

from teraz import zbieranie
from teraz.models import Zdarzenie
from teraz.tests.test_zasieg_rcb import ODBIORCY, linie_miejsca, zrodlo_rcb  # noqa: F401
from teraz.tests.test_zasieg_rcb_r38e import parsuj, parsuj_wszystkie, zakresy, zasieg_api
from teraz.zrodla import rcb

pytestmark = pytest.mark.django_db


def linie_bez_zakresow(alert):
    return [linia for linia in alert["miejsce"].splitlines() if not linia.startswith(rcb.PREFIKS_ZAKRES)]


# --- regresje punktów 1, 5 i 9 (naprawione w #38 i #40) ---
@pytest.mark.parametrize("zdanie,jednostka", [
    ("Alert RCB obowiązuje na terenie miasta Rumia w woj. pomorskim.", "pomorskie: miasto Rumia"),
    ("Alert RCB obejmuje gminę Żarów w woj. dolnośląskim.", "dolnośląskie: gmina Żarów"),
])
def test_pkt1_miasto_i_gmina_to_lista_otwarta_nigdy_zamknieta(zdanie, jednostka):
    alert = parsuj(zdanie)
    assert jednostka in alert["miejsce"].splitlines() and zakresy(alert)[0].endswith("lista_otwarta")


def test_pkt5_odsylacz_z_nr_nie_usuwa_powiatu():
    alert = parsuj("Alert RCB dotyczy powiatów chełmskiego i włodawskiego (odsyłacz nr 1) w woj. lubelskim.")
    assert linie_miejsca(alert) == ["lubelskie", "lubelskie: chełmskiego", "lubelskie: włodawskiego"]
    assert not [linia for linia in alert["miejsce"].splitlines() if linia.startswith(rcb.PREFIKS_NIEUSTALONE)]


# pkt 9 (HTTP 408 zostawia kartę archiwum do ponowienia): test_archiwum_przejsciowy_blad_ostatniej_karty_nie_konczy_archiwum
# w test_zasieg_rcb_r38e.py, parametr 408.


# --- pkt 2: część województwa nie jest całym województwem ---
def test_wybrane_rejony_wojewodztwa_to_czesc_nie_cale():
    alert = parsuj("Alert RCB wysłano do mieszkańców wybranych rejonów woj. lubelskiego.")
    assert zakresy(alert) == ["zakres: lubelskie: czesc"] and alert["teryt"] == ["06"]
    assert zasieg_api(alert) == "przyblizony" and alert["pewnosc_lokalizacji"] == 0.5


@pytest.mark.parametrize("zdanie", [
    "Alert RCB wysłano do mieszkańców niektórych obszarów woj. lubelskiego.",
    "Alert RCB wysłano do mieszkańców wybranych powiatów woj. lubelskiego.",
    "Alert RCB wysłano do mieszkańców poszczególnych miejscowości woj. lubelskiego.",
])
def test_inne_okreslenia_czesci_wojewodztwa(zdanie):
    alert = parsuj(zdanie)
    assert zakresy(alert) == ["zakres: lubelskie: czesc"] and zasieg_api(alert) == "przyblizony"


def test_czesc_wojewodztwa_w_tym_powiat_to_czesc_a_powiat_zostaje_na_liscie():
    alert = parsuj("Alert RCB obejmuje część woj. lubelskiego, w tym powiat chełmski.")
    assert zakresy(alert) == ["zakres: lubelskie: czesc"] and zasieg_api(alert) == "przyblizony"
    assert "lubelskie: chełmski" in alert["miejsce"].splitlines()


def test_czesc_w_jednym_czlonie_nie_zamyka_listy_z_drugiego():
    alert = parsuj(ODBIORCY + "w części woj. lubelskiego oraz w powiecie chełmskim w woj. lubelskim.")
    assert zakresy(alert) == ["zakres: lubelskie: czesc"]


def test_pelne_wojewodztwo_bez_zawezen_zostaje_cale():
    alert = parsuj(ODBIORCY + "w woj. lubelskim.")
    assert zakresy(alert) == ["zakres: lubelskie: cale"] and zasieg_api(alert) == "obszar"


# --- pkt 3: zdanie o wysłaniu służb nie dopisuje województwa ---
def test_sluzby_wyslane_do_miasta_w_innym_wojewodztwie_nie_dopisuja_wojewodztwa():
    alert = parsuj("Alert RCB obowiązuje w całym woj. lubelskim.",
                   "Dodatkowych strażaków wysłano do miasta Radom w woj. mazowieckim.")
    assert linie_bez_zakresow(alert) == ["lubelskie"] and alert["teryt"] == ["06"]
    assert zakresy(alert) == ["zakres: lubelskie: cale"] and zasieg_api(alert) == "obszar"


def test_sluzby_wyslane_w_zwiazku_z_alertem_tez_nie_sa_zdaniem_o_odbiorcach():
    alert = parsuj("Alert RCB obowiązuje w całym woj. lubelskim.",
                   "W związku z alertem wysłano jednostki do miasta Radom w woj. mazowieckim.")
    assert alert["teryt"] == ["06"]


def test_wyslanie_alertu_nadal_jest_zdaniem_o_odbiorcach():
    alert = parsuj("Wysłano alert do mieszkańców woj. mazowieckiego.")
    assert alert["teryt"] == ["14"] and zakresy(alert) == ["zakres: mazowieckie: cale"]


# --- pkt 4: wyłączenie bez podmiotu, „oprócz” ---
def test_nie_obowiazuje_juz_bez_podmiotu_to_wylaczenie_przypisane_do_ostatniego_zasiegu():
    alert = parsuj("Alert RCB obowiązuje w powiecie puckim w woj. pomorskim.", "Nie obowiązuje już w powiecie puckim.")
    assert "wyłączone: pomorskie: puckim" in alert["miejsce"].splitlines()
    assert alert["teryt"] == ["22"] and zasieg_api(alert) == "przyblizony"


def test_wylaczenie_bez_podmiotu_przy_kilku_wojewodztwach_zostaje_bez_wojewodztwa():
    alert = parsuj(ODBIORCY + "w woj. pomorskim i lubelskim.", "Nie obowiązuje już w powiecie puckim.")
    assert "wyłączone: puckim" in alert["miejsce"].splitlines() and alert["teryt"] == ["06", "22"]
    assert zasieg_api(alert) == "przyblizony"


def test_wylaczenie_bez_podmiotu_w_aktualizacji_trafia_do_zasiegu_pierwotnego_komunikatu():
    _, aktualizacja = parsuj_wszystkie(
        "Alert RCB obowiązuje w powiecie puckim w woj. pomorskim.", "Aktualizacja 11:00", "Nie obowiązuje już w powiecie puckim.")
    assert "wyłączone: pomorskie: puckim" in aktualizacja["miejsce"].splitlines()
    assert "pomorskie: puckim" in aktualizacja["miejsce"].splitlines() and aktualizacja["teryt"] == ["22"]


def test_nie_obowiazuje_z_zaleceniem_w_tym_samym_zdaniu_czyta_wylaczenie_do_zalecenia():
    alert = parsuj("Alert RCB obowiązuje w woj. pomorskim.", "Nie obowiązuje w powiecie puckim, zalecamy zachować spokój.")
    assert "wyłączone: pomorskie: puckim" in alert["miejsce"].splitlines()


def test_oprocz_x_alert_obejmuje_y_zostawia_y_w_zasiegu():
    alert = parsuj("Oprócz powiatu kartuskiego alert obejmuje również powiat kościerski w woj. pomorskim.")
    assert alert["teryt"] == ["22"], "pusty TERYT jest niedopuszczalny"
    linie = alert["miejsce"].splitlines()
    assert "pomorskie: kościerski" in linie and "wyłączone: pomorskie: kartuskiego" in linie
    assert "wyłączone: pomorskie: kościerski" not in linie and "wyłączone: nieokreślone" not in linie
    assert zasieg_api(alert) == "przyblizony"


def test_oprocz_z_przecinkiem_i_podmiotem():
    alert = parsuj("Oprócz powiatu kartuskiego, alert obejmuje również powiat kościerski w woj. pomorskim.")
    assert "pomorskie: kościerski" in alert["miejsce"].splitlines() and alert["teryt"] == ["22"]


def test_wylaczenie_z_przeczeniem_orzeczenia_nie_konczy_sie_przed_przeczeniem():
    # „alert nie dotyczy” po wyłączeniu to nadal część wyłączenia, nie nowy człon z zasięgiem
    alert = parsuj(ODBIORCY + "w woj. pomorskim z wyjątkiem powiatu puckiego, którego alert nie dotyczy.")
    assert alert["teryt"] == ["22"]
    assert "wyłączone: pomorskie: puckiego" in alert["miejsce"].splitlines() or "wyłączone: nieokreślone" in alert["miejsce"].splitlines()
    assert "pomorskie: puckiego" not in alert["miejsce"].splitlines()


def test_zdanie_nierozpoznane_ze_slowem_wylaczenia_oznacza_zasieg_jako_nieustalony():
    # bez czasownika odbiorców („Poza miastem Chełm…”): zasięg się nie zmienia, ale mógł zmienić znaczenie
    alert = parsuj(ODBIORCY + "w całym woj. lubelskim.", "Poza miastem Chełm sytuacja jest spokojna.")
    assert rcb.LINIA_NIEUSTALONE in alert["miejsce"].splitlines()
    assert alert["teryt"] == ["06"] and zasieg_api(alert) == "przyblizony"
    assert "Chełm" not in alert["miejsce"].replace("nieustalone", "")


def test_zdanie_nierozpoznane_bez_slowa_zmiany_zasiegu_niczego_nie_oznacza():
    alert = parsuj(ODBIORCY + "w całym woj. lubelskim.", "Punkty pomocy otwarto w mieście Chełm.")
    assert rcb.LINIA_NIEUSTALONE not in alert["miejsce"].splitlines() and zasieg_api(alert) == "obszar"


def test_zdanie_nierozpoznane_bez_zasiegu_nie_dopisuje_znacznika():
    alert = parsuj("Poza miastem Chełm sytuacja jest spokojna.")
    assert alert["miejsce"] == "" and alert["teryt"] == []


# --- pkt 6: „już tylko”, „wyłącznie”, „ogranicza się do” zastępują poprzednią listę ---
PIERWOTNY = "Alert RCB obejmuje powiat świdnicki w woj. dolnośląskim oraz powiat chełmski w woj. lubelskim."


@pytest.mark.parametrize("zdanie", [
    "Od 11:00 alert obejmuje już tylko powiat chełmski w woj. lubelskim.",
    "Od 11:00 alert obejmuje wyłącznie powiat chełmski w woj. lubelskim.",
    "Od 11:00 alert ogranicza się do powiatu chełmskiego w woj. lubelskim.",
])
def test_zawezenie_w_aktualizacji_zastepuje_poprzednia_liste(zdanie):
    pierwotny, aktualizacja = parsuj_wszystkie(PIERWOTNY, "Aktualizacja 11:00", zdanie)
    assert pierwotny["teryt"] == ["02", "06"]
    assert aktualizacja["teryt"] == ["06"] and "świdnick" not in aktualizacja["miejsce"] and "dolnośląskie" not in aktualizacja["miejsce"]
    assert "lubelskie: chełmski" in aktualizacja["miejsce"].splitlines() or "lubelskie: chełmskiego" in aktualizacja["miejsce"].splitlines()


def test_zawezenie_w_naglowku_aktualizacji_zastepuje_poprzednia_liste():
    pierwotny, aktualizacja = parsuj_wszystkie(
        PIERWOTNY, "Aktualizacja 11:00: od teraz alert obejmuje wyłącznie powiat chełmski w woj. lubelskim.")
    assert pierwotny["teryt"] == ["02", "06"]
    assert aktualizacja["teryt"] == ["06"] and "świdnick" not in aktualizacja["miejsce"]
    assert aktualizacja["tresc"].startswith("od teraz alert obejmuje wyłącznie")


@pytest.mark.parametrize("naglowek", ["Aktualizacja - g. 10:55", "Aktualizacja! - 22:41", "Aktualizacja 11:00", "Aktualizacja 11:00."])
def test_naglowek_aktualizacji_bez_tresci_nie_dopisuje_linii(naglowek):
    _, aktualizacja = parsuj_wszystkie(PIERWOTNY, naglowek, "Pozostańcie w domach.")
    assert aktualizacja["tresc"] == "Pozostańcie w domach."


def test_zawezenie_bez_odczytanego_wojewodztwa_zostawia_poprzedni_zasieg_jako_nieustalony():
    # nowego zasięgu z województwem nie umiemy odczytać: szerzej i przybliżony, nigdy węziej niż źródło
    pierwotny, aktualizacja = parsuj_wszystkie(PIERWOTNY, "Aktualizacja 11:00", "Od 11:00 alert obejmuje już tylko powiat chełmski.")
    assert aktualizacja["teryt"] == ["02", "06"] and "dolnośląskie: świdnicki" in aktualizacja["miejsce"].splitlines()
    assert rcb.LINIA_NIEUSTALONE in aktualizacja["miejsce"].splitlines() and zasieg_api(aktualizacja) == "przyblizony"


def test_aktualizacja_bez_zmiany_zasiegu_nie_dostaje_znacznika():
    _, aktualizacja = parsuj_wszystkie(PIERWOTNY, "Aktualizacja 11:00", "Pozostańcie w domach tylko do odwołania.")
    assert rcb.LINIA_NIEUSTALONE not in aktualizacja["miejsce"].splitlines()


def test_tozsamosc_aktualizacji_nie_zalezy_od_tresci_po_naglowku():
    # nagłówek z treścią nie zmienia identyfikatora aktualizacji, która ma też własne linie (brak duplikatów po przeparsowaniu)
    z_trescia = parsuj_wszystkie(PIERWOTNY, "Aktualizacja 11:00: alert obejmuje wyłącznie powiat chełmski w woj. lubelskim.", "Zachowajcie spokój.")[1]
    bez = parsuj_wszystkie(PIERWOTNY, "Aktualizacja 11:00", "Zachowajcie spokój.")[1]
    assert z_trescia["zewnetrzny_id"] == bez["zewnetrzny_id"]


# --- pkt 7: elementy listy i skróty ---
def test_elementy_li_pod_naglowkiem_z_dwukropkiem_to_lista_powiatow():
    alert = parsuj("Alert RCB obejmuje wyłącznie następujące powiaty w woj. pomorskim:", "li:pucki", "li:wejherowski")
    assert linie_bez_zakresow(alert) == ["pomorskie", "pomorskie: pucki", "pomorskie: wejherowski"]
    assert zakresy(alert) != ["zakres: pomorskie: cale"] and zasieg_api(alert) == "przyblizony"


def test_elementy_li_bez_wojewodztwa_w_naglowku():
    alert = parsuj("Alert RCB został wysłany do odbiorców w powiatach:", "li:pucki", "li:wejherowski")
    assert linie_miejsca(alert) == ["pucki", "wejherowski"]


def test_li_bez_naglowka_odbiorcow_nie_sa_zasiegiem():
    alert = parsuj(ODBIORCY + "w woj. pomorskim.", "Zalecenia:", "li:pucki")
    assert zakresy(alert) == ["zakres: pomorskie: cale"] and linie_miejsca(alert) == ["pomorskie"]


@pytest.mark.parametrize("zdanie", [
    "Alert RCB obowiązuje od godz. 11:00 w powiecie wejherowskim w woj. pomorskim.",
    "Alert RCB obowiązuje w pow. wejherowskim w woj. pomorskim.",
])
def test_kropka_po_skrocie_nie_konczy_zdania(zdanie):
    alert = parsuj(zdanie)
    assert "pomorskie: wejherowskim" in alert["miejsce"].splitlines() and alert["teryt"] == ["22"]


def test_kropka_po_skrotach_nie_dzieli_zdania_a_zwykla_dzieli():
    for skrot in ("godz", "ul", "woj", "pow", "al", "Godz", "WOJ"):
        assert len(rcb.KONIEC_ZDANIA.split(f"tekst {skrot}. dalej")) == 1, skrot
    assert len(rcb.KONIEC_ZDANIA.split("koniec zdania. Nowe zdanie.")) == 3
    assert len(rcb.KONIEC_ZDANIA.split("koniec w woj. dalej. Nowe")) == 2


def test_adres_z_ul_w_zdaniu_o_odbiorcach_nie_jest_jednostka():
    alert = parsuj(ODBIORCY + "w powiatach: chełmski, ul. Lubelska 5.")
    assert linie_miejsca(alert) == ["chełmski"]


# --- pkt 8: nazwa miasta z członem będącym nazwą województwa ---
def test_wysokie_mazowieckie_nie_tworzy_dodatkowego_wojewodztwa():
    alert = parsuj("Alert RCB obowiązuje w mieście Wysokie Mazowieckie w woj. podlaskim.")
    assert alert["teryt"] == ["20"]
    assert linie_bez_zakresow(alert) == ["podlaskie", "podlaskie: miasto Wysokie Mazowieckie"]
    assert zakresy(alert) == ["zakres: podlaskie: lista_otwarta"]


def test_mazowiecki_jako_czlon_nazwy_miasta():
    alert = parsuj("Alert RCB obowiązuje w mieście Nowy Dwór Mazowiecki w woj. mazowieckim.")
    assert alert["teryt"] == ["14"] and "mazowieckie: miasto Nowy Dwór Mazowiecki" in alert["miejsce"].splitlines()


def test_nazwa_wojewodztwa_wielkimi_literami_i_tytul_nadal_sa_wojewodztwem():
    assert parsuj("ALERT RCB OBOWIĄZUJE W WOJEWÓDZTWIE LUBELSKIM.")["teryt"] == ["06"]
    assert parsuj("Alert RCB obejmuje Województwa Mazowieckiego.")["teryt"] == ["14"]
    assert parsuj("Alert RCB obejmuje woj. Mazowieckie.")["teryt"] == ["14"]


def test_dwa_wojewodztwa_obok_siebie_z_wielkiej_litery_po_przecinku():
    assert parsuj("Alert RCB obejmuje Lubelskie, Podkarpackie.")["teryt"] == ["06", "18"]


# --- R38g: odwołanie dotyczy jednostek ze swojego zdania ---
LISTA_DWOCH = "Alert RCB obowiązuje w powiecie puckim i kartuskim w woj. pomorskim."


def test_odwolanie_jednego_powiatu_nie_odwoluje_calego_zdarzenia():
    pierwotny, odwolanie = parsuj_wszystkie(LISTA_DWOCH, "Aktualizacja 12:00", "Odwołano alert w powiecie puckim.")
    assert pierwotny["status_zdarzenia"] == odwolanie["status_zdarzenia"] == Zdarzenie.Status.KOMUNIKAT_OFICJALNY
    linie = odwolanie["miejsce"].splitlines()
    assert "wyłączone: pomorskie: puckim" in linie and "pomorskie: kartuskim" in linie
    assert "wyłączone: pomorskie: kartuskim" not in linie


def test_odwolanie_wszystkich_jednostek_zasiegu_odwoluje_zdarzenie():
    _, odwolanie = parsuj_wszystkie(
        LISTA_DWOCH, "Aktualizacja 12:00", "Odwołano alert w powiecie puckim i kartuskim w woj. pomorskim.")
    assert odwolanie["status_zdarzenia"] == Zdarzenie.Status.ODWOLANE
    assert not [linia for linia in odwolanie["miejsce"].splitlines() if linia.startswith(rcb.PREFIKS_WYLACZONE)]


def test_odwolanie_calego_wojewodztwa_odwoluje_zdarzenie():
    _, odwolanie = parsuj_wszystkie(
        ODBIORCY + "w woj. lubelskim.", "Aktualizacja 12:00", "Odwołano alert w woj. lubelskim.")
    assert odwolanie["status_zdarzenia"] == Zdarzenie.Status.ODWOLANE


def test_odwolanie_jednego_wojewodztwa_z_dwoch_nie_odwoluje_zdarzenia():
    _, odwolanie = parsuj_wszystkie(
        ODBIORCY + "w woj. lubelskim i podkarpackim.", "Aktualizacja 12:00", "Odwołano alert w woj. lubelskim.")
    assert odwolanie["status_zdarzenia"] == Zdarzenie.Status.KOMUNIKAT_OFICJALNY
    assert rcb.LINIA_WYLACZENIE_OGOLNE in odwolanie["miejsce"].splitlines()


@pytest.mark.parametrize("zdanie", ["Odwołano alert RCB.", "Alert został odwołany.", "Odwołanie alertu.",
                                    "Zakończył się atak z powietrza. Brak zagrożenia na terenie Polski."])
def test_odwolanie_bez_wskazania_jednostek_odwoluje_zdarzenie(zdanie):
    _, odwolanie = parsuj_wszystkie(LISTA_DWOCH, "Aktualizacja 12:00", zdanie)
    assert odwolanie["status_zdarzenia"] == Zdarzenie.Status.ODWOLANE


def test_odwolanie_bez_znanego_zasiegu_zostaje_odwolaniem():
    assert parsuj("Odwołano alert w powiecie puckim.")["status_zdarzenia"] == Zdarzenie.Status.ODWOLANE


def _zdarzenie(zrodlo, zrob_wpis, grupa="/web/rcb/karta"):
    wpis = zrob_wpis(zrodlo)
    teraz = timezone.now()
    zdarzenie = Zdarzenie.objects.create(
        zrodlo_automatu=zrodlo, identyfikator_automatu=zbieranie.hash_id_wpisu(grupa), status=Zdarzenie.Status.ODWOLANE,
        tytul_roboczy="Alert", pierwszy_wpis_at=teraz, ostatni_wpis_at=teraz)
    return wpis, grupa, zdarzenie


def test_zdarzenie_odwolane_przez_starszy_parser_wraca_do_komunikatu_gdy_karta_nie_ma_pelnego_odwolania(zrodlo_rcb, zrob_wpis):  # noqa: F811
    wpis, grupa, zdarzenie = _zdarzenie(zrodlo_rcb, zrob_wpis)
    zbieranie._dolacz_zdarzenie(wpis, grupa, Zdarzenie.Status.KOMUNIKAT_OFICJALNY, False)
    zdarzenie.refresh_from_db()
    assert zdarzenie.status == Zdarzenie.Status.KOMUNIKAT_OFICJALNY


def test_zdarzenie_zostaje_odwolane_gdy_ta_sama_karta_ma_pelne_odwolanie(zrodlo_rcb, zrob_wpis):  # noqa: F811
    wpis, grupa, zdarzenie = _zdarzenie(zrodlo_rcb, zrob_wpis)
    zbieranie._dolacz_zdarzenie(wpis, grupa, Zdarzenie.Status.KOMUNIKAT_OFICJALNY, True)
    zdarzenie.refresh_from_db()
    assert zdarzenie.status == Zdarzenie.Status.ODWOLANE


def test_zdarzenie_zweryfikowane_przez_redaktora_nie_wraca_automatycznie(zrodlo_rcb, zrob_wpis, django_user_model):  # noqa: F811
    wpis, grupa, zdarzenie = _zdarzenie(zrodlo_rcb, zrob_wpis)
    zdarzenie.zweryfikowal = django_user_model.objects.create_user("redaktor", password="x")
    zdarzenie.save()
    zbieranie._dolacz_zdarzenie(wpis, grupa, Zdarzenie.Status.KOMUNIKAT_OFICJALNY, False)
    zdarzenie.refresh_from_db()
    assert zdarzenie.status == Zdarzenie.Status.ODWOLANE


def test_inne_zrodlo_niz_rcb_zachowuje_dotychczasowa_regule_lepkiego_odwolania(zrob_zrodlo, zrob_wpis):
    zrodlo = zrob_zrodlo("imgw_test")
    wpis, grupa, zdarzenie = _zdarzenie(zrodlo, zrob_wpis, "imgw:1")
    zbieranie._dolacz_zdarzenie(wpis, grupa, Zdarzenie.Status.KOMUNIKAT_OFICJALNY, False)
    zdarzenie.refresh_from_db()
    assert zdarzenie.status == Zdarzenie.Status.ODWOLANE
