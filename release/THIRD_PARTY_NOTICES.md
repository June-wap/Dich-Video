# Third-party notices — release gate

This repository's current license review does **not** approve any combined
runtime and voice/model payload for production distribution.  Therefore the
installer build intentionally rejects an empty/unapproved model manifest rather
than silently shipping cached artifacts.

Before a commercial release, add one entry per shipped artifact to
`model-manifest.json` with the immutable source, SHA-256, license text/notice,
redistribution status, and reviewer approval. Include the resulting notices in
the installer. See `docs/model_license_matrix.md` for the open items.
