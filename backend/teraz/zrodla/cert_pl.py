from ..zbieranie import Adapter
from .kanaly import parsuj_kanal

URL_CERT = "https://cert.pl/rss.xml"


class AdapterCERT(Adapter):
    def parsuj(self, odpowiedz):
        return parsuj_kanal(odpowiedz, "CERT Polska")

    def przeprowadz(self, cykl):
        cykl.wykonaj(self.zrodlo.adres, zrzut=False)
