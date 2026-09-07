import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Sum, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Product, Customer, Supplier, Invoice, InvoiceItem, Purchase, PurchaseItem,
    Receipt, Payment, BusinessSettings, BusinessProfile,
)
from .forms import (
    ProductForm, CustomerForm, SupplierForm, BusinessSettingsForm, BusinessProfileForm,
    ReceiptForm, PaymentForm,
)


def _dec(value, default='0'):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal(default)


def _profile_snapshot(profile):
    return {
        'profile_name': profile.business_name,
        'profile_owner_name': getattr(profile, 'owner_name', ''),
        'profile_address': profile.address,
        'profile_phone': getattr(profile, 'phone', ''),
        'profile_email': getattr(profile, 'email', ''),
        'profile_gstin': profile.gstin,
        'profile_state': profile.state,
        'profile_city': getattr(profile, 'city', ''),
        'profile_pincode': getattr(profile, 'pincode', ''),
        'profile_currency': profile.currency,
        'profile_logo': getattr(profile.logo, 'name', '') if getattr(profile, 'logo', None) else '',
    }


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
def dashboard(request):
    products = Product.objects.all()
    low_stock = [p for p in products if p.is_low_stock]
    stock_value = sum((p.stock_value for p in products), Decimal('0'))
    today = timezone.localdate()
    today_total = (
        Invoice.objects.filter(date__date=today).aggregate(total=Sum('total'))['total']
        or Decimal('0')
    )
    recent_invoices = Invoice.objects.all()[:6]

    receivable = sum((invoice.balance_due for invoice in Invoice.objects.all()), Decimal('0'))
    payable = sum((s.balance_due for s in Supplier.objects.all()), Decimal('0'))

    context = {
        'stock_value': stock_value,
        'item_count': products.count(),
        'low_stock': low_stock[:6],
        'low_stock_count': len(low_stock),
        'today_total': today_total,
        'recent_invoices': recent_invoices,
        'receivable': receivable,
        'payable': payable,
    }
    return render(request, 'billing/dashboard.html', context)


# --------------------------------------------------------------------------
# Inventory
# --------------------------------------------------------------------------
def inventory_list(request):
    q = request.GET.get('q', '').strip()
    products = Product.objects.all()
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))

    stock_value = sum((p.stock_value for p in Product.objects.all()), Decimal('0'))
    context = {'products': products, 'q': q, 'stock_value': stock_value}
    return render(request, 'billing/inventory_list.html', context)


def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Item added.')
            return redirect('inventory_list')
    else:
        form = ProductForm()
    return render(request, 'billing/product_form.html', {'form': form, 'editing': False})


def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Item updated.')
            return redirect('inventory_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'billing/product_form.html', {'form': form, 'editing': True, 'product': product})


@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    messages.success(request, 'Item deleted.')
    return redirect('inventory_list')


# --------------------------------------------------------------------------
# Customers + party ledger
# --------------------------------------------------------------------------
def customer_list(request):
    customers = Customer.objects.all()
    return render(request, 'billing/customer_list.html', {'customers': customers})


def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Customer added.')
            return redirect('customer_list')
    else:
        form = CustomerForm()
    return render(request, 'billing/customer_form.html', {'form': form, 'editing': False})


def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Customer updated.')
            return redirect('customer_list')
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'billing/customer_form.html', {'form': form, 'editing': True, 'customer': customer})


@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.delete()
    messages.success(request, 'Customer deleted.')
    return redirect('customer_list')


def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = ReceiptForm(request.POST, customer=customer)
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.customer = customer
            receipt.save()
            messages.success(request, 'Payment recorded.')
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = ReceiptForm(customer=customer)

    # Combined ledger: invoices (debit) and receipts (credit), oldest first, running balance.
    entries = []
    for inv in customer.invoices.all().order_by('date'):
        entries.append({'date': inv.date, 'type': 'Bill', 'ref': inv.number, 'debit': inv.total, 'credit': None, 'link': inv})
    for r in customer.receipts.all().order_by('date'):
        entries.append({'date': r.date, 'type': 'Receipt', 'ref': r.mode, 'debit': None, 'credit': r.amount, 'link': None})
    entries.sort(key=lambda e: e['date'])
    running = Decimal('0')
    for e in entries:
        running += (e['debit'] or Decimal('0')) - (e['credit'] or Decimal('0'))
        e['balance'] = running

    context = {
        'customer': customer,
        'form': form,
        'entries': list(reversed(entries)),
    }
    return render(request, 'billing/customer_detail.html', context)


# --------------------------------------------------------------------------
# Suppliers + party ledger
# --------------------------------------------------------------------------
def supplier_list(request):
    suppliers = Supplier.objects.all()
    return render(request, 'billing/supplier_list.html', {'suppliers': suppliers})


def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier added.')
            return redirect('supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'billing/supplier_form.html', {'form': form, 'editing': False})


def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier updated.')
            return redirect('supplier_list')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'billing/supplier_form.html', {'form': form, 'editing': True, 'supplier': supplier})


@require_POST
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.delete()
    messages.success(request, 'Supplier deleted.')
    return redirect('supplier_list')


def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST, supplier=supplier)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.supplier = supplier
            payment.save()
            if payment.purchase and payment.purchase.amount_paid >= payment.purchase.total:
                payment.purchase.status = 'Paid'
                payment.purchase.save(update_fields=['status'])
            messages.success(request, 'Payment recorded.')
            return redirect('supplier_detail', pk=supplier.pk)
    else:
        form = PaymentForm(supplier=supplier)

    entries = []
    for pur in supplier.purchases.all().order_by('date'):
        entries.append({'date': pur.date, 'type': 'Purchase', 'ref': pur.number, 'debit': pur.total, 'credit': None, 'link': pur})
    for p in supplier.payments.all().order_by('date'):
        entries.append({'date': p.date, 'type': 'Payment', 'ref': p.mode, 'debit': None, 'credit': p.amount, 'link': None})
    entries.sort(key=lambda e: e['date'])
    running = Decimal('0')
    for e in entries:
        running += (e['debit'] or Decimal('0')) - (e['credit'] or Decimal('0'))
        e['balance'] = running

    context = {
        'supplier': supplier,
        'form': form,
        'entries': list(reversed(entries)),
    }
    return render(request, 'billing/supplier_detail.html', context)


# --------------------------------------------------------------------------
# Shared GST line-item parsing (used by both billing_new and purchase_new)
# --------------------------------------------------------------------------
def _parse_line_items(items_raw, products_by_id):
    """Returns (line_items, combined_qty_by_id) or (None, error_message)."""
    try:
        raw_items = json.loads(items_raw)
    except (json.JSONDecodeError, TypeError):
        return None, 'Could not read the item list. Please try again.'
    if not raw_items:
        return None, 'Add at least one item before generating this.'

    combined_qty = {}
    for item in raw_items:
        pid = str(item.get('product_id'))
        qty = _dec(item.get('qty'))
        if pid not in products_by_id:
            return None, 'One of the selected items no longer exists.'
        if qty <= 0:
            return None, 'Quantities must be greater than zero.'
        combined_qty[pid] = combined_qty.get(pid, Decimal('0')) + qty
    return raw_items, combined_qty


def _compute_gst_totals(raw_items, products_by_id, discount, is_interstate):
    """Returns (subtotal, cgst, sgst, igst, total, prepared_items)."""
    subtotal = Decimal('0')
    total_tax = Decimal('0')
    prepared = []
    for item in raw_items:
        product = products_by_id[str(item['product_id'])]
        qty = _dec(item['qty'])
        price = _dec(item.get('price', product.selling_price))
        line_taxable = qty * price
        line_tax = (line_taxable * product.gst_rate / Decimal('100')).quantize(Decimal('0.01'))
        subtotal += line_taxable
        total_tax += line_tax
        prepared.append({
            'product': product, 'qty': qty, 'price': price,
            'hsn_code': product.hsn_code, 'unit': product.unit, 'gst_rate': product.gst_rate,
        })

    if is_interstate:
        cgst, sgst, igst = Decimal('0'), Decimal('0'), total_tax
    else:
        half = (total_tax / 2).quantize(Decimal('0.01'))
        cgst, sgst, igst = half, total_tax - half, Decimal('0')

    total = max(Decimal('0'), subtotal - discount + total_tax)
    return subtotal, cgst, sgst, igst, total, prepared


# --------------------------------------------------------------------------
# New bill (sales)
# --------------------------------------------------------------------------
def billing_new(request):
    settings_obj = BusinessProfile.active() or BusinessSettings.load()

    if request.method == 'POST':
        customer_id = request.POST.get('customer_id') or None
        discount = _dec(request.POST.get('discount', '0'))
        customer = Customer.objects.filter(pk=customer_id).first() if customer_id else None
        is_interstate = settings_obj.is_interstate_with(customer.state if customer else '')

        items_raw = request.POST.get('items_json', '[]')
        try:
            parsed_preview = json.loads(items_raw)
        except (json.JSONDecodeError, TypeError):
            parsed_preview = []
        product_ids = [i.get('product_id') for i in parsed_preview]
        products_by_id = {str(p.pk): p for p in Product.objects.filter(pk__in=product_ids)}

        raw_items, combined_or_error = _parse_line_items(items_raw, products_by_id)
        if raw_items is None:
            messages.error(request, combined_or_error)
            return redirect('billing_new')

        for pid, qty in combined_or_error.items():
            product = products_by_id[pid]
            if product.quantity < qty:
                messages.error(request, f'Only {product.quantity} {product.get_unit_display()} left in stock for {product.name}.')
                return redirect('billing_new')

        subtotal, cgst, sgst, igst, total, prepared = _compute_gst_totals(
            raw_items, products_by_id, discount, is_interstate
        )

        with transaction.atomic():
            invoice = Invoice.objects.create(
                number=settings_obj.next_invoice_number(),
                customer=customer,
                customer_name=customer.name if customer else '',
                customer_gstin=customer.gstin if customer else '',
                **_profile_snapshot(settings_obj),
                is_interstate=is_interstate,
                subtotal=subtotal, discount=discount, cgst=cgst, sgst=sgst, igst=igst, total=total,
                status='Unpaid',
            )
            for item in prepared:
                InvoiceItem.objects.create(
                    invoice=invoice, product=item['product'], name=item['product'].name,
                    hsn_code=item['hsn_code'], unit=item['unit'], gst_rate=item['gst_rate'],
                    quantity=item['qty'], price=item['price'],
                )
                Product.objects.filter(pk=item['product'].pk).update(quantity=F('quantity') - item['qty'])

            if request.POST.get('mark_paid') == 'on':
                Receipt.objects.create(customer=customer, invoice=invoice, amount=total, mode='Cash')

        messages.success(request, f'Bill {invoice.number} generated.')
        return redirect('invoice_detail', pk=invoice.pk)

    products = Product.objects.filter(quantity__gt=0).order_by('name')
    all_products = Product.objects.all().order_by('name')
    customers = Customer.objects.all()
    context = {
        'products': products,
        'all_products': all_products,
        'customers': customers,
        'business_state': settings_obj.state,
        'currency': settings_obj.currency,
    }
    return render(request, 'billing/billing_new.html', context)


# --------------------------------------------------------------------------
# Invoices
# --------------------------------------------------------------------------
def invoice_list(request):
    search = request.GET.get('search', '').strip()
    invoices = Invoice.objects.all()
    if search:
        invoices = invoices.filter(customer_name__icontains=search)
    return render(request, 'billing/invoice_list.html', {
        'invoices': invoices,
        'search': search,
    })


def invoice_customer_suggestions(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse([], safe=False)
    customers = Customer.objects.filter(name__icontains=query).order_by('name')[:10]
    return JsonResponse(list(customers.values('id', 'name')), safe=False)


def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    invoice.refresh_payment_status()
    form = ReceiptForm(customer=invoice.customer, invoice=invoice)
    form.fields['amount'].widget.attrs['max'] = str(invoice.balance_due)
    return render(request, 'billing/invoice_detail.html', {'invoice': invoice, 'payment_form': form})


@require_POST
def invoice_payment(request, pk):
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=pk)
        form = ReceiptForm(request.POST, customer=invoice.customer, invoice=invoice)
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.customer = invoice.customer
            receipt.invoice = invoice
            receipt.save()
            messages.success(request, f'Payment of {receipt.amount} recorded for {invoice.number}.')
        else:
            form.fields['amount'].widget.attrs['max'] = str(invoice.balance_due)
            messages.error(request, 'Please correct the payment amount and try again.')
            return render(request, 'billing/invoice_detail.html', {'invoice': invoice, 'payment_form': form})
    return redirect('invoice_detail', pk=invoice.pk)


@require_POST
def invoice_mark_paid(request, pk):
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=pk)
        outstanding = invoice.balance_due
        if outstanding > 0:
            Receipt.objects.create(customer=invoice.customer, invoice=invoice, amount=outstanding, mode='Cash')
        else:
            invoice.refresh_payment_status()
    messages.success(request, f'{invoice.number} marked as paid.')
    return redirect('invoice_list')


# --------------------------------------------------------------------------
# New purchase entry
# --------------------------------------------------------------------------
def purchase_new(request):
    settings_obj = BusinessProfile.active() or BusinessSettings.load()

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id') or None
        discount = _dec(request.POST.get('discount', '0'))
        supplier = Supplier.objects.filter(pk=supplier_id).first() if supplier_id else None
        is_interstate = settings_obj.is_interstate_with(supplier.state if supplier else '')

        items_raw = request.POST.get('items_json', '[]')
        try:
            parsed_preview = json.loads(items_raw)
        except (json.JSONDecodeError, TypeError):
            parsed_preview = []
        product_ids = [i.get('product_id') for i in parsed_preview]
        products_by_id = {str(p.pk): p for p in Product.objects.filter(pk__in=product_ids)}

        raw_items, combined_or_error = _parse_line_items(items_raw, products_by_id)
        if raw_items is None:
            messages.error(request, combined_or_error)
            return redirect('purchase_new')

        subtotal, cgst, sgst, igst, total, prepared = _compute_gst_totals(
            raw_items, products_by_id, discount, is_interstate
        )

        with transaction.atomic():
            purchase = Purchase.objects.create(
                number=settings_obj.next_purchase_number(),
                supplier=supplier,
                supplier_name=supplier.name if supplier else '',
                supplier_gstin=supplier.gstin if supplier else '',
                **_profile_snapshot(settings_obj),
                is_interstate=is_interstate,
                subtotal=subtotal, discount=discount, cgst=cgst, sgst=sgst, igst=igst, total=total,
                status='Unpaid',
            )
            for item in prepared:
                PurchaseItem.objects.create(
                    purchase=purchase, product=item['product'], name=item['product'].name,
                    hsn_code=item['hsn_code'], unit=item['unit'], gst_rate=item['gst_rate'],
                    quantity=item['qty'], price=item['price'],
                )
                # Stock-in: purchasing increases quantity, and updates cost price to the latest paid.
                Product.objects.filter(pk=item['product'].pk).update(
                    quantity=F('quantity') + item['qty'], cost_price=item['price']
                )

            if request.POST.get('mark_paid') == 'on':
                if supplier:
                    Payment.objects.create(supplier=supplier, purchase=purchase, amount=total, mode='Cash')
                purchase.status = 'Paid'
                purchase.save(update_fields=['status'])

        messages.success(request, f'Purchase {purchase.number} recorded — stock updated.')
        return redirect('purchase_detail', pk=purchase.pk)

    all_products = Product.objects.all().order_by('name')
    suppliers = Supplier.objects.all()
    context = {
        'all_products': all_products,
        'suppliers': suppliers,
        'business_state': settings_obj.state,
        'currency': settings_obj.currency,
    }
    return render(request, 'billing/purchase_new.html', context)


def purchase_list(request):
    purchases = Purchase.objects.all()
    return render(request, 'billing/purchase_list.html', {'purchases': purchases})


def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    return render(request, 'billing/purchase_detail.html', {'purchase': purchase})


@require_POST
def purchase_mark_paid(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    outstanding = purchase.total - purchase.amount_paid
    if purchase.supplier and outstanding > 0:
        Payment.objects.create(supplier=purchase.supplier, purchase=purchase, amount=outstanding, mode='Cash')
    purchase.status = 'Paid'
    purchase.save(update_fields=['status'])
    messages.success(request, f'{purchase.number} marked as paid.')
    return redirect('purchase_list')


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
def business_settings_view(request):
    settings_obj = BusinessSettings.load()
    profiles = BusinessProfile.objects.all()
    active_profile = BusinessProfile.active()
    if request.method == 'POST':
        if request.POST.get('action') == 'save_profile':
            profile_id = request.POST.get('profile_id') or None
            profile = BusinessProfile.objects.filter(pk=profile_id).first() if profile_id else BusinessProfile()
            form = BusinessProfileForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                profile = form.save()
                if not profiles.exists():
                    profile.set_active()
                messages.success(request, 'Business profile saved.')
                return redirect('business_settings')
            settings_form = BusinessSettingsForm(instance=settings_obj)
        else:
            settings_form = BusinessSettingsForm(request.POST, instance=settings_obj)
            if settings_form.is_valid():
                settings_form.save()
                if active_profile:
                    active_profile.business_name = settings_obj.business_name
                    active_profile.address = settings_obj.address
                    active_profile.state = settings_obj.state
                    active_profile.gstin = settings_obj.gstin
                    active_profile.currency = settings_obj.currency
                    active_profile.default_gst_rate = settings_obj.default_gst_rate
                    active_profile.save()
                messages.success(request, 'Settings saved.')
                return redirect('business_settings')
            form = BusinessProfileForm()
    else:
        settings_form = BusinessSettingsForm(instance=settings_obj)
        form = BusinessProfileForm()
    return render(request, 'billing/settings.html', {
        'form': settings_form, 'profile_form': form, 'profiles': profiles,
        'active_profile': active_profile,
    })


def business_profile_edit(request, pk=None):
    profile = BusinessProfile.objects.filter(pk=pk).first() if pk else None
    if request.method == 'POST':
        form = BusinessProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save()
            if not BusinessProfile.objects.filter(is_active=True).exists():
                profile.set_active()
            messages.success(request, 'Business profile saved.')
            return redirect('business_settings')
    else:
        form = BusinessProfileForm(instance=profile)
    return render(request, 'billing/profile_form.html', {'form': form, 'profile': profile})


@require_POST
def business_profile_activate(request, pk):
    profile = get_object_or_404(BusinessProfile, pk=pk)
    profile.set_active()
    messages.success(request, f'{profile.business_name} is now active.')
    return redirect('business_settings')


@require_POST
def business_profile_delete(request, pk):
    profile = get_object_or_404(BusinessProfile, pk=pk)
    if profile.is_active:
        messages.error(request, 'Activate another profile before deleting this profile.')
    elif BusinessProfile.objects.count() <= 1:
        messages.error(request, 'At least one business profile must remain.')
    else:
        profile.delete()
        messages.success(request, 'Business profile deleted.')
    return redirect('business_settings')
