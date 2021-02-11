from copy import deepcopy

from django.core.mail.backends.base import BaseEmailBackend
from django.db import transaction

from .handlers import (
    DJNewsLetterSendingHandlers,
)
from .options import (
    DJNewsLetterSendingMethodOptions,
)


class DJNewsletterBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently, **kwargs)
        self.sending_options = DJNewsLetterSendingMethodOptions()

    def run_task(self, message, email, email_server):
        try:
            task = self.sending_options.get_task_by_sending_method(email_server.sending_method)
            task_options = {
                'countdown': getattr(message, 'countdown', None),
                'eta': getattr(message, 'eta', None),
            }
            task.apply_async(args=(message,), kwargs={'email_pk': email.pk}, **task_options)
        except Exception as e:
            email.status = str(e)
            email.save()

    def send_messages(self, email_messages):
        for email_message in email_messages:
            with transaction.atomic():
                message_handler = DJNewsLetterSendingHandlers().get_handler(email_message)
                message = message_handler.handle()
                for email_server, recipients in message.recipients_email_server_route.items():
                    from_email = self.sending_options.get_from_email(email_server)
                    email = message_handler.create_email(
                        sender=from_email,
                        recipients=recipients,
                        used_server=email_server,
                        status='sent to queue',
                    )
                    message_for_task = deepcopy(message)
                    message_for_task.to = recipients
                    message_for_task.from_email = from_email
                    setattr(message_for_task, 'email_server', email_server)
                    transaction.on_commit(
                        lambda m=message_for_task, e=email, es=email_server: self.run_task(
                            message=m,
                            email=e,
                            email_server=es,
                        )
                    )

        return len(email_messages)


class EmailBackend(DJNewsletterBackend):
    pass
