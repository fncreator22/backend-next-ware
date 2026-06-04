from decimal import Decimal
from typing import List, Dict, Any


class TaxEngine:
    """
    Centralized, deterministic, decimal-safe calculation engine for NexWare ERP Billing & Taxation.
    Supports dynamic multiple stacked percentage and fixed rate taxes per item.
    """

    @staticmethod
    def calculate_taxes(items: List[Dict[str, Any]], tax_rates: Dict[str, Decimal]) -> Dict[str, Any]:
        """
        Computes line-item and invoice-wide totals with full stacked tax configurations.
        
        Args:
            items: List of dictionary item drafts (price, qty, taxCategory, optional taxes overrides)
            tax_rates: Current active tax rates dictionary (e.g. {"normal": 0.05, "luxury": 0.15})
            
        Returns:
            Dict containing subtotal, total tax, grand total, item snapshots with calculated taxes,
            and grouped invoice-wide tax totals.
        """
        subtotal = Decimal("0.0")
        total_tax = Decimal("0.0")
        processed_items = []
        
        # Track grouped taxes scoped across the entire invoice
        grouped_taxes: Dict[str, Dict[str, Any]] = {}

        for item in items:
            qty = int(item.get("qty", 1))
            price = Decimal(str(item.get("price", "0.0")))
            
            line_subtotal = price * qty
            subtotal += line_subtotal
            
            # Determine active taxes for this line item
            taxes_list = []
            
            # If item contains structural custom taxes, parse them
            if "taxes" in item and item["taxes"] is not None:
                for t in item["taxes"]:
                    tax_name = t.get("name", "Tax")
                    tax_type = t.get("taxType", t.get("tax_type", "percentage"))
                    rate = Decimal(str(t.get("rate", "0.0")))
                    
                    if tax_type == "percentage":
                        # Percentage tax: line_subtotal * rate
                        amount = line_subtotal * rate
                    else:
                        # Fixed fee tax: qty * flat_rate
                        amount = Decimal(str(qty)) * rate
                        
                    taxes_list.append({
                        "name": tax_name,
                        "tax_type": tax_type,
                        "rate": rate,
                        "amount": amount
                    })
            else:
                # Fallback to current warehouse/global legacy flat keys
                tax_cat = item.get("taxCategory", item.get("tax_category", "normal"))
                rate = tax_rates.get(tax_cat, tax_rates.get("normal", Decimal("0.05")))
                
                # Single percentage tax snapshot
                amount = line_subtotal * rate
                taxes_list.append({
                    "name": f"GST ({tax_cat.capitalize()})",
                    "tax_type": "percentage",
                    "rate": rate,
                    "amount": amount
                })

            # Calculate total line tax
            line_tax = sum(t["amount"] for t in taxes_list)
            total_tax += line_tax
            line_total = line_subtotal + line_tax

            # Append to item snapshot list
            processed_items.append({
                "item_id": item.get("id", item.get("item_id")),
                "name": item.get("name"),
                "qty": qty,
                "price": price,
                "tax_category": item.get("taxCategory", item.get("tax_category", "normal")),
                "tax_rate_snapshot": taxes_list[0]["rate"] if taxes_list else Decimal("0.05"),
                "taxes": taxes_list,
                "subtotal": line_subtotal,
                "tax": line_tax,
                "total": line_total
            })

            # Accumulate into invoice-wide grouped taxes summary
            for t in taxes_list:
                name = t["name"]
                if name not in grouped_taxes:
                    grouped_taxes[name] = {
                        "name": name,
                        "tax_type": t["tax_type"],
                        "rate": t["rate"],
                        "amount": Decimal("0.0")
                    }
                grouped_taxes[name]["amount"] += t["amount"]

        grand_total = subtotal + total_tax

        return {
            "subtotal": subtotal,
            "tax": total_tax,
            "total": grand_total,
            "items": processed_items,
            "tax_details": list(grouped_taxes.values())
        }
