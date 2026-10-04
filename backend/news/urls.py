from __future__ import annotations
from news.thread_card import thread_card
from news.thread_steps import ThreadBoxView, ThreadStepsView
from news.thread_social import ThreadCommentReactionView, ThreadRatingsView, ThreadCommentsView, ThreadCommentDetailView, ThreadReportView, ThreadAppealView, ThreadModerationQueueView
from news.clinic_discussion import ClinicOpinionsView, ClinicCommentsView, ClinicCommentReportView

from news.clinic_api import clinic_council, clinic_corrections
from rest_framework.routers import DefaultRouter
from django.urls import include, path
from news import agents_api
from news import warden_api
from news import newsletter
from news import polls
from news.admin_status import admin_status
from news.admin_finance import admin_wallets
from news.social_publish import serve_video
from news.social_api import (SocialQueueView, SocialPublicationView, SocialPublishedView,
    SocialTasksView, StaffSocialTasksView, StaffSocialTaskDetailView, SocialPasswordResetConfirmView)
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
from news.community import resolve_link, community_threads, community_thread_detail
from news.clinic_api import (clinic_page, clinic_interviews, clinic_interview_detail, clinic_messages, clinic_message_detail, clinic_statistics, clinic_spins, clinic_spin_detail, clinic_spin_card, clinic_accounts, clinic_deleted, clinic_report,
                             suggest_x_account, clinic_queue, staff_interviews, review_diagnosis, review_message, hide_diagnosis, decide_flag)
from news.public_figures import public_figure_list, public_figure_detail, public_figure_context, public_figure_dossier, public_office_list

from news.views import ArticleViewSet, SearchViewSet, ThreadViewSet
from news.push_api import SubscriptionsView
from news.interview_vote_api import InterviewBallotView, InterviewVoteView, InterviewMessageView

router = DefaultRouter()
router.register(r"editor/threads", EditorialThreadViewSet, basename="editor-threads")
router.register(r"editor/articles", EditorialArticleViewSet, basename="editor-articles")
router.register(r"search", SearchViewSet, basename="search")
router.register(r"articles", ArticleViewSet, basename="articles")
router.register(r"threads", ThreadViewSet, basename="threads")

urlpatterns = [
    path('social/queue/', SocialQueueView.as_view()),
    path('social/published/', SocialPublishedView.as_view()),
    path('social/materials/<int:diagnosis_id>/', SocialPublicationView.as_view()),
    path('social/tasks/', SocialTasksView.as_view()),
    path('social/password/confirm/', SocialPasswordResetConfirmView.as_view()),
    path('staff/social/tasks/', StaffSocialTasksView.as_view()),
    path('staff/social/tasks/<int:task_id>/', StaffSocialTaskDetailView.as_view()),
    path('staff/agents/', agents_api.notes),
    path('staff/agents/map/', agents_api.agent_map),
    path('staff/daily-schedule/', agents_api.daily_schedule),
    path('staff/warden-reviews/', warden_api.reviews),
    path('staff/warden-reviews/<int:review_id>/decision/', warden_api.decide),
    path('staff/agents/<int:note_id>/decision/', agents_api.decide),
    path('push/subscriptions/', SubscriptionsView.as_view()),
    path('admin/status/', admin_status),
    path('admin/wallets/', admin_wallets),
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
    path('community/moderation/', ThreadModerationQueueView.as_view()),
    path('community/threads/<int:thread_id>/card.png', thread_card),
    path('community/reports/<int:report_id>/', ThreadAppealView.as_view()),
    path('community/threads/<int:thread_id>/comments/<int:comment_id>/reaction/', ThreadCommentReactionView.as_view()),
    path('community/threads/<int:thread_id>/comments/', ThreadCommentsView.as_view()),
    path('community/threads/<int:thread_id>/comments/<int:comment_id>/', ThreadCommentDetailView.as_view()),
    path('community/threads/<int:thread_id>/comments/<int:comment_id>/report/', ThreadReportView.as_view()),
    path('community/threads/<int:thread_id>/', community_thread_detail),
    path('community/threads/<int:thread_id>/opinions/', ThreadRatingsView.as_view()),
    path('community/threads/<int:thread_id>/steps/', ThreadStepsView.as_view()),
    path('community/threads/<int:thread_id>/boxes/<int:item_id>/', ThreadBoxView.as_view()),
    path('community/threads/<int:thread_id>/report/', ThreadReportView.as_view()),
    path('polls/<slug:slug>/', polls.poll_results),
    path('polls/<slug:slug>/vote/', polls.poll_vote),
    path('newsletter/subscribe/', newsletter.subscribe),
    path('newsletter/confirm/', newsletter.confirm),
    path('newsletter/unsubscribe/', newsletter.unsubscribe),
    path('staff/newsletter/', newsletter.staff_stats),
    path('social/video/<str:name>', serve_video),
    path('social/video/<str:name>/', serve_video),
    path('clinic/', clinic_page),
    path('clinic/corrections/', clinic_corrections),
    path('clinic/interviews/', clinic_interviews),
    path('clinic/interviews/voting/', InterviewBallotView.as_view()),
    path('clinic/interviews/voting/vote/', InterviewVoteView.as_view()),
    path('clinic/interviews/voting/message/', InterviewMessageView.as_view()),
    path('clinic/interviews/<int:interview_id>/', clinic_interview_detail),
    path('clinic/messages/', clinic_messages),
    path('clinic/messages/<str:day>/', clinic_message_detail),
    path('clinic/council/', clinic_council),
    path('clinic/spins/', clinic_spins),
    path('clinic/stats/', clinic_statistics),
    path('clinic/spins/<int:diagnosis_id>/', clinic_spin_detail),
    path('clinic/spins/<int:diagnosis_id>/card.png', clinic_spin_card),
    path('clinic/spins/<int:diagnosis_id>/card.png/', clinic_spin_card),
    path('clinic/spins/<int:target_id>/opinions/', ClinicOpinionsView.as_view(), {'kind': 'spins'}),
    path('clinic/interviews/<int:target_id>/opinions/', ClinicOpinionsView.as_view(), {'kind': 'interviews'}),
    path('clinic/spins/<int:target_id>/comments/', ClinicCommentsView.as_view(), {'kind': 'spins'}),
    path('clinic/interviews/<int:target_id>/comments/', ClinicCommentsView.as_view(), {'kind': 'interviews'}),
    path('clinic/spins/<int:target_id>/comments/<int:comment_id>/report/', ClinicCommentReportView.as_view(), {'kind': 'spins'}),
    path('clinic/interviews/<int:target_id>/comments/<int:comment_id>/report/', ClinicCommentReportView.as_view(), {'kind': 'interviews'}),
    path('clinic/accounts/', clinic_accounts),
    path('clinic/deleted/', clinic_deleted),
    path('clinic/report/', clinic_report),
    path('clinic/report/<str:week_end>/', clinic_report),
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
