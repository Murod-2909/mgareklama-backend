from django.contrib import admin
from django.contrib.auth.models import Group
from django.shortcuts import redirect
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from parler.admin import TranslatableAdmin

from apps.models import Gallery, SiteSetting, ContactForm, Partner, Service, ServiceWork, ClientEmail, GalleryGroup, Project, ProjectPhoto


class MediaPreviewMixin:
    @admin.display(description=_("Preview"))
    def preview(self, obj):
        if not obj.pk:
            return "-"
        poster = obj.image.url if obj.image else (obj.thumbnail.url if obj.thumbnail else '')
        if obj.media_type == 'video' and obj.video:
            return format_html(
                '<video src="{}" poster="{}" controls preload="metadata" style="max-width:320px"></video>',
                obj.video.url, poster)
        thumb = obj.thumbnail.url if obj.thumbnail else poster
        if thumb:
            return format_html('<img src="{}" style="max-width:160px;border-radius:4px">', thumb)
        return "-"


@admin.register(SiteSetting)
class SiteSettingsAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if SiteSetting.objects.exists():
            obj = SiteSetting.objects.first()
            return redirect(reverse('admin:apps_sitesetting_change', args=[obj.id]))
        return super().changelist_view(request, extra_context)

    class Media:
        js = (
            'https://code.jquery.com/jquery-3.6.0.min.js',
            "https://cdnjs.cloudflare.com/ajax/libs/jquery.inputmask/5.0.6/jquery.inputmask.min.js",
            'apps/js/phone_mask.js',
        )


@admin.register(ContactForm)
class ContactFormAdmin(admin.ModelAdmin):
    list_display = 'name', 'email', 'phone'
    search_fields = 'name', 'email', 'phone'


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    pass


class ServiceWorkInline(admin.TabularInline):
    model = ServiceWork
    extra = 3
    fields = ['image', 'order']


@admin.register(Service)
class ServiceTranslatableAdmin(TranslatableAdmin):
    list_display = 'title', 'slug'
    inlines = ServiceWorkInline,


class ProjectPhotoInline(MediaPreviewMixin, admin.TabularInline):
    model = ProjectPhoto
    extra = 3
    fields = ['image', 'video', 'order', 'preview', 'media_type', 'duration']
    readonly_fields = ['preview', 'media_type', 'duration']


@admin.register(Project)
class ProjectTranslatableAdmin(TranslatableAdmin):
    list_display = 'cover_preview', 'title', 'category', 'year', 'is_published', 'order'
    list_display_links = 'cover_preview', 'title'
    list_editable = 'is_published', 'order'
    list_filter = 'category', 'is_published'
    inlines = ProjectPhotoInline,

    @admin.display(description="Cover")
    def cover_preview(self, obj):
        image = obj.thumbnail or obj.cover
        if not image:
            return "-"
        return format_html('<img src="{}" style="height:48px;border-radius:4px">', image.url)


@admin.register(ClientEmail)
class ClientEmailModelAdmin(admin.ModelAdmin):
    pass


class GalleryGroupInline(MediaPreviewMixin, admin.TabularInline):
    model = GalleryGroup
    extra = 1
    fields = ['image', 'video', 'preview', 'media_type', 'duration']
    readonly_fields = ['preview', 'media_type', 'duration']
    verbose_name = "Additional image"
    verbose_name_plural = "Additional images"


@admin.register(Gallery)
class GalleryAdmin(MediaPreviewMixin, admin.ModelAdmin):
    list_display = 'preview', 'id', 'media_type'
    fields = ['image', 'video', 'preview', 'media_type', 'duration', 'thumbnail']
    readonly_fields = ['preview', 'media_type', 'duration', 'thumbnail']
    inlines = GalleryGroupInline,


admin.site.unregister(Group)
