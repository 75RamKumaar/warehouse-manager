# Ledger — Billing & Stock Management (Django)

A Django app for running a dhal shop (or any similar business): stock in
weighed units, GST-style sales and purchase invoicing, and running account
balances with customers and suppliers — the pieces of Tally most small
shops actually use day to day.

## Features

- **Dashboard** — stock value, low-stock alerts, today's billing total,
  total receivable (customers owe you) and payable (you owe suppliers)
- **Inventory** — products priced and stocked by weight (kg/g), litres, or
  pieces; each with an HSN code and its own GST rate
- **New bill** — pick a customer, add items by weight, discount, and GST
  (CGST+SGST for same-state, IGST for interstate — worked out automatically
  from your business state vs. the customer's), then generate — stock
  deducts automatically
- **New purchase** — record stock coming in from a supplier the same way;
  stock increases and the product's cost price updates to what you just paid
- **Invoices & Purchases** — full history, GST-itemised print view showing
  HSN codes and the CGST/SGST/IGST split
- **Customers & Suppliers** — each has a running ledger: every bill/purchase
  and every payment, with a live balance so you always know who owes what
- **Settings** — business name, address, GSTIN, state (for the GST split),
  currency, default GST rate for new items
- **Django admin** — every model registered at `/admin/` for bulk edits

## What this is *not*

This isn't full double-entry accounting — there's no day book, trial
balance, or profit & loss statement. It tracks stock, bills/purchases, and
what each customer/supplier owes, which is what was asked for. If you later
want a P&L or balance sheet, that's a real extension (see below).

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply migrations (creates db.sqlite3)
python manage.py makemigrations billing
python manage.py migrate

# 4. (Optional) create an admin user
python manage.py createsuperuser

# 5. (Optional) load starter inventory — common dhal varieties
python manage.py loaddata initial_products

# 6. Set your business GSTIN, state, and address
#    (visit /settings/ after starting the server, or use /admin/)

# 7. Run the dev server
python manage.py runserver
```

Then open **http://127.0.0.1:8000/** in your browser. The admin site is at
**http://127.0.0.1:8000/admin/**.

**Important:** set your business **state** in Settings first — the CGST vs
IGST split on every bill and purchase depends on comparing it against each
customer's/supplier's state, and both default to blank.

## Starter inventory

`billing/fixtures/initial_products.json` seeds 8 common dhal varieties
(toor, moong split & whole, chana, urad split & whole, masoor), each priced
per kg with an example HSN code (0713) and a 5% GST rate. **GST slabs on
pulses vary by whether they're branded/packaged vs loose — verify the
correct rate and HSN code with your CA or the current GST schedule before
relying on this for real filings.**

## How GST is calculated

- Each **product** carries its own GST rate and HSN code (set in Inventory).
- Each **customer/supplier** carries a state.
- On save, the business's state (Settings) is compared to the party's state:
  same state → the tax splits evenly into **CGST + SGST**; different state
  → the full amount goes to **IGST**. If either state is blank, it's
  treated as intra-state (CGST+SGST) to avoid a wrong IGST charge by default.
- Rates apply per line item, so a bill can mix items taxed at different
  rates — the invoice total is still exactly right.

## Party ledgers (Tally-style running balance)

- A **Receipt** records money received from a customer — optionally against
  one specific bill, or "on account" if it's a general payment.
- A **Payment** records money paid to a supplier the same way.
- Each customer/supplier detail page shows a full ledger (bills/purchases as
  debits, payments as credits) with a running balance, and a form to record
  a new payment right there.
- "Mark paid" on an invoice/purchase auto-creates a matching receipt/payment
  for the outstanding amount, so the ledger and the status label always agree.

## Project layout

```
ledger/
├── manage.py
├── requirements.txt
├── ledger_project/          # Django project (settings, urls, wsgi/asgi)
└── billing/                 # The app itself
    ├── models.py             # Product, Customer, Supplier, Invoice(+Item),
    │                         # Purchase(+Item), Receipt, Payment, BusinessSettings
    ├── views.py               # Dashboard, CRUD, billing/purchase builders, ledgers
    ├── forms.py                # ModelForms
    ├── urls.py
    ├── admin.py
    ├── context_processors.py  # exposes business settings in every template
    ├── fixtures/               # starter dhal inventory
    ├── templates/billing/      # server-rendered templates (ledger visual theme)
    └── static/billing/css/     # stylesheet
```

## Notes on the data model

- `Invoice`/`Purchase` snapshot the party's name, GSTIN, and each line
  item's product name/HSN/GST rate/price at the time of billing, so editing
  a product or party later never rewrites history.
- Stock changes happen inside a single `transaction.atomic()` block —
  sales re-validate available quantity server-side before deducting, and
  purchases add stock and update cost price together.
- Customer/supplier balances (`balance_due`) are computed live from the sum
  of their bills/purchases minus the sum of their receipts/payments — not
  stored, so they can never drift out of sync.

## Current workflows

### Business profiles

Open `/settings/` to manage business profiles. A profile can store the
business name, owner, address, phone, email, GSTIN, state, city, pincode,
currency, default GST rate, and an optional logo.

- Use **Set as Active** to choose the profile used for new bills and purchases.
- Only one profile can be active at a time.
- The active profile cannot be deleted. Activate another profile first.
- Existing `BusinessSettings` data is migrated into the initial active profile.
- New invoices and purchases snapshot the active profile, so older documents
  retain their original business information after a profile switch.

### Partial invoice payments

An invoice can have multiple receipts. The invoice detail page shows the bill
amount, total paid, balance due, status, and payment history.

- `Unpaid` means no receipts have been recorded.
- `Partially Paid` means receipts cover part of the invoice total.
- `Paid` means receipts cover the full invoice total.
- Receipt amounts are validated server-side with `Decimal` and cannot exceed
  the outstanding balance.
- **Mark paid** creates a receipt only for the remaining balance, so it does
  not duplicate earlier installments.

### Invoice search and suggestions

The invoice list supports case-insensitive partial customer-name search:

```text
/invoices/?search=Kumar
```

Type at least two characters into the invoice search field to receive up to
ten customer suggestions without reloading the page. Selecting a suggestion
filters the invoice list. Arrow Up/Down, Enter, Escape, outside-click closing,
and the Clear link are supported.

### Verification

After installing dependencies and applying migrations, run:

```bash
python manage.py check
python manage.py makemigrations --check
python manage.py test
```

Recommended manual checks:

1. Add two business profiles and switch the active profile.
2. Create an invoice and record multiple partial payments.
3. Confirm the payment summary, history, customer ledger, and dashboard
   receivable update after each installment.
4. Search invoices by full and partial customer names using different casing.
5. Test autocomplete selection with the mouse and keyboard.
6. Create a document after switching profiles and confirm older documents keep
   their original business details.

## Extending it

- Add authentication (`django.contrib.auth` is already installed) if more
  than one person will use this and you want logins per staff member.
- Add a day book / P&L view using Django's aggregation across Invoice,
  Purchase, Receipt, and Payment if you want fuller accounting later.
- Swap SQLite for Postgres in `DATABASES` for production use.
- Add DRF (`djangorestframework`) if you want an API alongside the UI.
- A GSTR-1-style HSN summary report (group invoice items by HSN+rate) would
  be a natural next addition on top of the data already being captured.

This hasn't been run in this environment (no network access to install
Django here), so run `python manage.py check` right after installing to
catch anything environment-specific before you rely on it.
#
