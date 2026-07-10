# Book with Kerry

A public booking site with:
- user-facing bookings without login
- admin dashboard at `/board`
- driver login at `/drivers`
- seat-based booking by trip/vehicle
- manual payment approval
- shareable receipt links
- uploadable logo and business card
- QR code that opens the live site

## Default admin
If no admin exists, the app seeds one from environment variables or defaults:

- username: `admin`
- password: `Admin123!`

Set your own values in production:
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_NAME`

## Notes
- Public users do not register or log in.
- Admin can upload branding from the settings page.
- Drivers are created by admin and only sign in.
- Bookings are stored in SQLite by default, so the app survives rebuilds when the database file is preserved.
