import builtins
import importlib
import io
import sys
import types


def test_production_storage_from_yaml(monkeypatch):
    """Ensure YAML config correctly sets STORAGES without leaking legacy globals."""

    def fake_get_env_setting(key):
        if key == "DISCOVERY_CFG":
            return "/fake/path/config.yaml"
        return ""

    fake_yaml_content = """
        DEFAULT_FILE_STORAGE: storages.backends.s3boto3.S3Boto3Storage
        STATICFILES_STORAGE: storage.ManifestStaticFilesStorage
        MEDIA_ROOT: /tmp/media
        MEDIA_URL: /media/
    """

    # Clear any cached module import
    sys.modules.pop("course_discovery.settings.production", None)

    # Patch out utils and open()
    monkeypatch.setitem(
        sys.modules,
        "course_discovery.settings.utils",
        types.SimpleNamespace(
            get_env_setting=fake_get_env_setting,
            get_logger_config=lambda *a, **kw: {},
        ),
    )
    monkeypatch.setattr(builtins, "open", lambda *a, **kw: io.StringIO(fake_yaml_content))

    # Import the production settings
    prod = importlib.import_module("course_discovery.settings.production")

    # Legacy globals should *not* be present
    assert not hasattr(prod, "DEFAULT_FILE_STORAGE")
    assert not hasattr(prod, "STATICFILES_STORAGE")

    # Modern STORAGES dict should be populated
    assert "default" in prod.STORAGES
    assert prod.STORAGES["default"]["BACKEND"] == "storages.backends.s3boto3.S3Boto3Storage"

    assert "staticfiles" in prod.STORAGES
    assert prod.STORAGES["staticfiles"]["BACKEND"] == "storage.ManifestStaticFilesStorage"

    # Media config still comes through
    assert prod.MEDIA_ROOT == "/tmp/media"
    assert prod.MEDIA_URL == "/media/"
