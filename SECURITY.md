# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it through GitHub Issues:

https://github.com/januspater630/FRT-Memory-Vault/issues

Please do **not** disclose vulnerabilities publicly before they have been addressed.

## Scope

- `src/` — compressor / judge / traces scripts (FRT Memory Vault v1.0)
- Build artifacts attached to GitHub Releases

## Notes

- All scripts are designed to process **local, trusted files only**.
- The `zlib.decompress()` call in `src/_t02_judge.py` has no explicit `max_length` limit;
  do **not** feed untrusted data into the judge without adding a decompression bound.
