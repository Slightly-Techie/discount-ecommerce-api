import pytest
from django.urls import reverse

from api.products.models import Product


def _ids(response):
    data = response.data
    rows = data["results"] if isinstance(data, dict) and "results" in data else data
    return {str(row["id"]) for row in rows}


@pytest.fixture
def list_url():
    return reverse("products:product-list-create")


def _detail(product):
    return reverse("products:product-detail", args=[product.id])


@pytest.mark.django_db
def test_read_payload_includes_vendor(api_client, vendor_factory, product_factory):
    vendor = vendor_factory()
    with_vendor = product_factory(vendor=vendor)
    without = product_factory(vendor=None)

    data = api_client.get(_detail(with_vendor)).data
    assert data["vendor"] == {"id": str(vendor.id), "name": vendor.name, "slug": vendor.slug}
    assert api_client.get(_detail(without)).data["vendor"] is None


@pytest.mark.django_db
def test_staff_can_assign_vendor(api_client, user_factory, vendor_factory, product_factory):
    staff = user_factory(is_staff=True)
    vendor = vendor_factory()
    product = product_factory(vendor=None)
    api_client.force_authenticate(staff)

    response = api_client.patch(_detail(product), {"vendor": str(vendor.id)}, format="json")
    assert response.status_code == 200
    product.refresh_from_db()
    assert product.vendor == vendor

    response = api_client.patch(_detail(product), {"vendor": None}, format="json")
    assert response.status_code == 200
    product.refresh_from_db()
    assert product.vendor is None


@pytest.mark.django_db
def test_vendor_admin_cannot_set_vendor_or_featured(
    api_client, user_factory, vendor_factory, list_url
):
    vendor_a = vendor_factory()
    vendor_b = vendor_factory()
    owner = user_factory(role="vendor_admin", vendor=vendor_a)
    api_client.force_authenticate(owner)

    response = api_client.post(
        list_url,
        {
            "name": "Mine",
            "price": "10.00",
            "vendor": str(vendor_b.id),
            "is_featured": True,
        },
        format="json",
    )
    assert response.status_code == 201
    product = Product.objects.get(name="Mine")
    assert product.vendor == vendor_a
    assert product.is_featured is False

    response = api_client.patch(
        _detail(product),
        {"vendor": str(vendor_b.id), "is_featured": True, "name": "New"},
        format="json",
    )
    assert response.status_code == 200
    product.refresh_from_db()
    assert product.name == "New"
    assert product.vendor == vendor_a
    assert product.is_featured is False


@pytest.mark.django_db
def test_shoppers_only_see_visible_products(
    api_client, vendor_factory, product_factory, list_url
):
    approved = vendor_factory(status="approved")
    suspended = vendor_factory(status="suspended")
    pending = vendor_factory(status="pending")
    visible = [
        product_factory(status="active", vendor=None),
        product_factory(status="active", vendor=approved),
    ]
    hidden = [
        product_factory(status="draft", vendor=None),
        product_factory(status="archived", vendor=None),
        product_factory(status="active", vendor=None, is_deleted=True),
        product_factory(status="active", vendor=suspended),
        product_factory(status="active", vendor=pending),
    ]

    ids = _ids(api_client.get(list_url))
    assert {str(p.id) for p in visible} <= ids
    assert not ({str(p.id) for p in hidden} & ids)
    for product in hidden:
        assert api_client.get(_detail(product)).status_code == 404


@pytest.mark.django_db
def test_vendor_admin_reads_shop_plus_own_but_writes_own_only(
    api_client, user_factory, vendor_factory, product_factory, list_url
):
    vendor_a = vendor_factory()
    vendor_b = vendor_factory()
    owner = user_factory(role="vendor_admin", vendor=vendor_a)
    own_draft = product_factory(status="draft", vendor=vendor_a)
    other = product_factory(status="active", vendor=vendor_b)
    api_client.force_authenticate(owner)

    ids = _ids(api_client.get(list_url))
    assert {str(own_draft.id), str(other.id)} <= ids

    ids = _ids(api_client.get(list_url, {"vendor": str(vendor_a.id)}))
    assert ids == {str(own_draft.id)}

    response = api_client.patch(_detail(other), {"name": "Hijack"}, format="json")
    assert response.status_code == 404


@pytest.mark.django_db
def test_staff_sees_everything(
    api_client, user_factory, vendor_factory, product_factory, list_url
):
    draft = product_factory(status="draft", vendor=None)
    suspended = product_factory(status="active", vendor=vendor_factory(status="suspended"))
    api_client.force_authenticate(user_factory(is_staff=True))

    ids = _ids(api_client.get(list_url))
    assert {str(draft.id), str(suspended.id)} <= ids


@pytest.mark.django_db
def test_vendorless_vendor_admin_does_not_see_hidden_platform_products(
    api_client, user_factory, product_factory, list_url
):
    hidden = product_factory(status="draft", vendor=None)
    visible = product_factory(status="active", vendor=None)
    api_client.force_authenticate(user_factory(role="vendor_admin"))

    ids = _ids(api_client.get(list_url))
    assert str(visible.id) in ids
    assert str(hidden.id) not in ids
    assert api_client.get(_detail(hidden)).status_code == 404


@pytest.mark.django_db
def test_vendor_cannot_link_another_vendors_product_as_related(
    api_client, user_factory, vendor_factory, product_factory
):
    vendor_a = vendor_factory()
    vendor_b = vendor_factory()
    mine = product_factory(vendor=vendor_a)
    theirs = product_factory(vendor=vendor_b)
    own_other = product_factory(vendor=vendor_a)
    api_client.force_authenticate(user_factory(role="vendor_admin", vendor=vendor_a))

    response = api_client.patch(
        _detail(mine),
        {"related_products": [str(theirs.id), str(own_other.id)]},
        format="json",
    )

    assert response.status_code == 200
    assert set(mine.related_products.all()) == {own_other}
    assert theirs.related_products.count() == 0


@pytest.mark.django_db
def test_staff_can_link_any_related_products(
    api_client, user_factory, vendor_factory, product_factory
):
    first = product_factory(vendor=vendor_factory())
    second = product_factory(vendor=vendor_factory())
    api_client.force_authenticate(user_factory(is_staff=True))

    response = api_client.patch(
        _detail(first), {"related_products": [str(second.id)]}, format="json"
    )

    assert response.status_code == 200
    assert set(first.related_products.all()) == {second}


@pytest.mark.django_db
def test_public_detail_hides_draft_related_products(
    api_client, product_factory
):
    product = product_factory(status="active")
    live = product_factory(status="active")
    draft = product_factory(status="draft")
    product.related_products.add(live, draft)

    related = api_client.get(_detail(product)).data["related_products"]

    assert {row["id"] for row in related} == {str(live.id)}


@pytest.mark.django_db
def test_vendor_sees_own_draft_in_related_products(
    api_client, user_factory, vendor_factory, product_factory
):
    vendor = vendor_factory()
    product = product_factory(vendor=vendor)
    own_draft = product_factory(status="draft", vendor=vendor)
    product.related_products.add(own_draft)
    api_client.force_authenticate(user_factory(role="vendor_admin", vendor=vendor))

    related = api_client.get(_detail(product)).data["related_products"]

    assert {row["id"] for row in related} == {str(own_draft.id)}


@pytest.fixture
def variant_url():
    return reverse("products:product-variant-list-create")


@pytest.fixture
def image_url():
    return reverse("products:product-image-list-create")


def _tiny_image():
    from django.core.files.uploadedfile import SimpleUploadedFile

    gif = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00"
        b"\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    )
    return SimpleUploadedFile("t.gif", gif, content_type="image/gif")


@pytest.mark.django_db
def test_customer_cannot_create_variant(api_client, user_factory, product_factory, variant_url):
    product = product_factory()
    api_client.force_authenticate(user_factory(role="customer"))

    response = api_client.post(
        variant_url, {"product": str(product.id), "name": "Color", "value": "Red"}
    )

    assert response.status_code == 403
    assert product.variants.count() == 0


@pytest.mark.django_db
def test_vendor_variant_create_is_own_products_only(
    api_client, user_factory, vendor_factory, product_factory, variant_url
):
    vendor_a = vendor_factory()
    vendor_b = vendor_factory()
    mine = product_factory(vendor=vendor_a)
    theirs = product_factory(vendor=vendor_b)
    api_client.force_authenticate(user_factory(role="vendor_admin", vendor=vendor_a))

    rejected = api_client.post(
        variant_url, {"product": str(theirs.id), "name": "Color", "value": "Red"}
    )
    created = api_client.post(
        variant_url, {"product": str(mine.id), "name": "Color", "value": "Red"}
    )

    assert rejected.status_code in (400, 403)
    assert theirs.variants.count() == 0
    assert created.status_code == 201


@pytest.mark.django_db
def test_staff_can_create_variant(api_client, user_factory, product_factory, variant_url):
    product = product_factory()
    api_client.force_authenticate(user_factory(is_staff=True, role="customer"))

    response = api_client.post(
        variant_url, {"product": str(product.id), "name": "Color", "value": "Red"}
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_vendor_cannot_change_or_delete_another_vendors_variant(
    api_client, user_factory, vendor_factory, product_factory, variant_url
):
    from api.products.models import ProductVariant

    vendor_a = vendor_factory()
    theirs = product_factory(vendor=vendor_factory())
    variant = ProductVariant.objects.create(product=theirs, name="Size", value="L")
    detail = reverse("products:product-variant-detail", args=[variant.id])
    api_client.force_authenticate(user_factory(role="vendor_admin", vendor=vendor_a))

    assert api_client.patch(detail, {"value": "XL"}, format="json").status_code in (403, 404)
    assert api_client.delete(detail).status_code in (403, 404)
    variant.refresh_from_db()
    assert variant.value == "L"


@pytest.mark.django_db
def test_vendor_can_edit_own_variant(
    api_client, user_factory, vendor_factory, product_factory
):
    from api.products.models import ProductVariant

    vendor = vendor_factory()
    variant = ProductVariant.objects.create(
        product=product_factory(vendor=vendor), name="Size", value="L"
    )
    detail = reverse("products:product-variant-detail", args=[variant.id])
    api_client.force_authenticate(user_factory(role="vendor_admin", vendor=vendor))

    assert api_client.patch(detail, {"value": "XL"}, format="json").status_code == 200


@pytest.mark.django_db
def test_customer_cannot_create_image(api_client, user_factory, product_factory, image_url):
    product = product_factory()
    api_client.force_authenticate(user_factory(role="customer"))

    response = api_client.post(image_url, {"product": str(product.id), "image": _tiny_image()})

    assert response.status_code == 403
    assert product.images.count() == 0


@pytest.mark.django_db
def test_vendor_image_create_is_own_products_only(
    api_client, user_factory, vendor_factory, product_factory, image_url
):
    vendor_a = vendor_factory()
    mine = product_factory(vendor=vendor_a)
    theirs = product_factory(vendor=vendor_factory())
    api_client.force_authenticate(user_factory(role="vendor_admin", vendor=vendor_a))

    rejected = api_client.post(image_url, {"product": str(theirs.id), "image": _tiny_image()})
    created = api_client.post(image_url, {"product": str(mine.id), "image": _tiny_image()})

    assert rejected.status_code in (400, 403)
    assert theirs.images.count() == 0
    assert created.status_code == 201


@pytest.mark.django_db
def test_vendor_cannot_change_or_delete_another_vendors_image(
    api_client, user_factory, vendor_factory, product_factory
):
    from api.products.models import ProductImage

    theirs = product_factory(vendor=vendor_factory())
    image = ProductImage.objects.create(product=theirs, alt_text="x", image="products/x.gif")
    detail = reverse("products:product-image-detail", args=[image.id])
    api_client.force_authenticate(user_factory(role="vendor_admin", vendor=vendor_factory()))

    assert api_client.patch(detail, {"alt_text": "y"}, format="json").status_code in (403, 404)
    assert api_client.delete(detail).status_code in (403, 404)
    assert ProductImage.objects.filter(pk=image.pk, alt_text="x").exists()
