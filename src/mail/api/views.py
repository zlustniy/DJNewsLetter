from gettext import gettext

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
        # TODO: send mails
        return Response(
            data={
                'detail': gettext('Письма отправлены.')
            },
            status=200,
        )
