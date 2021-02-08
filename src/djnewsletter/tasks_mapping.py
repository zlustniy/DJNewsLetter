from djnewsletter.tasks import (
    send_by_smtp,
    send_by_unisender,
)

SENDING_METHOD_MAPPING = {
    'smtp': {
        'label': 'SMTP сервер',
        'task': send_by_smtp,
    },
    'unisender_api': {
        'label': 'UniSender API',
        'task': send_by_unisender,
    },
}
