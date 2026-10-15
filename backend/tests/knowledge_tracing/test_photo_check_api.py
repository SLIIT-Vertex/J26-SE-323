"""The photo-check endpoint on a paper made by the real weekly-paper service."""

import io
import random
from uuid import uuid4

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.knowledge_tracing.infrastructure.pdf.paper_pdf import render_pages
from scripts.make_synthetic_photo import synthesize_photo
from tests.knowledge_tracing import test_weekly_paper as weekly

# The fixtures (an in-memory database with a question bank, and a test client) are shared with
# the weekly-paper tests; assigning them here is what makes pytest offer them to this module.
world = weekly.world
client = weekly.client
api_learner = weekly.api_learner


def jpeg(image: np.ndarray) -> bytes:
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    return data.tobytes()


def make_paper(client: TestClient, world: dict) -> tuple[dict, bytes]:
    learner_id = api_learner(world)
    paper = client.post(f"/api/v1/learners/{learner_id}/papers").json()
    pdf = client.get(paper["pdf_url"]).content
    return paper, pdf


def photo_of(pdf: bytes, page: int, seed: int = 3, **options) -> bytes:
    grays, px_per_mm = render_pages(pdf)
    return jpeg(
        synthesize_photo(
            grays[page - 1], px_per_mm, random.Random(seed), size=(1800, 2400), **options
        ).image
    )


def post(client: TestClient, paper: dict, page: int, data: bytes, **query: str):
    return client.post(
        f"/api/v1/papers/{paper['paper_id']}/pages/{page}/photo-check",
        params=query,
        files={"image": ("photo.jpg", data, "image/jpeg")},
    )


def test_a_good_photo_returns_the_page_and_its_question_blocks(world: dict, client: TestClient) -> None:
    paper, pdf = make_paper(client, world)

    response = post(client, paper, 1, photo_of(pdf, 1))

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["method"] == "markers"
    assert body["failure_reason"] is None
    assert body["blur_score"] >= 2.0
    on_page_one = [i for i in paper["items"] if i["page"] == 1]
    assert [b["position"] for b in body["blocks"]] == [i["position"] for i in on_page_one]
    assert [b["question_id"] for b in body["blocks"]] == [i["question_id"] for i in on_page_one]
    assert all(b["width_px"] > 400 and b["height_px"] > 100 for b in body["blocks"])


def test_the_overlay_and_a_single_crop_come_back_as_images(world: dict, client: TestClient) -> None:
    paper, pdf = make_paper(client, world)
    data = photo_of(pdf, 1)

    overlay = post(client, paper, 1, data, output="overlay")
    crop = post(client, paper, 1, data, output="crop", position="1")
    page = post(client, paper, 1, data, output="page")

    for response in (overlay, crop, page):
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")
    assert Image.open(io.BytesIO(page.content)).size == (1500, 2209)
    crop_size = Image.open(io.BytesIO(crop.content)).size
    assert crop_size[0] > 500 and crop_size[1] > 100


def test_a_missing_question_position_is_not_found(world: dict, client: TestClient) -> None:
    paper, pdf = make_paper(client, world)

    response = post(client, paper, 1, photo_of(pdf, 1), output="crop", position="99")

    assert response.status_code == 404


def test_a_photo_that_is_not_the_page_fails_with_a_clear_reason(world: dict, client: TestClient) -> None:
    paper, _ = make_paper(client, world)
    noise = np.random.default_rng(1).integers(0, 255, (1200, 900, 3), dtype=np.uint8)

    response = post(client, paper, 1, jpeg(noise))

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert body["failure_reason"] in {"low_match", "markers_missing"}
    assert body["message"]  # a sentence for the parent
    assert body["blocks"] == []


def test_a_blurry_photo_says_blurry(world: dict, client: TestClient) -> None:
    paper, pdf = make_paper(client, world)

    body = post(client, paper, 1, photo_of(pdf, 1, blur_sigma=3.5)).json()

    assert body["ok"] is False
    assert body["failure_reason"] == "blurry"
    assert "blurry" in body["message"].lower()
    assert body["blur_score"] < body["blur_minimum"]


def test_the_wrong_page_is_reported(world: dict, client: TestClient) -> None:
    paper, pdf = make_paper(client, world)
    if paper["page_count"] < 2:
        pytest.skip("this paper has one page")

    body = post(client, paper, 1, photo_of(pdf, 2)).json()

    assert body["ok"] is False
    assert body["failure_reason"] == "wrong_page"


def test_failures_as_images_are_422(world: dict, client: TestClient) -> None:
    paper, pdf = make_paper(client, world)

    response = post(client, paper, 1, photo_of(pdf, 1, blur_sigma=3.5), output="overlay")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "blurry"


def test_bytes_that_are_not_a_photo_are_unreadable(world: dict, client: TestClient) -> None:
    paper, _ = make_paper(client, world)

    body = post(client, paper, 1, b"not an image at all").json()

    assert body["ok"] is False
    assert body["failure_reason"] == "unreadable_image"


def test_unknown_paper_and_page_are_not_found(world: dict, client: TestClient) -> None:
    paper, pdf = make_paper(client, world)
    data = photo_of(pdf, 1)

    assert post(client, {"paper_id": str(uuid4())}, 1, data).status_code == 404
    assert post(client, paper, 9, data).status_code == 404
    assert post(client, paper, 0, data).status_code == 404


def test_nothing_is_stored_by_a_check(world: dict, client: TestClient) -> None:
    paper, pdf = make_paper(client, world)
    before = sorted(world["papers"].list(""))

    post(client, paper, 1, photo_of(pdf, 1))

    assert sorted(world["papers"].list("")) == before  # no photo, crop or result was written
