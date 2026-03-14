# Backend Notes

## Test Workflow

- Backend app root: `/workspace/development/frappe-bench/apps/mob_clinic`
- Bench root: `/workspace/development/frappe-bench`
- Main working test site: `dev2.localhost`

## Quick Checks

- Python syntax:
```bash
python -m py_compile mob_clinic/mob_clinic/api/payment.py mob_clinic/mob_clinic/procedure_items.py mob_clinic/mob_clinic/tests/test_payment.py
```

- Confirm site apps:
```bash
bench --site dev2.localhost list-apps
```

## Reliable Payment Test Run

- `bench --site dev2.localhost run-tests --module mob_clinic.mob_clinic.tests.test_payment` may fail because global `india_compliance` test bootstrap creates unrelated fixture errors.
- Use this isolated runner instead:
```bash
./env/bin/python - <<'PY'
import sys
import unittest

sys.path.insert(0, '/workspace/development/frappe-bench/apps')
sys.path.insert(0, '/workspace/development/frappe-bench/apps/mob_clinic')
sys.path.insert(0, '/workspace/development/frappe-bench/apps/frappe')

import frappe

frappe.init(site='dev2.localhost', sites_path='/workspace/development/frappe-bench/sites')
frappe.connect()
frappe.flags.in_test = True
frappe.set_user('Administrator')

from mob_clinic.mob_clinic.tests.test_payment import TestPaymentAPI

suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPaymentAPI)
result = unittest.TextTestRunner(verbosity=1).run(suite)

frappe.db.rollback()
frappe.destroy()

if not result.wasSuccessful():
    raise SystemExit(1)
PY
```

## Environment Notes

- If direct Frappe init complains about missing log paths, create:
```bash
mkdir -p /workspace/development/logs /workspace/development/frappe-bench/dev2.localhost/logs
```
