"""Private research records. Deliberately not related to Article or public feeds."""
from django.db import models
from django.utils import timezone


class PublicRecord(models.Model):
    source = models.CharField(max_length=32, db_index=True)
    kind = models.CharField(max_length=32, db_index=True)
    external_id = models.CharField(max_length=256)
    source_url = models.URLField(max_length=2048)
    fetched_at = models.DateTimeField(default=timezone.now)
    response_sha256 = models.CharField(max_length=64)
    # The URL whose bytes were hashed (a listing can describe a linked PDF).
    response_url = models.URLField(max_length=2048)
    fetch_attempt = models.ForeignKey('news.FetchAttempt', null=True, blank=True,
                                     on_delete=models.SET_NULL)
    term = models.PositiveSmallIntegerField(null=True, blank=True)
    date = models.DateField(null=True, blank=True, db_index=True)
    title = models.TextField(blank=True)
    text = models.TextField(blank=True)
    data = models.JSONField(default=dict)
    print_number = models.CharField(max_length=32, blank=True, db_index=True)
    official_print = models.ForeignKey('news.OfficialRecord', null=True, blank=True,
                                      on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'kind', 'external_id'],
                                               name='public_record_identity_090')]
        ordering = ['-fetched_at', '-pk']

    def __str__(self):
        return f'{self.source}/{self.kind}/{self.external_id}'


class PublicRecordPerson(models.Model):
    """Sejm IDs are scoped to a term. Unresolved IDs remain useful evidence."""
    record = models.ForeignKey(PublicRecord, on_delete=models.CASCADE, related_name='people')
    term = models.PositiveSmallIntegerField()
    mp_id = models.PositiveIntegerField()
    figure = models.ForeignKey('news.PublicFigure', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='private_public_records')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['record', 'term', 'mp_id'],
                                               name='public_record_person_090')]


class PublicCollectionState(models.Model):
    source = models.CharField(max_length=32, unique=True)
    since = models.DateField(null=True, blank=True)
    cycle_started_at = models.DateTimeField(null=True, blank=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_complete_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=32, default='idle')
    record_count = models.PositiveBigIntegerField(default=0)
    budget_day = models.DateField(null=True, blank=True)
    requests_today = models.PositiveIntegerField(default=0)
    next_request_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.CharField(max_length=36, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.source


class PublicCollectionJob(models.Model):
    """Durable bounded frontier: commit children and parent together, retry errors."""
    state = models.ForeignKey(PublicCollectionState, on_delete=models.CASCADE, related_name='jobs')
    identity = models.CharField(max_length=64)
    url = models.URLField(max_length=2048)
    kind = models.CharField(max_length=32)
    context = models.JSONField(default=dict)
    done = models.BooleanField(default=False)
    last_error = models.CharField(max_length=120, blank=True)
    failures = models.PositiveIntegerField(default=0)
    retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['state', 'identity'],
                                               name='public_collection_job_090')]
        indexes = [models.Index(fields=['state', 'done', 'id'], name='public_job_pending_090')]
