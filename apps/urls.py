from django.urls import path

from apps.views import SiteSettingView, PartnerListAPIView, ServiceListAPIView, \
    ContactFormCreateAPIView, EmailCreateAPIView, ProjectListAPIView, ProjectDetailAPIView

urlpatterns = [
    path('site-setting/', SiteSettingView.as_view()),
    path('partners/', PartnerListAPIView.as_view()),
    path('services/', ServiceListAPIView.as_view()),
    path('projects/', ProjectListAPIView.as_view()),
    path('projects/<slug:slug>/', ProjectDetailAPIView.as_view()),
    path('create-contact/', ContactFormCreateAPIView.as_view()),
    path('create-email/', EmailCreateAPIView.as_view()),
]