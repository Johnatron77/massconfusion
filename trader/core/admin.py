from django.db.migrations.recorder import MigrationRecorder
from django.contrib import admin

from trader import settings

# admin.site.register(MigrationRecorder.Migration)

admin.site.site_header = settings.ADMIN_TITLE
admin.site.site_title = settings.ADMIN_TITLE
admin.site.index_title = settings.ADMIN_TITLE
