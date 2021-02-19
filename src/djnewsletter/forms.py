from django import forms

from .models import EmailServers


class EmailServersAdminForm(forms.ModelForm):
    class Meta:
        model = EmailServers
        fields = "__all__"

    def clean(self):
        """
        Checks that all the words belong to the sentence's language.
        """
        has_sites = self.cleaned_data.get('sites')
        is_main = self.cleaned_data.get('main')
        is_active = self.cleaned_data.get('is_active')
        if has_sites and is_main and is_active:
            error_message = "Основной ,активный сервер не может быть привязан к сайту"
            self.add_error('main', error_message)
            self.add_error('sites', error_message)
            self.add_error('is_active', error_message)
            raise forms.ValidationError(
                "Основной активный сервер не может быть привязан к сайту, Деактивируйте сервер или назначьте другой"
                " сервер основным или уберите привязку к сайту"
            )

        return self.cleaned_data
