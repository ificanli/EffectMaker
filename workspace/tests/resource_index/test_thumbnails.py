import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from workspace.tools.resource_index.thumbnails import (
    _validate_output_paths,
    create_thumbnail,
    thumbnail_relative_path,
)


class ThumbnailTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.destination = self.root / "output"
        self.source = self.root / "source"
        self.source.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_thumbnail_path_is_deterministic_and_nested_by_asset_id(self):
        first = thumbnail_relative_path("a1b2c3")
        second = thumbnail_relative_path("a1b2c3")

        self.assertEqual(first, second)
        self.assertEqual(first.suffix, ".png")
        self.assertEqual(first.parts[:2], ("thumbnails", "a1"))
        self.assertEqual(first.name, "a1b2c3.png")

    def test_preserves_aspect_ratio_within_requested_size(self):
        source = self.source / "wide.png"
        Image.new("RGB", (800, 400), "red").save(source)

        relative_path, error = create_thumbnail(source, self.destination, "wide-id", size=256)

        self.assertIsNone(error)
        self.assertIsNotNone(relative_path)
        with Image.open(self.destination / relative_path) as thumbnail:
            self.assertEqual(thumbnail.size, (256, 128))
            self.assertEqual(thumbnail.format, "PNG")

    def test_rgba_thumbnail_is_composited_on_checkerboard_and_saved_as_rgb_png(self):
        source = self.source / "transparent.png"
        image = Image.new("RGBA", (2, 2), (255, 0, 0, 0))
        image.putpixel((0, 0), (255, 0, 0, 255))
        image.save(source)
        image.close()

        relative_path, error = create_thumbnail(source, self.destination, "rgba-id", size=2)

        self.assertIsNone(error)
        self.assertIsNotNone(relative_path)
        with Image.open(self.destination / relative_path) as thumbnail:
            self.assertEqual(thumbnail.format, "PNG")
            self.assertEqual(thumbnail.mode, "RGB")
            self.assertNotEqual(thumbnail.getpixel((1, 1)), (0, 0, 0))
            self.assertNotEqual(thumbnail.getpixel((0, 0)), thumbnail.getpixel((1, 1)))

    def test_special_pillow_modes_are_converted_before_thumbnail_resize(self):
        fixtures = {
            "P": (Image.new("P", (8, 4)), ".png"),
            "LA": (Image.new("LA", (8, 4), (128, 200)), ".png"),
            "I;16": (Image.new("I;16", (8, 4), 1024), ".png"),
        }
        original_thumbnail = Image.Image.thumbnail
        resized_modes = []

        def reject_unsafe_modes(image, *args, **kwargs):
            resized_modes.append(image.mode)
            if image.mode not in ("RGB", "RGBA"):
                raise ValueError("image has wrong mode")
            return original_thumbnail(image, *args, **kwargs)

        try:
            with patch.object(Image.Image, "thumbnail", reject_unsafe_modes):
                for mode, (image, suffix) in fixtures.items():
                    with self.subTest(mode=mode):
                        source = self.source / f"{mode.replace(';', '-')}{suffix}"
                        image.save(source)
                        relative_path, error = create_thumbnail(
                            source, self.destination, f"mode-{mode.replace(';', '-')}", size=4
                        )

                        self.assertIsNone(error)
                        self.assertIsNotNone(relative_path)
                        with Image.open(self.destination / relative_path) as thumbnail:
                            self.assertEqual(thumbnail.mode, "RGB")
                            self.assertEqual(thumbnail.size, (4, 2))
            self.assertEqual(resized_modes, ["RGBA", "RGBA", "RGB"])
        finally:
            for image, _ in fixtures.values():
                image.close()

    def test_unsupported_or_corrupt_asset_returns_error_without_raising(self):
        source = self.source / "not-image.bin"
        source.write_bytes(b"not an image")

        relative_path, error = create_thumbnail(source, self.destination, "bad-id")

        self.assertIsNone(relative_path)
        self.assertIsInstance(error, str)
        self.assertTrue(error)
        self.assertFalse(self.destination.exists())

        source = self.source / "corrupt.psd"
        source.write_bytes(b"8BPS\\x00\\x01truncated")

        relative_path, error = create_thumbnail(source, self.destination, "corrupt-psd")

        self.assertIsNone(relative_path)
        self.assertIsInstance(error, str)
        self.assertTrue(error)
        self.assertFalse(self.destination.exists())

    def test_rejects_asset_id_that_could_escape_destination_root(self):
        source = self.source / "image.png"
        Image.new("RGB", (10, 10), "blue").save(source)

        relative_path, error = create_thumbnail(source, self.destination, "../outside")

        self.assertIsNone(relative_path)
        self.assertIsInstance(error, str)
        self.assertFalse((self.root / "outside.png").exists())

    def test_decompression_bomb_returns_error_and_restores_pixel_limit(self):
        source = self.source / "large.png"
        Image.new("RGB", (2, 2), "blue").save(source)
        original_limit = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = 1
        try:
            relative_path, error = create_thumbnail(source, self.destination, "bomb-id")
        finally:
            Image.MAX_IMAGE_PIXELS = original_limit

        self.assertIsNone(relative_path)
        self.assertIsInstance(error, str)
        self.assertTrue(error)

    def test_rejects_destination_root_inside_source_directory(self):
        source = self.source / "image.png"
        Image.new("RGB", (10, 10), "blue").save(source)
        destination = self.source / "generated"

        relative_path, error = create_thumbnail(source, destination, "overlap-id")

        self.assertIsNone(relative_path)
        self.assertIsInstance(error, str)
        self.assertFalse(destination.exists())

    def test_rejects_output_path_equal_to_source_file(self):
        source = self.destination / "thumbnails" / "same" / "same.png"
        source.parent.mkdir(parents=True)
        Image.new("RGB", (10, 10), "blue").save(source)

        relative_path, error = create_thumbnail(source, self.destination, "same")

        self.assertIsNone(relative_path)
        self.assertIsInstance(error, str)
        with Image.open(source) as image:
            self.assertEqual(image.size, (10, 10))

    def test_rejects_resolved_output_descendant_of_source_parent(self):
        source = self.source / "image.png"
        Image.new("RGB", (10, 10), "blue").save(source)
        output_path = (self.source / "generated" / "thumbnails" / "de" / "descendant.png").resolve()

        with self.assertRaises(ValueError):
            _validate_output_paths(source.resolve(), self.source.resolve(), output_path)

        destination = self.source / "generated"
        relative_path, error = create_thumbnail(source, destination, "descendant")

        self.assertIsNone(relative_path)
        self.assertIsInstance(error, str)
        self.assertFalse((destination / "thumbnails" / "de" / "descendant.png").exists())

    def test_rejects_symlinked_thumbnail_directory_resolving_into_source_parent(self):
        source = self.source / "image.png"
        Image.new("RGB", (10, 10), "blue").save(source)
        destination = self.root / "symlink-destination"
        destination.mkdir()
        try:
            (destination / "thumbnails").symlink_to(self.source, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlink creation unavailable: {error}")

        relative_path, error = create_thumbnail(source, destination, "linked")

        self.assertIsNone(relative_path)
        self.assertIsInstance(error, str)
        self.assertFalse((self.source / "li" / "linked.png").exists())

        source = self.source / "image.png"
        Image.new("RGB", (10, 10), "blue").save(source)
        before = {path.relative_to(self.source) for path in self.source.rglob("*")}

        relative_path, error = create_thumbnail(source, self.destination, "safe-id")

        self.assertIsNone(error)
        self.assertIsNotNone(relative_path)
        after = {path.relative_to(self.source) for path in self.source.rglob("*")}
        self.assertEqual(before, after)
        self.assertTrue((self.destination / relative_path).is_file())


if __name__ == "__main__":
    unittest.main()
