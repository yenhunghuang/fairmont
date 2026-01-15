"""Shared constants and format definitions for Fairmont quotations.

Used by Excel generator for producing quotation files.
"""

# Fairmont company info
FAIRMONT_COMPANY = {
    "name": "Fairmont Designs & Hospitality",
    "address": "8F, #108, Sec. 5, Nanjing E. Rd., Taipei 105, Taiwan",
    "phone": "+886-2-2712-9606",
    "fax": "+886-2-2712-1626",
    "website": "www.fairmontdesignshospitality.com",
}

# Terms and Remarks (Fairmont standard)
FAIRMONT_TERMS_HEADER = "Terms & Remarks:"
FAIRMONT_TERMS = [
    "This quotation is only valid for 15days after submission;",
    "Supply only, exclude any work at site, including but not limited to: unloading, cross-docking, warehousing, assembling and installation;",
    "FOB term, freight cost is excluded;",
    "Payment term : 25% deposit before production, 25% upon approval of control samples & shop drawings, 50% balance before shipment by T/T;",
    "First-of-type, and/or prototypes are not covered by the unit rate above and will be charged double prices under ex-work term;",
    "Fabrics & leathers unit rates are based on local source similar to match specification;",
    "Production leadtime : 90 days production based on all details confirmed and material arrived factory;",
    "All the product specification detail as in the following pages. CBM / Gross weight / Package dimension are all estimated only;",
    "Port of loading will not be confirmed until the order been placed. FD may use any of its factories for production unless specified;",
    "Quote is contingent on locally sourced contract grade hardware for hinges, rails, etc. Upgrade is available at client's cost;",
    "Quote is contingent on indoor use only; unless otherwise stated in the note columns;",
    "Quote is contingent on CA-117 FR & CARB P2 VOC compliant materials. Upgrade is available at client's cost;",
    "Quote is contingent on specification in tender package. Any changes and/or alterations are subject to additional charges;",
    "Exclude any electrical product, including but not limited to lighting, socket, outlet, etc.; unless otherwise stated in the note columns;",
    "Bank guarantee and performance bond cost are exclusive; Calculation: Contract value x 1% / 360 x duration(days) + USD100.00;",
    "The actual fabric amount may be subject to change upon completion and confirmation of the shop drawings;",
]

# Fairmont format column definitions (15 columns)
# Format: (header_text, field_name, excel_width)
COLUMNS = [
    ("NO.", "no", 5),
    ("Item no.", "item_no", 13),
    ("Description", "description", 20),
    ("Photo", "photo", 15),
    ("Dimension\nWxDxH (mm)", "dimension", 18),
    ("Qty", "qty", 8),
    ("UOM", "uom", 6),
    ("Unit Rate\n(USD)", "unit_rate", 12),
    ("Amount\n(USD)", "amount", 12),
    ("Unit\nCBM", "unit_cbm", 8),
    ("Total\nCBM", "total_cbm", 8),
    ("Note", "note", 20),
    ("Location", "location", 15),
    ("Materials Used / Specs", "materials_specs", 20),
    ("Brand", "brand", 12),
]

# Row layout constants
HEADER_START_ROW = 1    # Company header starts at row 1
DATA_HEADER_ROW = 16    # Column headers at row 16
DATA_START_ROW = 17     # Data items start at row 17
