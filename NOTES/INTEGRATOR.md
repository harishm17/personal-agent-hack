
## STORE 11:25 — pool committed (data/pool/*.json, raw replies in data/pool/raw/)
Products per store and line (title rules in signoff/store/build_pool.py; every query of every line fetched once):
- carex.com 42: L1 14, L2 10, L3 2, L4 11, L5 3, L6 2
- vivehealth.com 22: L1 8, L2 3, L3 4, L4 3, L5 4, L6 0 (its search returns no bed rail)
- parentgiving.com 47: L1 15, L2 5, L3 8, L4 6, L5 2, L6 11
- No `product_key` appears at two stores (SKUs and titles differ even for Carex items sold at parentgiving.com). A strike
  holding "at every store" cannot be shown with this pool unless a product is added; tell me if you want the Carex
  Economy seat looked up at carex.com by SKU.
- parentgiving.com texts are short (300 to 1500 characters); some state no figure at all, which suits the not_stated demo.
- Text is title + plain description + "Selected option: ..." for the cheapest available variant (that variant's id and price).
