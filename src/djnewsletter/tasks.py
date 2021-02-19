from celery.task import task, current
from django.core.mail import get_connection

from .conf import (
    BACKEND,
    MAX_RETRIES,
    COUNTDOWN,
)
from .unisender import (
    UniSenderAPIClient,
)


@task(queue='emails', time_limit=300)
def send_by_smtp(email_message):
    try:
        server_settings = email_message.email_server.get_smtp_server_settings()
        if server_settings:
            conn = get_connection(backend=BACKEND, **server_settings)
        else:
            conn = get_connection(backend=BACKEND)

        email_message.attachments.extend(
            email_message.inline_attachments
        )
        for idx, attachment in enumerate(email_message.attachments):
            if isinstance(attachment, tuple) and len(attachment) == 3:
                email_message.attachments[idx] = email_message.create_mime_attachment(*attachment)

        conn.send_messages([email_message])
        email_message.email_instance.status = 'sent to user'
    except Exception as e:
        email_message.email_instance.status = str(e)
        send_by_smtp.retry(max_retries=MAX_RETRIES, countdown=COUNTDOWN * current.request.retries, exc=e)
    finally:
        email_message.email_instance.save(
            update_fields=(
                'status',
            ),
        )


@task(queue='emails', time_limit=300)
def send_by_unisender(email_message):
    unisender_api = UniSenderAPIClient(
        api_key=email_message.email_server.api_key,
        username=email_message.email_server.api_username,
    )
    try:
        response_json = unisender_api.send(
            subject=email_message.subject,
            body_html=email_message.body,
            from_email=email_message.from_email,
            from_name=email_message.email_server.api_from_name,
            recipients=email_message.to,
            attachments=email_message.attachments,
            inline_attachments=email_message.inline_attachments,
        )
    except Exception as e:
        email_message.email_instance.status = str(e)
        send_by_unisender.retry(max_retries=MAX_RETRIES, countdown=COUNTDOWN * current.request.retries, exc=e)
    else:
        email_message.email_instance.status = str(response_json)
        email_message.email_instance.email_remote_id = response_json.get('job_id')
    finally:
        email_message.email_instance.save()
        email_message.email_instance.save(
            update_fields=(
                'status',
                'email_remote_id',
            ),
        )
