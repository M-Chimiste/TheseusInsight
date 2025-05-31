# Postgres Path Fix

## Issue
The universal build script `scripts/fix-postgres.js` contained a hard coded
path to the developer's machine:
```
/Users/c/software_projects/TheseusInsight/electron-app/postgres/darwin/lib/libpq.5.dylib
```
When the Electron app was built, this absolute path was embedded in the binary
patching step. The resulting application worked only on the original machine but
failed on others when PostgreSQL was accessed.

## Fix
The script now resolves the path to `libpq.5.dylib` relative to the packaged
`.app` directory instead of using a fixed absolute path. During the patching
process each PostgreSQL binary is scanned for any reference to
`libpq.5.dylib`.  Regardless of what absolute path the build process embedded,
those references are rewritten to `@rpath/libpq.5.dylib` and an rpath of
`@loader_path/../lib` is added if required.

This ensures that the packaged application uses only relative paths to its own
resources, allowing it to run on any Mac after signing.
