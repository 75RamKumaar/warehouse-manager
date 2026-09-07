from decimal import Decimal

from django.db import models
from django.urls import reverse


UNIT_CHOICES = [
    ('kg', 'Kilogram (kg)'),
    ('g', 'Gram (g)'),
    ('ltr', 'Litre (ltr)'),
    ('ml', 'Millilitre (ml)'),
    ('pcs', 'Pieces (pcs)'),
    ('box', 'Box'),
    ('bag', 'Bag'),
]

PAYMENT_MODE_CHOICES = [
    ('Cash', 'Cash'),
    ('Bank Transfer', 'Bank Transfer'),
    ('UPI', 'UPI'),
    ('Cheque', 'Cheque'),
    ('Card', 'Card'),
]


class BusinessSettings(models.Model):
    """Singleton-style settings row (always pk=1)."""
    business_name = models.CharField(max_length=120, default='My Shop')
    address = models.TextField(blank=True)
    state = models.CharField(
        max_length=60, blank=True,
        help_text='Used to work out CGST+SGST (same state) vs IGST (different state) on bills.'
    )
    gstin = models.CharField('GSTIN', max_length=15, blank=True)
    currency = models.CharField(max_length=5, default='₹')
    default_gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    invoice_counter = models.PositiveIntegerField(default=1)
    purchase_counter = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Business settings'
        verbose_name_plural = 'Business settings'

    def __str__(self):
        return self.business_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def next_invoice_number(self):
        number = f'INV-{self.invoice_counter:04d}'
        while Invoice.objects.filter(number=number).exists():
            self.invoice_counter += 1
            number = f'INV-{self.invoice_counter:04d}'
        self.invoice_counter += 1
        self.save(update_fields=['invoice_counter'])
        return number

    def next_purchase_number(self):
        number = f'PUR-{self.purchase_counter:04d}'
        while Purchase.objects.filter(number=number).exists():
            self.purchase_counter += 1
            number = f'PUR-{self.purchase_counter:04d}'
        self.purchase_counter += 1
        self.save(update_fields=['purchase_counter'])
        return number

    def is_interstate_with(self, party_state):
        """True if the party's state differs from the business's (→ IGST instead of CGST+SGST)."""
        if not self.state or not party_state:
            return False
        return self.state.strip().lower() != party_state.strip().lower()


class BusinessProfile(models.Model):
    business_name = models.CharField(max_length=120, default='My Shop')
    owner_name = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    gstin = models.CharField('GSTIN', max_length=15, blank=True)
    state = models.CharField(max_length=60, blank=True)
    city = models.CharField(max_length=80, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    currency = models.CharField(max_length=5, default='₹')
    default_gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    logo = models.FileField(upload_to='business_logos/', blank=True)
    is_active = models.BooleanField(default=False)
    invoice_counter = models.PositiveIntegerField(default=1)
    purchase_counter = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'business_name']
        constraints = [
            models.UniqueConstraint(
                fields=['is_active'], condition=models.Q(is_active=True), name='one_active_business_profile'
            ),
        ]

    def __str__(self):
        return self.business_name

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).first() or cls.objects.order_by('pk').first()

    def set_active(self):
        type(self).objects.exclude(pk=self.pk).update(is_active=False)
        if not self.is_active:
            self.is_active = True
            self.save(update_fields=['is_active', 'updated_at'])

    def next_invoice_number(self):
        number = f'INV-{self.invoice_counter:04d}'
        while Invoice.objects.filter(number=number).exists():
            self.invoice_counter += 1
            number = f'INV-{self.invoice_counter:04d}'
        self.invoice_counter += 1
        self.save(update_fields=['invoice_counter', 'updated_at'])
        return number

    def next_purchase_number(self):
        number = f'PUR-{self.purchase_counter:04d}'
        while Purchase.objects.filter(number=number).exists():
            self.purchase_counter += 1
            number = f'PUR-{self.purchase_counter:04d}'
        self.purchase_counter += 1
        self.save(update_fields=['purchase_counter', 'updated_at'])
        return number

    def is_interstate_with(self, party_state):
        if not self.state or not party_state:
            return False
        return self.state.strip().lower() != party_state.strip().lower()


class Product(models.Model):
    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=40, unique=True)
    category = models.CharField(max_length=80, blank=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='kg')
    hsn_code = models.CharField('HSN code', max_length=15, blank=True)
    gst_rate = models.DecimalField('GST rate (%)', max_digits=5, decimal_places=2, default=Decimal('5.00'))
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.sku})'

    def get_absolute_url(self):
        return reverse('inventory_list')

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    @property
    def stock_value(self):
        return self.quantity * self.cost_price


class Party(models.Model):
    """Shared fields for Customer and Supplier — kept as an abstract base, not a table."""
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    state = models.CharField(max_length=60, blank=True, help_text='Used to work out CGST+SGST vs IGST.')
    gstin = models.CharField('GSTIN', max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['name']

    def __str__(self):
        return self.name


class Customer(Party):
    def get_absolute_url(self):
        return reverse('customer_detail', args=[self.pk])

    @property
    def total_billed(self):
        return self.invoices.aggregate(s=models.Sum('total'))['s'] or Decimal('0')

    @property
    def total_received(self):
        return self.receipts.aggregate(s=models.Sum('amount'))['s'] or Decimal('0')

    @property
    def balance_due(self):
        """Positive = customer owes you."""
        return self.total_billed - self.total_received


class Supplier(Party):
    def get_absolute_url(self):
        return reverse('supplier_detail', args=[self.pk])

    @property
    def total_purchased(self):
        return self.purchases.aggregate(s=models.Sum('total'))['s'] or Decimal('0')

    @property
    def total_paid(self):
        return self.payments.aggregate(s=models.Sum('amount'))['s'] or Decimal('0')

    @property
    def balance_due(self):
        """Positive = you owe the supplier."""
        return self.total_purchased - self.total_paid


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Partially Paid', 'Partially Paid'),
        ('Paid', 'Paid'),
    ]

    number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices'
    )
    customer_name = models.CharField(max_length=150, blank=True)   # snapshot
    customer_gstin = models.CharField(max_length=15, blank=True)   # snapshot
    profile_name = models.CharField(max_length=120, blank=True)
    profile_owner_name = models.CharField(max_length=120, blank=True)
    profile_address = models.TextField(blank=True)
    profile_phone = models.CharField(max_length=30, blank=True)
    profile_email = models.EmailField(blank=True)
    profile_gstin = models.CharField(max_length=15, blank=True)
    profile_state = models.CharField(max_length=60, blank=True)
    profile_city = models.CharField(max_length=80, blank=True)
    profile_pincode = models.CharField(max_length=10, blank=True)
    profile_currency = models.CharField(max_length=5, default='₹')
    profile_logo = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    is_interstate = models.BooleanField(default=False)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default='Unpaid')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.number

    def get_absolute_url(self):
        return reverse('invoice_detail', args=[self.pk])

    @property
    def total_tax(self):
        return self.cgst + self.sgst + self.igst

    @property
    def amount_received(self):
        return self.total_paid

    @property
    def total_amount(self):
        return self.total

    @property
    def total_paid(self):
        return self.receipts.aggregate(s=models.Sum('amount'))['s'] or Decimal('0')

    @property
    def balance_due(self):
        return max(self.total_amount - self.total_paid, Decimal('0'))

    def refresh_payment_status(self):
        paid = self.total_paid
        new_status = 'Unpaid' if paid <= 0 else 'Partially Paid' if paid < self.total_amount else 'Paid'
        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=['status'])


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL, related_name='invoice_items')
    name = models.CharField(max_length=150)          # snapshot
    hsn_code = models.CharField(max_length=15, blank=True)  # snapshot
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='kg')  # snapshot
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)   # snapshot
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_taxable(self):
        return self.quantity * self.price

    @property
    def line_tax(self):
        return (self.line_taxable * self.gst_rate / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def line_total(self):
        return self.line_taxable + self.line_tax

    def __str__(self):
        return f'{self.name} x{self.quantity}'


class Receipt(models.Model):
    """Money received from a customer — either against a specific invoice or on-account."""
    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.CASCADE, related_name='receipts'
    )
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.SET_NULL, related_name='receipts')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='Cash')
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'Receipt {self.amount} from {self.customer}'

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.amount is not None and self.amount <= Decimal('0'):
            raise ValidationError({'amount': 'Payment amount must be greater than zero.'})
        if self.invoice_id and self.customer_id != self.invoice.customer_id:
            raise ValidationError({'invoice': 'This invoice does not belong to the selected customer.'})
        if self.invoice_id and self.amount is not None:
            existing = self.invoice.total_paid
            if self.pk:
                existing -= self.amount
            if existing + self.amount > self.invoice.total_amount:
                raise ValidationError({'amount': 'Payment cannot exceed the outstanding balance.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if self.invoice_id:
            self.invoice.refresh_payment_status()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        result = super().delete(*args, **kwargs)
        if invoice:
            invoice.refresh_payment_status()
        return result


class Purchase(models.Model):
    STATUS_CHOICES = [('Unpaid', 'Unpaid'), ('Paid', 'Paid')]

    number = models.CharField(max_length=20, unique=True)
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name='purchases'
    )
    supplier_name = models.CharField(max_length=150, blank=True)   # snapshot
    supplier_gstin = models.CharField(max_length=15, blank=True)   # snapshot
    profile_name = models.CharField(max_length=120, blank=True)
    profile_owner_name = models.CharField(max_length=120, blank=True)
    profile_address = models.TextField(blank=True)
    profile_phone = models.CharField(max_length=30, blank=True)
    profile_email = models.EmailField(blank=True)
    profile_gstin = models.CharField(max_length=15, blank=True)
    profile_state = models.CharField(max_length=60, blank=True)
    profile_city = models.CharField(max_length=80, blank=True)
    profile_pincode = models.CharField(max_length=10, blank=True)
    profile_currency = models.CharField(max_length=5, default='₹')
    profile_logo = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    is_interstate = models.BooleanField(default=False)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Unpaid')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.number

    def get_absolute_url(self):
        return reverse('purchase_detail', args=[self.pk])

    @property
    def total_tax(self):
        return self.cgst + self.sgst + self.igst

    @property
    def amount_paid(self):
        return self.payments.aggregate(s=models.Sum('amount'))['s'] or Decimal('0')


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL, related_name='purchase_items')
    name = models.CharField(max_length=150)
    hsn_code = models.CharField(max_length=15, blank=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='kg')
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    price = models.DecimalField(max_digits=10, decimal_places=2)   # cost price paid

    @property
    def line_taxable(self):
        return self.quantity * self.price

    @property
    def line_tax(self):
        return (self.line_taxable * self.gst_rate / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def line_total(self):
        return self.line_taxable + self.line_tax

    def __str__(self):
        return f'{self.name} x{self.quantity}'


class Payment(models.Model):
    """Money paid to a supplier — either against a specific purchase or on-account."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='payments')
    purchase = models.ForeignKey(Purchase, null=True, blank=True, on_delete=models.SET_NULL, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='Cash')
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'Payment {self.amount} to {self.supplier}'
