import collections
from gettext import gettext

from django.contrib.sites.models import Site

from .exceptions import (
    SuitableEmailServerNotFoundException,
)
from .mail import (
    DJNewsLetterEmailMessage,
)
from .models import (
    Bounced,
    EmailServers, Emails,
)


class MessageHandler:
    def __init__(self):
        self.handlers = {
            DJNewsLetterEmailMessage: DJNewsLetterEmailMessageHandler,
        }

    def handle(self, message):
        message_handler = self.handlers.get(type(message), DefaultEmailMessageHandler)
        message = message_handler(message).handle()
        return message


class BaseEmailMessageHandler:
    def __init__(self, message):
        self.errors = []
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

    def create_email_instance(self, **kwargs):
        return Emails(kwargs)


class DefaultEmailMessageHandler(BaseEmailMessageHandler):
    def handle(self):
        return self.message


class DJNewsLetterEmailMessageHandler(BaseEmailMessageHandler):
    def handle(self):
        self.handle_bounced()
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
                self.errors.append(
                    gettext(
                        'Ранее были проблемы с получателями: `{bounced_emails}`. '
                        'Они исключены из списка получателей.'.format(
                            bounced_emails=bounced_emails,
                        )
                    )
                )
        return self.message

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
            email_server = next([
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
            ])
            if not email_server:
                raise SuitableEmailServerNotFoundException(
                    gettext(
                        'Ошибка выбора EmailServers для адреса: `email`'.format(
                            email=email,
                        )
                    )
                )
            recipients_email_server_route[email_server].append(email)
        self.set_recipients_email_server_route(recipients_email_server_route)
