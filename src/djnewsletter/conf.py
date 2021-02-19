from appconf import AppConf
# noinspection PyUnresolvedReferences
from django.conf import settings

MAX_RETRIES = 5
COUNTDOWN = 60  # seconds
BACKEND = getattr(settings, 'CELERY_EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')


class DjnewsletterAppConf(AppConf):
    LETTER_CONTEXT = {}
    INTERVAL_SENDING_TO_RECIPIENT = None
    UNISENDER_URL = None
    MIN_APPROX_COUNT = 10000
