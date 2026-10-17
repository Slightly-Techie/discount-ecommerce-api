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
