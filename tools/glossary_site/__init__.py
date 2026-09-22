"""Static site generator for the UNMC research data governance glossary.

The glossary is LinkML data, not LinkML classes: `src/schema/glossary.yaml`
describes the shape of a term, and `src/definitions/*.yaml` hold the governed
terms themselves. `gen-doc` documents the schema and says nothing about the
terms, so this package renders the terms and treats the gen-doc output as a
secondary technical reference.

Entry point: `python -m glossary_site.build`.
"""

__version__ = "0.2.0"
