from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string


class DJNewsLetterEmailMessage:
    content_subtype = 'html'

    def __init__(
            self,
            email_server=None,
            category=None,
            template=None,
            context={},
            newsletter=None,
            inline_attachments=[],  # Подумать что делать с ними
            server_settings={},  # Maybe need remove
            api_key={},  # Maybe need remove
            countdown=None,
            eta=None,
            message=None,
            **kwargs,
    ):
        """

        @param email_server:
        @param category:
        @param template:
        @param context:
        @param newsletter:
        @param inline_attachments:
        @param server_settings:
        @param api_key:
        @param countdown:
        @param eta:
        @param kwargs: Значения для EmailMessage
        """
        self.email_server = email_server
        self.category = category
        self.template = template
        self.context = context
        self.newsletter = newsletter
        self.inline_attachments = inline_attachments
        self.server_settings = server_settings
        self.api_key = api_key
        self.countdown = countdown
        self.eta = eta
        if message is None:
            message = EmailMessage(**kwargs)
        self.message = self.prepare_message(message)
        self.recipients_email_server_route = {}
        self.email_instance = None

    @property
    def to(self):
        return self.message.to

    def prepare_message(self, message):
        message.content_subtype = self.content_subtype
        return message

    def get_context(self):
        context = settings.DJNEWSLETTER_LETTER_CONTEXT
        context.update(self.context)
        return context

    def send(self, fail_silently=False):
        if self.template:
            self.message.body = render_to_string(self.template, self.get_context())

        return self.message.send(fail_silently)
