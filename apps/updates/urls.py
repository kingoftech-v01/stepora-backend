from django.urls import path

from . import views

urlpatterns = [
    path("check/", views.UpdateCheckView.as_view(), name="update-check"),
    path("upload/", views.BundleUploadView.as_view(), name="bundle-upload"),
]
