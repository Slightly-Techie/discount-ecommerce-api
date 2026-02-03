# Order Processing Guide

## Order System Overview

The order processing system handles the complete checkout flow including:
- Multi-vendor order splitting
- Shipping calculation by country/zone
- Tax calculation by country/zone
- Coupon/discount application
- Stock management
- Order status workflow

## Order Model Structure

### Order Model (api/orders/models.py:78)
```python
class Order(BaseModel):
    user = ForeignKey(User, on_delete=models.CASCADE)
    vendor = ForeignKey("vendors.Vendor", on_delete=models.SET_NULL, null=True)

    # Status tracking
    status = CharField(choices=Status.choices, default=Status.PENDING)

    # Financial
    subtotal = DecimalField(max_digits=10, decimal_places=2)
    tax_amount = DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = DecimalField(max_digits=10, decimal_places=2, default=0)
    total = DecimalField(max_digits=10, decimal_places=2)

    # Relationships
    address = ForeignKey(Address, on_delete=models.SET_NULL, null=True)
    coupon = ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)

    # Tracking
    order_number = CharField(max_length=50, unique=True, blank=True)
    tracking_number = CharField(max_length=100, blank=True)
    notes = TextField(blank=True)
```

### Order Status Choices (api/orders/models.py:72)
- **pending**: Initial state after order creation
- **paid**: Payment confirmed
- **shipped**: Order shipped to customer
- **delivered**: Order delivered successfully
- **cancelled**: Order cancelled (by user or admin)

### OrderItem Model (api/orders/models.py:125)
```python
class OrderItem(BaseModel):
    order = ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = PositiveIntegerField(default=1)
    price = DecimalField(max_digits=10, decimal_places=2)  # Price at time of order
    subtotal = DecimalField(max_digits=10, decimal_places=2)
```

## Checkout Flow

### Checkout Endpoint (api/orders/views.py:120)
```
POST /api/orders/checkout/
Headers: Authorization: Bearer {access_token}
Body: {
    "address_id": "uuid",
    "coupon_code": "SAVE20",  # Optional
    "shipping_method": "Standard",  # Optional, defaults to "Standard"
    "notes": "Please deliver in the morning"  # Optional
}
Response: {
    "orders": [...],  # Array of orders (split by vendor)
    "total_amount": "250.00",
    "message": "Orders created successfully"
}
```

### Step-by-Step Checkout Process

#### Step 1: Validate User & Cart
```python
user = request.user
cart = Cart.objects.filter(user=user).first()
if not cart or cart.items.count() == 0:
    return Response({"error": "Cart is empty"}, status=400)
```

#### Step 2: Validate Address
```python
address = get_object_or_404(Address, id=address_id, user=user)
```

#### Step 3: Check Delivery Availability (api/common/utils.py:110)
```python
from api.common.utils import check_delivery_availability

available, message = check_delivery_availability(address.country)
if not available:
    return Response({"error": message}, status=400)
```

#### Step 4: Group Cart Items by Vendor
```python
from collections import defaultdict

items_by_vendor = defaultdict(list)
for cart_item in cart.items.all():
    vendor = cart_item.product.vendor or None  # None for platform products
    items_by_vendor[vendor].append(cart_item)
```

**Why**: Each vendor needs separate order for independent fulfillment.

#### Step 5: Calculate Subtotal Per Vendor
```python
vendor_orders = []
for vendor, items in items_by_vendor.items():
    subtotal = sum(item.product.price * item.quantity for item in items)
```

#### Step 6: Calculate Shipping (api/common/utils.py:43)
```python
from api.common.utils import calculate_shipping

shipping_cost = calculate_shipping(
    subtotal=subtotal,
    address=address,
    shipping_method_name=shipping_method,
    weight=0  # Optional: calculate total weight
)

if shipping_cost is None:
    return Response({"error": "Shipping not available"}, status=400)
```

**Shipping Calculation Logic**:
1. Look up country → shipping zone
2. Find active shipping method in zone
3. Check if free shipping applies (subtotal > free_over threshold)
4. Return calculated cost or free_over amount

#### Step 7: Calculate Tax (api/common/utils.py:75)
```python
from api.common.utils import calculate_tax

tax_amount = calculate_tax(subtotal=subtotal, address=address)
```

**Tax Calculation Logic**:
1. Look up country → tax zone
2. Get latest active tax rate
3. Calculate: subtotal * rate.rate
4. Return tax amount (Decimal)

#### Step 8: Apply Coupon (if provided)
```python
discount_amount = Decimal("0.00")
coupon = None

if coupon_code:
    try:
        coupon = Coupon.objects.get(code=coupon_code, is_active=True)
        is_valid, reason = coupon.is_valid_for_user(user, subtotal)

        if is_valid:
            discount_amount = coupon.calculate_discount(subtotal)
        else:
            return Response({"error": reason}, status=400)
    except Coupon.DoesNotExist:
        return Response({"error": "Invalid coupon code"}, status=400)
```

#### Step 9: Calculate Total
```python
total = subtotal + shipping_cost + tax_amount - discount_amount
```

#### Step 10: Create Order (Within Transaction)
```python
from django.db import transaction

with transaction.atomic():
    # Generate unique order number
    order_number = f"ORD-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    # Create order
    order = Order.objects.create(
        user=user,
        vendor=vendor,
        order_number=order_number,
        subtotal=subtotal,
        tax_amount=tax_amount,
        shipping_cost=shipping_cost,
        discount_amount=discount_amount,
        total=total,
        address=address,
        coupon=coupon,
        status="pending",
        notes=notes
    )
```

#### Step 11: Create Order Items
```python
    for cart_item in items:
        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            quantity=cart_item.quantity,
            price=cart_item.product.price,
            subtotal=cart_item.product.price * cart_item.quantity
        )
```

#### Step 12: Update Product Stock
```python
        # Reduce stock
        product = cart_item.product
        if product.stock < cart_item.quantity:
            raise ValueError(f"Insufficient stock for {product.name}")

        product.stock -= cart_item.quantity
        product.save()
```

#### Step 13: Update Coupon Usage
```python
    if coupon:
        CouponUsage.objects.create(
            coupon=coupon,
            user=user,
            order=order,
            discount_amount=discount_amount
        )
```

#### Step 14: Clear Cart
```python
    cart.items.all().delete()  # Remove all cart items
```

#### Step 15: Return Response
```python
    vendor_orders.append(order)

return Response({
    "orders": OrderSerializer(vendor_orders, many=True).data,
    "total_amount": sum(order.total for order in vendor_orders),
    "message": f"{len(vendor_orders)} order(s) created successfully"
}, status=201)
```

## Shipping Management

### Country Model (api/orders/models.py:10)
```python
class Country(BaseModel):
    code = CharField(max_length=2, unique=True)  # ISO 3166-1 alpha-2
    name = CharField(max_length=255)
```

Load countries via management command (api/common/management/commands/add_countries.py:5):
```bash
python manage.py add_countries
```

### ShippingZone Model (api/orders/models.py:20)
```python
class ShippingZone(BaseModel):
    name = CharField(max_length=255)
    countries = ManyToManyField(Country, related_name="shipping_zones")
    is_active = BooleanField(default=True)
```

**Example Zones**:
- West Africa (Ghana, Nigeria, Senegal, etc.)
- East Africa (Kenya, Tanzania, Uganda, etc.)
- Europe (UK, Germany, France, etc.)
- North America (USA, Canada)

### ShippingMethod Model (api/orders/models.py:35)
```python
class ShippingMethod(BaseModel):
    zone = ForeignKey(ShippingZone, on_delete=models.CASCADE)
    name = CharField(max_length=255)  # "Standard", "Express", "Overnight"
    cost = DecimalField(max_digits=10, decimal_places=2)
    estimated_days = PositiveIntegerField()
    free_over = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = BooleanField(default=True)
```

**Free Shipping**: If order subtotal > `free_over`, shipping is free.

### Setting Up Shipping

**1. Create shipping zones**:
```python
zone = ShippingZone.objects.create(name="West Africa")
zone.countries.add(ghana, nigeria, senegal)
```

**2. Add shipping methods**:
```python
ShippingMethod.objects.create(
    zone=zone,
    name="Standard",
    cost=Decimal("10.00"),
    estimated_days=7,
    free_over=Decimal("100.00")  # Free shipping on orders over $100
)

ShippingMethod.objects.create(
    zone=zone,
    name="Express",
    cost=Decimal("25.00"),
    estimated_days=3,
    free_over=None  # No free shipping for express
)
```

## Tax Management

### TaxZone Model (api/orders/models.py:55)
```python
class TaxZone(BaseModel):
    name = CharField(max_length=255)
    countries = ManyToManyField(Country, related_name="tax_zones")
    is_active = BooleanField(default=True)
```

### TaxRate Model (api/orders/models.py:68)
```python
class TaxRate(BaseModel):
    zone = ForeignKey(TaxZone, on_delete=models.CASCADE)
    rate = DecimalField(max_digits=5, decimal_places=4)  # 0.1500 = 15%
    start_date = DateField()
    end_date = DateField(null=True, blank=True)
    is_active = BooleanField(default=True)
```

**Multiple Rates**: Support tax rate changes over time via start/end dates.

### Setting Up Tax

**1. Create tax zones**:
```python
zone = TaxZone.objects.create(name="Ghana VAT")
zone.countries.add(ghana)
```

**2. Add tax rates**:
```python
TaxRate.objects.create(
    zone=zone,
    rate=Decimal("0.1500"),  # 15% VAT
    start_date=date(2024, 1, 1),
    end_date=None  # Open-ended
)
```

## Coupon System

### Coupon Model (api/orders/models.py:150)
```python
class Coupon(BaseModel):
    code = CharField(max_length=50, unique=True)
    discount_type = CharField(choices=DiscountType.choices)  # "fixed" or "percentage"
    discount_value = DecimalField(max_digits=10, decimal_places=2)
    max_discount = DecimalField(max_digits=10, decimal_places=2, null=True)

    # Validity
    valid_from = DateTimeField()
    valid_to = DateTimeField()
    is_active = BooleanField(default=True)

    # Constraints
    min_order_amount = DecimalField(max_digits=10, decimal_places=2, default=0)
    usage_limit = PositiveIntegerField(null=True, blank=True)
    per_user_limit = PositiveIntegerField(null=True, blank=True)
```

### Coupon Validation (api/orders/models.py:180)
```python
def is_valid_for_user(self, user, order_amount):
    # Check if active
    if not self.is_active:
        return False, "Coupon is not active"

    # Check date range
    now = timezone.now()
    if now < self.valid_from or now > self.valid_to:
        return False, "Coupon has expired"

    # Check minimum order amount
    if order_amount < self.min_order_amount:
        return False, f"Minimum order amount is {self.min_order_amount}"

    # Check total usage limit
    if self.usage_limit:
        total_used = CouponUsage.objects.filter(coupon=self).count()
        if total_used >= self.usage_limit:
            return False, "Coupon usage limit reached"

    # Check per-user limit
    if self.per_user_limit:
        user_used = CouponUsage.objects.filter(coupon=self, user=user).count()
        if user_used >= self.per_user_limit:
            return False, "You have already used this coupon"

    return True, "Valid"
```

### Discount Calculation (api/orders/models.py:215)
```python
def calculate_discount(self, order_amount):
    if self.discount_type == "fixed":
        discount = self.discount_value
    else:  # percentage
        discount = order_amount * (self.discount_value / 100)

    # Apply max discount cap
    if self.max_discount and discount > self.max_discount:
        discount = self.max_discount

    return discount
```

### Creating Coupons

**Fixed discount**:
```python
Coupon.objects.create(
    code="SAVE20",
    discount_type="fixed",
    discount_value=Decimal("20.00"),
    valid_from=timezone.now(),
    valid_to=timezone.now() + timedelta(days=30),
    min_order_amount=Decimal("50.00")
)
```

**Percentage discount**:
```python
Coupon.objects.create(
    code="PERCENT15",
    discount_type="percentage",
    discount_value=Decimal("15.00"),  # 15%
    max_discount=Decimal("50.00"),  # Max $50 discount
    valid_from=timezone.now(),
    valid_to=timezone.now() + timedelta(days=30),
    usage_limit=100,  # Limited to 100 uses
    per_user_limit=1  # One per user
)
```

## Order Status Workflow

### Status Transitions (api/orders/models.py:230)
```python
STATUS_TRANSITIONS = {
    "pending": ["paid", "cancelled"],
    "paid": ["shipped", "cancelled"],
    "shipped": ["delivered"],
    "delivered": [],
    "cancelled": []
}

def can_transition_to(self, new_status):
    return new_status in STATUS_TRANSITIONS.get(self.status, [])
```

### Updating Order Status (api/orders/views.py:200)
```
PATCH /api/orders/{order_id}/
Headers: Authorization: Bearer {access_token}
Body: {"status": "shipped", "tracking_number": "TRACK123"}
Response: 200 with updated order
```

**Validation**:
```python
def perform_update(self, serializer):
    new_status = serializer.validated_data.get("status")
    order = self.get_object()

    if new_status and not order.can_transition_to(new_status):
        raise ValidationError(f"Cannot transition from {order.status} to {new_status}")

    serializer.save()
```

## Order Management Endpoints

### List User Orders (api/orders/views.py:30)
```
GET /api/orders/my-orders/
Headers: Authorization: Bearer {access_token}
Query: ?status=pending, ?ordering=-created_at
Response: Paginated list of user's orders
```

### List Vendor Orders (api/orders/views.py:45)
```
GET /api/orders/vendor-orders/
Headers: Authorization: Bearer {vendor_access_token}
Response: Orders containing vendor's products
```

**Permission**: IsVendorAdmin only.

### Get Order Detail (api/orders/views.py:70)
```
GET /api/orders/{order_id}/
Headers: Authorization: Bearer {access_token}
Response: Full order details with items
```

**Access Control**:
- Customer sees own orders
- Vendor sees orders containing their products
- Admin sees all orders

### Update Order Status (api/orders/views.py:85)
```
PATCH /api/orders/{order_id}/
Headers: Authorization: Bearer {access_token}
Body: {"status": "shipped", "tracking_number": "ABC123"}
Response: 200 with updated order
```

**Permissions**:
- Vendor can update own orders
- Admin can update any order
- Customer cannot update status (can only cancel)

### Cancel Order (api/orders/views.py:110)
```
POST /api/orders/{order_id}/cancel/
Headers: Authorization: Bearer {access_token}
Response: 200, order status set to "cancelled"
```

**Stock Restoration**: Restore product stock when order cancelled:
```python
for item in order.items.all():
    item.product.stock += item.quantity
    item.product.save()
```

## Testing Order Processing

### Factory for Orders (api/orders/tests/factories.py:5)
```python
class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    vendor = factory.SubFactory(VendorFactory)
    subtotal = factory.fuzzy.FuzzyDecimal(50.00, 500.00)
    total = factory.LazyAttribute(lambda o: o.subtotal)
    status = "pending"
```

### Test Checkout Flow
```python
@pytest.mark.django_db
def test_checkout(api_client, user, cart_with_items, address):
    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    data = {"address_id": str(address.id)}

    response = api_client.post(url, data)

    assert response.status_code == 201
    assert Order.objects.filter(user=user).exists()
    assert cart_with_items.items.count() == 0  # Cart cleared
```

### Test Stock Reduction
```python
@pytest.mark.django_db
def test_checkout_reduces_stock(api_client, user, product, address):
    initial_stock = product.stock
    cart = CartFactory(user=user)
    CartItemFactory(cart=cart, product=product, quantity=2)

    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {"address_id": str(address.id)})

    assert response.status_code == 201
    product.refresh_from_db()
    assert product.stock == initial_stock - 2
```

### Test Multi-Vendor Order Splitting
```python
@pytest.mark.django_db
def test_multi_vendor_checkout(api_client, user, address):
    vendor1 = VendorFactory()
    vendor2 = VendorFactory()

    product1 = ProductFactory(vendor=vendor1)
    product2 = ProductFactory(vendor=vendor2)

    cart = CartFactory(user=user)
    CartItemFactory(cart=cart, product=product1, quantity=1)
    CartItemFactory(cart=cart, product=product2, quantity=1)

    api_client.force_authenticate(user=user)
    url = reverse("orders:checkout")
    response = api_client.post(url, {"address_id": str(address.id)})

    assert response.status_code == 201
    assert len(response.data["orders"]) == 2  # Two separate orders
    assert Order.objects.filter(vendor=vendor1).exists()
    assert Order.objects.filter(vendor=vendor2).exists()
```

## Common Order Scenarios

### Scenario 1: Simple Checkout
1. Customer adds products to cart
2. Customer provides shipping address
3. POST /api/orders/checkout/
4. Order created with status="pending"
5. Stock reduced, cart cleared

### Scenario 2: Checkout with Coupon
1. Customer has $100 cart
2. Applies "SAVE20" coupon (fixed $20 off)
3. Order total: $100 - $20 = $80
4. Coupon usage recorded

### Scenario 3: Free Shipping
1. Customer cart subtotal: $150
2. Shipping method: Standard ($10, free over $100)
3. Shipping cost: $0 (free)
4. Order total: $150 + $0 + tax

### Scenario 4: Multi-Vendor Order
1. Cart contains products from 3 vendors
2. Checkout creates 3 separate orders
3. Each vendor ships independently
4. Customer receives 3 tracking numbers

### Scenario 5: Order Fulfillment
1. Vendor receives order (status="pending")
2. Customer pays (status="paid")
3. Vendor ships (status="shipped", adds tracking number)
4. Customer receives (status="delivered")

### Scenario 6: Order Cancellation
1. Customer cancels before shipping (status="pending")
2. System sets status="cancelled"
3. Product stock restored
4. Coupon usage removed (if applicable)
