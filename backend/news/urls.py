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
from news.community import resolve_link, community_threads, community_thread_detail, CommunityOpinionsView, report_thread
from news.clinic_api import (clinic_page, clinic_spins, clinic_spin_detail, clinic_accounts, SpinOpinionsView,
                             suggest_x_account, clinic_queue, staff_interviews, review_diagnosis, review_message, hide_diagnosis, decide_flag)
from news.public_figures import public_figure_list, public_figure_detail, public_figure_context, public_figure_dossier, public_office_list

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
    path('public-offices/', public_office_list),
    path('public-figures/<int:figure_id>/', public_figure_detail),
    path('public-figures/<int:figure_id>/x-suggestions/', suggest_x_account),
    path('community/links/', resolve_link),
    path('community/threads/', community_threads),
    path('community/threads/<int:thread_id>/', community_thread_detail),
    path('community/threads/<int:thread_id>/opinions/', CommunityOpinionsView.as_view()),
    path('community/threads/<int:thread_id>/report/', report_thread),
    path('clinic/', clinic_page),
    path('clinic/spins/', clinic_spins),
    path('clinic/spins/<int:diagnosis_id>/', clinic_spin_detail),
    path('clinic/spins/<int:diagnosis_id>/opinions/', SpinOpinionsView.as_view()),
    path('clinic/accounts/', clinic_accounts),
    path('staff/clinic/queue/', clinic_queue),
    path('staff/clinic/interviews/', staff_interviews),
    path('staff/clinic/diagnoses/<int:diagnosis_id>/review/', review_diagnosis),
    path('staff/clinic/diagnoses/<int:diagnosis_id>/hide/', hide_diagnosis),
    path('staff/clinic/messages/<int:message_id>/review/', review_message),
    path('staff/clinic/diagnoses/<int:diagnosis_id>/flag/', decide_flag),
    path('public-figures/<int:figure_id>/context/', public_figure_context),
    path('public-figures/<int:figure_id>/dossier/', public_figure_dossier),
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
