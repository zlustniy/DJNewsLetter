import mimetypes
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail.message import SafeMIMEText
from django.utils.encoding import smart_str
from djnewsletter.mail import DJNewsletterEmailMessage
from djnewsletter.models import EmailServers

DEFAULT_ATTACHMENT_MIME_TYPE = 'application/octet-stream'


def create_attachment(filename, content, mimetype=None, encoding=None):
    """
    Converts the filename, content, mimetype triple into a MIME attachment
    object. Use self.encoding when handling text attachments.
    """
    if mimetype is None:
        mimetype, _ = mimetypes.guess_type(filename)
        if mimetype is None:
            mimetype = DEFAULT_ATTACHMENT_MIME_TYPE

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


def get_content_subtype_and_body(message):
    if message.content_subtype != 'html':
        for body, content_subtype in getattr(message, 'alternatives', []):
            if content_subtype == 'text/html':
                return 'html', body

    return message.content_subtype, message.body


def send_email(**kwargs):
    recipients = kwargs.pop('to', [])
    email_servers = {}
    if 'email_server' in kwargs:
        email_server = kwargs.pop('email_server', None)
        is_ignore_site_id = True
    else:
        is_ignore_site_id = False
    for recipient in recipients:
        kwargs['to'] = [recipient]
        if not is_ignore_site_id:
            site_id = Site.objects.get_current().id
            domain = recipient.split('@')[1]
            key = '{}_{}'.format(domain, site_id)
            if key not in email_servers:
                email_servers[key] = EmailServers.objects.filter(
                    is_active=True,
                    sites__id=site_id,
                    preferred_domains__domain=domain,
                ).first() or EmailServers.objects.filter(
                    is_active=True,
                    sites__id=site_id,
                ).first()
            email_server = email_servers.get(key)

        if email_server:
            kwargs['custom_args'] = {'email_server': email_server}
        message = DJNewsletterEmailMessage(**kwargs)
        message.send()
