from django.db import migrations, models

# Pole addytywne: puste do czasu wypełnienia. Wartość wynika ze sposobu dostępu, a dla zaimplementowanych adapterów
# z rejestru (kopia teraz.zrodla.rejestr.RODZAJ_LACZA; migracja nie importuje adapterów).
Z_DOSTEPU = {"x": "x", "api": "api", "rss": "rss", "html": "scraping", "websocket": "websocket"}
ADAPTERY = {
    "teraz-testowy": "reczne",
    "rcb": "scraping",
    "imgw_meteo": "api",
    "imgw_hydro": "api",
    "gios": "api",
    "firms": "api",
    "emsc": "websocket",
    "usgs": "api",
    "gdacs": "rss",
    "cert_pl": "rss",
    "pse_osp": "rss",
}


def wypelnij_rodzaj(apps, schema_editor):
    zrodla = apps.get_model("teraz", "Zrodlo").objects.using(schema_editor.connection.alias)
    for zrodlo in zrodla.filter(rodzaj_lacza="").iterator():
        rodzaj = ADAPTERY.get(zrodlo.slug) or Z_DOSTEPU.get(zrodlo.sposob_dostepu, "")
        if rodzaj:
            zrodla.filter(pk=zrodlo.pk).update(rodzaj_lacza=rodzaj)


class Migration(migrations.Migration):
    dependencies = [("teraz", "0005_decyzje_archiwum_i_pomiary")]
    operations = [
        migrations.AddField(
            model_name="zrodlo",
            name="rodzaj_lacza",
            field=models.CharField(
                blank=True, default="", max_length=9,
                choices=[("x", "X"), ("api", "API"), ("mci", "MCI"), ("rss", "RSS"),
                         ("scraping", "Strona WWW (scraping)"), ("websocket", "WebSocket"),
                         ("plik", "Plik"), ("reczne", "Ręczne")],
                help_text="Rodzaj łącza pokazywany publicznie. Puste: wyprowadzane ze sposobu dostępu przy zapisie.",
            ),
            preserve_default=False,
        ),
        migrations.RunPython(wypelnij_rodzaj, migrations.RunPython.noop),
    ]
