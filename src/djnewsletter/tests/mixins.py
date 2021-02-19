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
    def create_smtp_email_server(
            email_default_from='email@example.com',
            email_host='email_host',
            email_port=1234,
            email_username='email_username',
            email_password='email_password',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=50,
            is_active=True,
            main=False,
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
            sending_method='smtp',
            is_active=is_active,
            main=main,
        )

    @staticmethod
    def create_unisender_email_server(
            api_key='api_key',
            api_username='api_username',
            api_from_email='from_unisender',
            is_active=True,
    ):
        return EmailServers.objects.create(
            api_key=api_key,
            api_username=api_username,
            api_from_email=api_from_email,
            sending_method='unisender_api',
            is_active=is_active,
        )

    @staticmethod
    def add_preferred_domain(domain, email_server):
        domain = Domains.objects.create(domain=domain)
        email_server.preferred_domains.add(domain)

    @staticmethod
    def get_mock_called(
            backend='django.core.mail.backends.smtp.EmailBackend',
            fail_silently=True,
            host='email_host',
            password='email_password',
            port=1234,
            timeout=50,
            use_ssl=True,
            use_tls=False,
            username='email_username',
    ):
        return dict(
            backend=backend,
            fail_silently=fail_silently,
            host=host,
            password=password,
            port=port,
            timeout=timeout,
            use_ssl=use_ssl,
            use_tls=use_tls,
            username=username,
        )
