"""Moderacja nitek czytelników: ukrycie nitki lub linku po zgłoszeniu."""
from django.contrib import admin, messages
from django.utils import timezone

from news.account_models import PersonalContextThread, PersonalContextThreadItem
from news.community_models import CommunityLink, CommunityThreadOpinion, CommunityThreadReport


@admin.action(description='Ukryj (moderacja)')
def hide(modeladmin, request, queryset):
    done = queryset.filter(hidden_at__isnull=True).update(hidden_at=timezone.now())
    modeladmin.message_user(request, f'Ukryto: {done}.', messages.SUCCESS)


@admin.action(description='Przywróć widoczność')
def unhide(modeladmin, request, queryset):
    done = queryset.update(hidden_at=None)
    modeladmin.message_user(request, f'Przywrócono: {done}.', messages.SUCCESS)


@admin.register(CommunityLink)
class CommunityLinkAdmin(admin.ModelAdmin):
    list_display = ('title', 'domain', 'title_origin', 'hidden_at', 'created_at')
    list_filter = ('title_origin', 'domain')
    search_fields = ('title', 'canonical_url')
    raw_id_fields = ('submitted_by',)
    actions = [hide, unhide]


@admin.register(CommunityThreadReport)
class CommunityThreadReportAdmin(admin.ModelAdmin):
    list_display = ('thread', 'reason', 'status', 'reporter', 'created_at')
    list_filter = ('status', 'reason')
    raw_id_fields = ('thread', 'reporter')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommunityThreadOpinion)
class CommunityThreadOpinionAdmin(admin.ModelAdmin):
    list_display = ('thread', 'user', 'polarity', 'body', 'created_at')
    raw_id_fields = ('thread', 'user')


class PublicThreadItemInline(admin.TabularInline):
    model = PersonalContextThreadItem
    fields = ('position', 'article', 'link', 'note', 'link_note')
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class PublicThreadAdmin(admin.ModelAdmin):
    inlines = [PublicThreadItemInline]
    list_display = ('title', 'owner', 'is_public', 'published_at', 'hidden_at')
    list_filter = ('is_public',)
    search_fields = ('title', 'owner__username')
    raw_id_fields = ('owner',)
    filter_horizontal = ('sources',)
    actions = [hide, unhide]


if admin.site.is_registered(PersonalContextThread):
    admin.site.unregister(PersonalContextThread)
admin.site.register(PersonalContextThread, PublicThreadAdmin)
