from django.urls import path, include

from .api.urls import mail_api_urlpatterns

mail_urlpatterns = [
    path('api/', include(mail_api_urlpatterns)),
]
