import factory
import factory.fuzzy

from api.vendors.models import Vendor


class VendorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Vendor

    name = factory.Sequence(lambda n: f"Vendor {n}")
    slug = factory.Sequence(lambda n: f"vendor-{n}")
    status = Vendor.Status.APPROVED
    business_email = factory.Faker("company_email")
    phone = factory.Sequence(lambda n: f"+233200{n:06d}")
    address = factory.Faker("address")
    website = factory.Faker("url")
    about = factory.Faker("text", max_nb_chars=200)
    rejection_reason = None
