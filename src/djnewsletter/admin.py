import json

from django.contrib import admin
from django.contrib import messages
from django.http.response import HttpResponseRedirect
from django.utils.html import format_html
from djnewsletter.forms import EmailServersAdminForm
from djnewsletter.helpers import send_email
from djnewsletter.mixins import ApproxCountPaginatorMixin
from djnewsletter.models import Unsubscribers, Emails, Bounced, Domains, EmailServers


class UnsubscribersAdmin(ApproxCountPaginatorMixin, admin.ModelAdmin):
    list_display = ['email', 'newsletter', 'unsubscribeDatetime']


class EmailsAdmin(ApproxCountPaginatorMixin, admin.ModelAdmin):
    list_display = ['subject', 'email_body', 'sender', 'recipient', 'newsletter', 'status', 'type', 'createDateTime',
                    'changeDateTime']
    search_fields = ['subject', 'body', 'sender', 'recipient']
    readonly_fields = ['used_server']

    def email_body(self, obj):
        return format_html(
            '<div style="word-break: break-word; overflow: auto; height: 100px;">{}</div>',
            obj.body,
        )


class BouncedAdmin(ApproxCountPaginatorMixin, admin.ModelAdmin):
    list_display = ['email', 'event', 'category', 'eventDateTime', 'reason', 'createDateTime']
    search_fields = ['email', 'event', 'category', 'reason']


class DomainsAdmin(admin.ModelAdmin):
    list_display = ['domain']
    search_fields = ['domain']


class EmailServersAdmin(admin.ModelAdmin):
    form = EmailServersAdminForm
    list_display = ['email_host', 'email_port', 'main', 'is_active', 'sending_method']
    filter_horizontal = ['preferred_domains']

    def send_test_email(self, request, object_id):
        try:
            send_email(
                to=[request.user.email],
                subject='Тестовое письмо. Test email',
                template='email/test_email.html',
                context={
                    'username': request.user.username,
                    'email': request.user.email,
                },
                attachments=[
                    ('latin_test.txt', 'Latin test'.encode('utf-8'), 'text/text'),
                    ('Проверка кириллицы.txt', 'Проверка кириллицы'.encode('utf-8'), 'text/text'),
                ],
                email_server=EmailServers.objects.get(id=object_id),
                headers={
                    'X-SMTPAPI': json.dumps({
                        "category": [
                            "test"
                        ]
                    })
                }
            )
        except Exception as e:
            messages.error(request, 'Во время отправки письма произошла ошибка: {}'.format(e))
        else:
            messages.success(request, 'Отправка тестового письма выполнена успешно')
        return HttpResponseRedirect(request.path)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if '_send_test_email' in request.POST:
            return self.send_test_email(request, object_id)

        return super(EmailServersAdmin, self).change_view(
            request, object_id, form_url=form_url, extra_context=extra_context
        )


admin.site.register(Unsubscribers, UnsubscribersAdmin)
admin.site.register(Emails, EmailsAdmin)
admin.site.register(Bounced, BouncedAdmin)
admin.site.register(Domains, DomainsAdmin)
admin.site.register(EmailServers, EmailServersAdmin)
