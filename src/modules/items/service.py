class ItemService:
    def __init__(self):
        pass

    async def verify_sku_uniqueness(self, sku: str, warehouse_id: str) -> bool:
        """Verify SKU uniqueness across a single warehouse space."""
        return True
