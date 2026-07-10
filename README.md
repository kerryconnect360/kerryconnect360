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

## Admin setup
Admin accounts now live in a separate SQLite file named `city.db`.

- The first admin is created from `/board/register`
- After the first admin exists, registration is hidden and only `/board/login` remains
- Additional admins can be created inside the board after login

## Notes
- Public users do not register or log in.
- Admin can upload branding from the settings page.
- Drivers are created by admin and only sign in.
- Bookings stay in the main app database, while admin access uses `city.db`.
- If you keep both database files, the site survives rebuilds without losing data.
