from django.urls import path
from news.accounts import (RegisterView, LoginView, LogoutView, AccountMeView,
                           TopicsView, TopicDetailView, OpinionsView)

from news.profiles import ProfileView, HistoryView, PublicActivityView, FavoritesView, FavoriteDetailView

urlpatterns = [
    path('account/profile/', ProfileView.as_view()),
    path('account/history/', HistoryView.as_view()),
    path('account/favorites/', FavoritesView.as_view()),
    path('account/favorites/<int:thread_id>/', FavoriteDetailView.as_view()),
    path('profiles/<str:username>/activity/', PublicActivityView.as_view()),
    path('account/register/', RegisterView.as_view()),
    path('account/login/', LoginView.as_view()),
    path('account/logout/', LogoutView.as_view()),
    path('account/me/', AccountMeView.as_view()),
    path('account/topics/', TopicsView.as_view()),
    path('account/topics/<int:topic_id>/', TopicDetailView.as_view()),
    path('articles/<int:article_id>/opinions/', OpinionsView.as_view()),
]
