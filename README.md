# XERXEZ Backend

Django REST Framework API powering the XERXEZ AI-powered ERP platform, built for enterprises in the **UAE (Abu Dhabi focus) and India**. Serves the ERP, the public marketing site's contact/careers/blog endpoints, and the XERXEZ Academy (LMA) learning platform from a single Django project.

XERXEZ replaces fragmented legacy systems with one AI-native platform spanning CRM, Sales, Procurement, Logistics, Accounting, Inventory, HR, and a full MLM distributor/commission engine — plus an industry-specific ERP layer for **EPC, Oil & Gas, Construction, Manufacturing, Facility Management, Healthcare, Logistics, and Retail** businesses.

## Features

- ✅ **CRM** — Customers, Contacts, Leads, Pipeline (Kanban deals), Activities, Notes
- ✅ **Sales** — Quotations, Sales Orders, quotation→order conversion, sales dashboard
- ✅ **Procurement** — Purchase Orders, Suppliers, Goods Receipts, Bills
- ✅ **Logistics** — Shipments, Tracking Updates, Deliveries, Warehouses
- ✅ **Accounting** — Accounts, Journal Entries, Expenses, Invoices, Payments
- ✅ **Invoicing** — Invoices, Payments, Recurring Invoices, Credit Notes
- ✅ **MLM** — Distributors, Commissions, Payouts, network tree, MLM dashboard/settings
- ✅ **HR** — Departments, Employees, Attendance, Leave Requests, Shifts, Salary Structures, Payroll, PaySlips, Performance Reviews, Employee Documents, Onboarding, Exit Management
- ✅ **Inventory** — Products, Product Categories, Warehouses, Stock Movements
- ✅ **Document Management** — Categorized documents with versioning and an approval workflow
- ✅ **XERXEZ Academy (LMA)** — Courses, modules, lessons, enrollments, certificates
- ✅ **Marketing site backend** — Blog, Services, Projects, Contact, Careers, Analytics, Chatbot

## Tech Stack

- **Django 6** + **Django REST Framework**
- **PostgreSQL** (Railway-hosted in production, SQLite fallback for local dev)
- **Python 3.13+**
- **JWT authentication** via `djangorestframework-simplejwt`
- **django-filter**, **django-cors-headers**, **WhiteNoise** (static files)
- **Gunicorn** application server
- Deployed on **Railway**, config-driven via `config/backend_config.py`

## API Documentation

All routes are versioned under `/api/v1/`. Interactive docs: `/docs/` (Swagger) and `/redoc/` (ReDoc).

Key endpoints:

| Module | Endpoint |
|---|---|
| CRM | `/api/v1/crm/customers/`, `/api/v1/crm/leads/`, `/api/v1/crm/deals/`, `/api/v1/crm/activities/` |
| Sales | `/api/v1/sales/orders/`, `/api/v1/sales/quotations/` |
| Procurement | `/api/v1/procurement/purchase-orders/`, `/api/v1/procurement/suppliers/` |
| Logistics | `/api/v1/logistics/shipments/`, `/api/v1/logistics/tracking/` |
| Invoicing | `/api/v1/invoicing/invoices/` |
| MLM | `/api/v1/mlm/distributors/`, `/api/v1/mlm/commissions/`, `/api/v1/mlm/payouts/` |
| HR | `/api/v1/hr/employees/`, `/api/v1/hr/payroll/`, `/api/v1/hr/attendance/` |
| Inventory | `/api/v1/inventory/products/` |
| Careers | `/api/v1/careers/apply/`, `/api/v1/careers/positions/` |
| Auth | `/api/v1/auth/` |

Health check lives outside the version prefix at `/health/health/`.

## Setup

```bash
git clone <repo-url>
cd backend
pip install -r requirements.txt
# copy .env.example to .env and fill in the variables below
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

There is no automated test suite — verify changes with `python manage.py check` and manual endpoint testing (see `CLAUDE.md` for the project's testing conventions).

## Environment Variables

| Variable | Purpose |
|---|---|
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection (falls back to SQLite if unset) |
| `DJANGO_SECRET_KEY` | Django secret key |
| `DJANGO_ENV` | `development` or `production` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | Comma-separated CORS origins (essential production/dev origins are always included in addition) |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated CSRF-trusted origins |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD` | SMTP for transactional email |
| `STORAGE_BACKEND` | `local` or `s3` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Required only if `STORAGE_BACKEND=s3` |

## Deployment

- **Backend**: Railway, auto-deploys from GitHub `main`. `Procfile` runs migrations, seed scripts, and `collectstatic` before starting Gunicorn.
- **Database**: PostgreSQL on Railway.

## Target Markets

- **UAE** (Abu Dhabi focus)
- **India**

## Industries Served

- EPC
- Oil & Gas
- Construction
- Manufacturing
- Facility Management
- Healthcare
- Logistics
- Retail

## Contact

- Website: [xerxez.com](https://www.xerxez.com)
- Email: xerxez.in@gmail.com
- ERP Portal: [xerxez.com/erp](https://www.xerxez.com/erp)
