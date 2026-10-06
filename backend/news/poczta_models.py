"""Poczta (właściciel 6.10): skrzynki projektów czytane i obsługiwane przez agenta. Minimalne metadane i treść
(treść usuwana po 180 dniach), stan każdej skrzynki (UID, błędy) do kontroli Dyżurnego. Bez sekretów w bazie."""
from django.db import models
from django.utils import timezone

CATEGORIES = [
    ('correction', 'Sprostowanie lub skarga na diagnozę'),
    ('question', 'Pytanie czytelnika'),
    ('press', 'Prasa, dziennikarz'),
    ('partner', 'Partner, zapytanie handlowe (przychodzące)'),
    ('institution', 'Instytucja, pismo urzędowe'),
    ('spam', 'Spam'),
    ('other', 'Inne'),
]
SAFE_CATEGORIES = ('correction', 'question', 'press', 'partner')
STATUSES = [
    ('new', 'Nowa'),
    ('replied', 'Odpowiedziano automatycznie'),
    ('escalated', 'Do właściciela'),
    ('skipped', 'Pominięta'),
    ('failed', 'Błąd wysyłki'),
]


class MailboxState(models.Model):
    """Stan skrzynki: ostatni UID i UIDVALIDITY (idempotentny odczyt), ostatni sukces i błąd (Dyżurny)."""
    mailbox = models.CharField(max_length=40, unique=True)
    uidvalidity = models.CharField(max_length=32, blank=True)
    last_uid = models.PositiveBigIntegerField(default=0)
    last_ok_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    consecutive_errors = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Stan skrzynki Poczty'
        verbose_name_plural = 'Stany skrzynek Poczty'

    def __str__(self):
        return self.mailbox


class MailMessage(models.Model):
    """Jedna wiadomość przychodząca. Treść tylko do klasyfikacji i odpowiedzi; po 180 dniach zostają metadane."""
    mailbox = models.CharField(max_length=40, db_index=True)
    uid = models.PositiveBigIntegerField()
    message_id = models.CharField(max_length=512, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=512, blank=True)
    references = models.TextField(blank=True)
    thread_key = models.CharField(max_length=64, blank=True, db_index=True)
    sender = models.CharField(max_length=320, blank=True)
    sender_address = models.CharField(max_length=254, blank=True, db_index=True)
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    auto_generated = models.BooleanField(default=False, help_text='Auto-Submitted, Precedence bulk/list, mailer-daemon: nigdy nie odpowiadamy.')
    received_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(default=timezone.now, db_index=True)
    category = models.CharField(max_length=16, choices=CATEGORIES, blank=True, db_index=True)
    category_reason = models.CharField(max_length=300, blank=True)
    confidence = models.PositiveSmallIntegerField(default=0, help_text='0-100 z modelu; poniżej progu zawsze do właściciela.')
    model_name = models.CharField(max_length=64, blank=True)
    classify_attempts = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=12, choices=STATUSES, default='new', db_index=True)
    status_reason = models.CharField(max_length=300, blank=True)
    reply_draft = models.TextField(blank=True)
    reply_checks = models.JSONField(default=list, blank=True, help_text='Zarzuty kontroli Recenzenta do szkicu (puste = czysto).')
    reply_sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reply_message_id = models.CharField(max_length=512, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True, db_index=True)
    digest_sent_at = models.DateTimeField(null=True, blank=True)
    body_deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('mailbox', 'uid')]
        ordering = ['-fetched_at', '-pk']
        verbose_name = 'Wiadomość Poczty'
        verbose_name_plural = 'Wiadomości Poczty'

    def __str__(self):
        return f'{self.mailbox}#{self.uid} {self.subject[:40]}'
