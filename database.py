import logging
import time
from typing import List, Optional, Dict, Any
from config import settings

logger = logging.getLogger("woodturnery.database")

class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.is_connected = False
        self._memory_products: List[Dict[str, Any]] = []
        self._memory_orders: Dict[str, Dict[str, Any]] = {}

    def initialize(self, seed_products: List[Dict[str, Any]]):
        self._memory_products = list(seed_products)

        if not settings.is_mongodb_ready:
            logger.info(
                "MongoDB URI contains placeholder '<db_password>'. "
                "Operating with in-memory store until credentials are provided in backend/.env."
            )
            return

        try:
            from pymongo import MongoClient
            # Set 3 second connection timeout to avoid blocking server start
            self.client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=3500,
                connectTimeoutMS=3500
            )
            # Trigger connection check
            self.client.admin.command('ping')
            self.db = self.client[settings.MONGODB_DB_NAME]
            self.is_connected = True
            logger.info(f"Connected to MongoDB Atlas: {settings.MONGODB_DB_NAME}")

            # Auto-seed products collection if empty
            products_col = self.db["products"]
            if products_col.count_documents({}) == 0:
                logger.info("Seeding MongoDB products collection with initial catalog...")
                # Insert seed products without Mongo '_id' clashes
                clean_seeds = [{k: v for k, v in p.items() if k != "_id"} for p in seed_products]
                products_col.insert_many(clean_seeds)
                logger.info(f"Seeded {len(clean_seeds)} products into MongoDB.")
        except Exception as e:
            logger.warning(
                f"Could not establish connection to MongoDB Atlas ({e}). "
                f"Falling back to high-performance in-memory repository."
            )
            self.is_connected = False
            self.client = None
            self.db = None

    def get_products(
        self,
        category: Optional[str] = None,
        main_category: Optional[str] = None,
        sub_category: Optional[str] = None,
        search: Optional[str] = None,
        featured: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        # Slugifier helper
        def to_slug(val: Optional[str]) -> str:
            if not val:
                return ""
            return val.lower().replace("&", "and").replace(" ", "-").replace("(", "").replace(")", "").replace(".", "").replace(",", "").replace("/", "-")

        # 1. Fetch source list (MongoDB or Memory)
        if self.is_connected and self.db is not None:
            try:
                raw_products = list(self.db["products"].find({}, {"_id": 0}))
            except Exception as e:
                logger.error(f"Error reading from MongoDB ({e}), falling back to memory.")
                raw_products = self._memory_products
        else:
            raw_products = self._memory_products

        results = raw_products

        # Filter by main category
        if main_category and main_category.lower() != "all":
            target = main_category.lower()
            results = [
                p for p in results
                if to_slug(p.get("mainCategory")) == to_slug(target)
                or p.get("mainCategory", "").lower() == target
                or (p.get("parentCategory") and p.get("parentCategory", "").lower() == target)
            ]

        # Filter by sub category
        if sub_category and sub_category.lower() != "all":
            target = sub_category.lower()
            results = [
                p for p in results
                if to_slug(p.get("subCategory")) == to_slug(target)
                or p.get("subCategory", "").lower() == target
            ]

        # General category filter
        if category and category.lower() != "all" and not main_category and not sub_category:
            cat_lower = category.lower()
            cat_slug = to_slug(category)
            results = [
                p for p in results
                if p.get("mainCategory", "").lower() == cat_lower
                or to_slug(p.get("mainCategory")) == cat_slug
                or (p.get("parentCategory") and p.get("parentCategory", "").lower() == cat_lower)
                or (p.get("category") and p.get("category", "").lower() == cat_lower)
                or p.get("subCategory", "").lower() == cat_lower
                or to_slug(p.get("subCategory")) == cat_slug
            ]

        # Filter by featured
        if featured is not None:
            results = [p for p in results if p.get("isFeatured") == featured]

        # Search query
        if search:
            q = search.lower()
            results = [
                p for p in results
                if q in p.get("name", "").lower()
                or q in p.get("description", "").lower()
                or (p.get("timber") and q in p.get("timber", "").lower())
                or q in p.get("mainCategory", "").lower()
                or q in p.get("subCategory", "").lower()
            ]

        return results

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        if self.is_connected and self.db is not None:
            try:
                doc = self.db["products"].find_one({"id": product_id}, {"_id": 0})
                if doc:
                    return doc
            except Exception as e:
                logger.error(f"Error querying product by ID ({e})")

        for p in self._memory_products:
            if p.get("id") == product_id:
                return p
        return None

    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves an order to MongoDB or in-memory repository."""
        order_data["createdAt"] = order_data.get("createdAt") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        order_id = order_data["id"]

        self._memory_orders[order_id] = order_data

        if self.is_connected and self.db is not None:
            try:
                # Save without mutable reference
                doc_to_save = dict(order_data)
                self.db["orders"].replace_one({"id": order_id}, doc_to_save, upsert=True)
                logger.info(f"Order {order_id} recorded in MongoDB Atlas.")
            except Exception as e:
                logger.error(f"Error inserting order into MongoDB ({e})")

        return order_data

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves order by order reference ID."""
        if self.is_connected and self.db is not None:
            try:
                doc = self.db["orders"].find_one({"id": order_id}, {"_id": 0})
                if doc:
                    return doc
            except Exception as e:
                logger.error(f"Error fetching order from MongoDB ({e})")

        return self._memory_orders.get(order_id)

    def update_order_payment(
        self,
        order_id: str,
        payment_status: str,
        transaction_id: str,
        payment_details: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Updates payment status on the order."""
        order = self.get_order(order_id)
        if not order:
            return None

        order["status"] = "CONFIRMED"
        order["paymentStatus"] = payment_status
        order["transactionId"] = transaction_id
        order["paidAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if payment_details:
            order["paymentDetails"] = payment_details

        self._memory_orders[order_id] = order

        if self.is_connected and self.db is not None:
            try:
                self.db["orders"].update_one(
                    {"id": order_id},
                    {"$set": {
                        "status": "CONFIRMED",
                        "paymentStatus": payment_status,
                        "transactionId": transaction_id,
                        "paidAt": order["paidAt"],
                        "paymentDetails": payment_details or {}
                    }}
                )
                logger.info(f"Order {order_id} payment updated in MongoDB.")
            except Exception as e:
                logger.error(f"Error updating order in MongoDB ({e})")

        return order

    def save_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or updates a product in MongoDB Atlas and in-memory repository."""
        import re
        product_id = product_data.get("id")
        if not product_id:
            name = product_data.get("name", "turned-piece")
            product_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
            product_data["id"] = product_id

        # Update in-memory
        existing_idx = next((i for i, p in enumerate(self._memory_products) if p.get("id") == product_id), None)
        if existing_idx is not None:
            self._memory_products[existing_idx] = dict(product_data)
        else:
            self._memory_products.insert(0, dict(product_data))

        # Persist to MongoDB Atlas
        if self.is_connected and self.db is not None:
            try:
                doc = {k: v for k, v in product_data.items() if k != "_id"}
                self.db["products"].replace_one({"id": product_id}, doc, upsert=True)
                logger.info(f"Product {product_id} saved to MongoDB Atlas.")
            except Exception as e:
                logger.error(f"Error saving product to MongoDB ({e})")

        return product_data

    def delete_product(self, product_id: str) -> bool:
        """Deletes a product from MongoDB Atlas and in-memory repository."""
        self._memory_products = [p for p in self._memory_products if p.get("id") != product_id]

        if self.is_connected and self.db is not None:
            try:
                res = self.db["products"].delete_one({"id": product_id})
                logger.info(f"Product {product_id} deleted from MongoDB Atlas (count={res.deleted_count}).")
                return res.deleted_count > 0
            except Exception as e:
                logger.error(f"Error deleting product from MongoDB ({e})")
                return False

        return True

    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Returns all orders sorted newest first."""
        if self.is_connected and self.db is not None:
            try:
                docs = list(self.db["orders"].find({}, {"_id": 0}).sort("createdAt", -1))
                if docs:
                    return docs
            except Exception as e:
                logger.error(f"Error fetching all orders from MongoDB ({e})")

        orders = list(self._memory_orders.values())
        orders.sort(key=lambda o: o.get("createdAt", ""), reverse=True)
        return orders

    def update_order_status(self, order_id: str, status: str, timeline_note: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Updates status of an order."""
        order = self.get_order(order_id)
        if not order:
            return None

        order["status"] = status
        now_str = time.strftime("%b %d, %Y - %I:%M %p", time.localtime())

        if "timeline" in order and isinstance(order["timeline"], list):
            step_map = {
                "CONFIRMED": 0,
                "IN_WORKSHOP": 1,
                "PACKAGING": 2,
                "DISPATCHED": 3,
                "DELIVERED": 4
            }
            if status in step_map:
                target_idx = step_map[status]
                for i, step in enumerate(order["timeline"]):
                    if i <= target_idx:
                        step["completed"] = True
                        if step.get("time") in ("Pending", "Scheduled"):
                            step["time"] = now_str
                    else:
                        step["completed"] = False

        self._memory_orders[order_id] = order

        if self.is_connected and self.db is not None:
            try:
                self.db["orders"].update_one(
                    {"id": order_id},
                    {"$set": {"status": status, "timeline": order.get("timeline", [])}}
                )
                logger.info(f"Order {order_id} status changed to {status} in MongoDB.")
            except Exception as e:
                logger.error(f"Error updating order status in MongoDB ({e})")

        return order

db_manager = DatabaseManager()
