"""Trasy spina3 v2 pod /api/spina3/ (na api.spina3.pl serwer odwrotny mapuje /api/ -> /api/spina3/, patrz docs/SPINA3_WDROZENIE.md)."""
from __future__ import annotations

from django.urls import path

from . import feeds, views

urlpatterns = [
    path('config/', views.ConfigView.as_view(), name='spina3-config'),
    path('silence/', views.SilenceView.as_view(), name='spina3-silence'),
    path('wall/', views.WallView.as_view(), name='spina3-wall'),
    path('facets/', views.FacetsView.as_view(), name='spina3-facets'),
    path('boxes/', views.BoxCreateView.as_view(), name='spina3-box-create'),
    path('boxes/search/', views.SearchView.as_view(), name='spina3-search'),
    path('box/<int:box_id>/', views.BoxView.as_view(), name='spina3-box'),
    path('box/<int:box_id>/related/', views.RelatedView.as_view(), name='spina3-related'),
    path('box/<int:box_id>/comments/', views.CommentsView.as_view(), name='spina3-comments'),
    path('pin/<int:pin_id>/', views.PinDetailView.as_view(), name='spina3-pin'),
    path('pin/<int:pin_id>/rating/', views.RatingView.as_view(), name='spina3-rating'),
    path('pin/<int:pin_id>/appeal/', views.AppealView.as_view(), name='spina3-appeal'),
    path('comment/<int:comment_id>/', views.CommentDetailView.as_view(), name='spina3-comment'),
    path('comment/<int:comment_id>/helpful/', views.CommentHelpfulView.as_view(), name='spina3-comment-helpful'),
    path('comment/<int:comment_id>/appeal/', views.CommentAppealView.as_view(), name='spina3-comment-appeal'),
    path('me/boxes/', views.MyBoxesView.as_view(), name='spina3-me-boxes'),
    path('me/ratings/', views.MyRatingsView.as_view(), name='spina3-me-ratings'),
    path('me/profile/', views.ProfileView.as_view(), name='spina3-me-profile'),
    path('me/consent/', views.ConsentView.as_view(), name='spina3-consent'),
    path('report/', views.ReportView.as_view(), name='spina3-report'),
    path('moderation/queue/', views.ModerationQueueView.as_view(), name='spina3-mod-queue'),
    path('moderation/reports/<int:report_id>/', views.ReportDecisionView.as_view(), name='spina3-mod-report'),
    path('moderation/appeals/<int:appeal_id>/', views.AppealDecisionView.as_view(), name='spina3-mod-appeal'),
    path('moderation/urls/<int:check_id>/', views.UrlDecisionView.as_view(), name='spina3-mod-url'),
    path('moderation/pins/<int:pin_id>/', views.PinHideView.as_view(), name='spina3-mod-pin'),
    path('moderation/comments/<int:comment_id>/', views.CommentHideView.as_view(), name='spina3-mod-comment'),
    path('moderation/metrics/', views.MetricsView.as_view(), name='spina3-metrics'),
    path('auth/exchange/', views.AuthExchangeView.as_view(), name='spina3-auth-exchange'),
    path('auth/refresh/', views.AuthRefreshView.as_view(), name='spina3-auth-refresh'),
    path('auth/logout-everywhere/', views.AuthLogoutEverywhereView.as_view(), name='spina3-auth-logout'),
    path('feed/wall.xml', feeds.WallFeed(), name='spina3-feed-wall'),
    path('feed/topic/<str:topic>.xml', feeds.TopicFeed(), name='spina3-feed-topic'),
    path('feed/person/<int:person_id>.xml', feeds.PersonFeed(), name='spina3-feed-person'),
]
