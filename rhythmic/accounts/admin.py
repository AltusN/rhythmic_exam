import csv

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.shortcuts import redirect
from django.urls import path
from django.views.decorators.http import require_POST
from simple_history.admin import SimpleHistoryAdmin

from accounts.models import JudgeProfile, RosterEntry, User
from accounts.roster import (
    RosterChanged,
    confirm_roster,
    diff_roster,
    from_session,
    load_roster,
    parse_roster,
    to_session,
)

admin.site.register(User, UserAdmin)


class RosterImportForm(forms.Form):
    roster = forms.FileField()
    year = forms.IntegerField()


@admin.register(JudgeProfile)
class JudgeProfileAdmin(SimpleHistoryAdmin):
    list_display = ("sagf_id", "user")
    search_fields = ("sagf_id", "user__username")


@admin.register(RosterEntry)
class RosterEntryAdmin(SimpleHistoryAdmin):
    list_display = ("sagf_id", "year", "email", "levels")
    list_filter = ("year",)
    search_fields = ("sagf_id", "email")

    def get_urls(self):
        return [
            path(
                "import/",
                self.admin_site.admin_view(self.import_view),
                name="accounts_rosterentry_import",
            ),
            path(
                "import/confirm/",
                self.admin_site.admin_view(require_POST(self.confirm_view)),
                name="accounts_rosterentry_confirm",
            ),
        ] + super().get_urls()

    def import_view(self, request):
        preview = None
        errors = []
        from django.shortcuts import render

        if request.method == "POST":
            form = RosterImportForm(request.POST, request.FILES)
            if form.is_valid():
                uploaded_file = form.cleaned_data["roster"]
                year = form.cleaned_data["year"]
                lines = uploaded_file.read().decode("utf-8-sig").splitlines()
                rows = list(csv.DictReader(lines))
                parsed, errors = parse_roster(rows)
                if not errors:
                    preview = diff_roster(load_roster(year), parsed)
                    request.session["roster_import"] = {
                        "year": year,
                        **to_session(parsed, preview),
                    }
        else:
            form = RosterImportForm()

        return render(
            request,
            "admin/accounts/rosterentry/import.html",
            {
                **self.admin_site.each_context(request),
                "form": form,
                "preview": preview,
                "errors": errors,
            },
        )

    def confirm_view(self, request):
        data = request.session.pop("roster_import", None)
        if data is None:
            messages.error(request, "No roster import to confirm.")
            return redirect("admin:accounts_rosterentry_import")
        incoming, preview = from_session(data)
        try:
            confirm_roster(incoming, year=data["year"], preview=preview)
        except RosterChanged:
            messages.error(
                request, "The roster changed since the preview. Upload the file again."
            )
            return redirect("admin:accounts_rosterentry_import")

        messages.success(request, "Roster import confirmed.")

        return redirect("admin:accounts_rosterentry_changelist")
