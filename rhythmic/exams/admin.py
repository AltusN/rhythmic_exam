import csv

from django import forms
from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from simple_history.admin import SimpleHistoryAdmin

from exams.category_import import diff_categories, load_categories, parse_categories
from exams.models import (
    CategoryRequirement,
    Certification,
    ComponentPracticalItem,
    ComponentQuestion,
    Cycle,
    Exam,
    ExamComponent,
    GradeBandRow,
    MarkingTableRow,
)
from exams.models.sitting import ComponentResult, Sitting, SittingItem


class ExamComponentInline(admin.TabularInline):
    model = ExamComponent
    extra = 1


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    inlines = [ExamComponentInline]


class ComponentQuestionInline(admin.TabularInline):
    model = ComponentQuestion
    extra = 1


class ComponentPracticalItemInline(admin.TabularInline):
    model = ComponentPracticalItem
    extra = 1


class MarkingTableRowInline(admin.TabularInline):
    model = MarkingTableRow
    extra = 1


class GradeBandRowInline(admin.TabularInline):
    model = GradeBandRow
    extra = 1


@admin.register(ExamComponent)
class ExamComponentAdmin(admin.ModelAdmin):
    inlines = [
        ComponentQuestionInline,
        ComponentPracticalItemInline,
        MarkingTableRowInline,
        GradeBandRowInline,
    ]


class CategoryRequirementInline(admin.TabularInline):
    model = CategoryRequirement
    extra = 1


@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    list_display = ("name", "first_year", "last_year")
    inlines = [CategoryRequirementInline]


@admin.register(SittingItem)
class SittingItemAdmin(admin.ModelAdmin):
    # frozen at the sitting's start: an audit trail, not an editable record
    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ComponentResult)
class ComponentResultAdmin(admin.ModelAdmin):
    # written once at submission: an audit trail, not an editable record
    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Sitting)
class SittingAdmin(SimpleHistoryAdmin):
    # progresses only through start_sitting/submit_sitting, never a raw edit
    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [
            path(
                "import/",
                self.admin_site.admin_view(self.import_view),
                name="exams_certification_import",
            ),
        ] + super().get_urls()

    def import_view(self, request):
        preview = None
        errors = []

        if request.method == "POST":
            form = CategoryImportForm(request.POST, request.FILES)
            if form.is_valid():
                categories_file = form.cleaned_data["categories"]
                cycle = form.cleaned_data["cycle"]
                lines = categories_file.read().decode("utf-8-sig").splitlines()
                rows = list(csv.DictReader(lines))
                parsed, errors = parse_categories(rows)
                if not errors:
                    preview = diff_categories(load_categories(cycle), parsed)
        else:
            form = CategoryImportForm()
        return render(
            request,
            "admin/exams/certification/import.html",
            {
                **self.admin_site.each_context(request),
                "form": form,
                "preview": preview,
                "errors": errors,
            },
        )


class CategoryImportForm(forms.Form):
    categories = forms.FileField()
    cycle = forms.ModelChoiceField(queryset=Cycle.objects.all())
