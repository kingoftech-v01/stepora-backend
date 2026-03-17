"""URL routing for the Ads app."""

from django.urls import path

from .views import AdConfigView

urlpatterns = [
    path("config/", AdConfigView.as_view(), name="ad-config"),
]
