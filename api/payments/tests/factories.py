from decimal import Decimal

import factory

from api.payments.models import PaymentAccount, PaymentSubmission


class PaymentAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PaymentAccount

    kind = PaymentAccount.Kind.MOMO
    provider = "MTN MoMo"
    account_name = "GrottoMore Ltd"
    account_number = factory.Sequence(lambda n: f"024{n:07d}")
    is_active = True


class PaymentSubmissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PaymentSubmission

    user = factory.SubFactory("api.users.tests.factories.UserFactory")
    account = factory.SubFactory(PaymentAccountFactory)
    amount_expected = Decimal("100.00")
    reference = factory.Sequence(lambda n: f"TX{n:08d}")
    sender_name = "Ama Mensah"
