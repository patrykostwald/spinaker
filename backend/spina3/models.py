"""Model danych spina3 v2 (osobna aplikacja; żadnych zmian w tabelach `news`).

Model produktu (właściciel 11.10, v2): autor boxa wstawia box (URL, zdjęcie albo box z bazy) i robi do niego DOKŁADNIE JEDNO
przypięcie (`Pin`, unikalne per box: URL, zdjęcie albo box z bazy, z komentarzem). Inni użytkownicy nie przypinają: oceniają
przypięcie autora (`Rating`: zgadzam się / nie zgadzam się, jedna ocena na użytkownika, zmiana i wycofanie dozwolone) oraz
komentują pod parą box + przypięcie (`Comment`, jeden poziom odpowiedzi, ocena "przydatny" = `CommentVote`).
Wzorzec treści: Dr. Spin publikuje BOX 1 = wpis polityka, BOX PRZYPIĘTY = diagnoza (`Pin.kind='diagnosis'`); użytkownicy oceniają
diagnozę, z ocen powstaje ranking. Dziennik zdarzeń jest pseudonimowy. Stan oczekiwania dotyczy CELU przypięcia (`target_status`).
"""
from __future__ import annotations

import secrets

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

BOX_KINDS = [
    ('post', 'Wpis'), ('interview', 'Wywiad'), ('article', 'Artykuł'), ('video', 'Film'), ('document', 'Dokument'),
    ('voting', 'Głosowanie'), ('legal_act', 'Akt prawny'), ('diagnosis', 'Diagnoza'),
    ('person', 'Osoba'), ('entity', 'Podmiot'), ('image', 'Zdjęcie'),
]
ADDED_BY = [('dr_spin', 'Dr. Spin'), ('importer', 'Importer'), ('user', 'Użytkownik'), ('team', 'Zespół spina3')]
SOURCE_STATUSES = [('active', 'Aktywny'), ('removed_at_source', 'Usunięty u źródła'), ('withdrawn', 'Wycofany')]
BOX_STATUSES = [('published', 'Opublikowany'), ('pending', 'Czeka na sprawdzenie'), ('hidden', 'Ukryty'),
                ('held', 'Wstrzymany (cisza wyborcza)')]
PIN_KINDS = [('box', 'Box z bazy'), ('url', 'Adres URL'), ('image', 'Zdjęcie (wyłączone)'), ('diagnosis', 'Diagnoza AI')]
PIN_STATUSES = [('published', 'Opublikowane'), ('hidden', 'Ukryte'), ('removed', 'Usunięte'), ('held', 'Wstrzymane')]
TARGET_STATUSES = [('ok', 'Dostępna'), ('pending', 'Oczekuje na weryfikację'), ('rejected', 'Odrzucona'),
                   ('unavailable', 'Materiał niedostępny')]
COMMENT_STATUSES = [('ok', 'Widoczny'), ('held', 'Czeka na sprawdzenie'), ('hidden', 'Ukryty'), ('empty', 'Brak')]
RATING_STATUSES = [('active', 'Aktywna'), ('withdrawn', 'Wycofana')]
THREAD_STATUSES = [('visible', 'Widoczny'), ('held', 'Czeka na sprawdzenie'), ('hidden', 'Ukryty'), ('removed', 'Usunięty')]
EVENT_KINDS = [('created', 'Utworzenie'), ('stance_changed', 'Zmiana stanowiska'), ('edited', 'Edycja'),
               ('removed', 'Usunięcie'), ('hidden', 'Ukrycie'), ('restored', 'Przywrócenie'), ('reported', 'Zgłoszenie'),
               ('target_unavailable', 'Rzecz niedostępna'), ('replaced', 'Wymiana rzeczy'), ('system', 'Systemowe'),
               ('rated', 'Ocena'), ('rating_changed', 'Zmiana oceny'), ('unrated', 'Wycofanie oceny'),
               ('commented', 'Komentarz'), ('comment_removed', 'Usunięcie komentarza')]


class Box(models.Model):
    kind = models.CharField(max_length=16, choices=BOX_KINDS, db_index=True)
    subtype = models.CharField(max_length=32, blank=True, default='', help_text='Podtyp dokumentu albo kategoria źródła.')
    article = models.ForeignKey('news.Article', null=True, blank=True, on_delete=models.SET_NULL, related_name='spina3_boxes')
    post = models.ForeignKey('news.PoliticalPost', null=True, blank=True, on_delete=models.SET_NULL, related_name='spina3_boxes')
    diagnosis = models.ForeignKey('news.SpinDiagnosis', null=True, blank=True, on_delete=models.SET_NULL, related_name='spina3_boxes')
    public_figure = models.ForeignKey('news.PublicFigure', null=True, blank=True, on_delete=models.SET_NULL, related_name='spina3_boxes')
    added_by = models.CharField(max_length=12, choices=ADDED_BY, default='importer')
    added_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1024, unique=True, help_text='Adres kanoniczny po normalizacji.')
    source_name = models.CharField(max_length=255, blank=True, default='')
    source_domain = models.CharField(max_length=255, blank=True, default='', db_index=True)
    author_name = models.CharField(max_length=200, blank=True, default='')
    author_handle = models.CharField(max_length=64, blank=True, default='')
    author_group = models.CharField(max_length=120, blank=True, default='',
                                    help_text='Publiczny atrybut polityka (partia) do limitu udziału; nigdy dane użytkownika.')
    text = models.TextField(blank=True, default='', help_text='Pełna treść tylko tam, gdzie wolno (wpis z API, dokument urzędowy).')
    quote = models.CharField(max_length=600, blank=True, default='')
    thumbnail_url = models.URLField(max_length=1024, blank=True, default='')
    show_title = models.BooleanField(default=True)
    show_quote = models.BooleanField(default=False)
    show_thumbnail = models.BooleanField(default=False)
    show_avatar = models.BooleanField(default=False)
    published_at = models.DateTimeField(db_index=True, default=timezone.now)
    topic = models.CharField(max_length=120, blank=True, default='', db_index=True)
    persons = models.JSONField(default=list, blank=True, help_text='[{"id": 1, "name": "..."}] osoby i podmioty (publiczne).')
    portals = models.JSONField(default=dict, blank=True, help_text='{spin_diagnosis_url, przeszlosc_url, spina3_url}')
    source_status = models.CharField(max_length=20, choices=SOURCE_STATUSES, default='active', db_index=True)
    status = models.CharField(max_length=12, choices=BOX_STATUSES, default='published', db_index=True)
    reader_link = models.BooleanField(default=False, help_text='Dodane z linku czytelnika (nasza publikacja, oznaczona).')
    noindex = models.BooleanField(default=False)
    pinnable_as_target = models.BooleanField(default=True)
    public_function = models.BooleanField(default=True, help_text='Osoba lub podmiot pełniący funkcję publiczną (cel przypięcia).')
    search_text = models.TextField(blank=True, default='', help_text='Tytuł, autor, cytat bez polskich znaków, małe litery.')
    held_until = models.DateTimeField(null=True, blank=True, help_text='Cisza wyborcza: publikacja po tej dacie.')
    hidden_reason = models.CharField(max_length=240, blank=True, default='')
    source_checked_at = models.DateTimeField(null=True, blank=True, db_index=True,
                                             help_text='Ostatnie sprawdzenie, czy wpis istnieje u źródła (oEmbed X).')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-pk']
        indexes = [models.Index(fields=['status', 'published_at']), models.Index(fields=['kind', 'status'])]
        constraints = [
            models.CheckConstraint(
                name='spina3_box_single_origin',
                condition=(
                    Q(article__isnull=True, post__isnull=True, diagnosis__isnull=True)
                    | Q(article__isnull=False, post__isnull=True, diagnosis__isnull=True)
                    | Q(article__isnull=True, post__isnull=False, diagnosis__isnull=True)
                    | Q(article__isnull=True, post__isnull=True, diagnosis__isnull=False)
                ),
            ),
        ]

    def __str__(self):
        return f'[{self.kind}] {self.title[:60]}'

    @property
    def is_visible(self) -> bool:
        return self.status == 'published'

    @property
    def is_frozen(self) -> bool:
        return self.source_status != 'active'

    @property
    def author_initials(self) -> str:
        parts = [p for p in (self.author_name or '').replace('-', ' ').split() if p]
        return ''.join(p[0].upper() for p in parts[:2])

    @property
    def active_pin(self):
        """Jedyne przypięcie boxa (opublikowane, ukryte albo wstrzymane; usunięte zwalnia miejsce)."""
        return self.pins.exclude(status='removed').first()


class BoxLink(models.Model):
    """Relacja box-box utrzymywana przez system: diagnoza AI przypięta do wpisu (jedna aktualna, historia wersji)."""
    KINDS = [('diagnosis_of', 'Diagnoza wpisu'), ('evidence_of', 'Dokument źródłowy'), ('bridge', 'Most')]
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='links')
    target = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='linked_from')
    kind = models.CharField(max_length=16, choices=KINDS, db_index=True)
    version = models.PositiveIntegerField(default=1)
    is_current = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['box', 'kind'], condition=Q(is_current=True), name='spina3_boxlink_one_current'),
            models.UniqueConstraint(fields=['box', 'target', 'kind', 'version'], name='spina3_boxlink_version'),
            models.CheckConstraint(condition=~Q(box=F('target')), name='spina3_boxlink_not_self'),
        ]


class Spina3Profile(models.Model):
    """Stan konta w spina3: pseudonim dziennika, zespół, poziom ręczny, sankcje, zgoda art. 9, klaster, kolor nicku."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spina3_profile')
    pseudonym = models.CharField(max_length=32, unique=True, default='', editable=False)
    is_team = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False, help_text='Dr. Spin: nigdy nie głosuje.')
    tier_manual = models.CharField(max_length=2, blank=True, default='', help_text="'T3' nadany przez zespół.")
    weight_zero_until = models.DateTimeField(null=True, blank=True)
    suspended_until = models.DateTimeField(null=True, blank=True)
    consent_art9_at = models.DateTimeField(null=True, blank=True)
    cluster_id = models.CharField(max_length=32, blank=True, default='', db_index=True)
    cluster_size = models.PositiveIntegerField(default=1)
    hidden_count = models.PositiveIntegerField(default=0, help_text='Przypięcia i komentarze ukryte przez moderację.')
    nick_color = models.CharField(max_length=16, blank=True, default='',
                                  help_text='Identyfikator z listy config.NICK_COLORS; "spin" zarezerwowany dla Dr. Spina.')
    age_16_plus_at = models.DateTimeField(null=True, blank=True,
                                          help_text='Oświadczenie "mam ukończone 16 lat" złożone przy zgodzie (bez daty urodzenia).')
    deletion_requested_at = models.DateTimeField(null=True, blank=True, db_index=True,
                                                 help_text='DELETE me/: dane spina3 do usunięcia; nick od razu anonimowy.')
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def deleted(self) -> bool:
        return self.deletion_requested_at is not None

    def save(self, *args, **kwargs):
        if not self.pseudonym:
            self.pseudonym = secrets.token_hex(16)
        return super().save(*args, **kwargs)

    @classmethod
    def for_user(cls, user) -> 'Spina3Profile':
        profile, _ = cls.objects.get_or_create(user=user)
        return profile

    @property
    def badge(self) -> str:
        if self.is_system:
            return 'dr_spin'
        if self.is_team:
            return 'team'
        return ''


class UrlCheck(models.Model):
    """Kolejka weryfikacji adresów spoza bazy (etap F). Bez sieci, dopóki flaga url_fetch_enabled jest wyłączona."""
    STATUSES = [('queued', 'W kolejce'), ('checking', 'Sprawdzanie'), ('needs_review', 'Do decyzji człowieka'),
                ('accepted', 'Zaakceptowany'), ('rejected', 'Odrzucony'), ('duplicate', 'Już w bazie')]
    url_input = models.URLField(max_length=2048)
    url_normalized = models.URLField(max_length=1024, unique=True)
    domain = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=16, choices=STATUSES, default='queued', db_index=True)
    reason = models.CharField(max_length=240, blank=True, default='')
    checks = models.JSONField(default=dict, blank=True, help_text='Wyniki kontroli automatycznych.')
    fetched = models.JSONField(default=dict, blank=True, help_text='Tytuł, canonical, typ treści (tylko metadane).')
    attempts = models.PositiveSmallIntegerField(default=0)
    box = models.ForeignKey(Box, null=True, blank=True, on_delete=models.SET_NULL, related_name='url_checks')
    submitted_by = models.CharField(max_length=32, blank=True, default='', help_text='Pseudonim zgłaszającego.')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    next_recheck_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']


class Pin(models.Model):
    """Jedyne przypięcie boxa (autor = user; Dr. Spin dla diagnoz). Oceniane przez innych użytkowników (`Rating`)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='spina3_pins')
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='pins')
    kind = models.CharField(max_length=10, choices=PIN_KINDS, default='box')
    pinned_box = models.ForeignKey(Box, null=True, blank=True, on_delete=models.SET_NULL, related_name='pinned_by')
    url = models.URLField(max_length=1024, blank=True, default='')
    url_check = models.ForeignKey(UrlCheck, null=True, blank=True, on_delete=models.SET_NULL, related_name='pins')
    stance = models.SmallIntegerField(null=True, blank=True,
                                      help_text='Stanowisko autora wobec treści boxa (+1 / 0 / -1), opcjonalne; nie liczy się do S.')
    title = models.CharField(max_length=80, blank=True, default='', validators=[MinLengthValidator(15)])
    subtitle = models.CharField(max_length=160, blank=True, default='')
    comment = models.CharField(max_length=280, blank=True, default='')
    comment_status = models.CharField(max_length=8, choices=COMMENT_STATUSES, default='empty')
    status = models.CharField(max_length=10, choices=PIN_STATUSES, default='published', db_index=True)
    target_status = models.CharField(max_length=12, choices=TARGET_STATUSES, default='ok', db_index=True)
    unavailable_since = models.DateTimeField(null=True, blank=True)
    replace_deadline = models.DateTimeField(null=True, blank=True)
    is_team = models.BooleanField(default=False)
    anonymized = models.BooleanField(default=False)
    # przypięcie systemowe 'diagnosis'
    diagnosis = models.ForeignKey('news.SpinDiagnosis', null=True, blank=True, on_delete=models.SET_NULL, related_name='spina3_pins')
    diagnosis_title = models.CharField(max_length=200, blank=True, default='')
    diagnosis_url = models.URLField(max_length=512, blank=True, default='')
    technique = models.CharField(max_length=160, blank=True, default='')
    approved_at = models.DateTimeField(null=True, blank=True, help_text='Zatwierdzenie diagnozy przez człowieka (klinika).')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    hidden_reason = models.CharField(max_length=240, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    stance_changed_at = models.DateTimeField(null=True, blank=True)
    held_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['box'], condition=~Q(status='removed'), name='spina3_pin_one_per_box'),
            models.CheckConstraint(condition=Q(pinned_box__isnull=True) | ~Q(pinned_box=F('box')), name='spina3_pin_not_self'),
            models.CheckConstraint(condition=Q(stance__isnull=True) | Q(stance__gte=-1, stance__lte=1), name='spina3_pin_stance_rule'),
            models.CheckConstraint(condition=~Q(kind='box') | Q(pinned_box__isnull=False), name='spina3_pin_box_needs_target'),
            models.CheckConstraint(condition=~Q(kind='url') | ~Q(url=''), name='spina3_pin_url_needs_url'),
        ]

    def __str__(self):
        return f'pin#{self.pk} box={self.box_id} kind={self.kind}'

    @property
    def is_system(self) -> bool:
        return self.kind == 'diagnosis'

    @property
    def ratable(self) -> bool:
        """Oceny liczą się tylko przy opublikowanym przypięciu z dostępnym dowodem."""
        return self.status == 'published' and self.target_status == 'ok'


class Rating(models.Model):
    """Ocena przypięcia autora przez innego użytkownika: +1 zgadzam się, -1 nie zgadzam się. Jedna na użytkownika i przypięcie."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='spina3_ratings')
    pin = models.ForeignKey(Pin, on_delete=models.CASCADE, related_name='ratings')
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='ratings', help_text='= pin.box (do zapytań).')
    stance = models.SmallIntegerField(help_text='+1 zgadzam się, -1 nie zgadzam się.')
    status = models.CharField(max_length=10, choices=RATING_STATUSES, default='active', db_index=True)
    is_team = models.BooleanField(default=False)
    account_weight = models.FloatField(default=1.0, help_text='Waga konta w chwili ostatniego przeliczenia (zostaje po usunięciu konta).')
    anonymized = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    stance_changed_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['user', 'pin'], condition=Q(user__isnull=False), name='spina3_rating_one_per_user_pin'),
            models.CheckConstraint(condition=Q(stance__in=(-1, 1)), name='spina3_rating_two_states'),
        ]

    @property
    def counts(self) -> bool:
        return self.status == 'active' and self.stance in (-1, 1)


class Comment(models.Model):
    """Komentarz pod parą box + przypięcie; jeden poziom odpowiedzi (parent tylko do komentarza głównego)."""
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='spina3_comments')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    text = models.CharField(max_length=600)
    status = models.CharField(max_length=8, choices=THREAD_STATUSES, default='visible', db_index=True)
    hidden_reason = models.CharField(max_length=240, blank=True, default='')
    helpful_count = models.PositiveIntegerField(default=0)
    reply_count = models.PositiveIntegerField(default=0)
    is_team = models.BooleanField(default=False)
    is_author = models.BooleanField(default=False, help_text='Autor przypięcia tego boxa (znaczek "autor").')
    anonymized = models.BooleanField(default=False)
    needs_review = models.BooleanField(default=False, db_index=True,
                                       help_text='Odpięty od nicku po wycofaniu zgody art. 9: do przeglądu (treść nie jest kasowana automatycznie).')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['box', 'status', 'created_at']), models.Index(fields=['box', 'status', 'helpful_count'])]

    def __str__(self):
        return f'comment#{self.pk} box={self.box_id}'


class CommentVote(models.Model):
    """Ocena komentarza "przydatny" (jedna na użytkownika i komentarz, wycofanie = usunięcie wiersza)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spina3_comment_votes')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='votes')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'comment'], name='spina3_comment_vote_once')]


class BoxSpinka(models.Model):
    """Zmaterializowana ocena boxa z OCEN przypięcia autora (przeliczana transakcyjnie po każdej zmianie)."""
    box = models.OneToOneField(Box, on_delete=models.CASCADE, related_name='spinka')
    n = models.PositiveIntegerField(default=0)
    weighted_n = models.FloatField(default=0.0)
    weighted_sum = models.FloatField(default=0.0)
    score = models.FloatField(default=0.0)
    level = models.CharField(max_length=4, default='open', db_index=True)
    level_raw = models.CharField(max_length=4, blank=True, default='')
    level_reason = models.CharField(max_length=24, default='open')
    level_pending = models.BooleanField(default=False)
    level_changed_at = models.DateTimeField(null=True, blank=True)
    first_rating_at = models.DateTimeField(null=True, blank=True)
    last_rating_at = models.DateTimeField(null=True, blank=True, db_index=True)
    distribution = models.JSONField(default=dict, blank=True)
    views = models.JSONField(default=dict, blank=True)
    frozen = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def color(self) -> str:
        from .config import COLORS
        return COLORS.get(self.level, COLORS['open'])


class PinEvent(models.Model):
    """Dziennik zdarzeń append-only, pseudonimowy (bez klucza do użytkownika)."""
    kind = models.CharField(max_length=20, choices=EVENT_KINDS, db_index=True)
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='events')
    pin_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    actor = models.CharField(max_length=32, blank=True, default='', db_index=True, help_text='Pseudonim konta.')
    stance_before = models.SmallIntegerField(null=True, blank=True)
    stance_after = models.SmallIntegerField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['created_at', 'pk']


class Report(models.Model):
    REASONS = [('private_data', 'Dane osoby prywatnej'), ('threat', 'Groźba lub obraza'), ('illegal', 'Treść nielegalna'),
               ('copyright', 'Prawa autorskie'), ('spam', 'Spam'), ('subject', 'Osoba, której dotyczy wpis'), ('other', 'Inne')]
    URGENT = ('private_data', 'threat', 'subject')
    STATUSES = [('new', 'Nowe'), ('hidden', 'Treść ukryta'), ('dismissed', 'Odrzucone')]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spina3_reports')
    pin = models.ForeignKey(Pin, null=True, blank=True, on_delete=models.CASCADE, related_name='reports')
    box = models.ForeignKey(Box, null=True, blank=True, on_delete=models.CASCADE, related_name='reports')
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=16, choices=REASONS)
    details = models.CharField(max_length=500, blank=True, default='')
    name = models.CharField(max_length=200, default='')
    email = models.EmailField(default='')
    good_faith = models.BooleanField(default=False)
    location = models.URLField(max_length=2048, blank=True, default='')
    explanation = models.TextField(max_length=2000, blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUSES, default='new', db_index=True)
    sla_deadline = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=600, blank=True, default='', help_text='Uzasadnienie decyzji (DSA art. 17).')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['status', 'sla_deadline', '-created_at']
        constraints = [
            models.CheckConstraint(condition=Q(pin__isnull=False, box__isnull=True, comment__isnull=True)
                                   | Q(pin__isnull=True, box__isnull=False, comment__isnull=True)
                                   | Q(pin__isnull=True, box__isnull=True, comment__isnull=False),
                                   name='spina3_report_one_target'),
            models.UniqueConstraint(fields=['reporter', 'pin'], condition=Q(pin__isnull=False), name='spina3_report_unique_pin'),
            models.UniqueConstraint(fields=['reporter', 'box'], condition=Q(box__isnull=False), name='spina3_report_unique_box'),
            models.UniqueConstraint(fields=['reporter', 'comment'], condition=Q(comment__isnull=False), name='spina3_report_unique_comment'),
        ]

    @property
    def target_box(self) -> Box:
        if self.box_id:
            return self.box
        return self.pin.box if self.pin_id else self.comment.box


class ModerationDecision(models.Model):
    """Uzasadnienie decyzji ograniczającej treść albo konto (DSA art. 17): co, jak, fakty, podstawa, automat, kto, odwołanie.

    Tworzone przez każdą akcję moderacji (spina3.moderation, spina3.comments.hide_comment, odrzucenie adresu). Autor widzi
    tylko własne decyzje (GET me/decisions/) i dostaje treść e-mailem. Retencja: 12 miesięcy (spina3_retention).
    """
    TARGETS = [('pin', 'Przypięcie'), ('box', 'Box'), ('comment', 'Komentarz'), ('account', 'Konto')]
    RESTRICTIONS = [('hide', 'Ukrycie'), ('remove', 'Usunięcie'), ('demote', 'Obniżenie wagi'), ('suspend', 'Zawieszenie')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='spina3_decisions',
                             help_text='Konto, którego dotyczy decyzja (autor treści).')
    target_type = models.CharField(max_length=8, choices=TARGETS)
    pin = models.ForeignKey(Pin, null=True, blank=True, on_delete=models.SET_NULL, related_name='decisions')
    box = models.ForeignKey(Box, null=True, blank=True, on_delete=models.SET_NULL, related_name='decisions')
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.SET_NULL, related_name='decisions')
    report = models.ForeignKey('Report', null=True, blank=True, on_delete=models.SET_NULL, related_name='decisions')
    restriction = models.CharField(max_length=8, choices=RESTRICTIONS)
    facts = models.TextField(help_text='Fakty i okoliczności, na których oparto decyzję.')
    basis = models.CharField(max_length=48, help_text='Klucz podstawy z spina3.legal.BASES (punkt Regulaminu albo przepis).')
    basis_text = models.TextField(blank=True, default='', help_text='Treść podstawy w chwili decyzji.')
    automated = models.BooleanField(default=False, help_text='Czy przy wykryciu lub decyzji użyto środków zautomatyzowanych.')
    until = models.DateTimeField(null=True, blank=True, help_text='Koniec ograniczenia czasowego (waga 0, zawieszenie).')
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    appeal_route = models.TextField(blank=True, default='')
    appeal_deadline = models.DateTimeField()
    email_sent_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True, help_text='Decyzja uchylona (uwzględnione odwołanie albo przywrócenie).')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class Appeal(models.Model):
    """Jedna apelacja na decyzję: od ukrycia przypięcia albo komentarza (pin/{id}/appeal/, comment/{id}/appeal/) albo od decyzji
    z dziennika (me/decisions/{id}/appeal/, także zawieszenie konta). 6 miesięcy na złożenie (DSA art. 20)."""
    STATUSES = [('open', 'Otwarta'), ('accepted', 'Uwzględniona'), ('rejected', 'Odrzucona')]
    pin = models.ForeignKey(Pin, null=True, blank=True, on_delete=models.CASCADE, related_name='appeals')
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE, related_name='appeals')
    decision = models.OneToOneField(ModerationDecision, null=True, blank=True, on_delete=models.CASCADE, related_name='appeal')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spina3_appeals')
    text = models.CharField(max_length=1000)
    status = models.CharField(max_length=10, choices=STATUSES, default='open', db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decision_reason = models.CharField(max_length=600, blank=True, default='')

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(pin__isnull=False, comment__isnull=True) | Q(pin__isnull=True, comment__isnull=False)
                                   | Q(pin__isnull=True, comment__isnull=True, decision__isnull=False),
                                   name='spina3_appeal_one_target'),
            models.UniqueConstraint(fields=['pin', 'author'], condition=Q(pin__isnull=False), name='spina3_one_appeal_per_decision'),
            models.UniqueConstraint(fields=['comment', 'author'], condition=Q(comment__isnull=False), name='spina3_one_appeal_per_comment'),
        ]


class RankingSnapshot(models.Model):
    """Migawka rankingu (co 10 minut): niezmienna lista wpisów; wersja w kursorze. Klient trzyma wersję do odświeżenia."""
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    mode = models.CharField(max_length=12, default='zgodnosc')
    period_days = models.PositiveIntegerField(default=90)
    formula_version = models.CharField(max_length=8, default='2.0')
    box_count = models.PositiveIntegerField(default=0)
    rated_share = models.FloatField(default=0.0)
    entries = models.JSONField(default=list, blank=True, help_text='[{id, level, lp (ostatnia zaufana ocena), n, pub, ...}, ...]')

    class Meta:
        ordering = ['-pk']

    @property
    def version(self) -> int:
        return self.pk


class BoxDailyCounter(models.Model):
    """Licznik otwarć boxa na dobę (bez IP, bez sesji): metryka 4.1."""
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='daily_counters')
    day = models.DateField()
    views = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['box', 'day'], name='spina3_box_day_counter')]


class HeldPublication(models.Model):
    """Kolejka publikacji systemowych wstrzymanych na czas ciszy wyborczej (boxy, przypięcia); zwalniana po jej końcu."""
    KINDS = [('box', 'Box'), ('pin', 'Przypięcie')]
    kind = models.CharField(max_length=4, choices=KINDS)
    object_id = models.BigIntegerField()
    release_at = models.DateTimeField(db_index=True)
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['kind', 'object_id'], name='spina3_held_once')]


class Chain(models.Model):
    """Zarezerwowane (CHAINS_ENABLED=false): kolekcja bez stanowisk, jeden autor."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spina3_chains')
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=600, blank=True, default='')
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)


class ChainItem(models.Model):
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE, related_name='items')
    pin = models.ForeignKey(Pin, on_delete=models.CASCADE, related_name='chain_items')
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position']
        constraints = [models.UniqueConstraint(fields=['chain', 'pin'], name='spina3_chain_pin_once')]


class Correction(models.Model):
    """Sprostowanie diagnozy (prawo prasowe art. 31a-33): składa osoba, której dotyczy wpis, do 21 dni od publikacji.

    Odmowa tylko z powodem z art. 33 (`rejection_reason`); termin publikacji: 3 dni robocze (`due_at`, spina3.legal).
    Imię i nazwisko publicznie wyłącznie za jawną zgodą (`consent_public_name`). E-mail nigdy publicznie.
    """
    STATUSES = [('pending', 'Czeka na decyzję'), ('published', 'Opublikowane'), ('rejected', 'Odmowa')]
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='corrections', help_text='Box kind=diagnosis.')
    name = models.CharField(max_length=200)
    email = models.EmailField(max_length=254)
    text = models.TextField()
    statement = models.BooleanField(default=False, help_text='Oświadczenie: jestem osobą, której dotyczy wpis; dane są prawdziwe.')
    consent_public_name = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUSES, default='pending', db_index=True)
    rejection_reason = models.CharField(max_length=32, blank=True, default='')
    rejection_note = models.CharField(max_length=600, blank=True, default='')
    due_at = models.DateTimeField(db_index=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['status', 'due_at', 'pk']
        constraints = [
            models.CheckConstraint(condition=~Q(status='rejected') | ~Q(rejection_reason=''), name='spina3_correction_rejection_reason'),
        ]


class DiagnosisApproval(models.Model):
    """Log zatwierdzeń diagnozy (wersje): kto zatwierdził (numer konta zespołu), kiedy, model, źródła, etykieta."""
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='diagnosis_approvals', help_text='Box wpisu (kind=post).')
    diagnosis_box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name='approvals', help_text='Box diagnozy.')
    version = models.PositiveIntegerField(default=1)
    change = models.CharField(max_length=12, default='created', help_text='created | updated | withdrawn | restored')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    approved_by_account = models.PositiveIntegerField(null=True, blank=True, help_text='Numer konta zespołu (publicznie zamiast imienia).')
    approved_at = models.DateTimeField(null=True, blank=True)
    model = models.CharField(max_length=100, blank=True, default='')
    sources = models.JSONField(default=list, blank=True)
    label = models.CharField(max_length=120, default='Diagnoza AI, zatwierdzona przez zespół spin.clinic')
    signature = models.CharField(max_length=64, blank=True, default='', help_text='Skrót treści wersji (wykrywanie zmian).')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['diagnosis_box_id', 'version']
        constraints = [models.UniqueConstraint(fields=['diagnosis_box', 'version'], name='spina3_diagnosis_approval_version')]


class SilencedAccount(models.Model):
    """Cisza wyborcza dla kandydatów i komitetów: w oknie [starts_at, ends_at) boxy konta bez rozkładu i poziomu, nowe oceny,
    komentarze i przypięcia przy nich: 423 election_silence. Lista z importu CSV (spina3_silence_import) po przeglądzie radcy."""
    KINDS = [('candidate', 'Kandydat'), ('committee', 'Komitet wyborczy')]
    handle = models.CharField(max_length=64, db_index=True, help_text='Uchwyt konta źródłowego (bez @, małe litery).')
    kind = models.CharField(max_length=10, choices=KINDS)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    source = models.CharField(max_length=300, help_text='Źródło listy (np. obwieszczenie PKW z datą).')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['handle', 'starts_at']
        constraints = [
            models.UniqueConstraint(fields=['handle', 'starts_at', 'ends_at'], name='spina3_silenced_once'),
            models.CheckConstraint(condition=Q(ends_at__gt=F('starts_at')), name='spina3_silenced_window'),
        ]
