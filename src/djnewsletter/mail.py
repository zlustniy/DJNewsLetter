import mimetypes
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.message import SafeMIMEText
from django.template.loader import render_to_string
from django.utils.encoding import smart_str


class DJNewsLetterEmailMessage(EmailMessage):
    content_subtype = 'html'
    default_attachment_mime_type = 'application/octet-stream'

    def __init__(
            self,
            email_server=None,
            category=None,
            template=None,
            context=None,
            newsletter=None,
            inline_attachments=None,
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
        self.context = context or {}
        self.newsletter = newsletter
        self.inline_attachments = inline_attachments or []
        self.countdown = countdown
        self.eta = eta
        self.recipients_email_server_route = {}
        self.email_instance = None
        super().__init__(**kwargs)

    def copy_attributes_from_child_instance(self, child_instance):
        self.__dict__.update(child_instance.__dict__)

    def get_context(self):
        context = settings.DJNEWSLETTER_LETTER_CONTEXT
        context.update(self.context)
        return context

    def send(self, fail_silently=False):
        if self.template:
            self.body = render_to_string(self.template, self.get_context())

        return super().send(fail_silently)

    def create_mime_attachment(self, filename, content, mimetype=None, encoding=None):
        return self._create_attachment(filename, content, mimetype, encoding)

    def _create_attachment(self, filename, content, mimetype=None, encoding=None):
        """
        Converts the filename, content, mimetype triple into a MIME attachment
        object. Use self.encoding when handling text attachments.
        """
        if mimetype is None:
            mimetype, _ = mimetypes.guess_type(filename)
            if mimetype is None:
                mimetype = self.default_attachment_mime_type

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
