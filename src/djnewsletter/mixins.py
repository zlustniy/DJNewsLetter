from django.conf import settings
from django.core.paginator import Paginator
from django.db import connection
from django.utils.functional import cached_property

__all__ = ['ApproxCountPaginatorMixin']


class ApproxCountPaginator(Paginator):
    def get_approx_count(self):
        approx_count = None

        get_approx_count_method = getattr(self, 'get_approx_count_{connection_vendor}'.format(
            connection_vendor=connection.vendor,
        ), None)
        if get_approx_count_method is not None:
            approx_count = get_approx_count_method()

        if approx_count is not None and approx_count > settings.DJNEWSLETTER_MIN_APPROX_COUNT:
            return approx_count
        return None

    def get_approx_count_mysql(self):
        # For MySQL
        # http://stackoverflow.com/a/10446271/366908
        cursor = connection.cursor()
        cursor.execute('SHOW TABLE STATUS LIKE %s', (self.object_list.query.model._meta.db_table,))
        approx_count = cursor.fetchall()[0][4]
        return approx_count

    def get_approx_count_postgresql(self):
        # For Postgres
        # http://stackoverflow.com/a/23118765/366908
        parts = [
            p.strip('"') for p in self.object_list.query.model._meta.db_table.split('.')
        ]
        cursor = connection.cursor()
        if len(parts) == 1:
            cursor.execute('SELECT reltuples::bigint FROM pg_class WHERE relname = %s', parts)
        else:
            cursor.execute(
                'SELECT reltuples::bigint FROM pg_class c JOIN pg_namespace n ON (c.relnamespace = n.oid) '
                'WHERE n.nspname = %s AND c.relname = %s', parts
            )
        approx_count = cursor.fetchall()[0][0]
        return approx_count

    @cached_property
    def count(self):
        approx_count = self.get_approx_count()
        if approx_count is None:
            return super(ApproxCountPaginator, self).count
        return approx_count


class ApproxCountPaginatorMixin:
    paginator = ApproxCountPaginator
