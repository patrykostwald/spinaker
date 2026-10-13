"""Serializery wejścia i opisy odpowiedzi (schemat OpenAPI przez drf-spectacular), v2."""
from __future__ import annotations

from rest_framework import serializers

from .config import NICK_COLORS
from .models import Report


class SpinkaOut(serializers.Serializer):
    n = serializers.IntegerField(help_text='Liczba ocen przypięcia autora')
    level = serializers.CharField(help_text='P1..P5 albo open (Otwarta)')
    label = serializers.CharField()
    color = serializers.CharField()
    score = serializers.FloatField(allow_null=True)
    reason = serializers.CharField(help_text='ok | open | hold_new_accounts | open_window | step_limited | frozen | silence | calibration | no_pin | target_unavailable')
    pending = serializers.BooleanField()
    distribution = serializers.DictField(child=serializers.IntegerField(), help_text='{agree, disagree}')
    dispute = serializers.BooleanField()
    views = serializers.DictField(child=serializers.BooleanField())
    last_rating_at = serializers.DateTimeField(allow_null=True)
    aria = serializers.CharField()
    formula_version = serializers.CharField()


class AuthorOut(serializers.Serializer):
    nick = serializers.CharField()
    badge = serializers.CharField(help_text="dr_spin | team | author | ''")
    color = serializers.CharField(allow_null=True, help_text='identyfikator z config.nick_colors; spin = Dr. Spin')
    is_team = serializers.BooleanField()
    system = serializers.BooleanField()
    label = serializers.CharField()


class PinSummaryOut(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField(help_text='box | url | image | diagnosis')
    status = serializers.CharField()
    target_status = serializers.CharField()
    author = AuthorOut()
    author_stance = serializers.CharField(allow_null=True)
    target_title = serializers.CharField()
    target_box_id = serializers.IntegerField(allow_null=True)
    comment = serializers.CharField()


class PortalsOut(serializers.Serializer):
    spin_diagnosis_url = serializers.CharField(allow_null=True)
    przeszlosc_url = serializers.CharField(allow_null=True)
    spina3_url = serializers.CharField()


class BoxItemOut(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    subtype = serializers.CharField()
    title = serializers.CharField()
    source = serializers.DictField()
    author = serializers.DictField(allow_null=True, help_text='Autor materiału (polityk, redakcja), nie użytkownik')
    published_at = serializers.DateTimeField(allow_null=True)
    quote = serializers.CharField(help_text='Tylko gdy show_quote')
    thumbnail_url = serializers.CharField(help_text='Tylko gdy show_thumbnail')
    source_status = serializers.CharField()
    status = serializers.CharField()
    reader_link = serializers.BooleanField()
    topic = serializers.CharField()
    persons = serializers.ListField(child=serializers.DictField())
    portals = PortalsOut()
    has_diagnosis = serializers.BooleanField()
    pinnable = serializers.BooleanField()
    has_pin = serializers.BooleanField()
    pin = PinSummaryOut(allow_null=True)
    spinka = SpinkaOut()
    my_rating = serializers.CharField(allow_null=True, help_text='agree | disagree (tylko dla zalogowanego)')
    comment_count = serializers.IntegerField()


class PinOut(serializers.Serializer):
    id = serializers.IntegerField()
    box_id = serializers.IntegerField()
    kind = serializers.CharField()
    system = serializers.BooleanField()
    ratings = serializers.DictField(child=serializers.IntegerField(), help_text='{n, agree, disagree}')
    my_rating = serializers.CharField(allow_null=True)
    ratable = serializers.BooleanField()
    author_stance = serializers.CharField(allow_null=True, help_text='agree | doubt | disagree | null')
    comment = serializers.CharField()
    target = serializers.DictField(allow_null=True)
    target_status = serializers.CharField()
    author = AuthorOut()
    editable = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class BoxDetailOut(BoxItemOut):
    text = serializers.CharField()
    url = serializers.CharField()
    ai_label = serializers.CharField()
    pin = PinOut(allow_null=True)
    can_pin = serializers.BooleanField(help_text='Zalogowany może dodać jedyne przypięcie (box bez przypięcia)')
    can_rate = serializers.BooleanField()
    question = serializers.CharField()
    diagnosis_history = serializers.ListField(child=serializers.DictField())


class WallOut(serializers.Serializer):
    items = BoxItemOut(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    version = serializers.IntegerField(help_text='Wersja migawki rankingu (co 10 minut)')
    snapshot_at = serializers.DateTimeField()
    sort = serializers.CharField(help_text='level | newest | today')
    rated_share = serializers.FloatField()
    period_days = serializers.IntegerField()
    sections = serializers.ListField(child=serializers.DictField())
    wall_end = serializers.BooleanField()
    end_message = serializers.CharField()
    election_silence = serializers.BooleanField()
    today = serializers.ListField(child=serializers.DictField(), required=False)


class BoxSpecIn(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['box', 'url', 'image'], default='box', help_text='Kotwica: box z bazy, adres URL albo zdjęcie')
    target = serializers.CharField(help_text='id boxa (kind=box) albo adres (kind=url)')
    title = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')
    type = serializers.ChoiceField(choices=['article', 'video', 'document', 'post'], required=False, default='article',
                                   help_text='Rodzaj nowego boxa z adresu')


class PinSpecIn(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['box', 'url', 'image'], default='box')
    target = serializers.CharField(help_text='id boxa (kind=box) albo adres (kind=url)')
    comment = serializers.CharField(required=False, allow_blank=True, max_length=280, default='')
    stance = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                   help_text='Stanowisko autora wobec boxa: agree | doubt | disagree (opcjonalne)')


class BoxWithPinIn(serializers.Serializer):
    box = BoxSpecIn()
    pin = PinSpecIn()


class BoxWithPinOut(serializers.Serializer):
    box = BoxItemOut()
    pin = PinOut()
    spinka = SpinkaOut()
    message = serializers.CharField(required=False)
    comment = serializers.CharField(required=False)


class PinPatchIn(serializers.Serializer):
    stance = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=280)
    kind = serializers.ChoiceField(choices=['box', 'url'], required=False)
    target = serializers.CharField(required=False)


class PinPatchOut(serializers.Serializer):
    pin = PinOut()
    spinka = SpinkaOut()
    message = serializers.CharField(required=False)
    comment = serializers.CharField(required=False)


class RatingIn(serializers.Serializer):
    stance = serializers.CharField(help_text='agree | disagree albo 1 | -1')


class RatingOut(serializers.Serializer):
    my_rating = serializers.CharField(allow_null=True)
    changed = serializers.BooleanField()
    spinka = SpinkaOut()
    pin = PinOut()


class CommentIn(serializers.Serializer):
    text = serializers.CharField(max_length=600)
    parent = serializers.IntegerField(required=False, allow_null=True, help_text='id komentarza głównego (jeden poziom odpowiedzi)')


class CommentPatchIn(serializers.Serializer):
    text = serializers.CharField(max_length=600)


class CommentOut(serializers.Serializer):
    id = serializers.IntegerField()
    box_id = serializers.IntegerField()
    parent_id = serializers.IntegerField(allow_null=True)
    text = serializers.CharField()
    status = serializers.CharField(help_text='visible | held | hidden | removed (stany held/hidden tylko dla autora)')
    hidden_reason = serializers.CharField()
    author = AuthorOut()
    helpful_count = serializers.IntegerField()
    my_helpful = serializers.BooleanField()
    reply_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    edited_at = serializers.DateTimeField(allow_null=True)
    editable = serializers.BooleanField()
    replies = serializers.ListField(child=serializers.DictField(), required=False)


class CommentsOut(serializers.Serializer):
    items = CommentOut(many=True)
    sort = serializers.CharField(help_text='newest | top')
    next_cursor = serializers.CharField(allow_null=True)
    total = serializers.IntegerField()


class CommentCreateOut(serializers.Serializer):
    comment = CommentOut()
    comment_status = serializers.CharField()
    message = serializers.CharField(required=False)


class ProfileIn(serializers.Serializer):
    nick_color = serializers.ChoiceField(choices=sorted(NICK_COLORS), help_text='Identyfikator z listy config.nick_colors')


class ProfileOut(serializers.Serializer):
    nick = serializers.CharField()
    nick_color = serializers.CharField()
    badge = serializers.CharField()
    consent_art9 = serializers.BooleanField()
    tier = serializers.CharField()
    limits = serializers.DictField()
    public_profile = serializers.BooleanField()


class ReportIn(serializers.Serializer):
    pin = serializers.IntegerField(required=False)
    box = serializers.IntegerField(required=False)
    comment = serializers.IntegerField(required=False)
    reason = serializers.ChoiceField(choices=[r for r, _ in Report.REASONS])
    details = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')


class DecisionIn(serializers.Serializer):
    decision = serializers.CharField()
    reason = serializers.CharField(max_length=600)
    sanction = serializers.ChoiceField(choices=['', 'weight_zero_30d', 'suspend_30d'], required=False, default='')


class UrlDecisionIn(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['accept', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=240, default='')
    title = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')
    kind = serializers.ChoiceField(choices=['article', 'video', 'document'], required=False, default='article')


class AppealIn(serializers.Serializer):
    text = serializers.CharField(max_length=1000)


class ConsentIn(serializers.Serializer):
    accepted = serializers.BooleanField()


class CodeIn(serializers.Serializer):
    code = serializers.CharField()


class SearchOut(serializers.Serializer):
    items = BoxItemOut(many=True)
    suggestions = serializers.ListField(child=serializers.CharField())
    query = serializers.CharField()
    normalized = serializers.CharField(required=False)
