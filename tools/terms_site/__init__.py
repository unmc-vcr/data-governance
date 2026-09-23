"""Static site generator for the UNMC Research Administration Data Governance term set.

The termset is LinkML data, not LinkML classes: `src/schema/terms.yaml`
describes the shape of a term, and `src/definitions/*.yaml` hold the governed
terms themselves. `gen-doc` documents the schema and says nothing about the
terms, so this package renders the terms and treats the gen-doc output as a
secondary technical reference.

Entry point: `python -m terms_site.build`.
"""

__version__ = "0.2.0"
