# Brewcraft Coffee Shop Management

A premium, responsive coffee shop management dashboard built with **Python + Flask + HTML/CSS/JavaScript + SQLite**.

## Features
- Owner sign-in
- Dashboard: today's revenue/orders, active products, low-stock alerts, weekly sales chart and best sellers
- POS: cart, quantities, customer name, Cash/UPI/Card payment selection, 5% tax calculation, checkout
- Product/menu management: add, edit, remove, search, category filters, SKU and stock quantities
- Automatic inventory deduction on completed orders
- Order history and printable order receipts
- Expense ledger
- CSV export of order records
- Responsive premium coffee-themed UI

## Run on macOS / Windows / Linux

1. Install Python 3.10 or newer.
2. Extract this folder and open Terminal/Command Prompt inside it.
3. Create and activate a virtual environment (recommended):

   **macOS/Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   **Windows**
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Set owner credentials before launching (recommended):

   **macOS/Linux**
   ```bash
   export SHOP_ADMIN_USER="yourname"
   export SHOP_ADMIN_PASSWORD="use-a-strong-password"
   export SECRET_KEY="put-a-long-random-secret-here"
   ```

   **Windows PowerShell**
   ```powershell
   $env:SHOP_ADMIN_USER="yourname"
   $env:SHOP_ADMIN_PASSWORD="use-a-strong-password"
   $env:SECRET_KEY="put-a-long-random-secret-here"
   ```

6. Start the app:
   ```bash
   python app.py
   ```
7. Open **http://127.0.0.1:5000** in your browser and sign in with the credentials you set.

If you skip step 5, the demo defaults are username `owner` and password `change-me-now`. Do not use those defaults for real shop data.

## Important notes
- The database file `coffee_shop.db` is created automatically on first launch and seeded with sample products.
- Back up `coffee_shop.db` regularly. Export order CSVs from Reports as an additional record.
- The POS currently applies a configurable demo tax rate of 5%. Adjust the `tax = round(subtotal * 0.05, 2)` line in `app.py` to your applicable tax policy.
- This is a local starter app, not yet hardened for public internet deployment. Before deploying, add CSRF protection, rate limiting, stronger user management, HTTPS, backups, and proper production server settings. Never expose the development server publicly.
- This starter records selected payment method but does not connect to a payment gateway or actually charge cards/UPI.
