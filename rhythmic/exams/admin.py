from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from exams.models import (
    ComponentPracticalItem,
    ComponentQuestion,
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
