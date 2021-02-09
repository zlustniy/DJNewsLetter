from celery.task import task, current
from django.conf import settings
from django.core.mail import get_connection

from djnewsletter.helpers import create_attachment, get_content_subtype_and_body
from djnewsletter.models import Emails
from djnewsletter.unisender import UniSenderAPIClient

MAX_RETRIES = 5
COUNTDOWN = 60  # seconds
BACKEND = getattr(settings, 'CELERY_EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')


@task(queue='emails', time_limit=300)
def send_by_smtp(message, **kwargs):
    email_instance = Emails.objects.get(pk=kwargs['email_pk'])
    try:
        server_settings = message.email_server.get_smtp_server_settings()
        if server_settings:
            fail_silently = server_settings.pop('fail_silently', False)
            conn = get_connection(backend=BACKEND, fail_silently=fail_silently, **server_settings)
        else:
            conn = get_connection(backend=BACKEND)

        inline_attachments = getattr(message, 'inline_attachments', [])
        message.attachments.extend(inline_attachments)
        for idx, attachment in enumerate(message.attachments):
            if isinstance(attachment, tuple) and len(attachment) == 3:
                message.attachments[idx] = create_attachment(*attachment)

        print(message)
        conn.send_messages([message])
        email_instance.status = 'sent to user'
    except Exception as e:
        email_instance.status = str(e)
        send_by_smtp.retry(max_retries=MAX_RETRIES, countdown=COUNTDOWN * current.request.retries, exc=e)
    finally:
        email_instance.save()


@task(queue='emails', time_limit=300)
def send_by_unisender(message, **kwargs):
    email_instance = Emails.objects.get(pk=kwargs['email_pk'])
    email_server = message.custom_args.get('email_server', None)
    if not email_server:
        raise Exception('Email send service unavailable. Active server doesn\'t exists')

    unisender_api = UniSenderAPIClient(
        api_key=email_server.api_key,
        username=email_server.api_username)

    try:
        _, body = get_content_subtype_and_body(message)

        inline_attachments = getattr(message, 'inline_attachments', [])
        response_json = unisender_api.send(
            subject=message.subject,
            body_html=body,
            from_email=message.from_email or email_server.api_default_from,
            from_name=email_server.api_from_name,
            recipients=message.to,
            attachments=message.attachments,
            inline_attachments=inline_attachments,
        )
    except Exception as e:
        email_instance.status = str(e)
        send_by_unisender.retry(max_retries=MAX_RETRIES, countdown=COUNTDOWN * current.request.retries, exc=e)
    else:
        email_instance.status = str(response_json)
        email_instance.email_remote_id = response_json.get('job_id')
    finally:
        email_instance.save()
        email_instance.save(update_fields=['status', 'email_remote_id'])
