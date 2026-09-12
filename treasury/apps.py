from django.apps import AppConfig
from django.db import connection


class TreasuryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'treasury'

    def ready(self):
        try:
            with connection.cursor() as cursor:
                # Check existing columns in treasury_payment
                columns = [col[0] for col in connection.introspection.get_table_description(cursor, 'treasury_payment')]
                if columns and 'fine_paid' not in columns:
                    cursor.execute('ALTER TABLE "treasury_payment" ADD COLUMN "fine_paid" bool NOT NULL DEFAULT 0;')
        except Exception:
            pass
