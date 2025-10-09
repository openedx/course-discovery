import importlib
import sys
import textwrap


def test_production_media_storage(monkeypatch, tmp_path):
    """Test that MEDIA_STORAGE_BACKEND YAML block overrides default storage + media settings."""

    # Create a temporary YAML file to act as DISCOVERY_CFG
    fake_config = tmp_path / "config.yaml"
    fake_yaml_content = textwrap.dedent("""
        MEDIA_STORAGE_BACKEND:
          AWS_S3_OBJECT_PARAMETERS:
            CacheControl: max-age=31536
          AWS_QUERYSTRING_AUTH: false
          AWS_QUERYSTRING_EXPIRE: false
          AWS_S3_CUSTOM_DOMAIN: cdn.org
          AWS_STORAGE_BUCKET_NAME: tests
          DEFAULT_FILE_STORAGE: storages.backends.s3boto3.S3Boto3Storage
          MEDIA_ROOT: media
          MEDIA_URL: https://cdn.org/media/
    """)
    fake_config.write_text(fake_yaml_content)

    # Patch environment variable so production.py sees the config
    monkeypatch.setenv("DISCOVERY_CFG", str(fake_config))

    # Remove production module if already imported
    sys.modules.pop("course_discovery.settings.production", None)
    # Import production settings fresh
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
    assert prod.AWS_S3_OBJECT_PARAMETERS == {"CacheControl": "max-age=31536"}
