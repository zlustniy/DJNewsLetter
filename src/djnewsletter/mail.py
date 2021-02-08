from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

DEFAULT_ATTACHMENT_MIME_TYPE = 'application/octet-stream'


class DJNewsLetterEmailMessage(EmailMessage):
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
        super().__init__(**kwargs)
        # subject='',
        # body='',
        # from_email=None,
        # to=None,
        # bcc=None,
        # connection=None,
        # attachments=None,
        # headers=None,
        # cc=None,
        # reply_to=None,

    def get_context(self):
        context = getattr(settings, 'DJNEWSLETTER_CONTEXT', {})
        context.update(self.context)
        return context

    def send(self, fail_silently=False):
        if self.template:
            self.body = render_to_string(self.template, self.get_context())

        super().send(fail_silently)

    # def _create_attachment(self, filename, content, mimetype=None):
    #     from djnewsletter.helpers import create_attachment
    #     create_attachment(filename, content, mimetype=mimetype, encoding=self.encoding)
