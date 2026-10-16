import uuid

from django.core.validators import RegexValidator
from django.db.models import Model, ImageField, DateTimeField, CharField, EmailField, URLField, TextField, ForeignKey, \
    CASCADE, PositiveIntegerField, PositiveSmallIntegerField, SlugField, BooleanField
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

from apps.image_utils import OptimizedImageModel, OptimizedMediaModel


class Banner(OptimizedImageModel):
    main_max_side = 1920

    image = ImageField(upload_to='banner', verbose_name=_("Image"))

    class Meta:
        verbose_name = _("Banner")
        verbose_name_plural = _("Banners")


class SiteSetting(OptimizedImageModel):
    image_field = 'banner'
    main_max_side = 1920

    phone_number = CharField(max_length=11, verbose_name=_("Phone Number"))
    email = EmailField(max_length=100, verbose_name=_("Email"))
    address = CharField(max_length=120, verbose_name=_("Address"))
    banner = ImageField(upload_to='banner/%Y/%m/%d', verbose_name=_("Banner Image"))
    text = TextField(verbose_name=_("Text"))
    instagram = CharField(max_length=120, verbose_name=_("Instagram"))
    facebook = CharField(max_length=120, verbose_name=_("Facebook"))
    youtube = CharField(max_length=120, verbose_name=_("YouTube"))
    telegram = CharField(max_length=120, verbose_name=_("Telegram"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Site Setting")
        verbose_name_plural = _("Site Settings")


class ContactForm(Model):
    name = CharField(max_length=100, verbose_name=_("Name"))
    email = EmailField(max_length=100, verbose_name=_("Email"))
    phone = CharField(max_length=32, blank=True, default='', verbose_name=_("Phone Number"),
                      validators=[RegexValidator(r'^[0-9\s+\-()]*$', _("Enter a valid phone number."))])
    subject = CharField(max_length=120, blank=True, default='', verbose_name=_("Subject"))
    message = TextField(verbose_name=_("Message"))
    created = DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    is_processed = BooleanField(default=False, verbose_name=_("Processed"))
    note = TextField(blank=True, default='', verbose_name=_("Note"))

    class Meta:
        verbose_name = _("Contact Form")
        verbose_name_plural = _("Contact Forms")




class Partner(OptimizedImageModel):
    trim_logo = True

    image = ImageField(upload_to='partners/%Y/%m/%d', verbose_name=_("Image"))
    url = URLField(max_length=100, verbose_name=_("URL"), null=True, blank=True)

    class Meta:
        verbose_name = _("Partner")
        verbose_name_plural = _("Partners")

    def __str__(self):
        return self.url


class Service(OptimizedImageModel, TranslatableModel):
    main_max_side = 1200

    translations = TranslatedFields(
        title = CharField(max_length=120, verbose_name=_("Title")),
        description = TextField(verbose_name=_("Description"), blank=True, default='')
    )

    slug = SlugField(max_length=80, unique=True, null=True, blank=True, verbose_name=_("Slug"))
    image = ImageField(upload_to='services-icon/%Y/%m/%d', verbose_name=_("Icon"), null=True, blank=True)

    class Meta:
        verbose_name = _("Service")
        verbose_name_plural = _("Services")

    def clean(self):
        super().clean()
        self.slug = (slugify(self.slug) if self.slug else '') or None

    def save(self, *args, **kwargs):
        self.slug = (slugify(self.slug) if self.slug else '') or None
        super().save(*args, **kwargs)


class ServiceWork(OptimizedImageModel):
    service = ForeignKey('apps.Service', verbose_name=_("Service"), related_name='works', on_delete=CASCADE)
    image = ImageField(upload_to='service-works/%Y/%m/%d/', verbose_name=_("Image"))
    order = PositiveIntegerField(default=0, verbose_name=_("Order"))

    class Meta:
        ordering = ['order', 'id']
        verbose_name = _("Service Work")
        verbose_name_plural = _("Service Works")

    def __str__(self):
        return f"Work {self.pk} for service {self.service_id}"




class ClientComment(Model):
    avatar = ImageField(upload_to='reviews/%Y/%m/%d', verbose_name=_("Avatar"))
    full_name = CharField(max_length=120, verbose_name=_("Full Name"))
    job = CharField(max_length=120, verbose_name=_("Job Title"))
    description = TextField(verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Client Comment")
        verbose_name_plural = _("Client Comments")


class ClientEmail(Model):
    email = EmailField(max_length=100, unique=True, verbose_name=_("Email"))

    class Meta:
        verbose_name = _("Client Email")
        verbose_name_plural = _("Client Emails")

    def __str__(self):
        return self.email



TEMP_SLUG_PREFIX = 'tmp-'


class Project(OptimizedImageModel, TranslatableModel):
    CATEGORY_CHOICES = [
        ('hotel', _("Hotel")),
        ('museum', _("Museum")),
        ('outdoor', _("Outdoor")),
        ('interior', _("Interior")),
        ('corporate', _("Corporate")),
        ('facade', _("Facade")),
    ]

    translations = TranslatedFields(
        title=CharField(max_length=120, verbose_name=_("Title")),
        location=CharField(max_length=120, blank=True, default='', verbose_name=_("Location")),
        description=TextField(blank=True, default='', verbose_name=_("Description")),
        materials=TextField(blank=True, default='', verbose_name=_("Materials")),
    )

    image_field = 'cover'

    slug = SlugField(unique=True, blank=True, verbose_name=_("Slug"),
                     help_text=_("Leave empty to generate it from the English title."))
    cover = ImageField(upload_to='projects/%Y/%m/%d', verbose_name=_("Cover"))
    year = PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Year"))
    category = CharField(max_length=20, choices=CATEGORY_CHOICES, default='outdoor', verbose_name=_("Category"))
    is_published = BooleanField(default=False, verbose_name=_("Published"))
    order = PositiveIntegerField(default=0, verbose_name=_("Order"))

    class Meta:
        ordering = ['order', 'id']
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")

    def __str__(self):
        return self.slug

    def clean(self):
        super().clean()
        self.slug = slugify(self.slug)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.slug) or f"{TEMP_SLUG_PREFIX}{uuid.uuid4().hex[:12]}"
        super().save(*args, **kwargs)


@receiver(post_save, sender=Project._parler_meta.root_model)
def set_project_slug_from_english_title(sender, instance, **kwargs):
    project = instance.master
    if instance.language_code != 'en' or not project.slug.startswith(TEMP_SLUG_PREFIX):
        return
    base = slugify(instance.title)[:45]
    if not base:
        return
    slug, n = base, 2
    while Project.objects.filter(slug=slug).exclude(pk=project.pk).exists():
        slug, n = f"{base}-{n}", n + 1
    Project.objects.filter(pk=project.pk).update(slug=slug)
    project.slug = slug


class ProjectPhoto(OptimizedMediaModel):
    project = ForeignKey('apps.Project', verbose_name=_("Project"), related_name='photos', on_delete=CASCADE)
    image = ImageField(upload_to='project-photos/%Y/%m/%d', verbose_name=_("Image"), blank=True,
                       help_text=_("Upload an image or a video. For a video the poster is created automatically; upload an image only to use your own poster."))
    order = PositiveIntegerField(default=0, verbose_name=_("Order"))

    class Meta:
        ordering = ['order', 'id']
        verbose_name = _("Project Photo")
        verbose_name_plural = _("Project Photos")

    def __str__(self):
        return f"Photo {self.pk} for project {self.project_id}"


@receiver(post_delete, sender=ProjectPhoto)
def delete_video_file(sender, instance, **kwargs):
    if instance.video:
        instance.video.storage.delete(instance.video.name)
