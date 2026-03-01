import json
from typing import Dict, Optional
from decimal import Decimal
from django.core.cache import cache
from loguru import logger

# Cart expires after 18 hours (in seconds)
CART_TTL = 18 * 60 * 60  # 64800 seconds


class CartService:
    """
    Redis-based shopping cart service.
    Cart is tied to a user (not pharmacy) and can contain items from multiple pharmacies.
    Cart items are stored in Redis with automatic expiration after 18 hours.
    """

    @staticmethod
    def _get_cart_key(user_id: str) -> str:
        """Generate a unique Redis key for the user's cart"""
        return f"cart:{user_id}"

    @staticmethod
    def _serialize_item(item: Dict) -> str:
        """Serialize cart item to JSON string"""
        # Convert Decimal to string for JSON serialization
        serialized = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                serialized[key] = str(value)
            else:
                serialized[key] = value
        return json.dumps(serialized)

    @staticmethod
    def _deserialize_item(item_str: str) -> Dict:
        """Deserialize JSON string to cart item"""
        item = json.loads(item_str)
        # Convert price strings back to Decimal
        if "unit_price" in item:
            item["unit_price"] = Decimal(item["unit_price"])
        if "subtotal" in item:
            item["subtotal"] = Decimal(item["subtotal"])
        return item

    @classmethod
    def get_cart(cls, user_id: str) -> Dict:
        """
        Get all items in the user's cart.
        Returns cart data with items grouped by pharmacy, totals, and metadata.
        """
        cart_key = cls._get_cart_key(user_id)
        cart_data = cache.get(cart_key)

        if not cart_data:
            return {
                "items": [],
                # "items_by_pharmacy": {},
                "total_items": 0,
                "total_amount": Decimal("0.00"),
                "prescription_code": None,
            }

        # Deserialize items
        items = []
        for item_str in cart_data.get("items", []):
            try:
                items.append(cls._deserialize_item(item_str))
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error deserializing cart item: {e}")
                continue

        # Group items by pharmacy
        # items_by_pharmacy = {}
        # for item in items:
        #     pharmacy_id = item.get("pharmacy_id")
        #     if pharmacy_id not in items_by_pharmacy:
        #         items_by_pharmacy[pharmacy_id] = {
        #             "pharmacy_id": pharmacy_id,
        #             "pharmacy_name": item.get("pharmacy_name"),
        #             "items": [],
        #             "subtotal": Decimal("0.00"),
        #         }
        #     items_by_pharmacy[pharmacy_id]["items"].append(item)
        #     items_by_pharmacy[pharmacy_id]["subtotal"] += Decimal(
        #         str(item.get("subtotal", 0))
        #     )

        # Calculate totals
        total_items = sum(item.get("quantity", 0) for item in items)
        total_amount = sum(Decimal(str(item.get("subtotal", 0))) for item in items)

        return {
            "items": items,
            # "items_by_pharmacy": list(items_by_pharmacy.values()),
            "total_items": total_items,
            "total_amount": total_amount,
            "prescription_code": cart_data.get("prescription_code"),
        }

    @classmethod
    def add_item(
        cls,
        user_id: str,
        pharmacy_id: str,
        pharmacy_name: str,
        drug_id: str,
        drug_name: str,
        quantity: int,
        unit_price: Decimal,
        drug_image: Optional[str] = None,
        base_unit: Optional[str] = None,
    ) -> Dict:
        """
        Add an item to the cart or update quantity if it already exists.
        Returns the updated cart.
        """
        cart_key = cls._get_cart_key(user_id)
        cart_data = cache.get(cart_key) or {"items": [], "prescription_code": None}

        # Deserialize existing items
        items = []
        for item_str in cart_data.get("items", []):
            try:
                items.append(cls._deserialize_item(item_str))
            except (json.JSONDecodeError, KeyError):
                continue

        # Check if item already exists (same drug AND same pharmacy)
        existing_item = None
        for item in items:
            if (
                item.get("drug_id") == drug_id
                and item.get("pharmacy_id") == pharmacy_id
            ):
                existing_item = item
                break

        if existing_item:
            # Update quantity
            existing_item["quantity"] += quantity
            existing_item["subtotal"] = (
                existing_item["unit_price"] * existing_item["quantity"]
            )
        else:
            # Add new item
            new_item = {
                "drug_id": drug_id,
                "drug_name": drug_name,
                "drug_image": drug_image,
                "base_unit": base_unit,
                "quantity": quantity,
                "unit_price": unit_price,
                "subtotal": unit_price * quantity,
                "pharmacy_id": pharmacy_id,
                "pharmacy_name": pharmacy_name,
            }
            items.append(new_item)

        # Serialize and save
        cart_data["items"] = [cls._serialize_item(item) for item in items]
        cache.set(cart_key, cart_data, timeout=CART_TTL)

        return cls.get_cart(user_id)

    @classmethod
    def update_item_quantity(
        cls,
        user_id: str,
        pharmacy_id: str,
        drug_id: str,
        quantity: int,
    ) -> Dict:
        """
        Update the quantity of an item in the cart.
        If quantity is 0 or less, the item is removed.
        Returns the updated cart.
        """
        if quantity <= 0:
            return cls.remove_item(user_id, pharmacy_id, drug_id)

        cart_key = cls._get_cart_key(user_id)
        cart_data = cache.get(cart_key)

        if not cart_data:
            return cls.get_cart(user_id)

        # Deserialize existing items
        items = []
        for item_str in cart_data.get("items", []):
            try:
                items.append(cls._deserialize_item(item_str))
            except (json.JSONDecodeError, KeyError):
                continue

        # Find and update item (match both drug_id and pharmacy_id)
        for item in items:
            if (
                item.get("drug_id") == drug_id
                and item.get("pharmacy_id") == pharmacy_id
            ):
                item["quantity"] = quantity
                item["subtotal"] = item["unit_price"] * quantity
                break

        # Serialize and save
        cart_data["items"] = [cls._serialize_item(item) for item in items]
        cache.set(cart_key, cart_data, timeout=CART_TTL)

        return cls.get_cart(user_id)

    @classmethod
    def remove_item(cls, user_id: str, pharmacy_id: str, drug_id: str) -> Dict:
        """
        Remove an item from the cart.
        Returns the updated cart.
        """
        cart_key = cls._get_cart_key(user_id)
        cart_data = cache.get(cart_key)

        if not cart_data:
            return cls.get_cart(user_id)

        # Deserialize existing items
        items = []
        for item_str in cart_data.get("items", []):
            try:
                items.append(cls._deserialize_item(item_str))
            except (json.JSONDecodeError, KeyError):
                continue

        # Remove the item (match both drug_id and pharmacy_id)
        items = [
            item
            for item in items
            if not (
                item.get("drug_id") == drug_id
                and item.get("pharmacy_id") == pharmacy_id
            )
        ]

        # Serialize and save
        cart_data["items"] = [cls._serialize_item(item) for item in items]
        cache.set(cart_key, cart_data, timeout=CART_TTL)

        return cls.get_cart(user_id)

    @classmethod
    def clear_cart(cls, user_id: str, pharmacy_id: Optional[str] = None) -> bool:
        """
        Clear items from the cart.
        If pharmacy_id is provided, only clear items from that pharmacy.
        If no pharmacy_id, clear entire cart.
        Returns True if successful.
        """
        cart_key = cls._get_cart_key(user_id)

        if pharmacy_id is None:
            # Clear entire cart
            cache.delete(cart_key)
            return True

        # Clear only items from specific pharmacy
        cart_data = cache.get(cart_key)
        if not cart_data:
            return True

        # Deserialize existing items
        items = []
        for item_str in cart_data.get("items", []):
            try:
                items.append(cls._deserialize_item(item_str))
            except (json.JSONDecodeError, KeyError):
                continue

        # Keep only items NOT from the specified pharmacy
        items = [item for item in items if item.get("pharmacy_id") != pharmacy_id]

        # Serialize and save
        cart_data["items"] = [cls._serialize_item(item) for item in items]
        cache.set(cart_key, cart_data, timeout=CART_TTL)

        return True

    @classmethod
    def set_prescription_code(cls, user_id: str, prescription_code: str) -> Dict:
        """
        Associate a prescription code with the cart.
        Returns the updated cart.
        """
        cart_key = cls._get_cart_key(user_id)
        cart_data = cache.get(cart_key) or {"items": [], "prescription_code": None}
        cart_data["prescription_code"] = prescription_code
        cache.set(cart_key, cart_data, timeout=CART_TTL)
        return cls.get_cart(user_id)

    @classmethod
    def refresh_cart_ttl(cls, user_id: str) -> bool:
        """
        Refresh the cart's TTL (reset the 18-hour timer).
        Returns True if successful.
        """
        cart_key = cls._get_cart_key(user_id)
        cart_data = cache.get(cart_key)
        if cart_data:
            cache.set(cart_key, cart_data, timeout=CART_TTL)
            return True
        return False

    @classmethod
    def get_cart_ttl(cls, user_id: str) -> Optional[int]:
        """
        Get the remaining TTL for the cart in seconds.
        Returns None if cart doesn't exist.
        """
        cart_key = cls._get_cart_key(user_id)
        cart_data = cache.get(cart_key)
        if cart_data:
            return CART_TTL  # Approximate, as we can't get exact TTL from Django cache
        return None
