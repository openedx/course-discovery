import builtins
import importlib
import io
import sys
import types


def test_production_media_storage(monkeypatch, tmp_path):
    """Test that MEDIA_STORAGE_BACKEND YAML block overrides default storage + media settings."""

    # Create a temporary YAML file to act as DISCOVERY_CFG
    fake_config = tmp_path / "config.yaml"
    fake_yaml_content = """
        MEDIA_STORAGE_BACKEND:
          AWS_S3_OBJECT_PARAMETERS:
            CacheControl: max-age=31536000
          AWS_QUERYSTRING_AUTH: false
          AWS_QUERYSTRING_EXPIRE: false
          AWS_S3_CUSTOM_DOMAIN: cdn.org
          AWS_STORAGE_BUCKET_NAME: tests
          DEFAULT_FILE_STORAGE: storages.backends.s3boto3.S3Boto3Storage
          MEDIA_ROOT: media
          MEDIA_URL: https://cdn.org/media/
    """
    fake_config.write_text(fake_yaml_content)

    # Patch environment variable so production.py sees the config
    monkeypatch.setenv("DISCOVERY_CFG", str(fake_config))

    # Remove production module if already imported
    sys.modules.pop("course_discovery.settings.production", None)

    # Patch dependencies
    monkeypatch.setitem(
        sys.modules,
        "course_discovery.settings.utils",
        types.SimpleNamespace(
            get_env_setting=lambda key: str(fake_config),
            get_logger_config=lambda *a, **kw: {},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "edx_django_utils.plugins",
        types.SimpleNamespace(add_plugins=lambda *a, **kw: None),
    )

    # Patch open so production reads our YAML content
    monkeypatch.setattr(builtins, "open", lambda *a, **kw: io.StringIO(fake_yaml_content))

    # Import production settings
    prod = importlib.import_module("course_discovery.settings.production")

    # Assert MEDIA_STORAGE_BACKEND unpacked correctly
    assert "default" in prod.STORAGES
    assert prod.STORAGES["default"]["BACKEND"] == "storages.backends.s3boto3.S3Boto3Storage"
    assert prod.MEDIA_URL == "https://cdn.org/media/"
    assert prod.MEDIA_ROOT == "media"

    # Assert all AWS keys are present
    assert prod.AWS_STORAGE_BUCKET_NAME == "tests"
    assert prod.AWS_S3_CUSTOM_DOMAIN == "cdn.org"
    assert prod.AWS_QUERYSTRING_AUTH is False
    assert prod.AWS_QUERYSTRING_EXPIRE is False
    assert prod.AWS_S3_OBJECT_PARAMETERS == {"CacheControl": "max-age=31536000"}
