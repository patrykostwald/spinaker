"""Strona z podglądem eksperymentu: strona/lotto/index.html (jeden plik), dane.json i przeglad.html.

    python strona.py

Bez zewnętrznych skryptów, czcionek i reklam; noindex, nofollow. Wdrożenie na serwer robi koordynator.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

import lotto

KATALOG = Path(__file__).resolve().parent
WYJSCIE = KATALOG / "strona" / "lotto"
PRZEGLAD_MD = KATALOG / "dane" / "przeglad_gier.md"   # kopia RAPORT.md z gałęzi cloud/prywatne-hazard (22.10.2026)
ANALIZA = KATALOG / "wyniki" / "analiza.json"
ANALIZA2 = KATALOG / "wyniki" / "analiza2.json"

NAZWY = {"historia": "Bez dawnych szóstek", "gorace": "Gorące liczby", "zimne": "Zimne liczby",
         "rzadko_grane": "Rzadko grane", "los": "Czysty los"}
OPISY = {"historia": "losowe zestawy, ale nigdy taki, który już padł",
         "gorace": "liczby najczęstsze w ostatnich 50 losowaniach",
         "zimne": "liczby najrzadsze w ostatnich 50 losowaniach",
         "rzadko_grane": "liczby powyżej 31, bez wzorków; mniej dzielenia nagrody",
         "los": "punkt odniesienia"}
KOLORY = {"historia": "#4a9eff", "gorace": "#ff6b6b", "zimne": "#7fd4f5", "rzadko_grane": "#4ed18a", "los": "#bcc1c8"}
TELEFONY = [("801 889 880", "telefon zaufania dla osób z problemem hazardowym i innych uzależnień behawioralnych, codziennie 17-22"),
            ("800 199 990", "bezpłatny Ogólnopolski Telefon Zaufania Uzależnienia, codziennie 16-21")]  # [DP] stan 10.2026
DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
# Przegląd gier na stronie: bez nazw osób, bez nazw i stron bukmacherów (zasady START2.md).
ZAMIANY_PRZEGLADU = [
    ("Kaunitz i in. (2017) zarobili", "Autorzy badania z 2017 r. zarobili"),
    (" (np. Betclic, LVBET)", ""),
]
ZAKAZANE_DOMENY = ("meczyki.pl",)


def e(x) -> str:
    return html.escape(str(x), quote=True)


def data_pl(d: dt.date) -> str:
    return f"{d.day}.{d.month:02d}.{d.year}"


def liczba(x: float, miejsc: int) -> str:
    return f"{x:.{miejsc}f}".replace(".", ",")


def zl(x: float) -> str:
    znak = "−" if x < 0 else ""
    return f"{znak}{abs(x):,.0f} zł".replace(",", " ")


# ---------- zbieranie danych ----------

def wczytaj_dziennik(plik: Path) -> list[dict]:
    if not plik.exists():
        return []
    with plik.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def zestawienie(wiersze: list[dict]) -> dict:
    """Dla każdej strategii: wydane, wygrane, bilans, trafienia 3/4/5/6 i bilans po każdym losowaniu."""
    daty = sorted({w["losowanie_data"] for w in wiersze})
    strategie = list(dict.fromkeys([*NAZWY, *(w["strategia"] for w in wiersze)]))
    out = {}
    for s in strategie:
        g = {w["losowanie_data"]: w for w in wiersze if w["strategia"] == s}
        if not g:
            continue
        bilans = 0.0
        przebieg = []
        for d in daty:
            if d in g:
                bilans += float(g[d]["wygrana_zl"]) - float(g[d]["wydane_zl"])
            przebieg.append(round(bilans, 2))
        wyd = sum(float(w["wydane_zl"]) for w in g.values())
        wyg = sum(float(w["wygrana_zl"]) for w in g.values())
        out[s] = {"nazwa": NAZWY.get(s, s), "losowan": len(g), "wydane": round(wyd, 2), "wygrane": round(wyg, 2),
                  "bilans": round(wyg - wyd, 2), "trafienia": {k: sum(int(w[f"t{k}"]) for w in g.values()) for k in (3, 4, 5, 6)},
                  "przebieg": przebieg}
    return {"daty": daty, "strategie": out}


def wczytaj_kupony(katalog: Path) -> list[dict]:
    out = []
    for plik in sorted(katalog.glob("*.json")):
        try:
            k = json.loads(plik.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        k["zgodna"] = lotto.suma_kontrolna(k) == k.get("sha256")
        out.append(k)
    return out


def ostatnie_losowanie(losowania, dziennik: list[dict]) -> dict | None:
    kand = []
    if losowania:
        l = losowania[-1]
        kand.append((l.data, {"data": l.data.isoformat(), "numer": l.numer, "liczby": list(l.liczby)}))
    for w in dziennik:
        d = dt.date.fromisoformat(w["losowanie_data"])
        kand.append((d, {"data": d.isoformat(), "numer": None, "liczby": [int(x) for x in w["wylosowane"].split()]}))
    if not kand:
        return None
    return max(kand, key=lambda x: (x[0], x[1]["numer"] is not None))[1]


def przeglad_tabela(md: str) -> list[dict]:
    """Wiersze tabeli ocen z przeglądu gier: numer, pozycja, legalność, ocena."""
    out = []
    for linia in md.splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|(.+)\|\s*$", linia)
        if not m:
            continue
        kol = [c.strip() for c in m.group(2).split("|")]
        if len(kol) < 6:
            continue
        out.append({"nr": int(m.group(1)), "pozycja": kol[0], "legalne": kol[1].replace("**", ""),
                    "ev": kol[2], "ocena": int(re.sub(r"\D", "", kol[5]) or 0)})
    return out


def wnioski(analiza: dict, analiza2: dict) -> dict:
    out = {"historia": None, "przewaga": None}
    if analiza:
        bt = analiza.get("backtest", {})
        out["historia"] = {
            "losowan": analiza.get("kontrola", {}).get("liczba_losowan"),
            "zwrot_teoria": round(analiza.get("teoria", {}).get("zwrot_proc", 0), 1),
            "chi2_p": analiza.get("chi2", {}).get("p"),
            "powtorki": len(analiza.get("powtorki", {}).get("powtorzone_zestawy", {})),
            "strategie": [{"nazwa": NAZWY.get(s, s), "srednia": v["srednia_trafien"], "z": v["z_wobec_teorii"],
                           "zwrot": v["zwrot_proc"]} for s, v in bt.items()],
        }
    if analiza2:
        h = analiza2.get("hipoteza", {})
        po = analiza2.get("pokrycie", {})
        pt = analiza2.get("pary_trojki", {})
        out["przewaga"] = {
            "cokolwiek": analiza2.get("werdykt", {}).get("cokolwiek_istotne", False),
            "wiersze": [
                ("Nierówne liczby w okresach", f"{analiza2['epoki']['istotnych_po_poprawce']} z {analiza2['epoki']['testow']} istotnych"),
                ("Pary i trójki częstsze od losu",
                 f"rekord pary {pt['pary']['rekord']}×, los daje średnio {pt['pary']['rekord_symulacje_sr']:.0f}×".replace(".", ",")),
                ("Zależność od poprzednich losowań",
                 f"{analiza2['zaleznosc']['istotnych_po_poprawce']} z {len(analiza2['zaleznosc']['miary'])} miar istotnych"),
                ("Model uczony na przeszłości", f"{analiza2['przewidywanie']['istotnych_po_poprawce']} z "
                 f"{len(analiza2['przewidywanie']['modele']) - 1} lepszych od losu"),
                (f"Liczby {h.get('wybrany', '')} ({h.get('uczenie', '')})",
                 f"padały {h.get('kierunek', '')}, ale nie w latach {h.get('test', '')}" if not h.get("potwierdzona")
                 else f"padały {h.get('kierunek', '')} także w latach {h.get('test', '')}"),
                ("Rozpisanie zakładów (20)", f"choć jedna wygrana {po['rozpisane_max_2_wspolne']['szansa_choc_jednej_wygranej_proc']:.1f}% "
                 f"zamiast {po['losowe_bez_ograniczen']['szansa_choc_jednej_wygranej_proc']:.1f}%, ta sama średnia".replace(".", ",")),
            ],
        }
    return out


def zbierz(teraz: dt.datetime | None = None, katalog_kuponow: Path = lotto.KUPONY, dziennik: Path = lotto.DZIENNIK,
           losowania=None) -> dict:
    teraz = teraz or dt.datetime.now()
    if losowania is None:
        losowania = lotto.dane.wczytaj_csv()
    wiersze = wczytaj_dziennik(dziennik)
    kupony = wczytaj_kupony(katalog_kuponow)
    sprawdzone_daty = {w["losowanie_data"] for w in wiersze}
    najblizsze = lotto.najblizsze_losowanie(teraz)
    # kupon do pokazania: najwcześniejszy jeszcze niesprawdzony, z datą od dziś (zwykle ten na najbliższe losowanie)
    otwarte = [k for k in kupony if k["losowanie_data"] not in sprawdzone_daty and k["losowanie_data"] >= teraz.date().isoformat()]
    kupon = min(otwarte, key=lambda k: k["losowanie_data"]) if otwarte else None
    if kupon:
        najblizsze = min(najblizsze, dt.date.fromisoformat(kupon["losowanie_data"]))
    analiza = json.loads(ANALIZA.read_text(encoding="utf-8")) if ANALIZA.exists() else {}
    analiza2 = json.loads(ANALIZA2.read_text(encoding="utf-8")) if ANALIZA2.exists() else {}
    md = PRZEGLAD_MD.read_text(encoding="utf-8") if PRZEGLAD_MD.exists() else ""
    return {
        "wygenerowano": teraz.isoformat(timespec="minutes"),
        "ostatnie": ostatnie_losowanie(losowania, wiersze),
        "najblizsze": {"data": najblizsze.isoformat(), "godzina": lotto.GODZINA_LOSOWANIA.strftime("%H:%M"),
                       "koniec_sprzedazy": lotto.KONIEC_SPRZEDAZY.strftime("%H:%M")},
        "kupon": None if not kupon else {
            "losowanie_data": kupon["losowanie_data"], "zapisano": kupon["zapisano"], "sha256": kupon["sha256"],
            "zgodna": kupon["zgodna"], "dane_do": kupon.get("dane_do"), "cena_zl": kupon["cena_zl"],
            "strategie": kupon["strategie"]},
        "budzet": {"na_losowanie": lotto.BUDZET, "cena": lotto.CENA, "zakladow": lotto.ZAKLADOW},
        "dziennik": zestawienie(wiersze),
        "wnioski": wnioski(analiza, analiza2),
        "przeglad": przeglad_tabela(md),
    }


# ---------- HTML ----------

CSS = """
:root{--bg:#0b0c0e;--s1:#121418;--s2:#181b20;--s3:#20242a;--line:#2a2e35;--t1:#e8eaed;--t2:#bcc1c8;--t3:#959ba3;
--acc:#4a9eff;--accs:rgba(74,158,255,.12);--neg:#ff6b6b;--pos:#4ed18a;--warn:#f2b441;--gap:16px;--r:12px}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--t1);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}
.w{max-width:1120px;margin:0 auto;padding:32px 24px 48px}
h1{font-size:28px;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:20px;line-height:1.3;margin:0}
h3{font-size:16px;line-height:1.35;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
p{margin:0}.t2{color:var(--t2)}.t3{color:var(--t3);font-size:14px}
a{color:var(--acc);font-weight:600;text-decoration:none}a:hover{text-decoration:underline}
a:focus-visible,button:focus-visible{outline:2px solid #7ab6ff;outline-offset:2px}
.sek{margin-top:40px}.sek>.nag{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:var(--gap)}
.uwaga{margin-top:20px;padding:14px 16px;border:1px solid rgba(242,180,65,.45);background:rgba(242,180,65,.08);border-radius:var(--r);
display:flex;gap:12px;align-items:flex-start}.uwaga b{color:var(--warn)}
header+.rz{margin-top:24px}
.rz .box>.dol{min-height:52px}
.rz{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--gap)}
.box{background:var(--s1);border:1px solid var(--line);border-radius:var(--r);padding:20px;display:grid;
grid-template-rows:auto 1fr auto;gap:14px;min-width:0}
.box>.dol{color:var(--t3);font-size:14px;line-height:20px;border-top:1px solid var(--line);padding-top:12px}
.tyt{display:flex;align-items:center;justify-content:space-between;gap:10px}
.et{font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;background:var(--accs);color:var(--acc);white-space:nowrap}
.et.ok{background:rgba(78,209,138,.12);color:var(--pos)}.et.zle{background:rgba(255,107,107,.12);color:var(--neg)}
.kule{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.kula{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:17px;
background:var(--t1);color:#0b0c0e}
.duza{font-size:24px;font-weight:700;line-height:1.25}
.taby{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:var(--gap)}
.taby button{min-height:44px;padding:0 16px;border-radius:999px;border:1px solid var(--line);background:var(--s1);color:var(--t2);
font:inherit;font-size:15px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:8px}
.taby button[aria-selected=true]{border-color:var(--acc);color:var(--t1);background:var(--accs)}
.kr{width:10px;height:10px;border-radius:50%;display:inline-block;flex:none}
.zaklady{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px 16px;list-style:none;margin:0;padding:0;counter-reset:z}
.zaklady li{display:flex;align-items:center;gap:6px;height:32px;counter-increment:z}
.zaklady li::before{content:counter(z);width:22px;color:var(--t3);font-size:13px;text-align:right;flex:none}
.zaklady span{width:30px;height:28px;display:grid;place-items:center;border-radius:6px;background:var(--s3);font-size:14px;font-weight:600}
.panel[hidden]{display:none}
table{width:100%;border-collapse:collapse;font-size:15px}
th,td{padding:10px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--t3);font-weight:600;font-size:13px}th:first-child,td:first-child{text-align:left;padding-left:0;white-space:normal}
td:last-child,th:last-child{padding-right:0}
.tab{overflow:hidden}.neg{color:var(--neg)}.pos{color:var(--pos)}
.wyk{width:100%;height:auto;display:block}
.leg{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:14px;color:var(--t2)}
.leg span{display:inline-flex;align-items:center;gap:6px}
.lista{list-style:none;margin:0;padding:0;display:grid;gap:0}
.lista li{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--line);font-size:15px}
.lista li:last-child{border-bottom:0}.lista li span:last-child{text-align:right;color:var(--t2)}
.ocena{display:inline-block;min-width:28px;text-align:center;font-weight:700;border-radius:6px;padding:1px 6px;background:var(--s3)}
.o-hi{color:var(--pos)}.o-mid{color:var(--warn)}.o-lo{color:var(--neg)}
.stopka{margin-top:40px;padding:20px;border-radius:var(--r);background:var(--s1);border:1px solid var(--line);display:grid;gap:10px}
.stopka .tel{font-size:20px;font-weight:700;color:var(--t1);white-space:nowrap}
.tele{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--gap)}
.tele>div{display:grid;gap:2px}
.pusty{color:var(--t2);padding:24px 0;text-align:center}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:13px;word-break:break-all}
@media (max-width:860px){.zaklady{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.w{padding:24px 16px 40px}.sek>.nag{flex-direction:column;gap:4px}
.md tr>:nth-child(4),.md tr>:nth-child(5),.md tr>:nth-child(6){display:none}h1{font-size:23px}.rz,.tele{grid-template-columns:1fr}
.sek{margin-top:32px}.kula{width:40px;height:40px;font-size:16px}.zaklady{gap:6px 10px}.zaklady span{width:28px}
.zaklady li::before{width:18px}.tab{overflow-x:auto}.ukryj-m{display:none}th,td{padding:9px 5px}.taby button{padding:0 12px;font-size:14px}}
@media (max-width:380px){.zaklady{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

JS = """
document.querySelectorAll('.taby').forEach(function(t){var b=t.querySelectorAll('button');b.forEach(function(x){
x.addEventListener('click',function(){b.forEach(function(y){var on=y===x;y.setAttribute('aria-selected',on);
document.getElementById(y.getAttribute('aria-controls')).hidden=!on;});});});});
"""


def kule(liczby) -> str:
    return '<div class="kule">' + "".join(f'<span class="kula">{int(x)}</span>' for x in liczby) + "</div>"


def wykres(dz: dict) -> str:
    daty, st = dz["daty"], dz["strategie"]
    if not daty:
        return ""
    W, H, L, P, G, D = 480, 250, 78, 8, 14, 30
    wart = [v for s in st.values() for v in s["przebieg"]] + [0.0]
    lo, hi = min(wart), max(wart)
    if hi - lo < 1:
        hi, lo = hi + 50, lo - 50
    n = len(daty)

    def x(i):
        return L + (W - L - P) * (i / (n - 1) if n > 1 else 0.5)

    def y(v):
        return G + (H - G - D) * (hi - v) / (hi - lo)
    out = [f'<svg class="wyk" viewBox="0 0 {W} {H}" role="img" aria-label="Bilans strategii po kolejnych losowaniach">']
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        out.append(f'<line x1="{L}" x2="{W - P}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#2a2e35"/>'
                   f'<text x="{L - 8}" y="{y(v) + 4:.1f}" fill="#959ba3" font-size="14" text-anchor="end">{e(zl(v))}</text>')
    out.append(f'<line x1="{L}" x2="{W - P}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="#959ba3" stroke-dasharray="4 4"/>')
    for i in sorted({0, n - 1}):
        out.append(f'<text x="{x(i):.1f}" y="{H - 8}" fill="#959ba3" font-size="14" '
                   f'text-anchor="{"start" if i == 0 and n > 1 else ("end" if n > 1 else "middle")}">'
                   f'{e(data_pl(dt.date.fromisoformat(daty[i])))}</text>')
    for s, d in st.items():
        k = KOLORY.get(s, "#bcc1c8")
        pkt = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(d["przebieg"]))
        if n > 1:
            out.append(f'<polyline points="{pkt}" fill="none" stroke="{k}" stroke-width="2" stroke-linejoin="round"/>')
        i, v = n - 1, d["przebieg"][-1]
        out.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5" fill="{k}"/>')
    out.append("</svg>")
    leg = "".join(f'<span><i class="kr" style="background:{KOLORY.get(s, "#bcc1c8")}"></i>{e(d["nazwa"])}</span>'
                  for s, d in st.items())
    return "".join(out) + f'<div class="leg">{leg}</div>'


def sekcja_losowania(d: dict) -> str:
    o, n, k = d["ostatnie"], d["najblizsze"], d["kupon"]
    if o:
        od = dt.date.fromisoformat(o["data"])
        lewy = (f'<div class="tyt"><h3>Ostatnie losowanie</h3><span class="et">wynik</span></div>'
                f'<div><p class="duza">{DNI[od.weekday()]}, {data_pl(od)}</p><div style="margin-top:14px">{kule(o["liczby"])}</div></div>'
                f'<p class="dol">{"Losowanie nr " + str(o["numer"]) + " · " if o["numer"] else ""}źródło: dane/lotto.csv i dziennik</p>')
    else:
        lewy = '<div class="tyt"><h3>Ostatnie losowanie</h3></div><p class="t2">Brak danych.</p><p class="dol">-</p>'
    nd = dt.date.fromisoformat(n["data"])
    if k:
        et = '<span class="et ok">zablokowane</span>' if k["zgodna"] else '<span class="et zle">suma niezgodna</span>'
        zap = dt.datetime.fromisoformat(k["zapisano"])
        srodek = (f'<div><p class="duza">{DNI[nd.weekday()]}, {data_pl(nd)}, {e(n["godzina"])}</p>'
                  f'<p class="t2" style="margin-top:10px">Kupony zapisane {data_pl(zap.date())} o {zap:%H:%M}, '
                  f'przed losowaniem; po zapisie nie da się ich zmienić bez zmiany sumy kontrolnej.</p></div>')
        dol = f'<p class="dol">SHA-256: <span class="mono">{e(k["sha256"][:16])}…</span></p>'
    else:
        et = '<span class="et">czeka</span>'
        srodek = (f'<div><p class="duza">{DNI[nd.weekday()]}, {data_pl(nd)}, {e(n["godzina"])}</p>'
                  f'<p class="t2" style="margin-top:10px">Kuponów jeszcze nie ma - automat zapisze je przed {e(n["koniec_sprzedazy"])}.</p></div>')
        dol = '<p class="dol">SHA-256: -</p>'
    prawy = f'<div class="tyt"><h3>Najbliższe losowanie</h3>{et}</div>{srodek}{dol}'
    return f'<div class="rz"><section class="box">{lewy}</section><section class="box">{prawy}</section></div>'


def sekcja_kuponow(d: dict) -> str:
    k = d["kupon"]
    b = d["budzet"]
    nag = (f'<div class="nag"><h2>Kupony na najbliższe losowanie</h2>'
           f'<span class="t3">{b["zakladow"]} zakładów po {b["cena"]:.0f} zł = {b["na_losowanie"]:.0f} zł wirtualnie na strategię</span></div>')
    if not k:
        return f'<section class="sek">{nag}<p class="pusty">Kupony pojawią się po uruchomieniu „python lotto.py generuj”.</p></section>'
    taby, panele = [], []
    for i, (s, zaklady) in enumerate(k["strategie"].items()):
        on = i == 0
        taby.append(f'<button role="tab" id="t-{s}" aria-controls="p-{s}" aria-selected="{str(on).lower()}">'
                    f'<i class="kr" style="background:{KOLORY.get(s, "#bcc1c8")}"></i>{e(NAZWY.get(s, s))}</button>')
        lista = "".join("<li>" + "".join(f"<span>{int(x)}</span>" for x in z) + "</li>" for z in zaklady)
        panele.append(f'<div class="panel box" id="p-{s}" role="tabpanel" aria-labelledby="t-{s}"{"" if on else " hidden"}>'
                      f'<div class="tyt"><h3>{e(NAZWY.get(s, s))}</h3><span class="t3 ukryj-m">{e(OPISY.get(s, ""))}</span></div>'
                      f'<ol class="zaklady">{lista}</ol>'
                      f'<p class="dol">Losowanie {data_pl(dt.date.fromisoformat(k["losowanie_data"]))} · dane do '
                      f'{data_pl(dt.date.fromisoformat(k["dane_do"])) if k.get("dane_do") else "-"} · '
                      f'suma kontrolna {"zgodna" if k["zgodna"] else "NIEZGODNA"}</p></div>')
    return f'<section class="sek">{nag}<div class="taby" role="tablist">{"".join(taby)}</div>{"".join(panele)}</section>'


def sekcja_dziennika(d: dict) -> str:
    dz = d["dziennik"]
    nag = (f'<div class="nag"><h2>Dziennik eksperymentu</h2>'
           f'<span class="t3">sprawdzonych losowań: {len(dz["daty"])}</span></div>')
    if not dz["daty"]:
        return (f'<section class="sek">{nag}<div class="box"><div class="tyt"><h3>Jeszcze bez wyników</h3></div>'
                f'<p class="t2">Pierwsze liczby pojawią się po sprawdzeniu pierwszego losowania („python lotto.py sprawdz” po 22:30).</p>'
                f'<p class="dol">Każda strategia gra za {d["budzet"]["na_losowanie"]:.0f} zł wirtualnie na losowanie.</p></div></section>')
    wiersze = []
    for s, v in dz["strategie"].items():
        t = v["trafienia"]
        wiersze.append(f'<tr><td><i class="kr" style="background:{KOLORY.get(s, "#bcc1c8")}"></i> {e(v["nazwa"])}</td>'
                       f'<td class="ukryj-m">{e(zl(v["wygrane"]))}</td>'
                       f'<td class="{"neg" if v["bilans"] < 0 else "pos"}">{e(zl(v["bilans"]))}</td>'
                       f'<td>{t[3]} / {t[4]} / {t[5]} / {t[6]}</td></tr>')
    tabela = ('<div class="tab"><table><thead><tr><th>Strategia</th><th class="ukryj-m">Wygrane</th>'
              '<th>Bilans</th><th>3/4/5/6</th></tr></thead><tbody>' + "".join(wiersze) + "</tbody></table></div>")
    return (f'<section class="sek">{nag}<div class="rz">'
            f'<div class="box"><div class="tyt"><h3>Wynik strategii</h3></div>{tabela}'
            f'<p class="dol">Wydane: {e(zl(max(v["wydane"] for v in dz["strategie"].values())))} na strategię. '
            f'Wygrane według kwot z losowania, gdy są znane, inaczej średnich.</p></div>'
            f'<div class="box"><div class="tyt"><h3>Bilans w czasie</h3></div><div>{wykres(dz)}</div>'
            f'<p class="dol">Linia przerywana: zero. Poniżej zera - strata.</p></div></div></section>')


def sekcja_wnioskow(d: dict) -> str:
    w = d["wnioski"]
    h, p = w["historia"], w["przewaga"]
    if h:
        lista = "".join(f'<li><span>{e(s["nazwa"])}</span><span>{liczba(s["srednia"], 4)} trafienia · '
                        f'zwrot {liczba(s["zwrot"], 1)}%</span></li>' for s in h["strategie"])
        lewy = (f'<div class="tyt"><h3>Test na historii: {h["losowan"]} losowań</h3><span class="et">1957-2026</span></div>'
                f'<div><p class="t2" style="margin-bottom:10px">Każda strategia grała 33 zakłady na każde losowanie. Los daje '
                f'0,7347 trafienia na zakład; wszystkie strategie trafiały tyle samo.</p><ul class="lista">{lista}</ul></div>'
                f'<p class="dol">Z 5 zł wraca średnio ok. {h["zwrot_teoria"]:.0f}% stawki. Szczegóły: RAPORT.md.</p>')
    else:
        lewy = '<div class="tyt"><h3>Test na historii</h3></div><p class="t2">Brak wyników (python analiza.py).</p><p class="dol">-</p>'
    if p:
        lista = "".join(f"<li><span>{e(a)}</span><span>{e(b)}</span></li>" for a, b in p["wiersze"])
        et = '<span class="et zle">znaleziono sygnał</span>' if p["cokolwiek"] else '<span class="et">brak przewagi</span>'
        lewy2 = (f'<div class="tyt"><h3>Szukanie przewagi</h3>{et}</div>'
                 f'<div><p class="t2" style="margin-bottom:10px">Sześć prób znalezienia niedoskonałości maszyny lub kul, '
                 f'z poprawką na wielokrotne testy.</p><ul class="lista">{lista}</ul></div>'
                 f'<p class="dol">Wniosek: nie da się zwiększyć szansy. Szczegóły: RAPORT2.md.</p>')
    else:
        lewy2 = '<div class="tyt"><h3>Szukanie przewagi</h3></div><p class="t2">Brak wyników (python analiza2.py).</p><p class="dol">-</p>'
    return (f'<section class="sek"><div class="nag"><h2>Wnioski</h2></div>'
            f'<div class="rz"><div class="box">{lewy}</div><div class="box">{lewy2}</div></div></section>')


def klasa_oceny(o: int) -> str:
    return "o-hi" if o >= 6 else ("o-mid" if o >= 3 else "o-lo")


def sekcja_przegladu(d: dict) -> str:
    if not d["przeglad"]:
        return ""
    wiersze = "".join(f'<tr><td>{e(r["pozycja"])}</td><td class="ukryj-m">{e(r["legalne"])}</td>'
                      f'<td><span class="ocena {klasa_oceny(r["ocena"])}">{r["ocena"]}</span></td></tr>' for r in d["przeglad"])
    return (f'<section class="sek"><div class="nag"><h2>Gdzie matematyka daje przewagę</h2>'
            f'<a href="przeglad.html">Pełny przegląd →</a></div>'
            f'<div class="box"><div class="tyt"><h3>Przegląd gier w Polsce (10.2026)</h3><span class="t3 ukryj-m">ocena 0-10</span></div>'
            f'<div class="tab"><table><thead><tr><th>Pozycja</th><th class="ukryj-m">Legalne w PL</th><th>Ocena</th></tr></thead>'
            f'<tbody>{wiersze}</tbody></table></div>'
            f'<p class="dol">W grach losowych przewagi nie ma. Dodatni wynik jest możliwy tylko tam, gdzie liczy się umiejętność.</p>'
            f'</div></section>')


def stopka() -> str:
    tel = "".join(f'<div><span class="tel">{e(n)}</span><span class="t3">{e(o)}</span></div>' for n, o in TELEFONY)
    return (f'<footer class="stopka"><div class="tyt"><h3>Odpowiedzialna gra</h3><span class="et zle">18+</span></div>'
            f'<p class="t2">Gry losowe są dozwolone od 18 lat. Jeśli grasz za pieniądze potrzebne na rachunki, ukrywasz granie '
            f'albo próbujesz się „odegrać” - porozmawiaj z kimś.</p><div class="tele">{tel}</div></footer>')


def szkielet(tytul: str, tresc: str, js: str = "") -> str:
    return (f'<!doctype html><html lang="pl"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="noindex, nofollow"><title>{e(tytul)}</title>'
            f'<style>{CSS}</style></head><body><main class="w">{tresc}</main>'
            + (f"<script>{js}</script>" if js else "") + "</body></html>")


def strona_html(d: dict) -> str:
    gen = dt.datetime.fromisoformat(d["wygenerowano"])
    naglowek = (f'<header><h1>Lotto: eksperyment z 5 strategiami</h1>'
                f'<p class="t2">Stan na {data_pl(gen.date())}, {gen:%H:%M}. Kupony zapisywane przed losowaniem, '
                f'wyniki sprawdzane automatycznie po losowaniu.</p>'
                f'<div class="uwaga" role="note"><b>!</b><p><b>Eksperyment na wirtualnych pieniądzach, żadna strategia nie '
                f'zwiększa szansy.</b> Nic nie jest kupowane; każdy zestaw liczb ma tę samą szansę 1 do 13 983 816.</p></div></header>')
    tresc = (naglowek + sekcja_losowania(d) + sekcja_kuponow(d) + sekcja_dziennika(d) + sekcja_wnioskow(d)
             + sekcja_przegladu(d) + stopka())
    return szkielet("Lotto - eksperyment", tresc, JS)


# ---------- przegląd gier: prosty Markdown -> HTML ----------

def _inline(t: str) -> str:
    t = e(t)

    def link(m):
        tekst, url = m.group(1), html.unescape(m.group(2))
        if any(dom in url for dom in ZAKAZANE_DOMENY):
            return "portal o zakładach, bez odnośnika"
        return f'<a href="{e(url)}" rel="nofollow noopener noreferrer">{tekst}</a>'
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def markdown_html(md: str) -> str:
    for a, b in ZAMIANY_PRZEGLADU:
        md = md.replace(a, b)
    linie = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(linie):
        l = linie[i]
        if not l.strip():
            i += 1
            continue
        if l.startswith("#"):
            poz = len(l) - len(l.lstrip("#"))
            out.append(f"<h{min(poz, 3)}>{_inline(l.lstrip('#').strip())}</h{min(poz, 3)}>")
            i += 1
        elif l.startswith("|"):
            wiersze = []
            while i < len(linie) and linie[i].startswith("|"):
                if not re.match(r"^\|[\s\-|:]+\|$", linie[i]):
                    wiersze.append([c.strip() for c in linie[i].strip().strip("|").split("|")])
                i += 1
            gl = "".join(f"<th>{_inline(c)}</th>" for c in wiersze[0])
            cialo = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in w) + "</tr>" for w in wiersze[1:])
            out.append(f'<div class="tab"><table class="md"><thead><tr>{gl}</tr></thead><tbody>{cialo}</tbody></table></div>')
        elif re.match(r"^\s*(-|\d+\.)\s", l):
            numerowana = bool(re.match(r"^\d+\.", l))
            elementy: list[str] = []
            while i < len(linie) and linie[i].strip() and (re.match(r"^\s*(-|\d+\.)\s", linie[i]) or linie[i].startswith("  ")):
                x = linie[i]
                if re.match(r"^\s*(-|\d+\.)\s", x):
                    wciecie = len(x) - len(x.lstrip())
                    tekst = re.sub(r"^\s*(-|\d+\.)\s", "", x)
                    elementy.append(("  " if wciecie >= 2 else "") + tekst)
                else:
                    elementy[-1] += " " + x.strip()
                i += 1
            html_el = []
            pod: list[str] = []
            for el in elementy:
                if el.startswith("  "):
                    pod.append(f"<li>{_inline(el.strip())}</li>")
                    continue
                if pod and html_el:
                    html_el[-1] = html_el[-1][:-5] + f"<ul>{''.join(pod)}</ul></li>"
                    pod = []
                html_el.append(f"<li>{_inline(el)}</li>")
            if pod and html_el:
                html_el[-1] = html_el[-1][:-5] + f"<ul>{''.join(pod)}</ul></li>"
            tag = "ol" if numerowana else "ul"
            out.append(f"<{tag}>{''.join(html_el)}</{tag}>")
        else:
            akapit = []
            while i < len(linie) and linie[i].strip() and not linie[i].startswith(("#", "|")) \
                    and not re.match(r"^\s*(-|\d+\.)\s", linie[i]):
                akapit.append(linie[i].strip())
                i += 1
            out.append(f"<p>{_inline(' '.join(akapit))}</p>")
    return "\n".join(out)


CSS_PRZEGLADU = """
.md-tresc h1{margin-top:12px}.md-tresc h2{margin:36px 0 12px}.md-tresc h3{margin:24px 0 8px;white-space:normal}
.md-tresc p{margin:0 0 12px;color:var(--t2)}.md-tresc ul,.md-tresc ol{margin:0 0 12px;padding-left:22px;color:var(--t2)}
.md-tresc li{margin:4px 0}.md-tresc b{color:var(--t1)}.md-tresc code{background:var(--s3);padding:1px 5px;border-radius:4px}
.md-tresc .tab{overflow-x:auto;margin:0 0 16px;background:var(--s1);border:1px solid var(--line);border-radius:12px;padding:4px 16px}
.md-tresc table.md td,.md-tresc table.md th{white-space:normal;text-align:left;vertical-align:top;min-width:70px}
.md-tresc a{font-weight:500}
@media (max-width:640px){.md-tresc .tab{padding:4px 10px}.md-tresc table.md td,.md-tresc table.md th{min-width:0;padding:8px 4px;
overflow-wrap:anywhere;font-size:14px}}
"""


def przeglad_html(md: str) -> str:
    tresc = (f'<p><a href="index.html">← Wróć do eksperymentu</a></p><article class="md-tresc">{markdown_html(md)}</article>'
             + stopka())
    return szkielet("Przegląd gier - Lotto", tresc).replace("</style>", CSS_PRZEGLADU + "</style>", 1)


# ---------- zapis ----------

def generuj(teraz: dt.datetime | None = None, wyjscie: Path = WYJSCIE, **kw) -> Path:
    d = zbierz(teraz, **kw)
    wyjscie.mkdir(parents=True, exist_ok=True)
    (wyjscie / "dane.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    (wyjscie / "index.html").write_text(strona_html(d), encoding="utf-8")
    md = PRZEGLAD_MD.read_text(encoding="utf-8") if PRZEGLAD_MD.exists() else "# Przegląd gier\n\nBrak pliku."
    (wyjscie / "przeglad.html").write_text(przeglad_html(md), encoding="utf-8")
    return wyjscie / "index.html"


def main(argv=None) -> int:
    plik = generuj()
    print(f"Strona: {plik} (oraz dane.json i przeglad.html)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
