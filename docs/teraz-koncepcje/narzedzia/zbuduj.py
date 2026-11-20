"""
Buduje dwa prototypy mapy Teraz (koncepcje A i B) jako samodzielne pliki HTML z wbudowanymi danymi.

Uruchomienie (z katalogu głównego repozytorium):
    python3 -I docs/teraz-koncepcje/narzedzia/zbuduj.py <katalog-podręczny>

<katalog-podręczny> to dowolny katalog poza repozytorium albo ignorowany przez git (np. .warsztat-zrzuty/dane).
Skrypt pobiera do niego (jeśli ich nie ma):
  - powiaty.geojson i wojewodztwa.geojson: uproszczone granice z Państwowego Rejestru Granic (GUGiK),
    w wersji z repozytorium github.com/ppatrzyk/polska-geojson (pliki *-min),
  - kafle wysokości Terrarium z otwartego zbioru AWS Terrain Tiles (z=6), z których powstaje siatka rzeźby.
Wynik: ../A-rzezba-nocna.html i ../B-makieta-polski.html (szablony w ./szablony).

Kodowanie danych (żeby pliki były małe):
  - współrzędne zaokrąglone do siatki 0,005 stopnia; wspólne granice powiatów mają te same punkty, więc obrys Polski
    i granice województw liczymy z topologii (krawędź użyta raz = granica państwa, krawędź między województwami = granica woj.),
  - pierścienie zapisane jako różnice kolejnych punktów (liczby całkowite),
  - rzeźba: wysokość / 10 m w jednym bajcie (0 = poziom morza lub niżej), base64.
"""
import base64
import json
import math
import os
import struct
import sys
import urllib.request
import zlib

TU = os.path.dirname(os.path.abspath(__file__))
WYJSCIE = os.path.dirname(TU)
Q = 200  # 1 / 0,005 stopnia

ZRODLA = {
    'powiaty.geojson': 'https://raw.githubusercontent.com/ppatrzyk/polska-geojson/master/powiaty/powiaty-min.geojson',
    'wojewodztwa.geojson': 'https://raw.githubusercontent.com/ppatrzyk/polska-geojson/master/wojewodztwa/wojewodztwa-min.geojson',
}
KAFLE = [(6, x, y) for x in (34, 35, 36) for y in (20, 21, 22)]
# Plik granic jest starszy niż rejestr TERYT z repozytorium: nazwy zmienione później (np. 2021).
DAWNE_NAZWY = {'jeleniogórski': 'karkonoski'}
TERYT = os.path.join(WYJSCIE, '..', '..', 'frontend-spin', 'public', 'teraz', 'teryt-powiaty.json')


def pobierz(cache):
    os.makedirs(cache, exist_ok=True)
    for nazwa, url in ZRODLA.items():
        p = os.path.join(cache, nazwa)
        if not os.path.exists(p):
            urllib.request.urlretrieve(url, p)
    for z, x, y in KAFLE:
        p = os.path.join(cache, f'terrarium-{z}-{x}-{y}.png')
        if not os.path.exists(p):
            urllib.request.urlretrieve(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png', p)


# ---------- PNG (8 bit RGB, bez przeplotu) ----------
def czytaj_png(sciezka):
    with open(sciezka, 'rb') as f:
        b = f.read()
    assert b[:8] == b'\x89PNG\r\n\x1a\n'
    i, idat, w, h = 8, b'', 0, 0
    while i < len(b):
        n = struct.unpack('>I', b[i:i + 4])[0]
        typ = b[i + 4:i + 8]
        dane = b[i + 8:i + 8 + n]
        if typ == b'IHDR':
            w, h, glebia, kolor = struct.unpack('>IIBB', dane[:10])
            assert glebia == 8 and kolor == 2, 'oczekiwano RGB 8 bit'
        elif typ == b'IDAT':
            idat += dane
        i += 12 + n
    surowe = zlib.decompress(idat)
    bpp, stride = 3, w * 3
    wynik = bytearray(h * stride)
    poprz = bytearray(stride)
    pos = 0
    for r in range(h):
        filtr = surowe[pos]
        lin = bytearray(surowe[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if filtr == 1:
            for k in range(bpp, stride):
                lin[k] = (lin[k] + lin[k - bpp]) & 255
        elif filtr == 2:
            for k in range(stride):
                lin[k] = (lin[k] + poprz[k]) & 255
        elif filtr == 3:
            for k in range(stride):
                a = lin[k - bpp] if k >= bpp else 0
                lin[k] = (lin[k] + ((a + poprz[k]) >> 1)) & 255
        elif filtr == 4:
            for k in range(stride):
                a = lin[k - bpp] if k >= bpp else 0
                c = poprz[k - bpp] if k >= bpp else 0
                bb = poprz[k]
                p = a + bb - c
                pa, pb, pc = abs(p - a), abs(p - bb), abs(p - c)
                lin[k] = (lin[k] + (a if pa <= pb and pa <= pc else bb if pb <= pc else c)) & 255
        wynik[r * stride:(r + 1) * stride] = lin
        poprz = lin
    return w, h, wynik


def rzezba(cache):
    kafle = {}
    for z, x, y in KAFLE:
        kafle[(x, y)] = czytaj_png(os.path.join(cache, f'terrarium-{z}-{x}-{y}.png'))
    n = 2 ** 6

    def wysokosc(lon, lat):
        fx = (lon + 180) / 360 * n
        fy = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
        tx, ty = int(fx), int(fy)
        w, h, px = kafle[(tx, ty)]
        ix, iy = min(w - 1, int((fx - tx) * w)), min(h - 1, int((fy - ty) * h))
        o = (iy * w + ix) * 3
        return px[o] * 256 + px[o + 1] + px[o + 2] / 256 - 32768

    lon0, lat0, dlon, dlat, sz, wy = 13.8, 55.0, 0.04, 0.025, 265, 248
    bajty = bytearray()
    for j in range(wy):
        lat = lat0 - j * dlat
        for i in range(sz):
            e = wysokosc(lon0 + i * dlon, lat)
            bajty.append(0 if e <= 0 else max(1, min(255, round(e / 10))))
    return {'lon0': lon0, 'lat0': lat0, 'dlon': dlon, 'dlat': dlat, 'w': sz, 'h': wy,
            'b64': base64.b64encode(bytes(bajty)).decode()}


# ---------- geometria ----------
def pierscienie(g):
    wiel = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
    return [r for p in wiel for r in p]


def kwantyzuj(r):
    out = []
    for lon, lat in r:
        p = (round(lon * Q), round(lat * Q))
        if not out or out[-1] != p:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out if len(out) >= 3 else None


def w_wielokacie(pt, rings):
    x, y = pt
    wewn = False
    for r in rings:
        n = len(r)
        for i in range(n):
            x1, y1 = r[i]
            x2, y2 = r[(i + 1) % n]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                wewn = not wewn
    return wewn


def punkt_wewnatrz(rings):
    """Punkt etykiety: środek najdłuższego poziomego odcinka wewnątrz największego pierścienia (działa też dla obwarzanków)."""
    zew = max(rings, key=len)
    ys = [p[1] for p in zew]
    najl = None
    for k in range(1, 12):
        y = min(ys) + (max(ys) - min(ys)) * k / 12 + 0.137
        xs = []
        for r in rings:
            n = len(r)
            for i in range(n):
                x1, y1 = r[i]
                x2, y2 = r[(i + 1) % n]
                if (y1 > y) != (y2 > y):
                    xs.append((x2 - x1) * (y - y1) / (y2 - y1) + x1)
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            dl = xs[i + 1] - xs[i]
            # preferuj odcinki blisko środka wysokości
            waga = dl * (1 - abs(k - 6) / 10)
            if najl is None or waga > najl[0]:
                najl = (waga, ((xs[i] + xs[i + 1]) / 2, y))
    return najl[1]


def kod_rozny(r):
    out = [r[0][0], r[0][1]]
    for i in range(1, len(r)):
        out += [r[i][0] - r[i - 1][0], r[i][1] - r[i - 1][1]]
    return out


def lancuchy(krawedzie):
    """Łączy krawędzie w łamane (granice)."""
    sasiedzi = {}
    for a, b in krawedzie:
        sasiedzi.setdefault(a, []).append(b)
        sasiedzi.setdefault(b, []).append(a)
    uzyte = set()
    wynik = []
    for a, b in krawedzie:
        if (a, b) in uzyte or (b, a) in uzyte:
            continue
        lin = [a, b]
        uzyte.add((a, b))
        for kierunek in (0, 1):
            while True:
                kon = lin[-1]
                nast = None
                for c in sasiedzi.get(kon, []):
                    if (kon, c) not in uzyte and (c, kon) not in uzyte:
                        nast = c
                        break
                if nast is None:
                    break
                uzyte.add((kon, nast))
                lin.append(nast)
            lin.reverse()
        wynik.append(lin)
    return wynik


def geometria(cache):
    pow_ = json.load(open(os.path.join(cache, 'powiaty.geojson'), encoding='utf-8'))
    woj = json.load(open(os.path.join(cache, 'wojewodztwa.geojson'), encoding='utf-8'))
    teryt = json.load(open(TERYT, encoding='utf-8'))
    woj_nazwa_kod = {w['nazwa']: w['kod'] for w in teryt['wojewodztwa']}
    woj_rings = [(woj_nazwa_kod[f['properties']['nazwa']], [[(x * Q, y * Q) for x, y in r] for r in pierscienie(f['geometry'])])
                 for f in woj['features']]
    kody = {}
    for p in teryt['powiaty']:
        kody.setdefault((p['nazwa'], p['kod'][:2]), p['kod'])

    powiaty, kraw_wl = [], {}
    for f in pow_['features']:
        rings = [k for k in (kwantyzuj(r) for r in pierscienie(f['geometry'])) if k]
        pt = punkt_wewnatrz(rings)
        wk = next((k for k, rr in woj_rings if w_wielokacie(pt, rr)), None)
        if wk is None:  # punkt tuż przy granicy uproszczonego województwa: najbliższy środek
            wk = min(woj_rings, key=lambda kr: min((pt[0] - x) ** 2 + (pt[1] - y) ** 2 for r in kr[1] for x, y in r))[0]
        nazwa = f['properties']['nazwa'].replace('powiat ', '', 1)
        nazwa = DAWNE_NAZWY.get(nazwa, nazwa)
        kod = kody.get((nazwa, wk))
        assert kod, (nazwa, wk)
        idx = len(powiaty)
        for r in rings:
            for i in range(len(r)):
                a, b = r[i], r[(i + 1) % len(r)]
                kraw_wl.setdefault((min(a, b), max(a, b)), []).append(idx)
        powiaty.append({'k': kod, 'n': nazwa, 'm': kod[2] >= '6', 'w': wk,
                        'p': [round(pt[0] / Q, 3), round(pt[1] / Q, 3)],
                        'r': [kod_rozny(r) for r in rings]})
    assert len({p['k'] for p in powiaty}) == 380

    kraj, wojg = [], []
    for kr, wl in kraw_wl.items():
        if len(wl) == 1:
            kraj.append(kr)
        elif len({powiaty[i]['w'] for i in wl}) > 1:
            wojg.append(kr)
    print('krawędzie: wszystkie', len(kraw_wl), 'granica państwa', len(kraj), 'granice województw', len(wojg))
    return {
        'q': Q,
        'powiaty': powiaty,
        'kraj': [kod_rozny(l) for l in lancuchy(kraj)],
        'woj': [kod_rozny(l) for l in lancuchy(wojg)],
        'wojewodztwa': teryt['wojewodztwa'],
    }


def buduj(cache):
    pobierz(cache)
    dane = geometria(cache)
    dane['dem'] = rzezba(cache)
    dane['zrodla'] = {
        'granice': 'Państwowy Rejestr Granic (GUGiK), uproszczenie: github.com/ppatrzyk/polska-geojson',
        'rzezba': 'AWS Terrain Tiles (Terrarium), m.in. SRTM i EU-DEM (Copernicus); siatka ok. 3 km',
        'teryt': 'kody TERYT: frontend-spin/public/teraz/teryt-powiaty.json',
    }
    tekst_danych = json.dumps(dane, ensure_ascii=False, separators=(',', ':'))
    szab = os.path.join(TU, 'szablony')
    css = open(os.path.join(szab, 'wspolne.css'), encoding='utf-8').read()
    js = open(os.path.join(szab, 'wspolne.js'), encoding='utf-8').read()
    for wej, wyj in (('a.html', 'A-rzezba-nocna.html'), ('b.html', 'B-makieta-polski.html')):
        html = open(os.path.join(szab, wej), encoding='utf-8').read()
        html = html.replace('/*WSPOLNE_CSS*/', css).replace('/*WSPOLNE_JS*/', js).replace('/*DANE*/', tekst_danych.replace('</', '<\\/'))
        with open(os.path.join(WYJSCIE, wyj), 'w', encoding='utf-8') as f:
            f.write(html)
        print(wyj, round(len(html.encode()) / 1024), 'KB')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('użycie: python3 -I docs/teraz-koncepcje/narzedzia/zbuduj.py <katalog-podręczny>')
    buduj(os.path.abspath(sys.argv[1]))
