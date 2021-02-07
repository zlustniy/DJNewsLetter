from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

DEFAULT_ATTACHMENT_MIME_TYPE = 'application/octet-stream'


class DJNewsletterEmailMessage(EmailMessage):
    content_subtype = 'html'

    def __init__(self, **kwargs):
        self.custom_args = kwargs.pop('custom_args', {})
        self.category = kwargs.pop('category', None)
        self.template = kwargs.pop('template', None)
        self.context = kwargs.pop('context', {})
        self.attachment_paths = kwargs.pop('attachment_paths', [])
        self.newsletter = kwargs.pop('newsletter', None)
        self.server_settings = kwargs.pop('server_settings', {})
        self.api_key = kwargs.pop('api_key', None)
        self.countdown = kwargs.pop('countdown', None)
        self.eta = kwargs.pop('eta', None)
        self.inline_attachments = kwargs.pop('inline_attachments', [])
        super(DJNewsletterEmailMessage, self).__init__(**kwargs)

    def get_context(self):
        context = getattr(settings, 'DJNEWSLETTER_CONTEXT', {})
        context.update(self.context)
        return context

    def send(self, fail_silently=False):
        if self.template:
            self.body = render_to_string(self.template, self.get_context())

        list(map(self.attach_file, self.attachment_paths))

        super(DJNewsletterEmailMessage, self).send(fail_silently)

    def _create_attachment(self, filename, content, mimetype=None):
        from djnewsletter.helpers import create_attachment
        create_attachment(filename, content, mimetype=mimetype, encoding=self.encoding)
