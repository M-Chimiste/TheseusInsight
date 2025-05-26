# Credential Management

Theseus Insight now keeps API keys and other sensitive settings encrypted in the database.
This document explains how the credentials workflow operates.

## Overview

Sensitive values such as `OPENAI_API_KEY` or `GMAIL_APP_PASSWORD` can be supplied
via a `.env` file for first time startup. The FastAPI service reads these values
at launch and stores them using simple XOR encryption keyed by the `APP_SECRET_KEY` environment variable.
Subsequent startups load the decrypted values from the database and populate
`os.environ` so the application libraries can access them normally.

A dedicated credentials section on the Settings page lets administrators review
and update all stored keys in one place. Each field is hidden by default, with a
show/hide toggle. `OLLAMA_URL` is not sensitive and is always shown in plain text.

The backend exposes two endpoints:

- `GET /api/settings/credentials` – return current credential values from the database or environment
- `PUT /api/settings/credentials` – update multiple credentials at once

The update endpoint encrypts new values before persisting them and updates the
running process environment so changes take immediate effect.

## Security Notes

- Encryption uses a simple XOR operation; choose a strong `APP_SECRET_KEY` to avoid
  trivial recovery of the plaintext values.
- Ensure your `.env` file permissions restrict access to authorised users only.
- Consider using Docker secrets or a vault in production.

