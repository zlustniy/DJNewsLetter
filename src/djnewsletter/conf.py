from appconf import AppConf
# noinspection PyUnresolvedReferences
from django.conf import settings


class DjnewsletterAppConf(AppConf):
    INTERVAL_SENDING_TO_RECIPIENT = None
    UNISENDER_URL = None
