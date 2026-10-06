from django.core.management.base import BaseCommand, CommandError

from apps.image_utils import build_variants
from apps.models import Banner, Gallery, GalleryGroup, Partner, Project, ProjectPhoto, Service, ServiceWork, SiteSetting


MODELS = (Gallery, GalleryGroup, Service, ServiceWork, Partner, Banner, SiteSetting, Project, ProjectPhoto)


def is_referenced(name):
    for model in MODELS:
        for field in (model.image_field, 'thumbnail'):
            if model.objects.filter(**{field: name}).exists():
                return True
    return False


class Command(BaseCommand):
    help = "Convert existing Gallery/GalleryGroup/ServiceWork/Partner/Banner/SiteSetting/Project/ProjectPhoto images to optimized WebP, create thumbnails, delete old files."

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help="Reprocess images that are already optimized.")
        parser.add_argument('--only', nargs='+', metavar='MODEL', help="Only process these models, e.g. --only partner service.")

    def handle(self, *args, **options):
        done = skipped = failed = 0
        saved_bytes = 0

        names = {name.lower() for name in options['only'] or ()}
        unknown = names - {model.__name__.lower() for model in MODELS}
        if unknown:
            raise CommandError(f"Unknown model(s): {', '.join(sorted(unknown))}")

        for model in MODELS:
            if names and model.__name__.lower() not in names:
                continue
            for obj in model.objects.iterator():
                source = obj.source_image
                if not source:
                    continue
                optimized = source.name.lower().endswith('.webp') and obj.thumbnail
                if optimized and not options['force']:
                    skipped += 1
                    continue

                old_name = source.name
                old_thumb = obj.thumbnail.name if obj.thumbnail else None
                try:
                    old_size = source.size
                    with source.open('rb') as f:
                        main, thumb = build_variants(f, obj.main_max_side, trim=obj.trim_logo)
                except Exception as exc:
                    failed += 1
                    self.stderr.write(f"{model.__name__} #{obj.pk} {old_name}: {exc}")
                    continue

                obj.apply_variants(main, thumb, old_name)
                obj.save()

                storage = obj.source_image.storage
                for stale in (old_name, old_thumb):
                    if stale and not is_referenced(stale):
                        storage.delete(stale)

                done += 1
                saved_bytes += old_size - len(main) - len(thumb)
                self.stdout.write(f"{model.__name__} #{obj.pk}: {old_size // 1024} KB -> "
                                  f"{len(main) // 1024} KB + thumb {len(thumb) // 1024} KB")

        self.stdout.write(self.style.SUCCESS(
            f"Done: {done} optimized, {skipped} skipped, {failed} failed, saved ~{saved_bytes // (1024 * 1024)} MB"))
