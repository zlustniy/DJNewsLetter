from copy import deepcopy

from django.core.mail.backends.base import BaseEmailBackend
from django.db import transaction

from .handlers import (
    DJNewsLetterSendingHandlers,
)
from .mail import (
    DJNewsLetterEmailMessage,
)
from .options import (
    DJNewsLetterSendingMethodOptions,
)


class DJNewsletterBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently, **kwargs)
        self.sending_options = DJNewsLetterSendingMethodOptions()

    def run_task(self, email_message, email):
        try:
            task = self.sending_options.get_task_by_sending_method(email_message.email_server.sending_method)
            task_options = {
                'countdown': email_message.countdown,
                'eta': email_message.eta,
            }
            task.apply_async(args=(email_message,), kwargs={'email_pk': email.pk}, **task_options)
        except Exception as e:
            email.status = str(e)
            email.save()

    @staticmethod
    def unify_email_message(message):
        if not isinstance(message, DJNewsLetterEmailMessage):
            return DJNewsLetterEmailMessage(
                message=message,
            )
        return message

    def send_messages(self, email_messages):
        for email_message in email_messages:
            email_message = self.unify_email_message(email_message)
            with transaction.atomic():
                message_handler = DJNewsLetterSendingHandlers().get_handler(email_message)
                email_message = message_handler.handle()
                for email_server, recipients in email_message.recipients_email_server_route.items():
                    from_email = self.sending_options.get_from_email(email_server)
                    email = message_handler.create_email(
                        sender=from_email,
                        recipients=recipients,
                        used_server=email_server,
                        status='sent to queue',
                    )
                    email_message_for_task = deepcopy(email_message)
                    email_message_for_task.message.to = recipients
                    email_message_for_task.message.from_email = from_email
                    email_message_for_task.email_server = email_server
                    transaction.on_commit(
                        lambda m=email_message_for_task, e=email, es=email_server: self.run_task(
                            email_message=m,
                            email=e,
                        )
                    )

        return len(email_messages)


class EmailBackend(DJNewsletterBackend):
    pass
