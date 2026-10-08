# Odoo 16 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Odoo 17-specific leftovers from the Odoo 16 skill pack so the 16.0 references are trustworthy for agent-generated guidance.

**Architecture:** Treat the review as a documentation-correctness bugfix across a small set of reference guides. Fix the issues by file cluster, replacing incorrect v17 APIs with validated v16 patterns, then run pattern-based verification sweeps to ensure the most dangerous leftovers are gone.

**Tech Stack:** Markdown reference files, `rg`, Git diff, GitHub PR review context

---

## File Map

- `skills/odoo-16.0/references/odoo-16-controller-guide.md`
  Responsibility: HTTP/controller auth guidance for Odoo 16.
- `skills/odoo-16.0/references/odoo-16-development-guide.md`
  Responsibility: Odoo 16 module lifecycle, hooks, structure, and examples.
- `skills/odoo-16.0/references/odoo-16-manifest-guide.md`
  Responsibility: manifest keys, hooks, and version metadata guidance.
- `skills/odoo-16.0/references/odoo-16-model-guide.md`
  Responsibility: ORM/search/domain/grouping API guidance.
- `skills/odoo-16.0/references/odoo-16-performance-guide.md`
  Responsibility: performance guidance, grouping, batching, and SQL patterns.
- `skills/odoo-16.0/references/odoo-16-decorator-guide.md`
  Responsibility: decorator reference and supported Odoo 16 API surface.
- `skills/odoo-16.0/references/odoo-16-security-guide.md`
  Responsibility: RPC exposure and secure model method guidance.
- `skills/odoo-16.0/references/odoo-16-actions-guide.md`
  Responsibility: server action states and XML configuration patterns.
- `skills/odoo-16.0/references/odoo-16-owl-guide.md`
  Responsibility: OWL/JS patching, assets, and translation usage for Odoo 16.
- `skills/odoo-16.0/references/odoo-16-migration-guide.md`
  Responsibility: upgrade/migration mechanics and version metadata examples.

### Task 1: Capture the current mismatch set

**Files:**
- Modify: `docs/superpowers/plans/2026-06-20-odoo-16-review-fixes.md`
- Verify: `skills/odoo-16.0/references/*.md`

- [ ] **Step 1: Run a pre-fix sweep for the known Odoo 17 leftovers**

Run:

```powershell
rg -n "post_init_hook\(env\)|search_fetch|search_count\(.*limit=|aggregates=\[|recordset\.grouped|\.grouped\(|@api\.private|self\.env\._\(|\bany\b|not any|odoo\.tools\.SQL|SQL\.identifier|webhook_url|webhook_field_ids|update_path|version_info = \(17, 0, 0|web\.assets_qweb|patch\(|2\.8\.2|In 17, implement your own bearer-token logic" skills/odoo-16.0/references
```

Expected: multiple hits in the controller, development, manifest, model, performance, decorator, security, actions, owl, and migration guides.

- [ ] **Step 2: Save the pre-fix evidence in the commit message or PR notes**

Use this summary in the implementation notes:

```text
Validated the external review locally. The reported Odoo 17 leftovers are present in the Odoo 16 pack and are concentrated in controller, development, manifest, model, performance, decorator, security, actions, owl, and migration guides.
```

### Task 2: Fix the quick textual leftovers first

**Files:**
- Modify: `skills/odoo-16.0/references/odoo-16-controller-guide.md`
- Modify: `skills/odoo-16.0/references/odoo-16-migration-guide.md`
- Modify: `skills/odoo-16.0/references/odoo-16-manifest-guide.md`

- [ ] **Step 1: Fix the bearer-token typo in the controller guide**

Replace the sentence under `### Odoo 16 does NOT have auth='bearer'`:

```md
`auth='bearer'` was introduced in later Odoo versions. In 16, implement your own bearer-token logic:
```

- [ ] **Step 2: Correct leftover `version_info` tuples**

Replace the Odoo 17 tuple references with the Odoo 16 tuple in these guides:

```md
`version_info = (16, 0, 0, FINAL, 0, '')`
```

Target files:

```text
skills/odoo-16.0/references/odoo-16-migration-guide.md
skills/odoo-16.0/references/odoo-16-manifest-guide.md
```

- [ ] **Step 3: Verify the quick textual leftovers are gone**

Run:

```powershell
rg -n "In 17, implement your own bearer-token logic|version_info = \(17, 0, 0" skills/odoo-16.0/references
```

Expected: no output.

### Task 3: Rewrite hook guidance to real Odoo 16 signatures

**Files:**
- Modify: `skills/odoo-16.0/references/odoo-16-development-guide.md`
- Modify: `skills/odoo-16.0/references/odoo-16-manifest-guide.md`

- [ ] **Step 1: Replace env-based hook signatures with `(cr, registry)`**

Use Odoo 16-compatible signatures:

```python
def pre_init_hook(cr):
    # optional raw SQL only; no Environment yet
    pass


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.config_parameter"].sudo().set_param("business_trip.enabled", "True")


def uninstall_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.config_parameter"].sudo().search([
        ("key", "=like", "business_trip.%"),
    ]).unlink()
```

- [ ] **Step 2: Update the explanatory prose around hook calling conventions**

Make the text say that in Odoo 16:

```md
- `pre_init_hook` runs before module installation with a cursor-only style entry point.
- `post_init_hook` and `uninstall_hook` are called with `(cr, registry)`.
- Build an `Environment` manually inside the hook when ORM access is needed.
```

- [ ] **Step 3: Verify hook guidance no longer advertises env-only hooks**

Run:

```powershell
rg -n "def pre_init_hook\(env\)|def post_init_hook\(env\)|def uninstall_hook\(env\)|All three are called with env|called with `env`" skills/odoo-16.0/references/odoo-16-development-guide.md skills/odoo-16.0/references/odoo-16-manifest-guide.md
```

Expected: no output.

### Task 4: Downgrade the ORM/model guidance to APIs that actually exist in Odoo 16

**Files:**
- Modify: `skills/odoo-16.0/references/odoo-16-model-guide.md`
- Modify: `skills/odoo-16.0/references/odoo-16-performance-guide.md`

- [ ] **Step 1: Remove `search_fetch()` as a user-facing Odoo 16 API**

Replace the dedicated `search_fetch()` section with Odoo 16-safe guidance:

```python
records = self.search([("state", "=", "done")], limit=100)
records.read(["name", "amount_total", "partner_id"])
```

And describe `search_read()` without claiming it delegates through a public `search_fetch()` API.

- [ ] **Step 2: Remove `search_count(limit=...)` from the Odoo 16 examples**

Use the v16-safe pattern:

```python
count = self.search_count([("state", "=", "draft")])
```

If an upper bound matters, document a separate `search(..., limit=...)` pattern instead of a `search_count(limit=...)` claim.

- [ ] **Step 3: Rewrite `_read_group()` coverage to avoid the v17 `aggregates=[...]` signature**

Replace the v17-style examples with Odoo 16-safe `read_group()` examples:

```python
rows = self.read_group(
    domain=[("state", "=", "done")],
    fields=["partner_id", "amount_total:sum"],
    groupby=["partner_id"],
    lazy=False,
)

amount_by_partner = {
    row["partner_id"][0]: row["amount_total"]
    for row in rows
    if row.get("partner_id")
}
```

If `_read_group()` remains documented at all, keep it explicitly caveated as an internal/core method and avoid documenting the v17 named-parameter shape as authoritative Odoo 16 API.

- [ ] **Step 4: Remove `any` / `not any` as supported Odoo 16 domain operators**

Replace that table entry and the dedicated section with relation traversal examples that are valid in Odoo 16:

```python
domain = [("order_line.product_id.qty_available", "<=", 0)]
domain = [("order_line.product_id.type", "!=", "service")]
```

If exact semantics differ from `not any`, prefer a warning that Odoo 16 does not expose the v17 `any` / `not any` operators.

- [ ] **Step 5: Remove `grouped()` as an Odoo 16 recordset API**

Use a plain Python grouping example instead:

```python
from collections import defaultdict

groups = defaultdict(lambda: self.env[self._name].browse())
for record in records:
    groups[record.state] |= record
```

- [ ] **Step 6: Fix Python translation guidance in the model guide**

Replace:

```python
translated = self.env._("Hello %s") % name
```

With:

```python
from odoo import _

translated = _("Hello %s") % name
```

- [ ] **Step 7: Verify the model/performance guides no longer advertise the v17 APIs**

Run:

```powershell
rg -n "search_fetch|search_count\(.*limit=|aggregates=\[|@api\.private|self\.env\._\(|\bany\b|not any|\.grouped\(|recordset\.grouped|SQL\.identifier|odoo\.tools\.SQL" skills/odoo-16.0/references/odoo-16-model-guide.md skills/odoo-16.0/references/odoo-16-performance-guide.md
```

Expected: no hits for the v17-only APIs. Legitimate uses of the English word "any" outside domain operators are fine and can remain if the search is tightened case-by-case.

### Task 5: Remove unsupported decorator and security guidance

**Files:**
- Modify: `skills/odoo-16.0/references/odoo-16-decorator-guide.md`
- Modify: `skills/odoo-16.0/references/odoo-16-security-guide.md`

- [ ] **Step 1: Delete `@api.private` from the Odoo 16 decorator reference**

Remove it from the description, table of contents, section headings, examples, summary table, and source citations.

Replace the guidance with the Odoo 16-safe convention:

```python
def _refund_total(self, reason):
    return self.amount_total
```

And state plainly that underscore-prefixed methods are the standard way to keep helpers out of RPC exposure in Odoo 16.

- [ ] **Step 2: Update the security guide to stop claiming `@api.private` exists in Odoo 16**

Replace the current note with:

```md
In Odoo 16, keep internal helpers underscore-prefixed so they are not callable through the RPC layer. Do not rely on `@api.private` in this version.
```

- [ ] **Step 3: Verify the decorator/security guides no longer claim `@api.private` support**

Run:

```powershell
rg -n "@api\.private|api\.private|_api_private" skills/odoo-16.0/references/odoo-16-decorator-guide.md skills/odoo-16.0/references/odoo-16-security-guide.md
```

Expected: no output.

### Task 6: Fix server action and OWL guidance to true Odoo 16 patterns

**Files:**
- Modify: `skills/odoo-16.0/references/odoo-16-actions-guide.md`
- Modify: `skills/odoo-16.0/references/odoo-16-owl-guide.md`

- [ ] **Step 1: Replace unsupported server action fields/states**

Remove or rewrite the `webhook` state examples and stop documenting `update_path` as the `object_write` configuration surface.

Use v16-safe `fields_lines` guidance instead:

```xml
<record id="action_mark_done" model="ir.actions.server">
    <field name="name">Mark Done</field>
    <field name="model_id" ref="model_my_model"/>
    <field name="state">object_write</field>
    <field name="fields_lines" eval="[(0, 0, {
        'col1': ref('base.field_ir_actions_server__fields_lines'),
        'value': 'done',
        'type': 'value',
    })]"/>
</record>
```

If the exact `fields_lines` example needs adjustment after source validation, keep the plan intent but use the real Odoo 16 XML shape from upstream docs or source.

- [ ] **Step 2: Rewrite OWL patching examples to the Odoo 16 patch signature**

Replace object-literal `patch(FormController.prototype, { ... super... })` examples with the Odoo 16 pattern:

```javascript
patch(FormController.prototype, "my_module.FormController", {
    async onWillSaveRecord(record) {
        const result = await this._super(...arguments);
        if (result && record.resModel === "sale.order") {
            console.log("Saving a sale order");
        }
        return result;
    },
});
```

Do the same for the ORM/service patch example and any checklist or summary lines that currently say to use native `super.method(...)`.

- [ ] **Step 3: Correct OWL/assets versioning leftovers**

Update the OWL version text and asset guidance so it no longer claims:

```text
- OWL 2.8.2
- web.assets_qweb as a valid Odoo 16 bundle
```

Keep the replacements source-backed. If exact OWL sub-version is not trivial to verify from the local repo, state the safer form "OWL 2.x shipped with Odoo 16" rather than inventing a number.

- [ ] **Step 4: Verify the server action and OWL leftovers are gone**

Run:

```powershell
rg -n "webhook_url|webhook_field_ids|update_path|patch\(.*\{|super\.|web\.assets_qweb|2\.8\.2" skills/odoo-16.0/references/odoo-16-actions-guide.md skills/odoo-16.0/references/odoo-16-owl-guide.md
```

Expected: no output for the removed v17-specific guidance.

### Task 7: Fix raw SQL guidance to remove the v17 `SQL` wrapper

**Files:**
- Modify: `skills/odoo-16.0/references/odoo-16-performance-guide.md`
- Modify: `skills/odoo-16.0/references/odoo-16-transaction-guide.md`

- [ ] **Step 1: Replace `odoo.tools.SQL` examples with plain parameterized SQL**

Use Odoo 16-safe cursor examples:

```python
self.env.cr.execute(
    "SELECT state, SUM(amount_total) FROM sale_order WHERE state = %s GROUP BY state",
    ("done",),
)
rows = self.env.cr.fetchall()
```

For dynamic identifiers, do not promise a public `SQL.identifier(...)` helper in v16. Either avoid dynamic identifiers in examples or explicitly label them as cases requiring careful manual quoting outside this guide's scope.

- [ ] **Step 2: Verify the SQL wrapper references are gone**

Run:

```powershell
rg -n "odoo\.tools\.SQL|SQL\.identifier|cr\.execute\(SQL" skills/odoo-16.0/references/odoo-16-performance-guide.md skills/odoo-16.0/references/odoo-16-transaction-guide.md
```

Expected: no output.

### Task 8: Final review sweep and commit prep

**Files:**
- Verify: `skills/odoo-16.0/references/*.md`

- [ ] **Step 1: Re-run the full leftover sweep**

Run:

```powershell
rg -n "post_init_hook\(env\)|search_fetch|search_count\(.*limit=|aggregates=\[|recordset\.grouped|\.grouped\(|@api\.private|self\.env\._\(|\bany\b|not any|odoo\.tools\.SQL|SQL\.identifier|webhook_url|webhook_field_ids|update_path|version_info = \(17, 0, 0|web\.assets_qweb|2\.8\.2|In 17, implement your own bearer-token logic" skills/odoo-16.0/references
```

Expected: no remaining hits for the targeted Odoo 17 leftovers. If `\bany\b` still returns normal English prose, refine the search and ensure the domain-operator examples are gone.

- [ ] **Step 2: Review the diff by file cluster**

Run:

```powershell
git diff -- skills/odoo-16.0/references/odoo-16-controller-guide.md skills/odoo-16.0/references/odoo-16-development-guide.md skills/odoo-16.0/references/odoo-16-manifest-guide.md skills/odoo-16.0/references/odoo-16-model-guide.md skills/odoo-16.0/references/odoo-16-performance-guide.md skills/odoo-16.0/references/odoo-16-decorator-guide.md skills/odoo-16.0/references/odoo-16-security-guide.md skills/odoo-16.0/references/odoo-16-actions-guide.md skills/odoo-16.0/references/odoo-16-owl-guide.md skills/odoo-16.0/references/odoo-16-migration-guide.md skills/odoo-16.0/references/odoo-16-transaction-guide.md
```

Expected: each change should clearly remove a v17-only claim or replace it with a v16-safe example.

- [ ] **Step 3: Commit with a docs-focused message**

```bash
git add skills/odoo-16.0/references docs/superpowers/plans/2026-06-20-odoo-16-review-fixes.md
git commit -m "fix: correct Odoo 16 reference pack version-specific APIs"
```

