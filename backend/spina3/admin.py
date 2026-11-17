from __future__ import annotations

from django.contrib import admin

from .models import Appeal, Box, BoxLink, BoxSpinka, Comment, Pin, RankingSnapshot, Rating, Report, Spina3Profile, UrlCheck


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
