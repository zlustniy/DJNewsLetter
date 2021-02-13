import mimetypes
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.message import SafeMIMEText
from django.template.loader import render_to_string
from django.utils.encoding import smart_str


class DJNewsLetterEmailMessage:
    CONTENT_SUBTYPE = 'html'
    DEFAULT_ATTACHMENT_MIME_TYPE = 'application/octet-stream'

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
        message.content_subtype = self.CONTENT_SUBTYPE
        return message

    def get_context(self):
        context = settings.DJNEWSLETTER_LETTER_CONTEXT
        context.update(self.context)
        return context

    def send(self, fail_silently=False):
        if self.template:
            self.message.body = render_to_string(self.template, self.get_context())

        return self.message.send(fail_silently)

    @staticmethod
    def create_mime_attachment(self, filename, content, mimetype=None, encoding=None):
        """
        Converts the filename, content, mimetype triple into a MIME attachment
        object. Use self.encoding when handling text attachments.
        """
        if mimetype is None:
            mimetype, _ = mimetypes.guess_type(filename)
            if mimetype is None:
                mimetype = self.DEFAULT_ATTACHMENT_MIME_TYPE

        basetype, subtype = mimetype.split('/', 1)
        if basetype == 'text':
            encoding = encoding or settings.DEFAULT_CHARSET
            attachment = SafeMIMEText(smart_str(content, settings.DEFAULT_CHARSET), subtype, encoding)
        else:
            # Encode non-text attachments with base64.
            attachment = MIMEBase(basetype, subtype)
            attachment.set_payload(content)
            encoders.encode_base64(attachment)

        if filename:
            try:
                filename.encode('ascii')
            except UnicodeEncodeError:
                filename = Header(filename, 'utf-8').encode()
            attachment.add_header('Content-Disposition', 'attachment', filename=filename)
            attachment.add_header('Content-ID', '<{}>'.format(filename))

        return attachment
