from __future__ import annotations

from django.contrib import admin

from .models import (Appeal, Box, BoxLink, BoxSpinka, Comment, Correction, DiagnosisApproval, ModerationDecision, Pin, RankingSnapshot,
                     Rating, Report, SilencedAccount, Spina3Profile, UrlCheck)


@admin.register(Box)
class BoxAdmin(admin.ModelAdmin):
    list_display = ('pk', 'kind', 'title', 'source_domain', 'status', 'source_status', 'added_by', 'published_at')
    list_filter = ('kind', 'status', 'source_status', 'added_by', 'reader_link')
    search_fields = ('title', 'url', 'author_handle')


@admin.register(Pin)
class PinAdmin(admin.ModelAdmin):
    list_display = ('pk', 'box', 'kind', 'user', 'status', 'target_status', 'is_team', 'created_at')
    list_filter = ('kind', 'status', 'target_status', 'is_team')


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('pk', 'pin', 'box', 'stance', 'status', 'account_weight', 'created_at')
    list_filter = ('stance', 'status', 'is_team')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('pk', 'box', 'user', 'status', 'helpful_count', 'reply_count', 'created_at')
    list_filter = ('status', 'is_team', 'is_author')
    search_fields = ('text',)


@admin.register(BoxSpinka)
class BoxSpinkaAdmin(admin.ModelAdmin):
    list_display = ('box', 'n', 'weighted_n', 'score', 'level', 'level_reason', 'last_rating_at')
    readonly_fields = tuple(f.name for f in BoxSpinka._meta.fields)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('pk', 'reason', 'status', 'pin', 'box', 'comment', 'sla_deadline', 'created_at')
    list_filter = ('status', 'reason')


admin.site.register(BoxLink)
admin.site.register(Spina3Profile)
admin.site.register(UrlCheck)
admin.site.register(Appeal)
admin.site.register(RankingSnapshot)


@admin.register(Correction)
class CorrectionAdmin(admin.ModelAdmin):
    """Kolejka sprostowań: najpierw oczekujące według terminu publikacji (3 dni robocze)."""
    list_display = ('pk', 'box', 'status', 'due_at', 'consent_public_name', 'rejection_reason', 'created_at')
    list_filter = ('status', 'rejection_reason')
    ordering = ('status', 'due_at')
    readonly_fields = ('box', 'name', 'email', 'text', 'statement', 'consent_public_name', 'due_at', 'created_at')


@admin.register(ModerationDecision)
class ModerationDecisionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'target_type', 'restriction', 'basis', 'automated', 'created_at', 'revoked_at', 'email_sent_at')
    list_filter = ('target_type', 'restriction', 'basis', 'automated')


@admin.register(SilencedAccount)
class SilencedAccountAdmin(admin.ModelAdmin):
    list_display = ('handle', 'kind', 'starts_at', 'ends_at', 'source')
    list_filter = ('kind',)
    search_fields = ('handle',)


@admin.register(DiagnosisApproval)
class DiagnosisApprovalAdmin(admin.ModelAdmin):
    list_display = ('diagnosis_box', 'version', 'change', 'approved_by_account', 'approved_at', 'model')
