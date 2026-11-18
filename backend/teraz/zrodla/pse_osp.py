from ..zbieranie import Adapter
from .kanaly import parsuj_kanal

URL_PSE = "https://www.pse.pl/komunikaty-osp/-/asset_publisher/UORxdCP4f0LA/rss"


class AdapterPSE(Adapter):
    def parsuj(self, odpowiedz):
        return parsuj_kanal(odpowiedz, "PSE", atom=True)

    def przeprowadz(self, cykl):
        cykl.wykonaj(self.zrodlo.adres, zrzut=False)
