from django.urls import path

from .views import (
    SendEmailsApiView,
)

mail_api_urlpatterns = [
    path('send_emails/', SendEmailsApiView.as_view(), name='send_emails_api_view'),
]
