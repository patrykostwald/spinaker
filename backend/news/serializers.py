from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from news.models import Article, Source, Thread, ThreadItem, Ballot
from news.editorial_roles import role_data
from news.source_groups import portal_group


def thread_author(thread, context):
    if not thread.created_by_id:
        return {'name': 'Redakcja', 'role': 'editor'}
    authors = context.setdefault('_thread_authors', {})
    if thread.created_by_id not in authors:
        authors[thread.created_by_id] = {'name': thread.created_by.get_username(),
                                       'role': role_data(thread.created_by)['role']}
    return authors[thread.created_by_id]

class BallotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ballot
        fields = ('mp_id', 'name', 'club', 'vote', 'list_votes')

class VotingSummarySerializer(serializers.Serializer):
    term = serializers.IntegerField()
    sitting = serializers.IntegerField()
    number = serializers.IntegerField()
    motion = serializers.CharField()
    kind = serializers.CharField()
    counts = serializers.JSONField()
    options = serializers.JSONField()
    matching_ballots = BallotSerializer(many=True)
    matching_ballots_count = serializers.IntegerField()
    ballots_url = serializers.CharField()

class EvidenceLinkSerializer(serializers.Serializer):
    phrase = serializers.CharField()
    source_url = serializers.URLField()
    explanation = serializers.CharField()

class SourceSerializer(serializers.ModelSerializer):
    # Grupa dla czytelnika: Publiczne / Media / Top media (news.source_groups).
    portal_group = serializers.SerializerMethodField()

    class Meta:
        model = Source
        fields = ('id', 'name', 'url', 'source_type', 'is_active', 'catalog_stage', 'portal_group')

    @extend_schema_field(serializers.ChoiceField(choices=['top', 'publiczne', 'media']))
    def get_portal_group(self, obj):
        return portal_group(obj)

class ArticleSerializer(serializers.ModelSerializer):
    source = SourceSerializer(read_only=True)
    voting = serializers.SerializerMethodField()
    evidence_links = serializers.SerializerMethodField()
    content_status = serializers.SerializerMethodField()
    @extend_schema_field(serializers.CharField())
    def get_content_status(self, obj):
        content = getattr(obj, 'content', None)
        return content.status if content else 'not_fetched'
    official = serializers.SerializerMethodField()
    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_official(self, obj):
        from urllib.parse import quote
        record = getattr(obj, 'official_record', None)
        if record is None:
            return None
        attachments = []
        if obj.category == 'parliamentary_print':
            attachments = [{'name': name, 'url': record.api_url + '/' + quote(name, safe='')} for name in record.raw_data.get('attachments', []) if isinstance(name, str)]
        return {'provider': record.provider, 'api_url': record.api_url, 'fetched_at': record.fetched_at.isoformat(),
            'date_label': {'voting': 'Data głosowania', 'parliamentary_print': 'Data doręczenia druku', 'legislation': 'Data ogłoszenia'}.get(obj.category, 'Data'),
            'status': record.raw_data.get('status', ''), 'document_type': record.raw_data.get('type', ''), 'attachments': attachments}
    @extend_schema_field(EvidenceLinkSerializer(many=True))
    def get_evidence_links(self, obj):
        return [{'phrase': row.phrase, 'source_url': row.source_url, 'explanation': row.explanation} for row in obj.evidence_links.all()]
    @extend_schema_field(VotingSummarySerializer(allow_null=True))
    def get_voting(self, obj):
        voting = getattr(obj, 'voting', None)
        if voting is None:
            return None
        tokens = self.context.get('search_tokens', [])
        ballots = list(voting.ballots.all()) if tokens else []
        name_tokens = [token.casefold() for token in tokens if any(token.casefold() in b.name.casefold() for b in ballots)]
        matches = [b for b in ballots if all(token in b.name.casefold() for token in name_tokens)] if name_tokens else []
        return {'term': voting.term, 'sitting': voting.sitting, 'number': voting.number, 'motion': voting.motion,
            'kind': voting.kind, 'counts': voting.counts, 'options': voting.options,
            'matching_ballots': BallotSerializer(matches[:50], many=True).data,
            'matching_ballots_count': len(matches), 'ballots_url': f'/api/articles/{obj.pk}/ballots/'}
    class Meta:
        model = Article
        fields = ('id', 'title', 'url', 'published_date', 'date_precision', 'category', 'tags', 'image_url', 'source', 'author', 'description', 'tweet_id', 'likes_count', 'retweets_count', 'discovered_at', 'ingestion_method', 'category_reviewed', 'evidence_note', 'voting', 'evidence_links', 'official', 'content_status')

class ThreadItemSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_role = serializers.SerializerMethodField()
    is_sponsored = serializers.BooleanField(source='thread.sponsorship_active', read_only=True)
    sponsor_name = serializers.CharField(source='thread.sponsor_name', read_only=True)
    sponsorship_label = serializers.CharField(source='thread.sponsorship_label', read_only=True)
    @extend_schema_field(serializers.CharField())
    def get_author_name(self, obj):
        return thread_author(obj.thread, self.context)['name']
    @extend_schema_field(serializers.CharField())
    def get_author_role(self, obj):
        return thread_author(obj.thread, self.context)['role']
    article = serializers.SerializerMethodField()
    @extend_schema_field(serializers.JSONField())
    def get_article(self, obj):
        if obj.article_id:
            return ArticleSerializer(obj.article, context=self.context).data
        from news.x_reference import reference_card
        return reference_card(obj.external_url, obj.pk)
    class Meta:
        model = ThreadItem
        fields = ('id', 'position', 'editorial_note', 'article', 'author_name', 'author_role', 'is_sponsored', 'sponsor_name', 'sponsorship_label')

class ThreadListSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_role = serializers.SerializerMethodField()
    is_sponsored = serializers.BooleanField(source='sponsorship_active', read_only=True)
    sponsorship_label = serializers.CharField(read_only=True)
    item_count = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    items = ThreadItemSerializer(source='visible_items', many=True, read_only=True)
    featured = serializers.BooleanField(source='is_featured', read_only=True)
    def get_author_name(self, obj) -> str:
        return thread_author(obj, self.context)['name']
    def get_author_role(self, obj) -> str:
        return thread_author(obj, self.context)['role']
    def get_item_count(self, obj) -> int:
        return len(obj.visible_items)
    def get_image_url(self, obj) -> str:
        return next((i.article.image_url for i in obj.visible_items if i.article_id and i.article.image_url), '')
    class Meta:
        model = Thread
        fields = ('id', 'title', 'slug', 'thread_type', 'editorial_slot', 'is_featured', 'featured', 'description', 'published', 'views_count', 'created_at', 'updated_at', 'item_count', 'image_url', 'items', 'author_name', 'author_role', 'is_sponsored', 'sponsor_name', 'sponsorship_label')

class ThreadSerializer(ThreadListSerializer):
    items = ThreadItemSerializer(source='visible_items', many=True, read_only=True)
    class Meta(ThreadListSerializer.Meta):
        fields = ThreadListSerializer.Meta.fields

class SearchTimelineSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    returned = serializers.IntegerField()
    truncated = serializers.BooleanField()
    page = serializers.IntegerField()
    next_page = serializers.IntegerField(allow_null=True)
    timeline = serializers.DictField(child=ArticleSerializer(many=True))
