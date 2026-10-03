from django.contrib import admin
from django.contrib.auth.models import Group
from django.shortcuts import redirect
from django.utils.html import format_html
from django.urls import reverse
from parler.admin import TranslatableAdmin

from apps.models import Gallery, SiteSetting, ContactForm, Partner, Service, ServiceWork, ClientEmail, GalleryGroup, Project, ProjectPhoto


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
    list_display = 'title',
    inlines = ServiceWorkInline,


class ProjectPhotoInline(admin.TabularInline):
    model = ProjectPhoto
    extra = 3
    fields = ['image', 'order']


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


class GalleryGroupInline(admin.TabularInline):
    model = GalleryGroup
    extra = 1
    fields = ['image']
    verbose_name = "Additional image"
    verbose_name_plural = "Additional images"


@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = 'id',
    inlines = GalleryGroupInline,


admin.site.unregister(Group)
