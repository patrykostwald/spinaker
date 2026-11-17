from django.urls import path

from . import api

app_name = "teraz"

urlpatterns = [
    path("warstwy/", api.WarstwyView.as_view(), name="warstwy"),
    path("wpisy/", api.WpisyView.as_view(), name="wpisy"),
    path("zdarzenia/", api.ZdarzeniaView.as_view(), name="zdarzenia"),
    path("zdarzenia/<int:pk>/", api.ZdarzenieView.as_view(), name="zdarzenie"),
    path("stan/", api.StanView.as_view(), name="stan"),
]
