import collections
from copy import deepcopy
from datetime import datetime, timedelta

from django.core.mail.backends.base import BaseEmailBackend
from django.db import transaction
from djnewsletter import tasks
from djnewsletter.conf import settings
from djnewsletter.exceptions import UnsubscribeEmailConflict
from djnewsletter.helpers import get_content_subtype_and_body
from djnewsletter.models import Emails, Unsubscribers, Bounced

from .models import EmailServers
from .options import DJNewsLetterSendingMethodOptions


class DJNewsletterBackend(BaseEmailBackend):
    def __init__(self):
        self.sending_options = DJNewsLetterSendingMethodOptions()

    def run_task(self, message, email, email_server):
        try:
            task = self.tasks_mapping[email_server.sending_method]
            task_options = {
                'countdown': getattr(message, 'countdown', None),
                'eta': getattr(message, 'eta', None),
            }
            task.apply_async(args=(message,), kwargs={'email_pk': email.pk}, **task_options)
        except Exception as e:
            email.status = str(e)
            email.save()

    def _get_from_email(self, email_server):
        if email_server.sending_method == 'smtp':
            return email_server.email_default_from
        elif email_server.sending_method == 'unisender_api':
            return email_server.api_from_email

    def send_messages(self, email_messages):
        for message in email_messages:
            mapped_mail_server_recipients = collections.defaultdict(list)

            newsletter = getattr(message, 'newsletter', None)
            bounced_qs = None
            status = ''
            if newsletter:
                bounced_qs = Bounced.objects.filter(email__in=message.to,
                                                    event__in=['bounce', 'dropped', 'spamreport']
                                                    ).values_list('email', flat=True)
                if bounced_qs:
                    message.to = list(filter(lambda email: email not in bounced_qs, message.to))
                    status = 'There were problems with the recipient this letter previously'

            if getattr(message, 'custom_args', None):
                email_server = message.custom_args.get('email_server', None)
                if email_server is not None and message.to:
                    mapped_mail_server_recipients[email_server] = message.to
            else:
                email_server = None
                message.custom_args = {}

            if not email_server:
                for recipient in message.to:
                    domain = recipient.split('@')[1]
                    email_server = EmailServers.objects.filter(preferred_domains__domain=domain, is_active=True,
                                                               sites__isnull=True).first()
                    if not email_server:
                        email_server = EmailServers.objects.filter(main=True, is_active=True,
                                                                   sites__isnull=True).first()
                    mapped_mail_server_recipients[email_server].append(recipient)

            message.custom_args.update({'mapped_mail_server_recipients': mapped_mail_server_recipients})

            content_subtype, body = get_content_subtype_and_body(message)
            with transaction.atomic():
                if bounced_qs:
                    email = Emails(
                        type=content_subtype,
                        sender='did not send',
                        recipient=list(bounced_qs),
                        body=body,
                        subject=message.subject,
                        newsletter=newsletter,
                        used_server=email_server,
                        status=status
                    )
                    email.save()

                for email_server, recipients in message.custom_args.get('mapped_mail_server_recipients').items():
                    message.custom_args.update({'email_server': email_server if email_server else None})
                    message.from_email = self._get_from_email(email_server)
                    message.to = recipients
                    email = Emails(
                        type=content_subtype,
                        sender=message.from_email,
                        recipient=message.to,
                        body=body,
                        subject=message.subject,
                        newsletter=newsletter,
                        used_server=email_server
                    )

                    if newsletter:
                        if 'List-Unsubscribe' in message.extra_headers:
                            if len(message.to) > 1:
                                raise UnsubscribeEmailConflict(
                                    'нельзя заголовок unsubscribe и много получателей одновременно')

                            if Unsubscribers.objects.filter(email=message.to[0],
                                                            newsletter=message.newsletter).exists():
                                email.status = 'Don\'t sent, because user is unsubscribe'
                                email.save()
                                continue

                        if settings.DJNEWSLETTER_INTERVAL_SENDING_TO_RECIPIENT is not None:
                            if Emails.objects.filter(
                                    recipient=message.to,
                                    newsletter=message.newsletter,
                                    status_hash='3b0cea37664e25d1060e6306dcdcef51',  # 'sent to user' hash
                                    changeDateTime__gt=datetime.now() - timedelta(
                                        hours=settings.DJNEWSLETTER_INTERVAL_SENDING_TO_RECIPIENT)
                            ).exists():
                                email.status = 'Letters are sent too frequently'
                                email.save()
                                continue

                    email.status = 'sent to queue'
                    email.save()

                    m1 = deepcopy(message)
                    transaction.on_commit(lambda m=m1, e=email, es=email_server: self.run_task(m, e, email_server=es))

        return len(email_messages)


class EmailBackend(DJNewsletterBackend):
    pass
