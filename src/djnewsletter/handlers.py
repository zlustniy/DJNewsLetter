import collections
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives

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


class DJNewsLetterSendingHandlers:
    def __init__(self):
        """
        Пока у нас один тип сообщений - DJNewsLetterEmailMessage.
        Отличия могут быть только во вложенном (родительском) объекте - DJNewsLetterEmailMessage.
        Отличия вызваны разными точками входа в DJNewsletterBackend().send_messages(email_messages):
        - метод send_email;
        - отправка формы из CMS;
        - другие.
        """
        self.handlers = {
            DJNewsLetterEmailMessage: DJNewsLetterEmailMessageHandler,
            EmailMultiAlternatives: EmailMultiAlternativesHandler,
        }

    def get_handler(self, email_message):
        handler = self.handlers.get(type(email_message), DefaultEmailMessageHandler)
        return handler(email_message)


class BaseEmailMessageHandler:
    def __init__(self, email_message):
        self.email_message = email_message
        self.site = self.get_site()

    def handle(self):
        raise NotImplementedError

    def handle_email_server(self):
        recipients_email_server_route = self.get_recipients_email_server_route()
        self.email_message.recipients_email_server_route = recipients_email_server_route

    def unify_email_message(self):
        djnewsletter_email_message = DJNewsLetterEmailMessage()
        djnewsletter_email_message.copy_attributes_from_child_instance(self.email_message)
        self.email_message = djnewsletter_email_message

    def get_email_servers(self, domain):
        email_servers = []
        if self.site is not None:
            email_servers.extend([
                EmailServers.objects.filter(
                    is_active=True,
                    sites=self.site,
                    preferred_domains__domain=domain,
                ),
                EmailServers.objects.filter(
                    is_active=True,
                    sites=self.site,
                ),
            ])
        email_servers.extend([
            EmailServers.objects.filter(
                is_active=True,
                preferred_domains__domain=domain,
                sites__isnull=True,
            ),
            EmailServers.objects.filter(
                main=True,
                is_active=True,
                sites__isnull=True,
            ),
        ])
        return email_servers

    def get_recipients_email_server_route(self):
        recipients_email_server_route = collections.defaultdict(list)
        email_servers_for_domains_cache = {}
        for email in self.email_message.to:
            domain = email.split('@')[1]
            cached_email_server_for_domain = email_servers_for_domains_cache.get(domain, None)
            if cached_email_server_for_domain:
                recipients_email_server_route[cached_email_server_for_domain].append(email)
                continue

            email_server = next(
                (
                    email_server.first() for email_server in self.get_email_servers(domain)
                    if email_server.first() is not None
                ),
                None,
            )

            if not email_server:
                raise SuitableEmailServerNotFoundException(
                    'Ошибка выбора EmailServers для адреса: `{email}`'.format(
                        email=email,
                    )
                )
            recipients_email_server_route[email_server].append(email)
            email_servers_for_domains_cache[domain] = email_server
        return recipients_email_server_route

    @staticmethod
    def get_site():
        if getattr(settings, 'SITE_ID', None):
            return Site.objects.get_current()
        return None

    def create_email(self, sender, recipients, status, used_server=None, save=True):
        email = Emails(
            type=self.email_message.content_subtype,
            sender=sender,
            recipient=recipients,
            body=self.email_message.body,
            subject=self.email_message.subject,
            newsletter=self.email_message.newsletter,
            status=status,
            used_server=used_server
        )
        if save:
            email.save()
        return email


class DefaultEmailMessageHandler(BaseEmailMessageHandler):
    def handle(self):
        self.unify_email_message()
        self.handle_email_server()
        return self.email_message


class EmailMultiAlternativesHandler(BaseEmailMessageHandler):
    def handle(self):
        self.rewrite_content_subtype_and_body()
        self.unify_email_message()
        self.handle_email_server()
        return self.email_message

    def rewrite_content_subtype_and_body(self):
        """Работа с alternative content types."""
        for body, content_subtype in self.email_message.alternatives:
            if content_subtype == 'text/html':
                self.email_message.content_subtype = 'html'
                self.email_message.body = body
                break


class DJNewsLetterEmailMessageHandler(BaseEmailMessageHandler):
    def handle(self):
        self.handle_bounced()
        self.handle_unsubscribe()
        self.handle_interval_sending()
        self.handle_email_server()
        return self.email_message

    def handle_bounced(self):
        if self.email_message.newsletter:
            bounced_emails = Bounced.objects.filter(
                email__in=self.email_message.to,
                event__in=['bounce', 'dropped', 'spamreport'],
            ).values_list('email', flat=True)
            if bounced_emails.exists():
                bounced_emails = list(bounced_emails)
                self.email_message.to = list(
                    filter(lambda email: email not in bounced_emails, self.email_message.to)
                )
                self.create_email(
                    sender='did not send',
                    recipients=bounced_emails,
                    status='There were problems with the recipient this letter previously',
                )

    def handle_unsubscribe(self):
        if self.email_message.newsletter:
            if 'List-Unsubscribe' in self.email_message.extra_headers:
                unsubscribers_emails = Unsubscribers.objects.filter(
                    email__in=self.email_message.to,
                    newsletter=self.email_message.newsletter,
                ).values_list('email', flat=True)
                if unsubscribers_emails.exists():
                    unsubscribers_emails = list(unsubscribers_emails)
                    self.email_message.to = list(
                        filter(lambda email: email not in unsubscribers_emails, self.email_message.to)
                    )
                    self.create_email(
                        sender='did not send',
                        recipients=unsubscribers_emails,
                        status='Don\'t sent, because user is unsubscribe',
                    )

    def handle_interval_sending(self):
        if self.email_message.newsletter:
            interval_sending_to_recipient = settings.DJNEWSLETTER_INTERVAL_SENDING_TO_RECIPIENT
            if interval_sending_to_recipient is not None:
                already_sent_emails = Emails.objects.filter(
                    recipient__in=self.email_message.to,
                    newsletter=self.email_message.newsletter,
                    status_hash='3b0cea37664e25d1060e6306dcdcef51',  # 'sent to user' hash
                    changeDateTime__gt=datetime.now() - timedelta(
                        hours=interval_sending_to_recipient,
                    )
                ).values_list('recipient', flat=True)
                if already_sent_emails.exists():
                    already_sent_emails = list(already_sent_emails)
                    self.email_message.to = list(
                        filter(lambda email: email not in already_sent_emails, self.email_message.to)
                    )
                    self.create_email(
                        sender='did not send',
                        recipients=already_sent_emails,
                        status='Letters are sent too frequently',
                    )

    def handle_email_server(self):
        if self.email_message.email_server:
            self.email_message.recipients_email_server_route = {
                self.email_message.email_server: self.email_message.to,
            }
            return

        super(DJNewsLetterEmailMessageHandler, self).handle_email_server()
