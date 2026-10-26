import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from api.products.models import Product


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


def _png(name="photo.png", size=(4, 4)):
    buf = io.BytesIO()
    Image.new("RGB", size, "teal").save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@pytest.fixture
def vendor_client(api_client, user_factory, vendor):
    api_client.force_authenticate(user_factory(role="vendor_admin", vendor=vendor))
    return api_client


@pytest.mark.django_db
def test_vendor_creates_product_with_uploaded_image(vendor_client):
    response = vendor_client.post(
        reverse("products:product-list-create"),
        {"name": "Kente scarf", "price": "120.00", "stock": 3, "image": _png()},
        format="multipart",
    )

    assert response.status_code == 201, response.data
    product = Product.objects.get(name="Kente scarf")
    assert response.data["id"] == str(product.id)
    assert product.image.name.startswith("product_images/")
    assert response.data["image"].endswith(".png")


@pytest.mark.django_db
def test_vendor_replaces_image_on_update(vendor_client, vendor, product_factory):
    product = product_factory(vendor=vendor)

    response = vendor_client.patch(
        reverse("products:product-detail", args=[product.id]),
        {"image": _png("new.png")},
        format="multipart",
    )

    assert response.status_code == 200, response.data
    product.refresh_from_db()
    assert product.image.name.startswith("product_images/new")


@pytest.mark.django_db
def test_rejects_unsupported_image_type(vendor_client):
    gif = SimpleUploadedFile(
        "anim.gif",
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01"
        b"\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
        content_type="image/gif",
    )
    response = vendor_client.post(
        reverse("products:product-list-create"),
        {"name": "Gif", "price": "10.00", "image": gif},
        format="multipart",
    )

    assert response.status_code == 400
    assert "image" in response.data


@pytest.mark.django_db
def test_rejects_oversized_image(vendor_client, monkeypatch):
    monkeypatch.setattr("api.products.serializers.MAX_PRODUCT_IMAGE_BYTES", 10)
    response = vendor_client.post(
        reverse("products:product-list-create"),
        {"name": "Big", "price": "10.00", "image": _png()},
        format="multipart",
    )

    assert response.status_code == 400
    assert "image" in response.data
