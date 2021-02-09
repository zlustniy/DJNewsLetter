from django.utils.functional import cached_property

from djnewsletter.tasks import (
    send_by_smtp,
    send_by_unisender,
)


class DJNewsLetterSendingMethodOptions:
    sending_method_options = {
        'smtp': {
            'label': 'SMTP сервер',
            'task': send_by_smtp,
        },
        'unisender_api': {
            'label': 'UniSender API',
            'task': send_by_unisender,
        },
    }

    @cached_property
    def sending_method_choises(self):
        return [
            (sending_method, options['label']) for sending_method, options in self.sending_method_options
        ]

    def get_task_by_sending_method(self, sending_method):
        return self.sending_method_options.get(sending_method)
