import base64
import json
import urllib.parse

import requests
from django.utils.encoding import force_text
from django.utils.functional import Promise

from djnewsletter.conf import settings


class LazyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Promise):
            return force_text(obj)
        return obj


class UniSenderAPIClient(object):
    def __init__(self, api_key, username):
        self.api_key = api_key
        self.username = username

        if not settings.DJNEWSLETTER_UNISENDER_URL:
            raise AttributeError('DJNEWSLETTER_UNISENDER_URL variable required.')

        self.url = urllib.parse.urljoin(
            settings.DJNEWSLETTER_UNISENDER_URL,
            '/ru/transactional/api/v1/email/send.json',
        )

    @staticmethod
    def _prepare_attachments(attachments):
        prepared_attachments = []
        for filename, content, mimetype in attachments:
            if not isinstance(content, bytes):
                content = content.encode('utf-8')
            prepared_attachments.append({
                'type': mimetype,
                'name': filename,
                'content': base64.b64encode(content).decode('utf-8'),
            })
        return prepared_attachments

    @staticmethod
    def _send_request(url, json_data):
        json_string = json.dumps(json_data, cls=LazyEncoder)
        response = requests.post(
            url=url,
            data=json_string,
            headers={
                'Content-Type': 'application/json',
            },
        )
        response_json = response.json()
        return response_json

    def send(self, subject, body_html, from_email, from_name, recipients, attachments, inline_attachments):
        message_data = {
            'subject': subject,
            'body': {
                'html': body_html,
            },
            'from_email': from_email,
            'is_transaction': 1,
            'track_links': 0,
            'track_read': 0,
            'recipients': [{'email': r} for r in recipients],
            'attachments': self._prepare_attachments(attachments),
            'inline_attachments': self._prepare_attachments(inline_attachments),
        }
        if from_name:
            message_data['from_name'] = from_name

        message = {
            'api_key': self.api_key,
            'username': self.username,
            'message': message_data,
        }

        return self._send_request(
            url=self.url,
            json_data=message,
        )
