import json
from gettext import gettext

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from djnewsletter.helpers import send_email
from .serialisers import SendEmailsSerialiser


class SendEmailsApiView(APIView):
    serializer_class = SendEmailsSerialiser
    permission_classes = (IsAuthenticated,)

    def post(self, *args, **kwargs):
        serializer = self.serializer_class(
            data=self.request.data,
        )
        serializer.is_valid(raise_exception=True)
        emails = serializer.validated_data['emails']
        send_email(
            to=emails,
            subject='Тестовое письмо. Test email',
            template='email/test_email.html',
            context={
                'username': self.request.user.username,
                'email': self.request.user.email,
            },
            attachments=[
                ('latin_test.txt', 'Latin test'.encode('utf-8'), 'text/text'),
                ('Проверка кириллицы.txt', 'Проверка кириллицы'.encode('utf-8'), 'text/text'),
            ],
            headers={
                'X-SMTPAPI': json.dumps({
                    "category": [
                        "test"
                    ]
                })
            }
        )
        return Response(
            data={
                'detail': gettext('Письма отправлены.')
            },
            status=200,
        )
