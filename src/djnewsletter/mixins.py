from django.conf import settings
from django.core.paginator import Paginator
from django.db import connection
from django.utils.functional import cached_property

__all__ = ['ApproxCountPaginatorMixin']


class ApproxCountPaginator(Paginator):
    def get_approx_count(self):
        count = None

        # For MySQL
        # http://stackoverflow.com/a/10446271/366908
        if connection.vendor == 'mysql':
            cursor = connection.cursor()
            cursor.execute('SHOW TABLE STATUS LIKE %s',
                           (self.object_list.query.model._meta.db_table,))
            count = cursor.fetchall()[0][4]
        # For Postgres
        # http://stackoverflow.com/a/23118765/366908
        elif connection.vendor == 'postgresql':
            parts = [p.strip('"')
                     for p in self.object_list.query.model._meta.db_table.split('.')]
            cursor = connection.cursor()
            if len(parts) == 1:
                cursor.execute('SELECT reltuples::bigint FROM pg_class WHERE relname = %s', parts)
            else:
                cursor.execute(
                    'SELECT reltuples::bigint FROM pg_class c JOIN pg_namespace n ON (c.relnamespace = n.oid) WHERE n.nspname = %s AND c.relname = %s',
                    parts)
            count = cursor.fetchall()[0][0]

        min_approx_count = getattr(settings, 'DJNEWSLETTER_MIN_APPROX_COUNT', 10000)
        if count is not None and count > min_approx_count:
            return count
        return None

    @cached_property
    def count(self):
        count = self.get_approx_count()
        if count is None:
            return super(ApproxCountPaginator, self).count
        return count


class ApproxCountPaginatorMixin:
    paginator = ApproxCountPaginator
