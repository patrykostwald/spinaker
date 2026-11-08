"""Rządowy Proces Legislacyjny (legislacja.rcl.gov.pl): projekty, etapy, dokumenty i dziennik zmian.

Zasady (pismo RCL.DPK.053.168.2026 z 21.10.2026 i docs/SOURCE_EXPANSION.md):
- każdy rekord ma link do strony w RCL i datę pobrania; publikując, podajemy "Źródło: Rządowe Centrum Legislacji, legislacja.rcl.gov.pl";
- nic nie jest nadpisywane po cichu: każda zmiana wartości, nowy lub znikający element trafia do LegislativeChange (tylko dopisywanie);
- zapisujemy metadane i linki do plików; same pliki tylko w osobnym, domyślnie wyłączonym kroku;
- nie zapisujemy imion i nazwisk pracowników wprowadzających dokumenty (pole "wprowadzony przez"), tylko autora dokumentu.
"""
from django.db import models
from django.utils import timezone

from scraper.rcl_guard import PROCESSING_NOTE, RCL_BASE_URL, SOURCE_LINE


class LegislativeProject(models.Model):
    class ActType(models.IntegerChoices):
        # Wartości typeId z menu serwisu (stan na 8.09.2026, wg kopii strony); inne wartości zapisujemy tak, jak przyszły.
        CONCEPT = 1, 'Projekty założeń projektów ustaw'
        BILL = 2, 'Projekty ustaw'
        OSR_EX_POST = 6, 'OSR ex post'
        REGULATION = 10, 'Projekty rozporządzeń'

    rcl_id = models.PositiveBigIntegerField(unique=True, help_text='Numer z adresu /projekt/<id> w RCL.')
    act_type_id = models.PositiveSmallIntegerField(db_index=True, help_text='typeId z listy projektów RCL.')
    act_type = models.CharField(max_length=80, blank=True, help_text='Rodzaj aktu (etykieta z menu serwisu).')
    title = models.CharField(max_length=1000)
    applicant = models.CharField(max_length=300, blank=True, help_text='Organ wnioskujący.')
    wykaz_number = models.CharField(max_length=40, blank=True, db_index=True, help_text='Numer w wykazie prac RM, np. UD463.')
    wykaz_url = models.URLField(max_length=1024, blank=True)
    wykaz_name = models.CharField(max_length=200, blank=True)
    rm_number = models.CharField(max_length=60, blank=True, help_text='Numer RM-... z odnośnika do Sejmu (jeśli jest).')
    sejm_url = models.URLField(max_length=1024, blank=True)
    status = models.CharField(max_length=60, blank=True)
    term = models.CharField(max_length=20, blank=True, help_text='Kadencja Sejmu.')
    departments = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    info = models.JSONField(default=dict, blank=True, help_text='Wszystkie wiersze karty projektu: etykieta -> tekst (kopia źródła).')
    notes = models.JSONField(default=list, blank=True, help_text='Uwagi ze strony projektu, np. zwolnienie z obowiązku.')
    created_on = models.DateField(null=True, blank=True, help_text='Data utworzenia projektu w RCL.')
    list_modified_on = models.DateField(null=True, blank=True, db_index=True, help_text='"Zmodyfikowany" z listy RCL.')
    source_url = models.URLField(max_length=1024)
    # Pobrania: lista (podsumowanie) i strona projektu (szczegóły) mają osobne daty.
    list_fetched_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='Data pobrania strony projektu.')
    first_seen_at = models.DateTimeField(default=timezone.now)
    needs_refresh = models.BooleanField(default=True, db_index=True, help_text='Do ponownego pobrania strony i katalogów etapów.')
    refresh_priority = models.PositiveSmallIntegerField(default=0, db_index=True, help_text='1 = nowość/zmiana z listy, 0 = archiwum.')
    refresh_failures = models.PositiveSmallIntegerField(default=0, help_text='Kolejne błędy odczytu strony; od 3 projekt wypada z kolejki do ręcznego sprawdzenia.')
    last_error = models.CharField(max_length=120, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-list_modified_on', '-rcl_id']
        indexes = [models.Index(fields=['needs_refresh', '-refresh_priority', '-list_modified_on'], name='rcl_project_queue')]

    def __str__(self):
        return f'RCL {self.rcl_id}: {self.title[:80]}'

    @property
    def attribution(self):
        return SOURCE_LINE

    @property
    def processing_note(self):
        return PROCESSING_NOTE

    @staticmethod
    def url_for(rcl_id):
        return f'{RCL_BASE_URL}/projekt/{int(rcl_id)}'


class LegislativeStage(models.Model):
    class State(models.TextChoices):
        NOT_STARTED = 'not_started', 'Jeszcze nie rozpoczęty'
        REACHED = 'reached', 'Osiągnięty'
        ACTIVE = 'active', 'Trwa'

    project = models.ForeignKey(LegislativeProject, on_delete=models.CASCADE, related_name='stages')
    rcl_id = models.PositiveBigIntegerField(help_text='Numer etapu (li id=) w RCL.')
    number = models.PositiveSmallIntegerField(null=True, blank=True)
    name = models.CharField(max_length=300)
    kind = models.CharField(max_length=24, blank=True, db_index=True,
                            help_text='Heurystyka po nazwie: lobbing, uzgodnienia, konsultacje, opiniowanie, komitet, sejm, inne.')
    state = models.CharField(max_length=16, choices=State.choices, default=State.NOT_STARTED)
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    modified_on = models.DateField(null=True, blank=True, help_text='"Data ostatniej modyfikacji" etapu.')
    catalog_url = models.URLField(max_length=1024, blank=True)
    catalog_fetched_at = models.DateTimeField(null=True, blank=True)
    catalog_modified_seen = models.DateField(null=True, blank=True,
                                             help_text='Wartość modified_on w chwili ostatniego pobrania katalogu.')
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['project_id', 'number', 'rcl_id']
        constraints = [models.UniqueConstraint(fields=['project', 'rcl_id'], name='rcl_stage_unique_per_project')]

    def __str__(self):
        return f'{self.number or "?"}. {self.name}'


class LegislativeDocument(models.Model):
    class Category(models.TextChoices):
        PROJECT = 'project', 'Projekt (wersja tekstu)'
        JUSTIFICATION = 'justification', 'Uzasadnienie'
        OSR = 'osr', 'Ocena skutków regulacji'
        COVER_LETTER = 'cover_letter', 'Pismo przewodnie lub kierujące'
        POSITION = 'position', 'Stanowisko lub uwagi zgłoszone w konsultacjach'
        COMMENT_TABLE = 'comment_table', 'Tabela uwag lub odniesienie wnioskodawcy'
        LOBBYING = 'lobbying', 'Zgłoszenie zainteresowania pracami (lobbing)'
        OTHER = 'other', 'Inny dokument'

    project = models.ForeignKey(LegislativeProject, on_delete=models.CASCADE, related_name='documents')
    stage = models.ForeignKey(LegislativeStage, null=True, blank=True, on_delete=models.SET_NULL, related_name='documents')
    rcl_doc_id = models.PositiveBigIntegerField(help_text='Numer z nazwy pliku dokument<id>.<rozszerzenie>.')
    folder_rcl_id = models.PositiveBigIntegerField(null=True, blank=True)
    folder_name = models.CharField(max_length=300, blank=True)
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.OTHER, db_index=True,
                                help_text='Heurystyka po nazwie folderu i dokumentu; nie jest oceną merytoryczną.')
    name = models.CharField(max_length=500)
    file_url = models.URLField(max_length=1024)
    file_ext = models.CharField(max_length=12, blank=True)
    author = models.CharField(max_length=300, blank=True, help_text='"Autor dokumentu" - podmiot zgłaszający lub organ.')
    created_on = models.DateField(null=True, blank=True, db_index=True, help_text='Data utworzenia dokumentu wg RCL.')
    source_page_url = models.URLField(max_length=1024)
    fetched_at = models.DateTimeField(help_text='Data pobrania strony katalogu, z której pochodzi wpis.')
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    removed_at = models.DateTimeField(null=True, blank=True, help_text='Dokument zniknął ze strony katalogu (pozostaje w naszych danych).')
    # Krok opcjonalny i domyślnie wyłączony (RCL_FILES_ENABLED): pobranie samego pliku.
    file_fetched_at = models.DateTimeField(null=True, blank=True)
    file_sha256 = models.CharField(max_length=64, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['project_id', '-created_on', '-rcl_doc_id']
        constraints = [models.UniqueConstraint(fields=['project', 'rcl_doc_id'], name='rcl_document_unique_per_project')]
        indexes = [models.Index(fields=['category', '-created_on'], name='rcl_document_category_date')]

    def __str__(self):
        return self.name[:80]


class LegislativeChange(models.Model):
    """Dziennik zmian (tylko dopisywanie): co, kiedy i z jakiej wartości na jaką."""

    class Kind(models.TextChoices):
        CREATED = 'created', 'Nowy'
        CHANGED = 'changed', 'Zmieniony'
        REMOVED = 'removed', 'Zniknął ze strony'
        REAPPEARED = 'reappeared', 'Pojawił się ponownie'

    project = models.ForeignKey(LegislativeProject, on_delete=models.CASCADE, related_name='changes')
    entity = models.CharField(max_length=12, db_index=True, help_text='project | stage | document')
    entity_key = models.CharField(max_length=40, help_text='rcl_id etapu lub dokumentu; dla projektu jego rcl_id.')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    changes = models.JSONField(default=dict, blank=True, help_text='{pole: [stara, nowa]}; dla nowych: {pole: [null, nowa]}.')
    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    fetched_at = models.DateTimeField()
    source_url = models.URLField(max_length=1024)

    class Meta:
        ordering = ['-detected_at', '-id']
        indexes = [models.Index(fields=['project', 'entity', 'entity_key'], name='rcl_change_entity')]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError('Dziennik zmian RCL jest tylko do dopisywania.')
        super().save(*args, **kwargs)


class RclFetchEvent(models.Model):
    """Zdarzenia pobierania: wstrzymania po 429/503, odrzucenie przez zaporę, zamknięcie okna, błędy parsowania."""

    kind = models.CharField(max_length=32, db_index=True)
    url = models.CharField(max_length=500, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
