import json
from datetime import datetime, timedelta

from djnewsletter.models import Emails


class Analytics:
    def __init__(self, ranges):
        """
        Статистика по email
        :param ranges: список дней, за которые нужно получить статистику, например ['today', 5, '15', 30]
        """
        self.ranges = ranges
        self.backends = {
            'smtp': self.parse_status_smtp,
            'unisender_api': self.parse_status_unisender,
        }
        self.statuses = {
            # внутренний ключ: ключ для отображения
            'success': 'success',
            'error': 'error',
        }
        self.now = datetime.now()
        self.start_today = self.now.replace(hour=0, minute=0, second=0, microsecond=0)

    def _get_filter_range(self, days):
        if isinstance(days, str):
            if days == 'today' or days == '0':
                return self.start_today, self.now
            days = int(days)
        return self.now - timedelta(days=days), self.now

    def get_email_stats(self, email):
        full_statistics = {}
        emails_qs = Emails.objects.filter(
            recipient__icontains=email
        )
        for days in self.ranges:
            period_statistics = {field: 0 for _, field in self.statuses.items()}
            emails = emails_qs.filter(
                createDateTime__range=self._get_filter_range(days)
            ).select_related('used_server')
            for email_instance in emails:
                parse_status = self.backends.get(email_instance.used_server.sending_method)
                status = parse_status(email, email_instance.status)
                period_statistics[status] += 1
            period_statistics.update({'total': sum(period_statistics.values())})
            full_statistics.update({days: period_statistics})
        return full_statistics

    def parse_status_unisender(self, email, status):
        try:
            status = json.loads(status.replace('\'', '\"'))
            if status.get('status') == 'success' and email in status.get('emails', []):
                return self.statuses['success']
            return self.statuses['error']
        except ValueError:
            return self.statuses['error']

    def parse_status_smtp(self, email, status):
        if status == 'sent to user':
            return self.statuses['success']
        return self.statuses['error']
