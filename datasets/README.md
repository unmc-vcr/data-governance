# Governed data sets

The data stores, data sets, data elements and classification levels that the
glossary's terms describe, written as instance data for the
[Data Governance Ontology](https://github.com/james-geiger/dgo) **0.2.0**, the
first release with data sets.

| File | What it holds |
| --- | --- |
| `classification.yaml` | The four sensitivity levels from the (provisional) [data classification standard](../content/standards/data-classification.md). |
| `data_stores.yaml` | RADB and the Research Analytics data warehouse. |
| `sponsored_programs/dept_awards_requests.yaml` | The Department Awards & Requests data set, its two sources of truth, and one data element per column. |

## Why this isn't under `governance/`

dgo-atlas 0.5.2 can't hold data sets yet. Its record has no `data_stores`,
`data_sets` or `data_elements` lists, so it rejects any file under
`governance/` that declares them. It also can't resolve a term's
`informed_by`, because the data elements it points at can't be declared. These
files live here, outside the build, until dgo-atlas supports them. The site
and its CI don't read them.

The ids use the `data:` prefix (`https://w3id.org/unmc/data/`), which is
registered in `dgo-atlas.yaml` so the namespace is reserved for the move.

## Where the data set is used

The dbt project [unmc-vcr/data-orchestration](https://github.com/unmc-vcr/data-orchestration)
builds `data:dept-awards-requests` as the model `dept_awards_requests`. Its
exposure (the Department Dashboards Tableau workbook) and every column carry
these IRIs and the glossary terms in their `meta`, so dbt docs link each
column to its term. DGO has no slot pointing back from a data set to its
consumers or its physical table, so that link lives on the dbt side only.

## Validating

Validate against DGO 0.2.0's template. Use `src/dgo-template.yaml` at the tag:
the `dist/dgo-template.yaml` published with 0.2.0 is stale and has no
data-set lists.

```bash
git clone --depth 1 --branch 0.2.0 https://github.com/james-geiger/dgo.git /tmp/dgo
for f in datasets/*.yaml datasets/**/*.yaml; do
  uv run linkml-validate -s /tmp/dgo/src/dgo-template.yaml -C GovernanceRecord "$f"
done
```

`linkml-validate` checks shape and required fields only. It doesn't check that
a referenced id (a term, an office, another data set) exists. The dgo-atlas
build will, once these files move into `governance/`.

## Moving into `governance/`

Once dgo-atlas supports data sets:

1. Set `dgo_version: "0.2.0"` (or later) in `dgo-atlas.yaml`.
2. Move these files under `governance/` (for example `governance/datasets/`).
3. Add `informed_by` to each glossary term below, listing the data elements
   marked `# informs:` in `dept_awards_requests.yaml`. Direct Cost, Indirect
   Cost and Research Project are already approved, so record a
   `term_modifications` entry for each of those.

| Term | Informed by columns of `dept_awards_requests` |
| --- | --- |
| `term:award` | record_category, record_id |
| `term:budget-period` | record_begin_date, record_end_date |
| `term:direct-cost` | direct_cost |
| `term:federal-pass-through` | funding_category |
| `term:grant-id` | project_id |
| `term:indirect-cost` | indirect_cost |
| `term:instructional-project` | project_category_label |
| `term:period-of-performance` | project_begin_date, project_end_date |
| `term:prime-sponsor` | sponsor_prime_name, sponsor_prime_type_label |
| `term:principal-investigator` | pi_name_first, pi_name_last, pi_personnel_number, pi_nuid |
| `term:proposal` | record_category, record_id, record_type_code, record_type_label |
| `term:public-service-project` | project_category_label |
| `term:research-project` | project_category_label |
| `term:sponsor` | sponsor_direct_name, sponsor_direct_type_label |

For example, in `governance/research/sponsored_programs/terms/direct_cost.yaml`:

```yaml
    informed_by:
      - data:dept-awards-requests/direct_cost
```

`unit`, `department`, `division` and `hr_org_unit` are the principal
investigator's home department, not the project's administering department,
so they deliberately inform no term.
