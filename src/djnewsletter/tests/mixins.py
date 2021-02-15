from django.core import mail

from djnewsletter.models import EmailServers, Domains


class EmailTestsMixin:
    @staticmethod
    def send_simple_mail(
            subject='Subject here',
            message='Here is the <b>message</b>',
            from_email='from@example.com',
            recipient_list=None,
            fail_silently=False,
    ):
        if recipient_list is None:
            recipient_list = ['some@email.com']
        mail.send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=fail_silently,
        )

    @staticmethod
    def create_email_server(
            email_default_from='email@example.com',
            email_host='email_host',
            email_port=1234,
            email_username='email_username',
            email_password='email_password',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=50,
            sending_method='smtp',
            is_active=True,
    ):
        return EmailServers.objects.create(
            email_default_from=email_default_from,
            email_host=email_host,
            email_port=email_port,
            email_username=email_username,
            email_password=email_password,
            email_use_ssl=email_use_ssl,
            email_fail_silently=email_fail_silently,
            email_timeout=email_timeout,
            sending_method=sending_method,
            is_active=is_active,
        )

    @staticmethod
    def add_preferred_domain(domain, email_server):
        domain = Domains.objects.create(domain=domain)
        email_server.preferred_domains.add(domain)
