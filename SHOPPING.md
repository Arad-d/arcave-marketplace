# Shopping reliability

## Completed checklist

- [x] Prevent simultaneous checkouts from overselling inventory.
- [x] Prevent duplicate checkout submissions from creating duplicate purchases.
- [x] Validate quantities, positive prices, supported categories and required fields.
- [x] Restrict product reviews to customers who purchased the product.
- [x] Handle repeated and concurrent seller replies without overwriting the first reply.
- [x] Preserve purchased product names, store names, prices and quantities after listing edits or deletion.
- [x] Give orders unique receipt numbers and visible fulfillment statuses.

## How checkout works

The cart page issues a signed, customer-specific confirmation valid for 30 minutes. It includes a fingerprint of cart row IDs, products, quantities and displayed prices. Changed prices or cart contents require the customer to review the cart again. This confirmation supplements Django's CSRF protection.

Checkout locks the customer, then all affected products in ascending ID order. Stock validation, receipt creation, deductions and removal of purchased cart entries commit together. Any failure rolls back the entire transaction. Cart changes use the same customer lock. A repeated confirmation returns the original receipt, even if the customer has since added a new cart. Separate tabs with different confirmations cannot purchase the same cart twice.

Stock is not reserved by adding an item to a cart. It is checked again at checkout. Each product can have 1–5 units in a customer's cart, bounded by current stock. Seller and administrator edits require the original stock value from their form; if checkout has changed it, the edit is rejected until refreshed. Product edits lock the same row used by checkout.

These guarantees require PostgreSQL row locking. The concurrency tests run on independent PostgreSQL connections and intentionally skip on databases without row-lock support. Administrative cart and purchase editing is disabled to keep mutations in the coordinated shopping flow.

## Receipts and status

Each order gets a unique `ARC-<UUID>` number. Customers can view only their own receipts. Seller dashboards show only that seller's purchased items, including items whose listings were deleted. Historical receipt lines retain product/store names, unit price, quantity and line total. Nullable links to listings and sellers allow those records to be deleted without removing the receipt.

New orders start as **Placed**, then staff with order-change permission can advance them to **Processing** and **Completed** through the order list in Django admin. Receipt amounts and lines are read-only there. Status describes fulfillment, not payment. This project does not collect payments; cancellation, refunds, stock returns and delivery integrations remain future work.

## Existing databases

Back up the database with a compatible PostgreSQL `pg_dump` and verify the archive before running `python manage.py migrate`. Migration `shop.0004_shopping_reliability` creates one **Legacy / unknown status** order per existing purchase because the old schema did not record which lines were checked out together. It preserves recorded totals and timestamps. For legacy lines, unit price is derived from a known line total, rounded to two decimals. Unknown totals remain unknown; the migration never substitutes today's product price. Names are copied from the surviving listing, so pre-migration edits cannot be reconstructed.

New database constraints reject nonpositive prices, unsupported categories, cart quantities outside 1–5 and nonpositive purchase quantities. Correct any existing violations before migrating; the migration deliberately does not silently rewrite historical quantities or prices. Back up before rollback as well: reversing the schema loses new receipt metadata and restores the old destructive product relationship.

## Verification

Run the full suite against a dedicated PostgreSQL test database:

```bash
cd django_project
python manage.py test accounts shop arcave --settings=arcave.test_settings
```

Tests cover competing buyers, repeated confirmations, separate browser tabs, concurrent replies, cart/price changes, expired confirmations, rollback after database failure, ownership, deleted listings, seller/admin stale inventory edits, database constraints and legacy receipt migration.
