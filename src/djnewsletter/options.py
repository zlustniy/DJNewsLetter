from django.utils.functional import cached_property

from .tasks import (
    send_by_smtp,
    send_by_unisender,
)


class DJNewsLetterSendingMethodOptions:
    sending_method_options = {
        'smtp': {
            'label': 'SMTP сервер',
            'task': send_by_smtp,
            'from_email': 'email_default_from',
        },
        'unisender_api': {
            'label': 'UniSender API',
            'task': send_by_unisender,
            'from_email': 'api_from_email',
        },
    }

    @cached_property
    def sending_method_choises(self):
        return [
            (sending_method, options['label']) for sending_method, options in self.sending_method_options
        ]

    def get_task_by_sending_method(self, sending_method):
        options = self.sending_method_options.get(sending_method)
        return options['task']

    def get_from_email(self, email_server):
        options = self.sending_method_options.get(email_server.sending_method)
        return getattr(email_server, options['from_email'])
