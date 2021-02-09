import collections
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.sites.models import Site

from .exceptions import (
    SuitableEmailServerNotFoundException,
)
from .mail import (
    DJNewsLetterEmailMessage,
)
from .models import (
    Bounced,
    EmailServers,
    Emails,
    Unsubscribers,
)
from .options import (
    DJNewsLetterSendingMethodOptions,
)


class DJNewsLetterSendingHandlers:
    def __init__(self):
        self.handlers = {
            DJNewsLetterEmailMessage: DJNewsLetterEmailMessageHandler,
        }

    def get_handler(self, message):
        handler = self.handlers.get(type(message), DefaultEmailMessageHandler)
        return handler(message)


class BaseEmailMessageHandler:
    def __init__(self, message):
        self.sending_options = DJNewsLetterSendingMethodOptions()
        self.message = message
        self.site_id = self.get_site_id()

    def handle(self):
        raise NotImplementedError

    def get_site_id(self):
        return Site.objects.get_current().id

    def set_recipients_email_server_route(self, recipients_email_server_route):
        """

        @param recipients_email_server_route: Через какой почтовый сервер на какие электронные адреса отправлять письма.
        {
            EmailServers_object_1: ['email_1@mail.ru', 'email_3@mail.ru'],
            EmailServers_object_2: ['email_2@mail.ru', 'email_4@mail.ru'],
            EmailServers_object_3: ['email_5@mail.ru'],
        }

        """
        setattr(self.message, 'recipients_email_server_route', recipients_email_server_route)

    def rewrite_content_subtype_and_body(self):
        """
        Работа с alternative content types.
        :param message:
        :return:
        """
        if self.message.content_subtype != 'html':
            for body, content_subtype in getattr(self.message, 'alternatives', []):
                if content_subtype == 'text/html':
                    setattr(self.message, 'content_subtype', 'html')
                    setattr(self.message, 'body', body)

    def create_email(self, sender, recipients, status, used_server=None, save=True):
        email = Emails(
            type=self.message.content_subtype,
            sender=sender,
            recipient=recipients,
            body=self.message.body,
            subject=self.message.subject,
            newsletter=self.message.newsletter,
            status=status,
            used_server=used_server
        )
        if save:
            email.save()
        return email


class DefaultEmailMessageHandler(BaseEmailMessageHandler):
    def handle(self):
        return self.message


class DJNewsLetterEmailMessageHandler(BaseEmailMessageHandler):
    def handle(self):
        self.rewrite_content_subtype_and_body()
        self.handle_bounced()
        self.handle_unsubscribe()
        self.handle_interval_sending()
        self.handle_email_server()
        return self.message

    def handle_bounced(self):
        if self.message.newsletter:
            bounced_emails = Bounced.objects.filter(
                email__in=self.message.to,
                event__in=['bounce', 'dropped', 'spamreport'],
            ).values_list('email', flat=True)
            if bounced_emails.exists():
                bounced_emails = list(bounced_emails)
                self.message.to = list(filter(lambda email: email not in bounced_emails, self.message.to))
                self.create_email(
                    sender='did not send',
                    recipients=bounced_emails,
                    status='There were problems with the recipient this letter previously',
                )

    def handle_unsubscribe(self):
        if self.message.newsletter:
            if 'List-Unsubscribe' in self.message.extra_headers:
                unsubscribers_emails = Unsubscribers.objects.filter(
                    email__in=self.message.to,
                    newsletter=self.message.newsletter,
                ).values_list('email', flat=True)
                if unsubscribers_emails.exists():
                    unsubscribers_emails = list(unsubscribers_emails)
                    self.message.to = list(filter(lambda email: email not in unsubscribers_emails, self.message.to))
                    self.create_email(
                        sender='did not send',
                        recipients=unsubscribers_emails,
                        status='Don\'t sent, because user is unsubscribe',
                    )

    def handle_interval_sending(self):
        if self.message.newsletter:
            interval_sending_to_recipient = settings.DJNEWSLETTER_INTERVAL_SENDING_TO_RECIPIENT
            if interval_sending_to_recipient is not None:
                already_sent_emails = Emails.objects.filter(
                    recipient__in=self.message.to,
                    newsletter=self.message.newsletter,
                    status_hash='3b0cea37664e25d1060e6306dcdcef51',  # 'sent to user' hash
                    changeDateTime__gt=datetime.now() - timedelta(
                        hours=interval_sending_to_recipient,
                    )
                ).values_list('recipient', flat=True)
                if already_sent_emails.exists():
                    already_sent_emails = list(already_sent_emails)
                    self.message.to = list(filter(lambda email: email not in already_sent_emails, self.message.to))
                    self.create_email(
                        sender='did not send',
                        recipients=already_sent_emails,
                        status='Letters are sent too frequently',
                    )

    def handle_email_server(self):
        explicitly_specified_email_server = self.message.email_server
        if explicitly_specified_email_server:
            self.set_recipients_email_server_route({
                explicitly_specified_email_server: self.message.to,
            })
            return
        recipients_email_server_route = collections.defaultdict(list)
        for email in self.message.to:
            domain = email.split('@')[1]
            email_server = next(email_server for email_server in [
                EmailServers.objects.filter(
                    is_active=True,
                    sites__id=self.site_id,
                    preferred_domains__domain=domain,
                ).first(),
                EmailServers.objects.filter(
                    is_active=True,
                    sites__id=self.site_id,
                ).first(),
                EmailServers.objects.filter(
                    is_active=True,
                    preferred_domains__domain=domain,
                    sites__isnull=True,
                ).first(),
                EmailServers.objects.filter(
                    main=True,
                    is_active=True,
                    sites__isnull=True,
                ).first()
            ] if email_server is not None)
            if not email_server:
                raise SuitableEmailServerNotFoundException(
                    'Ошибка выбора EmailServers для адреса: `email`'.format(
                        email=email,
                    )
                )
            recipients_email_server_route[email_server].append(email)
        self.set_recipients_email_server_route(recipients_email_server_route)