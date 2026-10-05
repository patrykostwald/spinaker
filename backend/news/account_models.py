from django.conf import settings
from django.db import models


class SavedTopic(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_topics')
    label = models.CharField(max_length=80)
    query = models.CharField(max_length=200, blank=True, default='')
    categories = models.JSONField(default=list)
    topics = models.JSONField(default=list)
    sources = models.ManyToManyField('news.Source', blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    slot = models.PositiveSmallIntegerField(editable=False)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'slot'], name='unique_topic_owner_slot'),
            models.CheckConstraint(condition=models.Q(slot__gte=0, slot__lt=10), name='topic_slot_max_ten'),
        ]


class ArticleOpinion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_opinions')
    article = models.ForeignKey('news.Article', on_delete=models.CASCADE, related_name='opinions')
    polarity = models.CharField(max_length=8, choices=[('positive', 'Pozytywny'), ('negative', 'Negatywny')])
    body = models.CharField(max_length=240, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'article'], name='one_opinion_per_user_article'),
            models.CheckConstraint(condition=models.Q(polarity__in=['positive', 'negative']), name='opinion_valid_polarity'),
        ]


class ThreadOpinion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='thread_opinions')
    thread = models.ForeignKey('news.Thread', on_delete=models.CASCADE, related_name='opinions')
    polarity = models.CharField(max_length=8, choices=[('positive', 'Pozytywny'), ('negative', 'Negatywny')])
    body = models.CharField(max_length=240, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'thread'], name='one_opinion_per_user_thread'),
            models.CheckConstraint(condition=models.Q(polarity__in=['positive', 'negative']), name='thread_opinion_valid_polarity'),
        ]


class ProfilePreference(models.Model):
    bio = models.CharField(max_length=160, blank=True, default='')
    nick_changed_at = models.DateTimeField(null=True, blank=True)
    hidden_at = models.DateTimeField(null=True, blank=True)
    THEME_CHOICES = [
        ('auto', 'Automatyczny'),
        ('dark', 'Ciemny'),
        ('light', 'Jasny'),
        ('pastel', 'Pastelowy'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_preference')
    public_activity = models.BooleanField(default=False)
    theme_preference = models.CharField(max_length=8, choices=THEME_CHOICES, default='auto')
    # Kolor nicka (właściciel 3.10): tylko dla kont połączonych z X - znak lepiej zweryfikowanego konta; konto z samym e-mailem ma biały.
    # Paleta bez zieleni, żółci i czerwieni, bo te kolory znaczą reakcje ✓ ? ✕.
    # niebieski jest zarezerwowany dla Dr. Spina (właściciel 6.10): czytelnicy wybierają spośród pozostałych
    NICK_COLORS = ['#a78bfa', '#2dd4bf', '#f472b6', '#fb923c', '#e879f9', '#d6d3d1']
    nick_color = models.CharField(max_length=7, blank=True, default='')


class UserXConnection(models.Model):
    """OAuth-proven X identity for login, display name and share controls.

    No access or refresh token is persisted: publication remains in the X
    compose window, under the user's final control.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='x_connection')
    x_user_id = models.CharField(max_length=32, unique=True)
    username = models.CharField(max_length=15)
    use_x_name = models.BooleanField(default=False)
    connected_at = models.DateTimeField(auto_now_add=True)


class ThreadFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='thread_favorites')
    thread = models.ForeignKey('news.Thread', on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['user', 'thread'], name='unique_user_thread_favorite')]


class ArticleFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_favorites')
    article = models.ForeignKey('news.Article', on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['user', 'article'], name='unique_user_article_favorite')]


class PersonalContextThread(models.Model):
    """Nitka kontekstowa czytelnika. Domyślnie prywatna; po publikacji widoczna w /nitki.

    Rozkład diagnozy ma diagnosis zamiast właściciela. Zespół może ukryć każdą nitkę.
    """
    signal_kind = models.CharField(max_length=24, blank=True, default='', choices=[('', 'Pozostałe'), ('lobbying', 'Sygnał lobbingu'), ('new_narrative', 'Nowa narracja')])
    signal_key = models.CharField(max_length=64, null=True, blank=True, unique=True)
    signal_data = models.JSONField(default=dict, blank=True)
    # Izba przyjęć: trop czytelnika trafia na główną listę dopiero po spełnieniu progów (news/admission.py).
    admitted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    continues = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='continuations')
    # przepięcie (właściciel 3.10): te same boksy co w cudzej spince, spięte po swojemu (własne wyjaśnienia i spinki)
    repin_of = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='repins')
    narrative_message = models.OneToOneField('news.ClinicDailyMessage', null=True, blank=True,
        on_delete=models.CASCADE, related_name='narrative_thread')
    narrative_score = models.PositiveIntegerField(default=0)
    diagnosis = models.OneToOneField('news.SpinDiagnosis', null=True, blank=True,
        on_delete=models.CASCADE, related_name='context_thread')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name='personal_context_threads')
    title = models.TextField()
    description = models.CharField(max_length=500, blank=True, default='')
    query = models.CharField(max_length=200, blank=True, default='')
    categories = models.JSONField(default=list)
    topics = models.JSONField(default=list)
    sources = models.ManyToManyField('news.Source', blank=True, related_name='personal_context_threads')
    is_public = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    hidden_at = models.DateTimeField(null=True, blank=True, help_text='Ukrycie przez zespół po zgłoszeniu.')
    hidden_reason = models.CharField(max_length=240, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        constraints = [models.CheckConstraint(
            condition=(models.Q(owner__isnull=False, diagnosis__isnull=True, narrative_message__isnull=True, signal_kind='') |
                       models.Q(owner__isnull=True, diagnosis__isnull=False, narrative_message__isnull=True, signal_kind='') |
                       models.Q(owner__isnull=True, diagnosis__isnull=True, narrative_message__isnull=False, signal_kind='') |
                       models.Q(owner__isnull=True, diagnosis__isnull=True, narrative_message__isnull=True, signal_kind__in=['lobbying', 'new_narrative'], signal_key__isnull=False)),
            name='context_thread_origin_091')]


class PersonalContextThreadItem(models.Model):
    """Dokładnie jeden element: materiał z Bazy, link czytelnika albo fragment diagnozy."""
    thread = models.ForeignKey(PersonalContextThread, on_delete=models.CASCADE, related_name='items')
    article = models.ForeignKey('news.Article', null=True, blank=True, on_delete=models.CASCADE,
                                related_name='personal_context_thread_items')
    link = models.ForeignKey('news.CommunityLink', null=True, blank=True, on_delete=models.CASCADE,
                             related_name='thread_items')
    note = models.TextField(blank=True, default='')
    link_note = models.TextField(blank=True, default='')
    box_data = models.JSONField(null=True, blank=True, help_text='Deterministyczny fragment diagnozy Dr. Spina.')
    # rodzaj boksu i rodzaj spinki do poprzedniego (właściciel 4.10, werdykt Konsylium 2357): pokazywane nad boksem i nad zatrzaskiem
    ROLES = [('', '-'), ('teza', 'Teza'), ('fakt', 'Fakt'), ('kontekst', 'Kontekst'), ('pytanie', 'Pytanie'), ('opinia', 'Opinia'), ('wniosek', 'Wniosek')]
    LINK_KINDS = [('', '-'), ('bo', 'bo'), ('ale', 'ale'), ('czy_na_pewno', 'czy na pewno?'), ('przeczy', 'przeczy'), ('wynika_z', 'wynika z'), ('jak', 'jak?')]
    role = models.CharField(max_length=12, blank=True, default='', choices=ROLES)
    link_kind = models.CharField(max_length=16, blank=True, default='', choices=LINK_KINDS)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['thread', 'article'], name='unique_personal_context_thread_article'),
            models.UniqueConstraint(fields=['thread', 'link'], name='unique_personal_context_thread_link'),
            models.UniqueConstraint(fields=['thread', 'position'], name='unique_personal_context_thread_position'),
            models.CheckConstraint(condition=~models.Q(position=0) | models.Q(link_note=''),
                                   name='personal_thread_first_without_link_note'),
            models.CheckConstraint(condition=(models.Q(article__isnull=False, link__isnull=True, box_data__isnull=True) |
                models.Q(article__isnull=True, link__isnull=False, box_data__isnull=True) |
                models.Q(article__isnull=True, link__isnull=True, box_data__isnull=False)),
                                   name='personal_thread_item_article_xor_link'),
        ]


class CommentReport(models.Model):
    REASONS = [
        ('spam', 'Spam'), ('abuse', 'Naruszenie zasad'), ('privacy', 'Dane prywatne'),
        ('off_topic', 'Poza tematem'), ('other', 'Inne'),
    ]
    STATUSES = [('new', 'Nowe'), ('reviewed', 'Rozpatrzone'), ('hidden', 'Ukryte')]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comment_reports')
    article_opinion = models.ForeignKey(ArticleOpinion, null=True, blank=True, on_delete=models.CASCADE,
        related_name='reports')
    thread_opinion = models.ForeignKey(ThreadOpinion, null=True, blank=True, on_delete=models.CASCADE,
        related_name='reports')
    reason = models.CharField(max_length=16, choices=REASONS)
    details = models.CharField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=16, choices=STATUSES, default='new', db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_comment_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['status', '-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(article_opinion__isnull=False, thread_opinion__isnull=True) |
                           models.Q(article_opinion__isnull=True, thread_opinion__isnull=False)),
                name='comment_report_has_exactly_one_target',
            ),
            models.UniqueConstraint(fields=['reporter', 'article_opinion'], name='unique_reporter_article_comment_report'),
            models.UniqueConstraint(fields=['reporter', 'thread_opinion'], name='unique_reporter_thread_comment_report'),
        ]


class AccountIdentity(models.Model):
    adult_declared_at = models.DateTimeField(null=True, blank=True)
    newsletter_consent_at = models.DateTimeField(null=True, blank=True)
    comments_blocked_until = models.DateTimeField(null=True, blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='account_identity')
    email = models.EmailField(unique=True, null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    accepted_terms_version = models.CharField(max_length=40, default='')
    accepted_privacy_version = models.CharField(max_length=40, default='')
    accepted_at = models.DateTimeField(null=True, blank=True)
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)
    verification_nonce = models.CharField(max_length=64, default='')


class MutedUser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='muted_users')
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'target'], name='unique_muted_user_086'),
            models.CheckConstraint(condition=~models.Q(user=models.F('target')), name='mute_other_user_086'),
        ]
