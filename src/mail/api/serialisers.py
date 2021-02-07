from rest_framework import serializers


class SendEmailsSerialiser(serializers.Serializer):
    emails = serializers.ListSerializer(
        child=serializers.EmailField(
            label='E-mail',
        ),
    )
