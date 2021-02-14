from datetime import datetime, timedelta

import mock
from django.contrib.sites.models import Site
from django.core import mail
from django.db import transaction
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import gettext_lazy as _

from djnewsletter.analytics import Analytics
from djnewsletter.helpers import send_email
from djnewsletter.mail import DJNewsLetterEmailMessage
from djnewsletter.models import Emails, EmailServers, Domains, Bounced
from djnewsletter.unisender import UniSenderAPIClient


class SimpleEmailTest(TestCase):
    def test_send_email(self):
        mail.send_mail(
            subject='Subject here',
            message='Here is the <b>message</b>',
            from_email='from@example.com',
            recipient_list=['some@email.com'],
            fail_silently=False,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Subject here')
        self.assertEqual(Emails.objects.count(), 0)


class DummyBackendDJNewsletterEmailMessageTests(TestCase):
    def test_send_email(self):
        send_email(
            subject='Subject here',
            body='Here is the <b>message</b>',
            from_email='from@example.com',
            to=['some@email.com'],
        )

        emails = Emails.objects.all()
        self.assertEqual(emails.count(), 0)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Subject here')
        self.assertEqual(Emails.objects.count(), 0)


@override_settings(
    EMAIL_BACKEND='djnewsletter.backends.EmailBackend'
)
@mock.patch('djnewsletter.tasks.get_connection')
class EmailBackendDJNewsletterEmailMessageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        domain = Domains.objects.create(domain='email.com')
        cls.email_server = EmailServers.objects.create(
            email_default_from='email@example.com',
            email_host='some host',
            email_port=1234,
            email_username='lame',
            email_password='123',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=50,
            sending_method='smtp',
            is_active=True
        )
        cls.email_server.preferred_domains.add(domain)

    def test_send_email(self, mocked_get_connection):
        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            send_email(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com'],
                email_server=self.email_server,
                category='test_category'
            )

            mocked_get_connection.assert_called_once_with(backend='django.core.mail.backends.smtp.EmailBackend',
                                                          fail_silently=True, host='some host', password='123',
                                                          port=1234, timeout=50, use_ssl=True, use_tls=False,
                                                          username='lame')

            emails = Emails.objects.all()
            self.assertEqual(emails.count(), 1)

            email_instance = emails[0]
            self.assertEqual(email_instance.recipient, "['some@email.com']")
            self.assertEqual(email_instance.status, 'sent to user')

    def test_no_preferred_domains(self, mocked_get_connection):
        self.email_server.preferred_domains.clear()
        self.email_server.main = True
        self.email_server.save(update_fields=('main',))
        self.email_server.refresh_from_db()
        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            send_email(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com'],
                category='test_category'
            )

            mocked_get_connection.assert_called_once_with(backend='django.core.mail.backends.smtp.EmailBackend',
                                                          fail_silently=True, host='some host', password='123',
                                                          port=1234, timeout=50, use_ssl=True, use_tls=False,
                                                          username='lame')

            emails = Emails.objects.all()
            self.assertEqual(emails.count(), 1)

            email_instance = emails[0]
            self.assertEqual(email_instance.recipient, "['some@email.com']")
            self.assertEqual(email_instance.status, 'sent to user')

    def test_send_email_many_recipients(self, mocked_get_connection):
        domain_2 = Domains.objects.create(domain='email_2.com')
        domain_3 = Domains.objects.create(domain='email_3.com')  # Bounced
        domain_4 = Domains.objects.create(domain='email_4.com')
        email_server_2 = EmailServers.objects.create(
            email_default_from='email_2@example.com',
            email_host='some host email_2',
            email_port=1234,
            email_username='email_2',
            email_password='email_2',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=50,
            sending_method='smtp',
            is_active=True
        )
        email_server_2.preferred_domains.add(domain_2)
        email_server_2.preferred_domains.add(domain_3)
        email_server_2.preferred_domains.add(domain_4)
        Bounced.objects.create(email='some@email_3.com', event='bounce', eventDateTime=datetime.now())
        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            kw = dict(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com', 'some@email_2.com', 'some@email_3.com', 'some@email_4.com'],
                category='test_category',
                newsletter='newsletter title'
            )
            message = DJNewsLetterEmailMessage(**kw)
            message.send()

            self.assertEqual(mocked_get_connection.call_count, 2)
            mocked_get_connection.call_args_list[0].assert_called_with(
                backend='django.core.mail.backends.smtp.EmailBackend',
                fail_silently=True, host='some host', password='123',
                port=1234, timeout=50, use_ssl=True, use_tls=False,
                username='lame')
            mocked_get_connection.call_args_list[1].assert_called_with(
                backend='django.core.mail.backends.smtp.EmailBackend',
                fail_silently=True, host='some host email_2', password='email_2',
                port=1234, timeout=50, use_ssl=True, use_tls=False,
                username='email_2')

            self.assertEqual(Emails.objects.all().count(), 3)
            email_instance = Emails.objects.get(sender='email@example.com')
            self.assertEqual(email_instance.recipient, "['some@email.com']")

            email_instance = Emails.objects.get(sender='email_2@example.com')
            self.assertEqual(email_instance.recipient, "['some@email_2.com', 'some@email_4.com']")

            email_instance = Emails.objects.get(sender='did not send')
            self.assertEqual(email_instance.recipient, "['some@email_3.com']")

            Emails.objects.all().delete()
            del kw['newsletter']
            message = DJNewsLetterEmailMessage(**kw)
            message.send()
            self.assertEqual(Emails.objects.all().count(), 2)

            mocked_get_connection.call_args_list[2].assert_called_with(
                backend='django.core.mail.backends.smtp.EmailBackend',
                fail_silently=True, host='some host', password='123',
                port=1234, timeout=50, use_ssl=True, use_tls=False,
                username='lame')
            mocked_get_connection.call_args_list[3].assert_called_with(
                backend='django.core.mail.backends.smtp.EmailBackend',
                fail_silently=True, host='some host email_2', password='email_2',
                port=1234, timeout=50, use_ssl=True, use_tls=False,
                username='email_2')

            email_instance = Emails.objects.get(sender='email@example.com')
            self.assertEqual(email_instance.recipient, "['some@email.com']")

            email_instance = Emails.objects.get(sender='email_2@example.com')
            self.assertEqual(email_instance.recipient, "['some@email_2.com', 'some@email_3.com', 'some@email_4.com']")

    @override_settings(DJNEWSLETTER_UNISENDER_URL='http://test.url')
    @mock.patch('djnewsletter.unisender.UniSenderAPIClient._send_request')
    def test_send_email_many_recipients_by_unisender(self, mocked_unisender, mocked_get_connection):
        mocked_unisender.return_value = {
            'status': 'success'
        }
        domain_2 = Domains.objects.create(domain='email_2.com')
        domain_3 = Domains.objects.create(domain='email_3.com')  # Bounced
        domain_4 = Domains.objects.create(domain='email_4.com')
        email_server_2 = EmailServers.objects.create(
            api_key='api_key',
            api_username='api_username',
            api_from_email='from_unisender',
            sending_method='unisender_api',
            is_active=True
        )
        email_server_2.preferred_domains.add(domain_2)
        email_server_2.preferred_domains.add(domain_3)
        email_server_2.preferred_domains.add(domain_4)
        Bounced.objects.create(email='some@email_3.com', event='bounce', eventDateTime=datetime.now())
        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            kw = dict(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com', 'some@email_2.com', 'some@email_3.com', 'some@email_4.com'],
                category='test_category',
                newsletter='newsletter title'
            )
            message = DJNewsLetterEmailMessage(**kw)
            message.send()
            self.assertEqual(mocked_get_connection.call_count, 1)
            self.assertEqual(mocked_unisender.call_count, 1)

            self.assertEqual(Emails.objects.all().count(), 3)
            email_instance = Emails.objects.get(sender='email@example.com')
            self.assertEqual(email_instance.recipient, "['some@email.com']")

            email_instance = Emails.objects.get(sender='from_unisender')
            self.assertListEqual(
                mocked_unisender.call_args[1]['json_data']['message']['recipients'],
                [
                    {'email': 'some@email_2.com'},
                    {'email': 'some@email_4.com'},
                ],
            )
            self.assertEqual(email_instance.recipient, "['some@email_2.com', 'some@email_4.com']")
            self.assertEqual(email_instance.status, "{'status': 'success'}")

            email_instance = Emails.objects.get(sender='did not send')
            self.assertEqual(email_instance.recipient, "['some@email_3.com']")

            Emails.objects.all().delete()
            del kw['newsletter']
            message = DJNewsLetterEmailMessage(**kw)
            message.send()
            self.assertEqual(Emails.objects.all().count(), 2)

            email_instance = Emails.objects.get(sender='email@example.com')
            self.assertEqual(email_instance.recipient, "['some@email.com']")

            email_instance = Emails.objects.get(sender='from_unisender')
            self.assertListEqual(
                mocked_unisender.call_args[1]['json_data']['message']['recipients'],
                [
                    {'email': 'some@email_2.com'},
                    {'email': 'some@email_3.com'},
                    {'email': 'some@email_4.com'},
                ],
            )
            self.assertEqual(email_instance.recipient, "['some@email_2.com', 'some@email_3.com', 'some@email_4.com']")
            self.assertEqual(email_instance.status, "{'status': 'success'}")

    def test_send_email_to_first_server_with_site_id(self, mocked_get_connection):
        email_server_2 = EmailServers.objects.create(
            email_default_from='email_2@example.com',
            email_host='some host email_2',
            email_port=1230,
            email_username='email_2',
            email_password='email_2',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=True
        )
        email_server_3 = EmailServers.objects.create(
            email_default_from='email_3@example.com',
            email_host='some host email_3',
            email_port=1230,
            email_username='email_3',
            email_password='email_3',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=True
        )
        site = Site.objects.get_current()
        email_server_2.sites.add(site)
        email_server_3.sites.add(site)
        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            send_email(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com'],
                category='test_category'
            )
            mocked_get_connection.assert_called_once_with(backend='django.core.mail.backends.smtp.EmailBackend',
                                                          fail_silently=email_server_2.email_fail_silently,
                                                          host=email_server_2.email_host,
                                                          password=email_server_2.email_password,
                                                          port=email_server_2.email_port,
                                                          timeout=email_server_2.email_timeout,
                                                          use_ssl=email_server_2.email_use_ssl,
                                                          use_tls=email_server_2.email_use_tls,
                                                          username=email_server_2.email_username)

            emails = Emails.objects.all()
            self.assertEqual(emails.count(), 1)

            email_instance = emails[0]
            self.assertEqual(email_instance.recipient, "['some@email.com']")
            self.assertEqual(email_instance.status, 'sent to user')

    def test_send_email_to_default_server_if_site_not_found_and_without_preferred_domains_and_default_server_without_site(
            self, mocked_get_connection):
        self.email_server.preferred_domains.clear()
        email_server_2 = EmailServers.objects.create(
            email_default_from='email_2@example.com',
            email_host='some host email_2',
            email_port=1230,
            email_username='email_2',
            email_password='email_2',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=False
        )
        site = Site.objects.get_current()
        email_server_2.sites.add(site)

        email_server3 = EmailServers.objects.create(
            email_default_from='email3@example.com',
            email_host='some email_server3',
            email_port=4321,
            email_username='lameemail_server3',
            email_password='4321',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=70,
            sending_method='smtp',
            is_active=True,
            main=True
        )

        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            send_email(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com'],
                category='test_category'
            )
            mocked_get_connection.assert_called_once_with(backend='django.core.mail.backends.smtp.EmailBackend',
                                                          fail_silently=email_server3.email_fail_silently,
                                                          host=email_server3.email_host,
                                                          password=email_server3.email_password,
                                                          port=email_server3.email_port,
                                                          timeout=email_server3.email_timeout,
                                                          use_ssl=email_server3.email_use_ssl,
                                                          use_tls=email_server3.email_use_tls,
                                                          username=email_server3.email_username)
            emails = Emails.objects.all()
            self.assertEqual(emails.count(), 1)

            email_instance = emails[0]
            self.assertEqual(email_instance.recipient, "['some@email.com']")
            self.assertEqual(email_instance.status, 'sent to user')

    def test_send_email_to_default_server_if_site_not_found_and_with_preferred_domains(self, mocked_get_connection):
        email_server_2 = EmailServers.objects.create(
            email_default_from='email_2@example.com',
            email_host='some host email_2',
            email_port=1230,
            email_username='email_2',
            email_password='email_2',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=False
        )
        site = Site.objects.get_current()
        email_server_2.sites.add(site)

        email_server3 = EmailServers.objects.create(
            email_default_from='email3@example.com',
            email_host='some email_server3',
            email_port=4321,
            email_username='lameemail_server3',
            email_password='4321',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=70,
            sending_method='smtp',
            is_active=True,
            main=True
        )

        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            send_email(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com'],
                category='test_category'
            )
            mocked_get_connection.assert_called_once_with(backend='django.core.mail.backends.smtp.EmailBackend',
                                                          fail_silently=self.email_server.email_fail_silently,
                                                          host=self.email_server.email_host,
                                                          password=self.email_server.email_password,
                                                          port=self.email_server.email_port,
                                                          timeout=self.email_server.email_timeout,
                                                          use_ssl=self.email_server.email_use_ssl,
                                                          use_tls=self.email_server.email_use_tls,
                                                          username=self.email_server.email_username)
            emails = Emails.objects.all()
            self.assertEqual(emails.count(), 1)

            email_instance = emails[0]
            self.assertEqual(email_instance.recipient, "['some@email.com']")
            self.assertEqual(email_instance.status, 'sent to user')

    def test_send_any_email_to_site(self, mocked_get_connection):
        email_server_2 = EmailServers.objects.create(
            email_default_from='email_2@example.com',
            email_host='some host email_2',
            email_port=1230,
            email_username='email_2',
            email_password='email_2',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=True
        )
        email_server_3 = EmailServers.objects.create(
            email_default_from='email_3@example.com',
            email_host='some host email_3',
            email_port=1230,
            email_username='email_3',
            email_password='email_3',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=True
        )
        site = Site.objects.get_current()
        email_server_2.sites.add(site)
        email_server_3.sites.add(site)
        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            send_email(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com', 'get@email.com'],
                category='test_category'
            )
            for server in mocked_get_connection.call_args_list:
                server.assert_called_with(backend='django.core.mail.backends.smtp.EmailBackend',
                                          fail_silently=email_server_2.email_fail_silently,
                                          host=email_server_2.email_host,
                                          password=email_server_2.email_password,
                                          port=email_server_2.email_port,
                                          timeout=email_server_2.email_timeout,
                                          use_ssl=email_server_2.email_use_ssl,
                                          use_tls=email_server_2.email_use_tls,
                                          username=email_server_2.email_username)

            self.assertEqual(Emails.objects.count(), 1)

            email_instance = Emails.objects.first()
            self.assertEqual(email_instance.recipient, "['some@email.com', 'get@email.com']")
            self.assertEqual(email_instance.status, 'sent to user')

    def test_send_any_email_on_site_id_or_site_id_and_preferred(self, mocked_get_connection):
        email_server_2 = EmailServers.objects.create(
            email_default_from='email_2@example.com',
            email_host='some host email_2',
            email_port=1230,
            email_username='email_2',
            email_password='email_2',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=True
        )
        email_server_3 = EmailServers.objects.create(
            email_default_from='email_3@example.com',
            email_host='some host email_3',
            email_port=1230,
            email_username='email_3',
            email_password='email_3',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=True
        )
        site = Site.objects.get_current()
        email_server_2.sites.add(site)
        email_server_3.sites.add(site)
        domain = Domains.objects.create(domain='email_preferred.com')
        email_server_3.preferred_domains.add(domain)
        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            send_email(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com', 'some2@email_preferred.com', 'some3@data.ru', 'some4@email_preferred.com'],
                category='test_category'
            )
        emails = Emails.objects.all()
        self.assertEqual(mocked_get_connection.call_args_list[0].kwargs['host'], email_server_2.email_host)
        self.assertEqual(mocked_get_connection.call_args_list[1].kwargs['host'], email_server_3.email_host)
        self.assertEqual(emails.count(), 2)
        self.assertEqual(emails[0].recipient, "['some@email.com', 'some3@data.ru']")
        self.assertEqual(emails[1].recipient, "['some2@email_preferred.com', 'some4@email_preferred.com']")

    @override_settings(SITE_ID=3)
    def test_site_not_found(self, mocked_get_connection):
        email_server_2 = EmailServers.objects.create(
            email_default_from='email_2@example.com',
            email_host='some host email_2',
            email_port=1230,
            email_username='email_2',
            email_password='email_2',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=True
        )
        site = Site.objects.get(id=1)
        email_server_2.sites.add(site)
        with self.assertRaises(Site.DoesNotExist):
            with mock.patch.object(transaction, 'on_commit', lambda f: f()):
                send_email(
                    subject='Subject here',
                    body='Here is the <b>message</b>.',
                    to=['some@email.com', 'some2@email_preferred.com', 'some3@data.ru', 'some4@email_preferred.com'],
                    category='test_category'
                )
        self.assertEqual(Emails.objects.count(), 0)

    def test_ignore_site_id_if_server_in_email(self, mocked_get_connection):
        email_server_2 = EmailServers.objects.create(
            email_default_from='email_2@example.com',
            email_host='some host email_2',
            email_port=1230,
            email_username='email_2',
            email_password='email_2',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=True
        )
        email_server_3 = EmailServers.objects.create(
            email_default_from='email_3@example.com',
            email_host='some host email_3',
            email_port=1230,
            email_username='email_3',
            email_password='email_3',
            email_use_ssl=True,
            email_fail_silently=True,
            email_timeout=60,
            sending_method='smtp',
            is_active=True
        )
        site = Site.objects.get_current()
        email_server_2.sites.add(site)
        email_server_3.sites.add(site)
        domain = Domains.objects.create(domain='email_preferred.com')
        email_server_3.preferred_domains.add(domain)
        with mock.patch.object(transaction, 'on_commit', lambda f: f()):
            send_email(
                subject='Subject here',
                body='Here is the <b>message</b>.',
                to=['some@email.com', 'some2@email_preferred.com', 'some3@data.ru', 'some4@email_preferred.com'],
                email_server=self.email_server,
                category='test_category'
            )
        self.assertEqual(mocked_get_connection.call_count, 1)
        self.assertEqual(mocked_get_connection.call_args_list[0].kwargs['host'], self.email_server.email_host)
        self.assertEqual(Emails.objects.count(), 1)
        email = Emails.objects.first()
        self.assertEqual(
            email.recipient,
            "['some@email.com', 'some2@email_preferred.com', 'some3@data.ru', 'some4@email_preferred.com']",
        )


@override_settings(DJNEWSLETTER_UNISENDER_URL='http://test.url')
@mock.patch('djnewsletter.unisender.requests.post')
class UniSenderAPIClientTestCase(TestCase):
    def test_can_pass_lazy_args_to_send_email_func(self, mock_requests_post):
        unisender_api = UniSenderAPIClient(
            api_key='api_key',
            username='api_username',
        )

        unisender_api.send(
            subject=_('тест'),
            body_html='body',
            from_email='example@email.com',
            from_name='from_name',
            recipients=['example@email.com'],
            attachments=[],
            inline_attachments=[],
        )

        mock_requests_post.assert_called_once()

    @override_settings(DJNEWSLETTER_UNISENDER_URL=None)
    def test_when_unisender_url_setting_not_set(self, mock_requests_post):
        with self.assertRaisesMessage(AttributeError, 'DJNEWSLETTER_UNISENDER_URL variable required.'):
            UniSenderAPIClient(
                api_key='api_key',
                username='api_username',
            )


class AnalyticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.smtp = EmailServers.objects.create(
            sending_method='smtp',
        )
        cls.unisender = EmailServers.objects.create(
            sending_method='unisender_api',
        )
        cls.recipient = '[email@email.com]'

    def _create_email(self, email_server, recipient, status):
        return Emails.objects.create(
            type='html',
            sender='send',
            recipient=recipient,
            body='body',
            subject='subject',
            used_server=email_server,
            status=status
        )

    def _shift_create_datetime(self, email, days_offset):
        email.createDateTime = email.createDateTime - timedelta(days=days_offset)
        email.save(update_fields=('createDateTime',))

    def test_get_email_stats(self):
        self._create_email(self.smtp, self.recipient, 'sent to user')
        self._create_email(self.smtp, '[email2@email.com, email@email.com]', 'sent to user')
        self._create_email(self.smtp, '[email2@email.com]', 'sent to user')
        email_2_day_ago = self._create_email(self.smtp, self.recipient, 'sent to user')
        self._shift_create_datetime(email_2_day_ago, 2)
        unisender_response = {
            'job_id': 'xxx-xxx',
            'status': 'success',
            'emails': self.recipient
        }
        email_6_day_ago = self._create_email(self.unisender, self.recipient, str(unisender_response))
        self._shift_create_datetime(email_6_day_ago, 6)
        excepted_dict = {
            'today': {
                'success': 2,
                'error': 0,
                'total': 2,
            },
            5: {
                'success': 3,
                'error': 0,
                'total': 3,
            },
            '30': {
                'success': 4,
                'error': 0,
                'total': 4,
            },
        }
        analytics = Analytics(excepted_dict.keys())
        self.assertDictEqual(excepted_dict, analytics.get_email_stats('email@email.com'))
        analytics = Analytics(['today', 5, '30'])
        self.assertDictEqual(excepted_dict, analytics.get_email_stats('email@email.com'))

    def test_get_email_stats_with_errors(self):
        self._create_email(self.smtp, self.recipient, 'sent to user')
        self._create_email(self.smtp, '[email2@email.com, email@email.com]', 'sent to user')
        self._create_email(self.smtp, self.recipient, 'sent to queue')
        self._create_email(self.unisender, self.recipient, str({
            'job_id': 'xxx-xxx',
            'status': 'success',
            'emails': self.recipient
        }))
        self._create_email(self.unisender, self.recipient, str({
            'job_id': 'xxx-xxx',
        }))
        self._create_email(self.unisender, self.recipient, str({
            'job_id': 'xxx-xxx',
            'status': 'success',
            'emails': '[email2@email.com]',
            'failed_emails': {
                'email@email.com': 'unsubscribed'
            }
        }))
        analytics = Analytics(['today'])
        excepted_today_dict = {
            'success': 3,
            'error': 3,
            'total': 6,
        }
        self.assertDictEqual(excepted_today_dict, analytics.get_email_stats('email@email.com')['today'])
