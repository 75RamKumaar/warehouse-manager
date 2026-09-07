from decimal import Decimal

from django import forms
from .models import Product, Customer, Supplier, BusinessSettings, BusinessProfile, Receipt, Payment


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'category', 'unit', 'hsn_code', 'gst_rate',
            'cost_price', 'selling_price', 'quantity', 'reorder_level',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Toor Dal'}),
            'sku': forms.TextInput(attrs={'placeholder': 'DHAL-TOOR-1KG'}),
            'category': forms.TextInput(attrs={'placeholder': 'Dhal'}),
            'hsn_code': forms.TextInput(attrs={'placeholder': 'e.g. 0713'}),
            'gst_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'cost_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'selling_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'quantity': forms.NumberInput(attrs={'step': '0.001', 'min': '0'}),
            'reorder_level': forms.NumberInput(attrs={'step': '0.001', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            profile = BusinessProfile.active() or BusinessSettings.load()
            self.fields['gst_rate'].initial = profile.default_gst_rate


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'email', 'address', 'state', 'gstin']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'gstin': forms.TextInput(attrs={'placeholder': '22AAAAA0000A1Z5 (optional)'}),
            'state': forms.TextInput(attrs={'placeholder': 'e.g. Tamil Nadu'}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'phone', 'email', 'address', 'state', 'gstin']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'gstin': forms.TextInput(attrs={'placeholder': '22AAAAA0000A1Z5 (optional)'}),
            'state': forms.TextInput(attrs={'placeholder': 'e.g. Tamil Nadu'}),
        }


class BusinessSettingsForm(forms.ModelForm):
    class Meta:
        model = BusinessSettings
        fields = ['business_name', 'address', 'state', 'gstin', 'currency', 'default_gst_rate']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'state': forms.TextInput(attrs={'placeholder': 'e.g. Tamil Nadu'}),
            'gstin': forms.TextInput(attrs={'placeholder': '22AAAAA0000A1Z5'}),
            'default_gst_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class BusinessProfileForm(forms.ModelForm):
    class Meta:
        model = BusinessProfile
        fields = [
            'business_name', 'owner_name', 'address', 'phone', 'email', 'gstin',
            'state', 'city', 'pincode', 'currency', 'default_gst_rate', 'logo',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'gstin': forms.TextInput(attrs={'placeholder': '22AAAAA0000A1Z5'}),
            'state': forms.TextInput(attrs={'placeholder': 'e.g. Tamil Nadu'}),
            'default_gst_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = ['amount', 'mode', 'invoice', 'note']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'note': forms.TextInput(attrs={'placeholder': 'Optional note'}),
        }

    def __init__(self, *args, customer=None, invoice=None, **kwargs):
        super().__init__(*args, **kwargs)
        if customer is not None:
            self.fields['invoice'].queryset = customer.invoices.all()
        if invoice is not None:
            self.fields['invoice'].queryset = self.fields['invoice'].queryset.filter(pk=invoice.pk)
            self.fields['invoice'].initial = invoice
            self.fields['invoice'].widget = forms.HiddenInput()
        self.fields['invoice'].required = False
        self.fields['invoice'].empty_label = 'On account (not tied to one bill)'

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        invoice = cleaned_data.get('invoice')
        if amount is not None and amount <= Decimal('0'):
            self.add_error('amount', 'Payment amount must be greater than zero.')
        if invoice and amount is not None:
            outstanding = invoice.balance_due
            if self.instance.pk and self.instance.invoice_id == invoice.pk:
                outstanding += self.instance.amount
            if amount > outstanding:
                self.add_error('amount', 'Payment cannot exceed the outstanding balance.')
        return cleaned_data


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'mode', 'purchase', 'note']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'note': forms.TextInput(attrs={'placeholder': 'Optional note'}),
        }

    def __init__(self, *args, supplier=None, **kwargs):
        super().__init__(*args, **kwargs)
        if supplier is not None:
            self.fields['purchase'].queryset = supplier.purchases.all()
        self.fields['purchase'].required = False
        self.fields['purchase'].empty_label = 'On account (not tied to one purchase)'
