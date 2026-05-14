# ElksContacts audit — 2026-05-13

## Module facts
- Version: 19.0.3.9 (one bump above last committed 19.0.3.8)
- Declared depends: `base`, `base_import`, `contacts`, `hr`, `hr_skills`, `mail`, `website`
- Models inherited: `res.partner` (twice — see BLOCKER), `res.users`, `hr.employee`, `base_import.import`, `mail.thread`, `mail.activity.mixin`
- Models created (17): `elks.officer.term`, `elks.volunteer.training`, `elks.committee`, `elks.committee.assignment`, `elks.charitable.activity`, `elks.member.history`, `elks.membership.application`, `elks.ballot.wizard`, `elks.initiate.wizard`, `elks.drop.wizard`, `elks.suspension.wizard`, `elks.volunteer.link.wizard`, `elks.volunteer.link.wizard.line`, `elks.employee.merge.wizard`, `elks.volunteer.signup.wizard`, `elks.volunteer.signup.wizard.match`, `clms.import.wizard`
- Files in `models/` NOT imported in `__init__.py`: **`models/res_partner.py`** (confirmed dead — see BLOCKER #1)

---

## Findings

### BLOCKER — Dead duplicate `models/res_partner.py` is a latent footgun
**File:** `models/res_partner.py` (entire file, 240 lines) vs `models/elks_contact.py:953-1160`

**What:** `models/res_partner.py` defines an exact duplicate of every "Return to Sender / Suspension / Dues / Drop / Undrop / cron_update_is_dues_paid" field and method already present in `elks_contact.py`. It is currently NOT in `models/__init__.py`, so it is dead code. The runtime works because the same fields exist in `elks_contact.py`.

**Why it matters:** If anyone re-adds `from . import res_partner` to `models/__init__.py`, Odoo will register two `res.partner` model classes with overlapping field definitions in the same module. Field redeclaration in the same module raises `TypeError: Field x_is_suspended … is defined multiple times`. Install/upgrade fails immediately. Also: the two copies have already drifted; any future edit applied only to the dead file looks like it worked but ships nothing.

**Fix:** Delete `models/res_partner.py`. No DB columns will be dropped because the column definitions in `elks_contact.py` already cover the same `x_*` columns.

---

### BLOCKER — `view_partner_form_elks_pay_dues_front` xpath fragility
**File:** `views/elks_contact_views.xml:378-395`

**What:** The new "Pay Dues" smart button targets `//div[hasclass('oe_button_box')]/*[1]` with `position="before"`. If at view-application time the `oe_button_box` div has no element children, the xpath fails and the module install/upgrade crashes.

**Why it matters:** A single xpath miss aborts the upgrade. Priority 99 means this view loads last, so it depends on every other module's button-box contributions still being in place.

**Fix:** Target by name (`//div[@name='button_box']`) with `position="inside"`, then reorder via the inherited view's natural append/prepend behavior. Or wrap the button in a `<div name="button_box" position="inside">` block. Safer to fall back to `inside` and accept the button lands at the end of the bar.

---

### INSTALL — Migration 19.0.3.2 silently drops data
**File:** `migrations/19.0.3.2/pre-migrate.py:80-95`

**What:** Builds a `mapping` dict of old text values → `res_country_state.id`, then runs `ALTER TABLE … DROP COLUMN … ADD COLUMN … INTEGER`, then logs that the mapped values "have been reset". The work of building the mapping is thrown away.

**Why it matters:** Upgrade succeeds but silently nukes user data. Any existing reinstatement application loses its `reinstatement_previous_state` value.

**Fix:** Rename old column → add new INTEGER column → `UPDATE … SET … = CASE WHEN old = 'Colorado' THEN <id> …` → drop old. Build mapping BEFORE dropping.

---

### INSTALL — Stored compute fields on res.partner trigger heavy recompute on upgrade
**File:** `models/elks_contact.py:88-94, 314, 317, 1047-1054`

**What:** Four stored computed fields on `res.partner`: `x_is_member`, `x_elks_officer_type`, `x_is_elks_officer`, `x_is_dues_paid`. Recomputed for every partner row on upgrades that touch the field graph.

**Why it matters:** Single-lodge: fast. Multi-lodge with tens of thousands of partners: minutes. Plan the maintenance window.

**Fix:** None required. Acceptable as-is.

---

### INSTALL — `_pre_init_set_application_defaults` signature vs docs
**File:** `__init__.py:7`

**What:** Hook declared `def _pre_init_set_application_defaults(env):`. Odoo 19 docs PDF still says pre-init hooks receive a cursor; 17+ runtime passes `env`. Empirically works at v19.0.3.8.

**Why it matters:** Future point releases that revert behavior would break this.

**Fix:** Defensive accept-both: `def _pre_init_set_application_defaults(env_or_cr): cr = getattr(env_or_cr, 'cr', env_or_cr); env = getattr(env_or_cr, 'env', None) or api.Environment(cr, SUPERUSER_ID, {})`.

---

### STANDALONE — Pass
No findings. All foreign `env[…]` accesses are guarded (e.g. `if 'elks.dues.payment' in self.env:`). Module installs and runs without elksfrs or other sibling Elks modules.

---

### SOFT-DEP — Pay Dues button click crashes when elksfrs absent
**File:** `views/elks_contact_views.xml:385-392`

**What:** Button renders for every `x_is_member`, but `action_pay_dues` exists only in elksfrs.

**Why it matters:** Bad UX on a fresh install without elksfrs.

**Fix:** Options: (a) move the button to a view defined inside elksfrs (preferred — button belongs with its method); (b) add a wrapper method `action_pay_dues` on elkscontacts' res.partner that raises a friendly UserError if elksfrs is missing, and shadows the elksfrs method when present.

---

### SOFT-DEP — `action_create_initiation_payment` — REFERENCE PATTERN
**File:** `models/elks_membership_application.py:1242-1245`

**What:** Checks `if 'elks.dues.payment' not in self.env:` and raises a `UserError`. This is the right idiom for soft dependencies — use it as a template.

---

### BEST-PRACTICE — `pre_init_hook` only fires on first install, not upgrade
**File:** `__init__.py:6-49`

**What:** Docstring says "so that new NOT-NULL / required columns don't fail on module upgrade." But `pre_init_hook` only runs on install. For upgrades, equivalent work must be in a `migrations/<version>/pre-migrate.py`.

**Fix:** Either move the same logic into a `migrations/19.0.3.X/pre-migrate.py` for the version that added the required fields, or correct the docstring.

---

### BEST-PRACTICE — `models/elks_contact.py` is 1161 lines
**File:** `models/elks_contact.py`

**What:** Single file holds CLMS field mirror + name composition + phone composition + volunteer↔HR sync + return-to-sender + suspension + dues + drop/undrop + cron. The dead `res_partner.py` was likely a half-finished split.

**Fix:** After deleting the dead file, split into `res_partner_clms.py`, `res_partner_return_to_sender.py`, `res_partner_suspension.py`, `res_partner_dues.py`, `res_partner_drop.py` each with its own `_inherit = "res.partner"` class.

---

### BEST-PRACTICE — `__init__.py` import order
**File:** `__init__.py:1-3`

**What:** Imports `controllers` before `models`. Convention is `models → wizards → controllers`.

**Fix:** Reorder.

---

### Top 10 minor nits
1. `__pycache__/` checked into `migrations/19.0.3.4/` (stale).
2. `wizard/clms_import_wizard.py:249, 273` use bare `except Exception:` — should narrow.
3. `models/elks_contact.py:370` has a method-level `import re` — move to module top.
4. `_logger` declared unevenly across model files.
5. Indent style inconsistent across `data/*.xml`.
6. No `tests/` directory.
7. View IDs use mixed prefix patterns.
8. `_check_unique_member_num` is a Python constraint where a partial unique index would be DB-enforced and faster on bulk import.
9. Compute method `_compute_investigation_committee_members` lacks `@api.depends`.
10. Mixed translatable-string formatting styles (`_("…") % (…)` vs `_("…", a, b)`).

---

## Summary

| Severity | Count |
|---|---|
| Blockers | **2** |
| Install/upgrade issues | 3 |
| Standalone breakers | 0 ✅ |
| Soft-dep items | 2 |
| Best-practice items | 4 + ~10 nits |

### Goals assessment
- ✅ **Standalone install** — module installs and runs without sibling Elks modules.
- ✅ **Optional features when siblings present** — `env[...]` guards in place where it matters; the new Pay-Dues button is the only soft reference that needs attention.
- ⚠️ **Clean upgrade on existing DBs** — two blockers (dead `res_partner.py` ready to bite, fragile Pay-Dues xpath) plus the 19.0.3.2 data-loss migration. Fix the blockers before next deployment.

### Recommended order of fixes
1. **Delete `models/res_partner.py`** — highest leverage, zero downside.
2. **Harden the Pay-Dues xpath** — switch to `name='button_box'` + `position='inside'` (accepts the trade-off of the new button landing at the end of the bar; if "front-of-bar" matters, target a known elkscontacts-owned button like `Mark RTS` and use `position='before'`).
3. **Add a defensive wrapper for `action_pay_dues`** on res.partner so a click without elksfrs raises a friendly UserError instead of an exception trace.
4. **Patch the 19.0.3.2 migration** to preserve the reinstatement_previous_state mapping (only if any DB ever had real data in that column).
5. Best-practice items can wait for a refactor cycle.
