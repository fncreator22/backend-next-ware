from fastapi import APIRouter, Depends, status, Query, Response
from fastapi.responses import HTMLResponse
from typing import Optional, List
from src.modules.auth.dependencies import get_current_user
from src.modules.billing.schema import InvoiceCreate, InvoiceResponse
from src.modules.billing.service import BillingService

router = APIRouter(prefix="/billing", tags=["Billing & Taxation"])


@router.get("/analytics/revenue")
async def get_analytics_revenue(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """Compute gross revenue, tax collected, and net earnings for dashboard cards."""
    data = await service.get_analytics_revenue(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/analytics/trends")
async def get_analytics_trends(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """Aggregate monthly invoicing and taxation volumes for charts."""
    data = await service.get_analytics_trends(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/analytics/top-items")
async def get_analytics_top_items(
    warehouse_id: Optional[str] = Query(None, alias="warehouseId"),
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """Identify and list top selling inventory items by sales counts."""
    data = await service.get_analytics_top_items(current_user, warehouse_id=warehouse_id)
    return {"success": True, "data": data}


@router.get("/analytics/warehouse-performance")
async def get_analytics_warehouse_performance(
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """Super Admin metrics showing revenue and invoice stats grouped per warehouse."""
    data = await service.get_analytics_warehouse_performance(current_user)
    return {"success": True, "data": data}


@router.get("/", response_model=dict)
async def list_invoices(
    search: str = Query("", description="Search matching invoice customer or Bill No"),
    warehouse_id: Optional[str] = Query(None, alias="warehouseId", description="Warehouse filter"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """List invoices under tenant with dynamic structural scoping."""
    res = await service.list_invoices(
        current_user,
        search_q=search,
        warehouse_filter=warehouse_id,
        page=page,
        limit=limit
    )
    serialized = [InvoiceResponse.model_validate(bill).model_dump(by_alias=True) for bill in res["bills"]]
    return {
        "success": True,
        "data": serialized,
        "total": res["total"],
        "pages": res["pages"],
        "message": "Invoices fetched successfully."
    }


@router.get("/{id}")
async def get_invoice_detail(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """Fetch specific invoice detailed configuration snapshot."""
    bill = await service.get_invoice_detail(id, current_user)
    serialized = InvoiceResponse.model_validate(bill).model_dump(by_alias=True)
    return {"success": True, "data": serialized}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def generate_invoice(
    payload: InvoiceCreate,
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """Generate invoice, trigger atomic stock reductions, and record tax snapshots."""
    bill = await service.create_invoice(payload, current_user)
    serialized = InvoiceResponse.model_validate(bill).model_dump(by_alias=True)
    return {
        "success": True,
        "message": "Invoice generated successfully.",
        "data": serialized
    }


@router.delete("/{id}", response_model=dict)
async def delete_invoice(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """Soft delete invoice registry (super_admin or admin only)."""
    await service.delete_invoice(id, current_user)
    return {
        "success": True,
        "message": "Invoice deleted and moved to recovery storage successfully."
    }


@router.get("/{id}/print", response_class=HTMLResponse)
async def stream_invoice_pdf(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """Stream a premium, high-fidelity printable HTML representation of the historic invoice."""
    bill = await service.get_invoice_detail(id, current_user)
    wh = await service.warehouse_repo.find_by_id_and_tenant(bill["warehouse_id"], current_user["tenant_id"])

    # Retrieve logo, business name, currency settings
    wh_logo = wh.get("logo", "🏭") if wh else "🏭"
    wh_currency = bill.get("currency") or (wh.get("currency", "USD") if wh else "USD")
    wh_currency_symbol = "₹" if wh_currency == "INR" else "€" if wh_currency == "EUR" else "£" if wh_currency == "GBP" else "$"
    
    wh_email = wh.get("email", "") if wh else ""
    wh_contact = wh.get("contact", "") if wh else ""
    wh_address = wh.get("address", "Primary Logistics Hub") if wh else "Primary Logistics Hub"
    wh_business = wh.get("businessName") or wh.get("name", "NexWare ERP") if wh else "NexWare ERP"
    wh_name = wh.get("name", "Primary Hub") if wh else "Primary Hub"

    gstin_fallback = f"27{wh_email.upper()[:3]}C{wh_contact[-4:] if len(wh_contact) >= 4 else '1234'}F1Z5" if wh_email else "27AAPCW1234F1Z5"

    # Extract corporate fields
    seller_address = bill.get("seller_address") or wh_address
    seller_contact = bill.get("seller_contact") or wh_contact
    seller_tax_number = bill.get("seller_tax_number") or gstin_fallback
    buyer_billing_address = bill.get("buyer_billing_address") or "N/A"
    buyer_shipping_address = bill.get("buyer_shipping_address") or "N/A"
    customer_phone = bill.get("customer_phone") or "N/A"
    customer_email = bill.get("customer_email") or "N/A"
    employee_name = bill.get("employee_name") or "System Creator"
    employee_role = bill.get("employee_role") or "Staff"

    # Format rows
    rows_html = ""
    for i in bill.get("items", []):
        line_base = i["qty"] * float(i["price"])
        
        # Handle dynamic multiple taxes snapshot
        if "taxes" in i and i["taxes"]:
            line_tax = sum(float(t.get("amount", 0)) for t in i["taxes"])
            tax_parts = []
            for t in i["taxes"]:
                t_name = t.get("name", "Tax")
                t_type = t.get("tax_type", t.get("taxType", "percentage"))
                t_rate = float(t.get("rate", 0))
                if t_type == "percentage":
                    tax_parts.append(f"{t_name}: {t_rate*100:.0f}%")
                else:
                    tax_parts.append(f"{t_name}: {wh_currency_symbol}{t_rate:.2f}")
            tax_rate_text = ", ".join(tax_parts)
        else:
            tax_rate = float(i.get("tax_rate_snapshot", 0.05))
            line_tax = line_base * tax_rate
            tax_rate_text = f"{(tax_rate*100):.0f}%"

        line_total = line_base + line_tax
        rows_html += f"""
        <tr>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;font-weight:600">{i['name']}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:center"><span class="badge" style="background-color:#6366f1;color:#fff;padding:2px 6px;border-radius:4px;font-size:10px">{i.get('tax_category', 'normal')}</span></td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:center;font-weight:600">{i['qty']}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:right">{wh_currency_symbol}{float(i['price']):.2f}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:center;font-weight:600;color:#b45309;font-size:11px">{tax_rate_text}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:right;color:#b45309">{wh_currency_symbol}{line_tax:.2f}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:right;font-weight:700">{wh_currency_symbol}{line_total:.2f}</td>
        </tr>
        """
    
    # Due Date calculation (created_at + 15 days)
    from datetime import datetime, timedelta
    created_at = bill.get("created_at")
    if isinstance(created_at, str):
        try:
            # Handle ISO strings like 2026-06-04T20:00:00 or with timezone suffix
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            created_at = datetime.utcnow()
    elif not isinstance(created_at, datetime):
        created_at = datetime.utcnow()

    due_date = created_at + timedelta(days=15)

    # Tax details grouped summary
    tax_summary_html = ""
    if "tax_details" in bill and bill["tax_details"]:
        for t in bill["tax_details"]:
            tax_amt = float(t.get("amount", 0))
            rate_val = float(t.get("rate", 0))
            rate_text = f"{(rate_val*100):.1f}%" if t.get("tax_type", "percentage") == "percentage" else f"{wh_currency_symbol}{rate_val:.2f}"
            tax_summary_html += f"""
            <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px dashed #e5e7eb;font-size:13px;color:#b45309">
              <span style="color:#b45309">{t['name']} ({rate_text})</span><span style="font-weight:600">{wh_currency_symbol}{tax_amt:.2f}</span>
            </div>
            """
    else:
        tax_summary_html = f"""
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #e5e7eb;font-size:13px">
          <span style="color:#b45309">Total Tax</span><span style="color:#b45309;font-weight:600">{wh_currency_symbol}{float(bill['tax']):.2f}</span>
        </div>
        """

    invoice_html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Invoice {bill['bill_no']}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:system-ui,-apple-system,sans-serif; background:#fff; color:#111; padding:20mm; }}
    @page {{ size:A4; margin:15mm; }}
    @media print {{
      body {{ padding:0; }}
      .no-print {{ display:none !important; }}
    }}
    .badge {{
      display: inline-block;
      padding: 0.25em 0.4em;
      font-size: 75%;
      font-weight: 700;
      line-height: 1;
      text-align: center;
      white-space: nowrap;
      vertical-align: baseline;
      border-radius: 0.25rem;
      background-color: #6366f1;
      color: #fff;
    }}
  </style>
</head>
<body>
  <div class="no-print" style="text-align:center;padding:12px;background:#6366f1;color:#fff;font-family:sans-serif;font-size:14px;cursor:pointer;border-radius:8px;margin-bottom:20px;" onclick="window.print()">
    🖨️ Click here to Print / Save as PDF
  </div>
  <div style="padding:20px;max-width:800px;margin:0 auto;background:#fff;border-radius:12px">
    <!-- Header: Seller & Corporate Identity -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px;padding-bottom:18px;border-bottom:2px solid #e5e7eb">
      <div>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
          <div style="width:40px;height:40px;border-radius:8px;background:linear-gradient(135deg, #6366f1, #4f46e5);display:flex;align-items:center;justify-content:center;font-size:20px;color:white">{wh_logo}</div>
          <div>
            <div style="font-size:22px;font-weight:800;color:#1e1b4b;line-height:1">{wh_business}</div>
            <div style="font-size:11px;font-weight:700;color:#6366f1;letter-spacing:1px;margin-top:4px">TAX ID/GSTIN: {seller_tax_number}</div>
          </div>
        </div>
        <div style="font-size:12px;color:#4b5563;line-height:1.5">
          📍 Address: {seller_address}<br/>
          📞 Contact: {seller_contact}
        </div>
      </div>
      <div style="text-align:right">
        <div style="font-size:28px;font-weight:900;color:#6366f1;letter-spacing:1px;line-height:1;margin-bottom:6px">INVOICE</div>
        <div style="font-size:14px;font-weight:700;font-family:monospace;color:#1e1b4b">{bill['bill_no']}</div>
        <div style="font-size:11px;color:#9ca3af;margin-top:4px">Source Hub: {wh_name}</div>
      </div>
    </div>

    <!-- Buyer & Metadata Block -->
    <div style="display:grid;grid-template-columns:1.5fr 1fr;gap:20px;margin-bottom:24px">
      <div style="background:#f9fafb;border-left:4px solid #6366f1;padding:12px 16px;border-radius:0 8px 8px 0">
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:#6366f1;margin-bottom:6px">Bill To (Buyer)</div>
        <div style="font-size:15px;font-weight:700;color:#111;margin-bottom:4px">{bill['customer']}</div>
        <div style="font-size:11px;color:#4b5563;line-height:1.4">
          🏢 <strong>Billing:</strong> {buyer_billing_address}<br/>
          🚚 <strong>Shipping:</strong> {buyer_shipping_address}<br/>
          📞 <strong>Contact:</strong> {customer_phone} {f' · 📧 {customer_email}' if customer_email else ''}
        </div>
      </div>
      <div style="background:#f9fafb;border-left:4px solid #10b981;padding:12px 16px;border-radius:0 8px 8px 0">
        <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:#10b981;margin-bottom:6px">Invoice Metadata</div>
        <div style="font-size:11px;color:#4b5563;line-height:1.5">
          📅 <strong>Issue Date:</strong> {created_at.strftime('%Y-%m-%d')}<br/>
          📅 <strong>Due Date:</strong> {due_date.strftime('%Y-%m-%d')}<br/>
          👤 <strong>Billed By:</strong> {employee_name} ({employee_role})<br/>
          💳 <strong>Payment Method:</strong> Bank Transfer (Net 15)<br/>
          💵 <strong>Currency:</strong> {wh_currency} {f'(Rate: {bill["exchange_rate"]})' if bill.get("exchange_rate") and float(bill["exchange_rate"]) != 1.0 else ''}
        </div>
      </div>
    </div>

    <!-- Items Table -->
    <table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:12px">
      <thead>
        <tr style="background:#f3f4f6;color:#1e1b4b">
          <th style="padding:10px 8px;text-align:left;border-radius:6px 0 0 6px">Item Details</th>
          <th style="padding:10px 8px;text-align:center">Category</th>
          <th style="padding:10px 8px;text-align:center">Qty</th>
          <th style="padding:10px 8px;text-align:right">Rate</th>
          <th style="padding:10px 8px;text-align:center">Tax %</th>
          <th style="padding:10px 8px;text-align:right">Tax Amt</th>
          <th style="padding:10px 8px;text-align:right;border-radius:0 6px 6px 0">Total</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>

    <!-- Bottom Section: Totals & Signature -->
    <div style="display:grid;grid-template-columns:1.2fr 1fr;gap:24px;margin-bottom:24px;align-items:end">
      <!-- Terms & Notes -->
      <div style="font-size:11px;color:#9ca3af;line-height:1.5">
        <div style="font-weight:700;color:#4b5563;margin-bottom:4px">Terms & Declarations</div>
        <div>1. Payment is strictly due within 15 days of invoice generation date.</div>
        <div>2. Interest at 18% p.a. will be charged for delayed payments.</div>
        <div>3. Subject to local judicial jurisdiction. Goods once sold will not be returned.</div>
      </div>
      <!-- Grand Totals -->
      <div style="min-width:220px">
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #e5e7eb;font-size:13px">
          <span style="color:#9ca3af">Subtotal</span><span style="font-weight:600">{wh_currency_symbol}{float(bill['subtotal']):.2f}</span>
        </div>
        {tax_summary_html}
        <div style="display:flex;justify-content:space-between;padding:10px 0;background:#f9fafb;border-radius:8px;padding:10px 12px;margin-top:4px">
          <span style="font-size:14px;font-weight:800;color:#1e1b4b">Grand Total</span>
          <span style="font-size:18px;font-weight:900;color:#6366f1">{wh_currency_symbol}{float(bill['total']):.2f}</span>
        </div>
      </div>
    </div>

    <!-- Footer: Signature & Systems Metadata -->
    <div style="border-top:1.5px solid #e5e7eb;padding-top:16px;display:flex;justify-content:space-between;align-items:center">
      <div style="font-size:10px;color:#9ca3af">
        <div>Generated by NexWare ERP</div>
        <div>Date & Time: {created_at.strftime('%Y-%m-%d %H:%M:%S')}</div>
      </div>
      <div style="text-align:right;min-width:180px">
        <div style="border-bottom:1px solid #e5e7eb;height:30px;width:100%;margin-bottom:4px"></div>
        <div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase">Authorized Signatory</div>
      </div>
    </div>
  </div>
  <script>setTimeout(()=>window.print(),600);</script>
</body>
</html>"""

    return HTMLResponse(content=invoice_html, status_code=200)
