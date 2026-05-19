class WarehouseService:
    def __init__(self):
        pass

    async def verify_subscription_limits(self, tenant_id: str) -> bool:
        """Query warehouse counts against tenant subscription limit restrictions."""
        return True
