from django.db import migrations


def fix_outstandingtoken_fk(apps, schema_editor):
    """token_blacklist_outstandingtoken.user_id can still point at Django's
    stock auth_user table (leftover from before AUTH_USER_MODEL was swapped to
    accounts.User) instead of accounts_user. That's harmless until a user who
    only exists in accounts_user gets a token minted, which raises an
    unhandled IntegrityError. Repoint the constraint if it's wrong; no-op if
    it's already correct or the table doesn't exist yet.
    """
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.token_blacklist_outstandingtoken')")
        if not cursor.fetchone()[0]:
            return

        cursor.execute("""
            SELECT tc.constraint_name, ccu.table_name AS foreign_table_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = 'token_blacklist_outstandingtoken'
              AND kcu.column_name = 'user_id'
        """)
        row = cursor.fetchone()
        if not row:
            return
        constraint_name, foreign_table = row
        if foreign_table == 'accounts_user':
            return

        cursor.execute(
            f'ALTER TABLE token_blacklist_outstandingtoken DROP CONSTRAINT "{constraint_name}"'
        )
        cursor.execute(
            'ALTER TABLE token_blacklist_outstandingtoken '
            'ADD CONSTRAINT token_blacklist_outstandingtoken_user_id_fk_accounts_user '
            'FOREIGN KEY (user_id) REFERENCES accounts_user(id) ON DELETE CASCADE'
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_alter_user_first_name_alter_user_last_name_and_more'),
        ('token_blacklist', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fix_outstandingtoken_fk, noop_reverse),
    ]
