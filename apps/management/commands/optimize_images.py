from django.core.management.base import BaseCommand

from apps.image_utils import build_variants
from apps.models import Gallery, GalleryGroup, ServiceWork


class Command(BaseCommand):
    help = "Convert existing Gallery/GalleryGroup/ServiceWork images to optimized WebP, create thumbnails, delete old files."

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help="Reprocess images that are already optimized.")

    def handle(self, *args, **options):
        done = skipped = failed = 0
        saved_bytes = 0

        for model in (Gallery, GalleryGroup, ServiceWork):
            for obj in model.objects.iterator():
                if not obj.image:
                    continue
                optimized = obj.image.name.lower().endswith('.webp') and obj.thumbnail
                if optimized and not options['force']:
                    skipped += 1
                    continue

                old_name = obj.image.name
                old_thumb = obj.thumbnail.name if obj.thumbnail else None
                try:
                    old_size = obj.image.size
                    with obj.image.open('rb') as f:
                        main, thumb = build_variants(f)
                except Exception as exc:
                    failed += 1
                    self.stderr.write(f"{model.__name__} #{obj.pk} {old_name}: {exc}")
                    continue

                obj.apply_variants(main, thumb, old_name)
                obj.save()

                storage = obj.image.storage
                for stale in (old_name, old_thumb):
                    if stale and stale not in (obj.image.name, obj.thumbnail.name):
                        storage.delete(stale)

                done += 1
                saved_bytes += old_size - len(main) - len(thumb)
                self.stdout.write(f"{model.__name__} #{obj.pk}: {old_size // 1024} KB -> "
                                  f"{len(main) // 1024} KB + thumb {len(thumb) // 1024} KB")

        self.stdout.write(self.style.SUCCESS(
            f"Done: {done} optimized, {skipped} skipped, {failed} failed, saved ~{saved_bytes // (1024 * 1024)} MB"))
