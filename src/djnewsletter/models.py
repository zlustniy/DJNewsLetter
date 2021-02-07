from hashlib import md5

from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models


class Unsubscribers(models.Model):
    email = models.EmailField(max_length=255, verbose_name='email')
    newsletter = models.CharField(max_length=20)
    unsubscribeDatetime = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Unsubscribers'


class Emails(models.Model):
    type = models.CharField(max_length=5)
    sender = models.EmailField(max_length=255)
    recipient = models.EmailField(max_length=255)
    body = models.TextField()
    subject = models.CharField(max_length=256)
    newsletter = models.CharField(max_length=20, null=True, blank=True)
    status = models.TextField()
    createDateTime = models.DateTimeField(auto_now_add=True)
    changeDateTime = models.DateTimeField(auto_now=True)
    status_hash = models.CharField(max_length=32, null=True, blank=True,
                                   verbose_name='Хеш статуса для безгеморройного индексирования')
    used_server = models.ForeignKey('djnewsletter.EmailServers', on_delete=models.CASCADE, null=True, blank=True)
    email_remote_id = models.CharField(max_length=128, null=True, blank=True)

    def save(self, **kwargs):
        self.status_hash = md5(self.status.encode('utf-8')).hexdigest()
        super(Emails, self).save(**kwargs)

    class Meta:
        verbose_name_plural = 'Emails'
        indexes = [
            models.Index(fields=['-createDateTime', ]),
            models.Index(fields=['-changeDateTime', ]),
        ]


class Bounced(models.Model):
    email = models.CharField(max_length=100, db_index=True)
    event = models.CharField(max_length=255, db_index=True)
    eventDateTime = models.DateTimeField()
    category = models.CharField(max_length=255, null=True, blank=True)
    reason = models.CharField(max_length=255, null=True, blank=True)
    createDateTime = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Bounceds'


class Domains(models.Model):
    domain = models.CharField(verbose_name='Домен', max_length=100, null=False, blank=False)

    class Meta:
        verbose_name_plural = 'Domains'

    def __str__(self):
        return self.domain


class EmailServers(models.Model):
    SENDING_METHOD_CHOICES = (
        ('smtp', 'SMTP сервер'),
        ('unisender_api', 'UniSender API'),
    )

    email_default_from = models.CharField(verbose_name='from:', max_length=100, null=True, blank=True)
    email_host = models.CharField(verbose_name='хост', max_length=100, null=True, blank=True)
    email_port = models.IntegerField(verbose_name='порт', null=True, blank=True)
    email_username = models.CharField(verbose_name='имя пользователя', max_length=100, null=True, blank=True)
    email_password = models.CharField(verbose_name='пароль', max_length=100, null=True, blank=True)
    email_use_ssl = models.BooleanField(verbose_name='использовать SSL', default=False)
    email_use_tls = models.BooleanField(verbose_name='использовать TLS', default=False)
    email_fail_silently = models.BooleanField(default=False, verbose_name='Тихое подавление ошибок')
    email_timeout = models.IntegerField(verbose_name='тайм-аут', null=True, blank=True)
    email_ssl_certfile = models.FileField(max_length=500, upload_to='EmailServers/certfile/%Y/%m/%d',
                                          verbose_name='Сертификат', null=True, blank=True)
    email_ssl_keyfile = models.FileField(max_length=500, upload_to='EmailServers/keyfile/%Y/%m/%d',
                                         verbose_name='Файл ключа', null=True, blank=True)
    api_key = models.CharField(verbose_name='API KEY', max_length=255, null=True, blank=True)
    api_username = models.CharField(
        verbose_name='Имя пользователя для авторизации в API', max_length=128, null=True, blank=True)
    api_from_email = models.CharField(
        verbose_name='Email адрес для отправки через API', max_length=128, null=True, blank=True)
    api_from_name = models.CharField(
        verbose_name='Имя перед адресом для отправки через API', max_length=128, null=True, blank=True)
    sending_method = models.CharField(
        max_length=32, verbose_name='Способ отправки писем', choices=SENDING_METHOD_CHOICES, default='smtp')
    main = models.BooleanField(default=False, verbose_name='Основной сервер')
    is_active = models.BooleanField(default=False, verbose_name='Сервер активен')
    preferred_domains = models.ManyToManyField(Domains, verbose_name='Предпочтительней для доменов', blank=True)
    sites = models.ManyToManyField(Site, verbose_name='Сайт', blank=True)

    class Meta:
        verbose_name_plural = 'EmailServers'

    def __str__(self):
        return "{} (sending_method:{})".format(self.email_host, self.get_sending_method_display())

    def get_smtp_server_settings(self):
        server_settings = {
            'host': self.email_host,
            'port': self.email_port,
            'username': self.email_username,
            'password': self.email_password,
            'use_ssl': self.email_use_ssl,
            'use_tls': self.email_use_tls,
            'fail_silently': self.email_fail_silently,
            'timeout': self.email_timeout,
        }

        if self.email_ssl_certfile:
            server_settings['ssl_certfile'] = self.email_ssl_certfile.path

        if self.email_ssl_keyfile:
            server_settings['ssl_keyfile'] = self.email_ssl_keyfile.path

        for key, value in list(server_settings.items()):
            if value == '':
                server_settings[key] = None

        return server_settings

    def clean(self):
        required_fields_mapping = {
            'smtp': [
                'email_host',
                'email_port',
                'email_username',
                'email_password',
                'email_use_ssl',
                'email_use_tls',
                'email_default_from',
                'email_fail_silently',
            ],
            # 'sendgrid_api': [],
            'unisender_api': [
                'api_key',
                'api_username',
                'api_from_email',
            ]
        }

        required_fields = required_fields_mapping.get(self.sending_method)
        unfilled_required_fields = []
        for required_field in required_fields:
            if getattr(self, required_field) is None:
                unfilled_required_fields.append(required_field)

        if unfilled_required_fields:
            raise ValidationError(
                'Для выбранного метода отправки необходимо заполнить поля {}'.format(
                    ", ".join(unfilled_required_fields)))
