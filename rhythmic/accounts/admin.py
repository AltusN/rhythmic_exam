from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from simple_history.admin import SimpleHistoryAdmin

from accounts.models import JudgeProfile, RosterEntry, User

admin.site.register(User, UserAdmin)


@admin.register(JudgeProfile)
class JudgeProfileAdmin(SimpleHistoryAdmin):
    list_display = ("sagf_id", "user")
    search_fields = ("sagf_id", "user__username")


@admin.register(RosterEntry)
class RosterEntryAdmin(SimpleHistoryAdmin):
    list_display = ("sagf_id", "year", "email", "levels")
    list_filter = ("year",)
    search_fields = ("sagf_id", "email")
