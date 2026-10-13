import io
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.config import Settings
from app.knowledge_tracing.infrastructure.storage import (
    InvalidStorageKey,
    LocalStorage,
    S3Storage,
    StorageKeyNotFound,
    create_storage,
)

BUCKET = "test-bucket"


@pytest.fixture
def local(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "store")


def test_local_round_trip(local: LocalStorage) -> None:
    local.put("questions/3/3.41.png", b"\x89PNG data")

    assert local.exists("questions/3/3.41.png")
    assert local.get("questions/3/3.41.png") == b"\x89PNG data"


def test_local_overwrite_replaces_content(local: LocalStorage) -> None:
    local.put("a/b.txt", b"one")
    local.put("a/b.txt", b"two")

    assert local.get("a/b.txt") == b"two"


def test_local_missing_key(local: LocalStorage) -> None:
    assert not local.exists("nope.png")
    with pytest.raises(StorageKeyNotFound):
        local.get("nope.png")
    with pytest.raises(StorageKeyNotFound):
        local.delete("nope.png")
    with pytest.raises(StorageKeyNotFound):
        local.signed_url("nope.png", 600)


def test_local_list_filters_by_prefix_and_sorts(local: LocalStorage) -> None:
    for key in ["questions/2/2.1.png", "questions/1/1.2.png", "questions/1/1.1.png", "papers/x.pdf"]:
        local.put(key, b"x")

    assert local.list("questions/1/") == ["questions/1/1.1.png", "questions/1/1.2.png"]
    assert local.list("questions/") == [
        "questions/1/1.1.png",
        "questions/1/1.2.png",
        "questions/2/2.1.png",
    ]
    assert local.list() == sorted(local.list())
    assert local.list("missing/") == []


def test_local_delete(local: LocalStorage) -> None:
    local.put("a.txt", b"x")
    local.delete("a.txt")

    assert not local.exists("a.txt")


def test_local_signed_url_points_at_the_file(local: LocalStorage) -> None:
    local.put("papers/p.pdf", b"%PDF")

    assert local.signed_url("papers/p.pdf", 600).startswith("file:///")


@pytest.mark.parametrize(
    "key",
    ["", " ", "../secret.txt", "a/../../secret.txt", "/etc/passwd", "a//b.png", "a/./b.png",
     "C:/Windows/win.ini", "a\\b.png", " lead.png", "trail.png "],
)
def test_unsafe_keys_are_rejected(local: LocalStorage, key: str) -> None:
    with pytest.raises(InvalidStorageKey):
        local.put(key, b"x")
    with pytest.raises(InvalidStorageKey):
        local.get(key)
    with pytest.raises(InvalidStorageKey):
        local.exists(key)


def test_nothing_is_written_outside_the_root(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "store")
    with pytest.raises(InvalidStorageKey):
        storage.put("../escaped.txt", b"x")

    assert not (tmp_path / "escaped.txt").exists()


# --- S3 (no network: botocore Stubber and local presigning) ---------------------------------


@pytest.fixture
def s3() -> tuple[S3Storage, Stubber]:
    client = boto3.client(
        "s3",
        region_name="ap-south-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    stubber = Stubber(client)
    stubber.activate()
    return S3Storage(BUCKET, "ap-south-1", client=client), stubber


def test_s3_get(s3: tuple[S3Storage, Stubber]) -> None:
    storage, stubber = s3
    stubber.add_response(
        "get_object",
        {"Body": _body(b"image bytes")},
        {"Bucket": BUCKET, "Key": "questions/1/1.1.png"},
    )

    assert storage.get("questions/1/1.1.png") == b"image bytes"
    stubber.assert_no_pending_responses()


def test_s3_get_missing_key(s3: tuple[S3Storage, Stubber]) -> None:
    storage, stubber = s3
    stubber.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)

    with pytest.raises(StorageKeyNotFound):
        storage.get("questions/1/9.9.png")


def test_s3_put_sets_content_type(s3: tuple[S3Storage, Stubber]) -> None:
    storage, stubber = s3
    stubber.add_response(
        "put_object",
        {},
        {"Bucket": BUCKET, "Key": "papers/p.pdf", "Body": b"%PDF", "ContentType": "application/pdf"},
    )

    storage.put("papers/p.pdf", b"%PDF", content_type="application/pdf")
    stubber.assert_no_pending_responses()


def test_s3_exists(s3: tuple[S3Storage, Stubber]) -> None:
    storage, stubber = s3
    stubber.add_response("head_object", {}, {"Bucket": BUCKET, "Key": "a.png"})
    stubber.add_client_error("head_object", service_error_code="404", http_status_code=404)

    assert storage.exists("a.png")
    assert not storage.exists("b.png")


def test_s3_list_follows_pagination(s3: tuple[S3Storage, Stubber]) -> None:
    storage, stubber = s3
    stubber.add_response(
        "list_objects_v2",
        {
            "IsTruncated": True,
            "NextContinuationToken": "t1",
            "Contents": [{"Key": "questions/1/1.2.png"}, {"Key": "questions/1/1.1.png"}],
        },
        {"Bucket": BUCKET, "Prefix": "questions/1/"},
    )
    stubber.add_response(
        "list_objects_v2",
        {"IsTruncated": False, "Contents": [{"Key": "questions/1/1.3.png"}]},
        {"Bucket": BUCKET, "Prefix": "questions/1/", "ContinuationToken": "t1"},
    )

    assert storage.list("questions/1/") == [
        "questions/1/1.1.png",
        "questions/1/1.2.png",
        "questions/1/1.3.png",
    ]


def test_s3_list_empty_prefix(s3: tuple[S3Storage, Stubber]) -> None:
    storage, stubber = s3
    stubber.add_response(
        "list_objects_v2", {"IsTruncated": False}, {"Bucket": BUCKET, "Prefix": "nothing/"}
    )

    assert storage.list("nothing/") == []


def test_s3_signed_url_is_short_lived_and_private(s3: tuple[S3Storage, Stubber]) -> None:
    storage, _ = s3

    url = storage.signed_url("questions/1/1.1.png", 600)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert BUCKET in parsed.netloc or BUCKET in parsed.path
    assert parsed.path.endswith("questions/1/1.1.png")
    assert query["X-Amz-Expires"] == ["600"]
    assert "X-Amz-Signature" in query


def test_s3_rejects_unsafe_keys(s3: tuple[S3Storage, Stubber]) -> None:
    storage, _ = s3

    with pytest.raises(InvalidStorageKey):
        storage.get("../x")
    with pytest.raises(InvalidStorageKey):
        storage.signed_url("/abs", 60)


def test_s3_requires_a_bucket() -> None:
    with pytest.raises(ValueError):
        S3Storage("")


# --- factory --------------------------------------------------------------------------------


def _settings(**values: str) -> Settings:
    return Settings(database_url="sqlite://", _env_file=None, **values)  # type: ignore[call-arg]


def test_factory_builds_local(tmp_path: Path) -> None:
    storage = create_storage(
        _settings(storage_backend="local", local_storage_dir=str(tmp_path / "files"))
    )

    assert isinstance(storage, LocalStorage)


def test_factory_builds_s3() -> None:
    storage = create_storage(
        _settings(storage_backend="S3", s3_bucket=BUCKET, s3_region="ap-south-1")
    )

    assert isinstance(storage, S3Storage)
    assert storage.bucket == BUCKET


def test_factory_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError):
        create_storage(_settings(storage_backend="ftp"))


def _body(data: bytes) -> StreamingBody:
    return StreamingBody(io.BytesIO(data), len(data))
