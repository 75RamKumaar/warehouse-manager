from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/add/', views.product_create, name='product_create'),
    path('inventory/<int:pk>/edit/', views.product_update, name='product_update'),
    path('inventory/<int:pk>/delete/', views.product_delete, name='product_delete'),

    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_update, name='customer_update'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),

    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', views.supplier_update, name='supplier_update'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),

    path('billing/new/', views.billing_new, name='billing_new'),
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/customer-suggestions/', views.invoice_customer_suggestions, name='invoice_customer_suggestions'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/payment/', views.invoice_payment, name='invoice_payment'),
    path('invoices/<int:pk>/mark-paid/', views.invoice_mark_paid, name='invoice_mark_paid'),

    path('purchases/new/', views.purchase_new, name='purchase_new'),
    path('purchases/', views.purchase_list, name='purchase_list'),
    path('purchases/<int:pk>/', views.purchase_detail, name='purchase_detail'),
    path('purchases/<int:pk>/mark-paid/', views.purchase_mark_paid, name='purchase_mark_paid'),

    path('settings/', views.business_settings_view, name='business_settings'),
    path('settings/profiles/add/', views.business_profile_edit, name='business_profile_add'),
    path('settings/profiles/<int:pk>/edit/', views.business_profile_edit, name='business_profile_edit'),
    path('settings/profiles/<int:pk>/activate/', views.business_profile_activate, name='business_profile_activate'),
    path('settings/profiles/<int:pk>/delete/', views.business_profile_delete, name='business_profile_delete'),
]
