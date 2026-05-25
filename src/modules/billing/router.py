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


@router.get("/{id}/print", response_class=HTMLResponse)
async def stream_invoice_pdf(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: BillingService = Depends()
):
    """Stream a premium, high-fidelity printable HTML representation of the historic invoice."""
    bill = await service.get_invoice_detail(id, current_user)
    wh = await service.warehouse_repo.find_by_id_and_tenant(bill["warehouse_id"], current_user["tenant_id"])

    # Format rows
    rows_html = ""
    for i in bill["items"]:
        tax_rate = i.get("tax_rate_snapshot", 0.05)
        line_base = i["qty"] * float(i["price"])
        line_tax = line_base * float(tax_rate)
        line_total = line_base + line_tax
        rows_html += f"""
        <tr>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb">{i['name']}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:center">{i['tax_category']}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:center">{i['qty']}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:right">${float(i['price']):.2f}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:center;font-weight:600;color:#b45309">{(float(tax_rate)*100):.0f}%</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:right;color:#b45309">${line_tax:.2f}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;text-align:right;font-weight:700">${line_total:.2f}</td>
        </tr>
        """

    tax_cfg = bill.get("tax_config_snapshot", {"normal": 5.0, "luxury": 15.0})
    wh_name = wh.get("name") if wh else "Warehouse"
    wh_business = wh.get("businessName") if wh else "WareOps ERP"
    wh_address = wh.get("address") if wh else "Industrial Sector"
    wh_contact = wh.get("contact") if wh else ""
    wh_email = wh.get("email") if wh else ""

    invoice_html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Invoice {bill['bill_no']}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:Georgia,serif; background:#fff; color:#111; padding:20mm; }}
    @page {{ size:A4; margin:15mm; }}
    @media print {{
      body {{ padding:0; }}
      .no-print {{ display:none !important; }}
    }}
  </style>
</head>
<body>
  <div class="no-print" style="text-align:center;padding:12px;background:#6366f1;color:#fff;font-family:sans-serif;font-size:14px;cursor:pointer" onclick="window.print()">
    🖨️ Click here to Print / Save as PDF
  </div>
  <div style="padding:20px;max-width:800px;margin:0 auto;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:32px;padding-bottom:20px;border-bottom:3px solid #1e1b4b;font-family:sans-serif;">
      <div>
        <div style="font-size:28px;font-weight:900;color:#1e1b4b;letter-spacing:-0.5px">{wh_business}</div>
        <div style="font-size:13px;color:#6b7280;margin-top:4px">{wh_address}</div>
        <div style="font-size:13px;color:#6b7280">{wh_contact} · {wh_email}</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:32px;font-weight:900;color:#6366f1;letter-spacing:1px">INVOICE</div>
        <div style="font-size:16px;font-weight:700;color:#1e1b4b;margin-top:4px">{bill['bill_no']}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:4px">Date: {bill['created_at'].strftime('%Y-%m-%d')}</div>
      </div>
    </div>

    <div style="display:flex;justify-content:space-between;margin-bottom:28px;font-family:sans-serif;">
      <div style="background:#f8f9ff;border-left:4px solid #6366f1;padding:14px 18px;border-radius:0 8px 8px 0;min-width:200px">
        <div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:#6366f1;margin-bottom:6px">Bill To</div>
        <div style="font-size:16px;font-weight:700;color:#111">{bill['customer']}</div>
      </div>
      <div style="background:#f8f9ff;border-left:4px solid #10b981;padding:14px 18px;border-radius:0 8px 8px 0;min-width:160px">
        <div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:#10b981;margin-bottom:6px">Warehouse</div>
        <div style="font-size:15px;font-weight:700;color:#111">{wh_name}</div>
      </div>
    </div>

    <table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px;font-family:sans-serif;">
      <thead>
        <tr style="background:#1e1b4b;color:#fff">
          <th style="padding:12px 8px;text-align:left;border-radius:6px 0 0 0">Item</th>
          <th style="padding:12px 8px;text-align:center">Category</th>
          <th style="padding:12px 8px;text-align:center">Qty</th>
          <th style="padding:12px 8px;text-align:right">Unit Price</th>
          <th style="padding:12px 8px;text-align:center">Tax %</th>
          <th style="padding:12px 8px;text-align:right">Tax Amt</th>
          <th style="padding:12px 8px;text-align:right;border-radius:0 6px 0 0">Total</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>

    <div style="display:flex;justify-content:flex-end;margin-bottom:28px;font-family:sans-serif;">
      <div style="min-width:260px">
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:14px">
          <span style="color:#6b7280">Subtotal</span><span style="font-weight:600">${float(bill['subtotal']):.2f}</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:14px">
          <span style="color:#b45309">Total Tax</span><span style="color:#b45309;font-weight:600">${float(bill['tax']):.2f}</span>
        </div>
        <div style="display:flex;justify-content:space-between;border-top:1px solid var(--border-default);padding-top:12px;margin-top:4px">
          <span style="font-size:16px;font-weight:800;color:#1e1b4b">Grand Total</span>
          <span style="font-size:20px;font-weight:900;color:#6366f1">${float(bill['total']):.2f}</span>
        </div>
      </div>
    </div>

    <div style="border-top:2px solid #e5e7eb;padding-top:16px;display:flex;justify-content:space-between;align-items:center;font-family:sans-serif;">
      <div style="font-size:11px;color:#9ca3af">
        <div>Generated by WareOps ERP</div>
        <div>{bill['created_at'].strftime('%Y-%m-%d %H:%M:%S')}</div>
      </div>
      <div style="font-size:12px;font-weight:700;color:#10b981;background:#f0fdf4;padding:6px 16px;border-radius:99px;border:1px solid #bbf7d0">✓ PAID</div>
    </div>
  </div>
  <script>setTimeout(()=>window.print(),600);</script>
</body>
</html>"""


    return HTMLResponse(content=invoice_html, status_code=200)
