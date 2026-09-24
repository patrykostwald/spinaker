from django.urls import include, path
from rest_framework.routers import SimpleRouter
from news.political_api import (PoliticalAccountViewSet, PoliticalPostViewSet,
    PoliticalDraftViewSet, political_status)

router = SimpleRouter()
router.register('accounts', PoliticalAccountViewSet, basename='political-account')
router.register('posts', PoliticalPostViewSet, basename='political-post')
router.register('drafts', PoliticalDraftViewSet, basename='political-draft')

urlpatterns = [path('status/', political_status, name='political-status'), path('', include(router.urls))]
