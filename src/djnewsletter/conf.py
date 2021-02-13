from appconf import AppConf
# noinspection PyUnresolvedReferences
from django.conf import settings


class DjnewsletterAppConf(AppConf):
    LETTER_CONTEXT = {}
    INTERVAL_SENDING_TO_RECIPIENT = None
    UNISENDER_URL = None
    MIN_APPROX_COUNT = 10000
