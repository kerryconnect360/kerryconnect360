# City Connect

A mobile-first booking and admin platform built with Flask, HTML, CSS, and JavaScript.

## Structure
- Public homepage opens at `/`
- Customer booking page at `/book`
- Customer app at `/app`
- Protected admin board at `/board`
- Admin login at `/board/login`
- First-time setup at `/setup`

## Features
- First user becomes admin automatically
- Admin can add other users and change roles
- Public site, customer portal, and protected admin board are separated
- PWA install button and service worker
- SQLite persistence in `instance/` by default
- Optional `DATABASE_URL` for hosted deployments

## Run locally
```bash
pip install -r requirements.txt
python app.py
```

## Deploy
Use the `Procfile` with Gunicorn.
