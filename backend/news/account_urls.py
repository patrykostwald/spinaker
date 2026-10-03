from django.urls import path
from news.accounts import (RegisterView, LoginView, LogoutView, AccountMeView,
                           TopicsView, TopicDetailView, OpinionsView, ThreadOpinionsView)

from news.profiles import ProfileView, HistoryView, PublicActivityView, FavoritesView, FavoriteDetailView
from news.personal_context import (ArticleFavoritesView, ArticleFavoriteDetailView, CommentReportsView,
    PersonalContextThreadsView, PersonalContextThreadDetailView)
from news.account_activity import MyReactionsView
from news.accounts import XConnectionView, XConnectionStartView, XConnectionCallbackView

urlpatterns = [
    path('account/x/start/', XConnectionStartView.as_view()),
    path('account/x/callback/', XConnectionCallbackView.as_view()),
    path('account/profile/', ProfileView.as_view()),
    path('account/history/', HistoryView.as_view()),
    path('account/reactions/', MyReactionsView.as_view()),
    path('account/favorites/', FavoritesView.as_view()),
    path('account/favorites/<int:thread_id>/', FavoriteDetailView.as_view()),
    path('account/article-favorites/', ArticleFavoritesView.as_view()),
    path('account/article-favorites/<int:article_id>/', ArticleFavoriteDetailView.as_view()),
    path('account/context-threads/', PersonalContextThreadsView.as_view()),
    path('account/context-threads/<int:thread_id>/', PersonalContextThreadDetailView.as_view()),
    path('comments/reports/', CommentReportsView.as_view()),
    path('profiles/<str:username>/activity/', PublicActivityView.as_view()),
    path('account/register/', RegisterView.as_view()),
    path('account/login/', LoginView.as_view()),
    path('account/logout/', LogoutView.as_view()),
    path('account/me/', AccountMeView.as_view()),
    path('account/x-connection/', XConnectionView.as_view()),
    path('account/x-connection/start/', XConnectionStartView.as_view()),
    path('account/x-connection/callback/', XConnectionCallbackView.as_view()),
    path('account/topics/', TopicsView.as_view()),
    path('account/topics/<int:topic_id>/', TopicDetailView.as_view()),
    path('articles/<int:article_id>/opinions/', OpinionsView.as_view()),
    path('threads/<slug:slug>/opinions/', ThreadOpinionsView.as_view()),
]

from news.account_lifecycle import (VerifyEmailView, ResendVerificationView, PasswordResetView,
    PasswordResetConfirmView, AccountExportView, AccountDeleteView)
from news.google_accounts import GoogleStartView, GoogleCallbackView
from news.notification_api import (FollowsView, FollowDetailView, NotificationsView,
    NotificationReadView, NotificationSettingsView)

urlpatterns += [
    path('account/verify-email/', VerifyEmailView.as_view()),
    path('account/verify-email/resend/', ResendVerificationView.as_view()),
    path('account/password-reset/', PasswordResetView.as_view()),
    path('account/password-reset/confirm/', PasswordResetConfirmView.as_view()),
    path('account/export/', AccountExportView.as_view()),
    path('account/delete/', AccountDeleteView.as_view()),
    path('account/google/start/', GoogleStartView.as_view()),
    path('account/google/callback/', GoogleCallbackView.as_view()),
    path('account/follows/', FollowsView.as_view()),
    path('account/follows/<int:follow_id>/', FollowDetailView.as_view()),
    path('account/notifications/', NotificationsView.as_view()),
    path('account/notifications/read/', NotificationReadView.as_view()),
    path('account/notification-settings/', NotificationSettingsView.as_view()),
]
