"""Build Dr Abby Projects.html from Gersh Deals.xlsx"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
DEALS_XLSX = SCRIPT_DIR / "Gersh Deals.xlsx"
TEMPLATE = SCRIPT_DIR / "projects_dashboard_template.html"
OUTPUT = SCRIPT_DIR / "3 Dr Abby Projects.html"


def flexible_get(row, *keys):
    """Case-insensitive, trimmed column lookup."""
    for k in keys:
        for col in row.index:
            if col.strip().lower() == k.lower():
                val = row[col]
                if pd.notna(val) and val != '':
                    return val
    return None


def to_date_str(val):
    """Convert value to YYYY-MM-DD string."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, pd.Timestamp):
        return val.strftime('%Y-%m-%d')
    try:
        d = pd.to_datetime(val)
        if pd.isna(d):
            return None
        return d.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return None


def build_data():
    df = pd.read_excel(DEALS_XLSX, sheet_name=0)

    deals = []
    for _, row in df.iterrows():
        company = flexible_get(row, 'Brand', 'brand', 'Company', 'company')
        if company is None:
            continue
        company = str(company).strip()
        if not company:
            continue

        offer = to_date_str(flexible_get(row, 'Offer Date', 'OfferDate', 'offer date', 'offer'))
        live = to_date_str(flexible_get(row, 'Live Date', 'LiveDate', 'live date', 'live'))
        if not offer or not live:
            continue

        product = flexible_get(row, 'Product', 'product')
        product = str(product).strip() if product else '—'

        fee_val = flexible_get(row, 'Fee', 'Fees', 'fee', 'fees')
        try:
            fee = float(fee_val) if fee_val is not None else 0
        except (ValueError, TypeError):
            fee = 0

        deliverables = flexible_get(row, 'Deliverables', 'Deliverable', 'deliverables')
        deliverables = str(deliverables).strip() if deliverables else ''

        usage = flexible_get(row, 'Suage', 'Usage', 'usage', 'suage')
        usage = str(usage).strip() if usage else ''

        exclusivity = flexible_get(row, 'Exclusivity', 'exclusivity')
        exclusivity = str(exclusivity).strip() if exclusivity else ''

        deals.append({
            'company': company,
            'product': product,
            'offer': offer,
            'live': live,
            'fee': fee,
            'deliverables': deliverables,
            'usage': usage,
            'exclusivity': exclusivity,
        })

    return deals


def main():
    deals = build_data()
    deals_json = json.dumps(deals, default=str)

    html = TEMPLATE.read_text()
    html = html.replace('__SNAPSHOT_PLACEHOLDER__', deals_json)
    html = html.replace('__BUILD_TIMESTAMP__', datetime.now(tz=ZoneInfo('America/New_York')).strftime('%b %d, %Y %I:%M %p'))
    OUTPUT.write_text(html)

    total_fees = sum(d['fee'] for d in deals)
    print(f"Projects Dashboard built: {len(deals)} deals, ${total_fees:,.0f} total fees")


if __name__ == '__main__':
    main()
