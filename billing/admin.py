from django.contrib import admin
from .models import (
    Product, Customer, Supplier, Invoice, InvoiceItem, Purchase, PurchaseItem,
    Receipt, Payment, BusinessSettings, BusinessProfile,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'unit', 'hsn_code', 'gst_rate', 'cost_price', 'selling_price', 'quantity', 'reorder_level')
    search_fields = ('name', 'sku', 'category', 'hsn_code')
    list_filter = ('category', 'unit')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'state', 'gstin', 'balance_due')
    search_fields = ('name', 'phone', 'email', 'gstin')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'state', 'gstin', 'balance_due')
    search_fields = ('name', 'phone', 'email', 'gstin')


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer_name', 'date', 'subtotal', 'cgst', 'sgst', 'igst', 'total', 'status')
    list_filter = ('status', 'is_interstate')
    search_fields = ('number', 'customer_name', 'customer_gstin')
    inlines = [InvoiceItemInline]


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('number', 'supplier_name', 'date', 'subtotal', 'cgst', 'sgst', 'igst', 'total', 'status')
    list_filter = ('status', 'is_interstate')
    search_fields = ('number', 'supplier_name', 'supplier_gstin')
    inlines = [PurchaseItemInline]


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('customer', 'invoice', 'amount', 'mode', 'date')
    list_filter = ('mode',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'purchase', 'amount', 'mode', 'date')
    list_filter = ('mode',)


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'gstin', 'state', 'currency', 'invoice_counter', 'purchase_counter')


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'owner_name', 'gstin', 'state', 'is_active', 'updated_at')
    list_filter = ('is_active', 'state')
    search_fields = ('business_name', 'owner_name', 'gstin', 'phone', 'email')
