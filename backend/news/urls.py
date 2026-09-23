from __future__ import annotations

from rest_framework.routers import DefaultRouter
from django.urls import include, path
from news.views import source_coverage, archive_status, health, me, google_news, patronite_webhook, editorial_status
from news.auth_views import csrf, sign_in, sign_out
from news.editorial import EditorialThreadViewSet, EditorialArticleViewSet
from news.metadata import preview_url
from news.youtube import search_youtube
from news.external_search import external_search
from news.draft import EditorialDraftView
from news.ai_research import AIResearchView
from news.ai_research_stream import AIResearchStreamView, AIResearchSourcesView
from news.source_catalog import SourceCatalogList, SourceCatalogDetail, SourceCatalogExport
from news.portal import feed, portal_config, article_context, context_counts
from news.daily_topic import topic_of_day
from news.public_figures import public_figure_list, public_figure_detail

from news.views import ArticleViewSet, SearchViewSet, ThreadViewSet

router = DefaultRouter()
router.register(r"editor/threads", EditorialThreadViewSet, basename="editor-threads")
router.register(r"editor/articles", EditorialArticleViewSet, basename="editor-articles")
router.register(r"search", SearchViewSet, basename="search")
router.register(r"articles", ArticleViewSet, basename="articles")
router.register(r"threads", ThreadViewSet, basename="threads")

urlpatterns = [
    path('', include('news.account_urls')),
    path('staff/political/', include('news.political_urls')),
    path('feed/', feed),
    path('portal/config/', portal_config),
    path('portal/topic-of-day/', topic_of_day),
    path('public-figures/', public_figure_list),
    path('public-figures/<int:figure_id>/', public_figure_detail),
    path('articles/<int:article_id>/context/', article_context),
    path('context/counts/', context_counts),
    path("editor/sources/", SourceCatalogList.as_view()),
    path("editor/sources/export/", SourceCatalogExport.as_view()),
    path("editor/sources/<int:source_id>/", SourceCatalogDetail.as_view()),
    path("ai/research/", AIResearchView.as_view()),
    path("ai/research/stream/", AIResearchStreamView.as_view()),
    path("ai/research/sources/", AIResearchSourcesView.as_view()),
    path("editor/draft-thread/", EditorialDraftView.as_view()),
    path("search/external/", external_search),
    path("youtube/search/", search_youtube),
    path("sources/coverage/", source_coverage),
    path("archive/status/", archive_status),
    path("editor/status/", editorial_status),
    path("editor/preview-url/", preview_url),
    path("auth/csrf/", csrf),
    path("auth/login/", sign_in),
    path("auth/logout/", sign_out),
    path("health/", health),
    path("me/", me),
    path("admin/google-news/", google_news),
    path("patronite/webhook/", patronite_webhook),
    *router.urls,
]
