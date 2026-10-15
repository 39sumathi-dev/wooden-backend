import random
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import settings
from database import db_manager
from storage import storage_client

app = FastAPI(
    title="SK Wood Turnery E-Commerce API",
    description="Backend service for SK Wood Turnery — Handcrafted Turned Wood Objects with MongoDB & Cloudflare R2",
    version="2.0.0"
)

# Enable CORS for Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class Variant(BaseModel):
    label: str
    price: int
    dimensions: Optional[str] = None

class SubCategoryItem(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    count: Optional[int] = 0
    image: Optional[str] = None

class CategoryGroupItem(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    image: Optional[str] = None
    subCategories: List[SubCategoryItem]
    count: Optional[int] = 0

class Product(BaseModel):
    id: str
    name: str
    mainCategory: str
    subCategory: str
    parentCategory: Optional[str] = None
    category: Optional[str] = None
    timber: Optional[str] = None
    description: str
    images: List[str]
    price: Optional[int] = None
    variants: Optional[List[Variant]] = None
    displayOrder: Optional[int] = None
    isFeatured: Optional[bool] = False
    isNew: Optional[bool] = False
    badge: Optional[str] = None

class ProductUpsert(BaseModel):
    id: Optional[str] = None
    name: str
    mainCategory: str
    subCategory: str
    parentCategory: Optional[str] = None
    category: Optional[str] = None
    timber: Optional[str] = None
    description: str
    images: List[str]
    price: Optional[int] = None
    variants: Optional[List[Variant]] = None
    displayOrder: Optional[int] = None
    isFeatured: Optional[bool] = False
    isNew: Optional[bool] = False
    badge: Optional[str] = None

class AdminLogin(BaseModel):
    username: str
    password: str

class OrderStatusUpdate(BaseModel):
    status: str

# --- ORDER & PAYMENT MODELS ---
class OrderItem(BaseModel):
    productId: str
    productName: str
    variantLabel: str
    price: int
    quantity: int
    image: str

class ShippingAddress(BaseModel):
    fullName: str
    email: str
    phone: str
    addressLine1: str
    addressLine2: Optional[str] = None
    city: str
    state: str
    postalCode: str
    country: str = "India"
    deliveryNotes: Optional[str] = None

class OrderCreate(BaseModel):
    items: List[OrderItem]
    shipping: ShippingAddress
    paymentMethod: str  # 'card', 'upi', 'netbanking', 'cod', 'demo_pay'
    notes: Optional[str] = None

class PaymentProcess(BaseModel):
    paymentMethod: str
    transactionRef: Optional[str] = None
    cardNumber: Optional[str] = None
    upiId: Optional[str] = None
    bankName: Optional[str] = None

# --- TAXONOMY STRUCTURE ---
CATEGORY_TAXONOMY = [
    {
        "id": "functional-homeware",
        "name": "Functional Homeware",
        "slug": "functional-homeware",
        "description": "Utilitarian vessels, bowls, and tableware designed to bring tactile woodcraft to daily living.",
        "image": "assets/products/bowl-oak.png",
        "subCategories": [
            {
                "id": "bowls-trays",
                "name": "Bowls & Trays",
                "slug": "bowls-trays",
                "description": "Centerpiece salad bowls, platters, and shallow trays carved from seasoned billets.",
                "image": "assets/products/bowl-oak.png"
            },
            {
                "id": "goblets-drinkware",
                "name": "Goblets & Drinkware",
                "slug": "goblets-drinkware",
                "description": "Turned wooden chalices, wine goblets, and tumblers finished with food-safe natural seals.",
                "image": "assets/products/goblets-teak.jpg"
            },
            {
                "id": "kitchen-accessories",
                "name": "Kitchen Accessories (Bottle Stoppers, ...)",
                "slug": "kitchen-accessories",
                "description": "Precision wine bottle stoppers, salt & pepper mills, and kitchen tools turned from exotic woods.",
                "image": "assets/products/bottle-stoppers.jpg"
            }
        ]
    },
    {
        "id": "fine-writing-gifts",
        "name": "Fine Writing Instruments & Gifts",
        "slug": "fine-writing-gifts",
        "description": "Meticulously turned luxury fountain pens, pen display boxes, and heirloom ring cases.",
        "image": "assets/products/pen-set.png",
        "subCategories": [
            {
                "id": "executive-pens",
                "name": "Executive Pens & Sets",
                "slug": "executive-pens",
                "description": "Hand-turned pens made from precious hardwoods with solid German nibs and brass fittings.",
                "image": "assets/products/pen-set.png"
            },
            {
                "id": "pen-boxes-cases",
                "name": "Wooden Pen Boxes & Cases",
                "slug": "pen-boxes-cases",
                "description": "Solid walnut and hardwood desk display cases lined with premium velvet.",
                "image": "assets/products/pen-box-walnut.jpg"
            },
            {
                "id": "custom-ring-boxes",
                "name": "Custom Ring Boxes",
                "slug": "custom-ring-boxes",
                "description": "Heirloom magnetic swivel ring boxes crafted from rich burl wood and rare timbers.",
                "image": "assets/products/ring-box-burl.jpg"
            }
        ]
    },
    {
        "id": "art-accent-pieces",
        "name": "Art & Accent Pieces",
        "slug": "art-accent-pieces",
        "description": "Museum-grade hollow forms, gallery finials, desk curios, and specialty hybrid resin artworks.",
        "image": "assets/products/finial-hollow-form.jpg",
        "subCategories": [
            {
                "id": "finials-hollow-forms",
                "name": "Finials & Hollow Forms",
                "slug": "finials-hollow-forms",
                "description": "Delicate thin-walled hollow forms and needle finials turned from contrasting timbers.",
                "image": "assets/products/finial-hollow-form.jpg"
            },
            {
                "id": "spinning-tops-curios",
                "name": "Spinning Tops & Desk Curios",
                "slug": "spinning-tops-curios",
                "description": "Balanced precision wooden spinning tops and sculptural tactile desk artifacts.",
                "image": "assets/products/spinning-tops.jpg"
            },
            {
                "id": "specialty-hybrid-pieces",
                "name": "Specialty / Hybrid Pieces (Resin & Pearl)",
                "slug": "specialty-hybrid-pieces",
                "description": "Striking combination of natural burl timber fused with swirling pearl and emerald epoxy resin.",
                "image": "assets/products/hybrid-resin-bowl.jpg"
            }
        ]
    }
]

# --- SEED PRODUCTS ---
SEED_PRODUCTS = [
    {
        "id": "golden-ember-magnolia-bowl",
        "name": "Golden Ember — Handcrafted Magnolia Wood Bowl",
        "mainCategory": "Functional Homeware",
        "subCategory": "Bowls & Trays",
        "parentCategory": "Functional Homeware",
        "category": "Functional Homeware",
        "timber": "Magnolia",
        "description": "Celebrate the natural beauty of magnolia wood with this one-of-a-kind handcrafted bowl. Golden Ember features beautiful honey-gold and amber tones, flowing wood grain, and dramatic dark markings that create a striking contrast across its sculptural form. The generously curved interior, gently flared rim, and organic contours showcase the character of the wood, making this piece a distinctive addition to any home. Perfect as a coffee-table centerpiece, a decorative accent, or a thoughtful gift for a woodcraft enthusiast, this artisan bowl brings warmth, texture, and natural elegance to any setting.\n\nDetails:\n• Wood: Magnolia\n• Color: Honey gold, amber, and rich brown\n• Style: Rustic artisan with natural organic character\n• Design: Rounded body with a wide, gently flared rim\n• Uniqueness: Natural grain and markings make each piece individual\n• Care: Avoid soaking or dishwashing. Confirm the finish is food-safe before using with food.\n\nA distinctive celebration of magnolia wood and its natural beauty.",
        "images": ["assets/products/golden-ember-bowl.jpg"],
        "price": 95,
        "variants": [
            {"label": "Standard Artisan Edition", "price": 95, "dimensions": "28cm × 11cm"}
        ],
        "isFeatured": True,
        "isNew": True,
        "badge": "Suggested $95",
        "displayOrder": 1
    },
    {
        "id": "emerald-glow-cherry-bowl",
        "name": "Emerald Glow — Handcrafted Cherry Wood Bowl with Iridescent Embellishment",
        "mainCategory": "Functional Homeware",
        "subCategory": "Bowls & Trays",
        "parentCategory": "Functional Homeware",
        "category": "Functional Homeware",
        "timber": "Solid Cherry with Iridescent Embellishment",
        "description": "Beautifully turned from solid cherry wood, this one-of-a-kind artisan bowl showcases the warm honey and amber tones of natural cherry, complemented by distinctive grain patterns and character markings. A striking band of shimmering emerald green, turquoise, and hints of violet embellishment wraps around the exterior, framed by elegant black accent lines.\n\nThe smooth, rounded form, gently flared rim, and carefully finished interior highlight the natural beauty of the wood. The combination of traditional woodturning and vibrant, iridescent detailing creates a captivating piece that blends rustic warmth with contemporary artistic flair. Perfect as a decorative centerpiece, a conversation piece, or a thoughtful gift for someone who appreciates handmade craftsmanship and natural materials.\n\nDetails:\n• Material: Solid cherry wood\n• Design: Hand-turned with iridescent green and turquoise embellishment\n• Accents: Contrasting black decorative bands\n• Finish: Smooth, natural-looking wood finish\n• Style: Contemporary artisan, nature-inspired\n• Uniqueness: One of a kind, with distinctive natural grain and markings\n• Care: Dust with a soft, dry cloth. Avoid soaking, dishwashers, and prolonged exposure to moisture or direct sunlight. Unless the finish and embellishment are confirmed food-safe, use for decorative purposes only.",
        "images": ["assets/products/emerald-glow-bowl.jpg"],
        "price": 125,
        "variants": [
            {"label": "Signature Iridescent Edition", "price": 125, "dimensions": "26cm × 13cm"}
        ],
        "isFeatured": True,
        "isNew": True,
        "badge": "Suggested $125",
        "displayOrder": 2
    },
    {
        "id": "cherry-glow-bowl",
        "name": "Cherry Glow — Hand-Turned Cherry Bowl",
        "mainCategory": "Functional Homeware",
        "subCategory": "Bowls & Trays",
        "parentCategory": "Functional Homeware",
        "category": "Functional Homeware",
        "timber": "Solid Cherry Wood",
        "description": "Showcasing the natural warmth and rich reddish-brown tones of cherry wood, this hand-turned bowl features beautiful flowing grain, distinctive natural figuring, and a smooth, gently curved profile. Its shallow, elegant shape makes it a lovely centerpiece, decorative accent, or serving bowl. Each piece highlights the unique character of the wood, making it one of a kind.\n\nDetails:\n• Material: Solid cherry wood\n• Finish: Smooth, natural wood finish\n• Care: Hand-wipe with a soft, slightly damp cloth; avoid soaking or the dishwasher. Use for food only if the finish is food-safe.",
        "images": ["assets/products/cherry-glow-bowl.jpg"],
        "price": 65,
        "variants": [
            {"label": "Shallow Profile Edition", "price": 65, "dimensions": "24cm × 6cm"}
        ],
        "isFeatured": True,
        "isNew": False,
        "badge": "Suggested $65",
        "displayOrder": 3
    },
    {
        "id": "natures-edge-rustic-bowl",
        "name": "Nature’s Edge — Rustic Live Edge Bowl",
        "mainCategory": "Functional Homeware",
        "subCategory": "Bowls & Trays",
        "parentCategory": "Functional Homeware",
        "category": "Functional Homeware",
        "timber": "Natural Wood with Live Bark Edge",
        "description": "Celebrate the beauty of natural wood with this one-of-a-kind live edge bowl. Its organic, irregular rim preserves the character of the original tree, including rugged bark details and contrasting golden wood grain. The rounded form and sculptural silhouette create a striking balance between rustic charm and refined craftsmanship. A distinctive accent for a coffee table, shelf, or nature-inspired interior.\n\nDetails:\n• Material: Natural wood with preserved live edge and bark features\n• Finish: Smoothly finished interior and exterior with natural edge details\n• Care: Keep dry and clean with a soft cloth. Avoid soaking and direct heat.",
        "images": ["assets/products/natures-edge-bowl.jpg"],
        "price": 95,
        "variants": [
            {"label": "Sculptural Live Edge Edition", "price": 95, "dimensions": "30cm × 14cm"}
        ],
        "isFeatured": True,
        "isNew": True,
        "badge": "Suggested $95",
        "displayOrder": 4
    },
    {
        "id": "woodland-trio-segmented-goblet",
        "name": "Woodland Trio — Segmented Artisan Goblet",
        "mainCategory": "Functional Homeware",
        "subCategory": "Goblets & Drinkware",
        "parentCategory": "Functional Homeware",
        "category": "Functional Homeware",
        "timber": "Cherry, Pine & Ash",
        "description": "A distinctive woodturned goblet handcrafted from three contrasting woods: cherry, pine, and ash. Rich reddish-brown cherry, warm golden pine, and light ash combine to create a beautiful interplay of colors and natural grain patterns. The elongated cup, graceful stem, and sculpted base give this piece an elegant silhouette, making it an eye-catching display piece, a memorable handmade gift, or a unique addition to a woodturning collection.\n\nDetails:\n• Materials: Cherry, pine, and ash\n• Construction: Segmented woodturning\n• Finish: Smooth, polished wood finish\n• Care: Wipe clean with a soft cloth. Not intended for dishwasher use and beverage use.",
        "images": ["assets/products/woodland-trio-goblet.jpg"],
        "price": 85,
        "variants": [
            {"label": "Segmented Artisan Chalice", "price": 85, "dimensions": "21cm × 8cm"}
        ],
        "isFeatured": True,
        "isNew": True,
        "badge": "Suggested $85",
        "displayOrder": 5
    }
]

# Initialize Database (MongoDB Atlas with fallback)
@app.on_event("startup")
def startup_event():
    db_manager.initialize(SEED_PRODUCTS)

# --- ROUTES ---

@app.get("/")
def read_root():
    return {
        "brand": "SK Wood Turnery",
        "tagline": "Handcrafted · Timeless · Quality",
        "status": "online",
        "database": {
            "type": "mongodb_atlas" if db_manager.is_connected else "in_memory_ready",
            "is_connected": db_manager.is_connected,
            "uri_configured": settings.is_mongodb_ready,
            "target_cluster": "cluster0.tp0iccb.mongodb.net",
            "db_name": settings.MONGODB_DB_NAME
        },
        "storage": {
            "type": "cloudflare_r2" if settings.is_r2_ready else "local_assets_fallback",
            "bucket": settings.R2_BUCKET_NAME,
            "public_url": settings.R2_PUBLIC_URL
        },
        "payments": {
            "mode": settings.PAYMENT_GATEWAY_MODE,
            "currency": settings.PAYMENT_CURRENCY,
            "supported_methods": ["card", "upi", "netbanking", "cod", "demo_pay"]
        },
        "endpoints": [
            "/products",
            "/products/{id}",
            "/categories/tree",
            "/categories",
            "/orders",
            "/orders/{id}",
            "/orders/{id}/pay",
            "/api/upload"
        ]
    }

@app.get("/categories/tree", response_model=List[CategoryGroupItem])
def get_categories_tree():
    """Returns full category and subcategory hierarchy with dynamic product counts."""
    products = db_manager.get_products()
    tree = []

    for cat in CATEGORY_TAXONOMY:
        cat_copy = dict(cat)
        sub_list = []
        total_cat_count = 0

        for sub in cat["subCategories"]:
            count = sum(
                1 for p in products
                if (p.get("mainCategory", "").lower() == cat["name"].lower()
                    or p.get("parentCategory", "").lower() == cat["name"].lower())
                and p.get("subCategory", "").lower() == sub["name"].lower()
            )
            sub_copy = dict(sub)
            sub_copy["count"] = count
            total_cat_count += count
            sub_list.append(SubCategoryItem(**sub_copy))

        cat_copy["subCategories"] = sub_list
        cat_copy["count"] = total_cat_count
        tree.append(CategoryGroupItem(**cat_copy))
    return tree

@app.get("/products", response_model=List[Product])
def get_products(
    category: Optional[str] = Query(None, description="Filter by main category or subcategory name/slug"),
    main_category: Optional[str] = Query(None, description="Filter by main category name or slug"),
    sub_category: Optional[str] = Query(None, description="Filter by subcategory name or slug"),
    search: Optional[str] = Query(None, description="Search query across name, timber, description"),
    featured: Optional[bool] = Query(None, description="Filter for featured products only")
):
    return db_manager.get_products(
        category=category,
        main_category=main_category,
        sub_category=sub_category,
        search=search,
        featured=featured
    )

@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: str):
    product = db_manager.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.get("/categories")
def get_categories():
    products = db_manager.get_products()
    cat_map = {}
    for p in products:
        cat = p.get("mainCategory", "General")
        if cat not in cat_map:
            cat_map[cat] = {
                "name": cat,
                "slug": cat.lower().replace("&", "and").replace(" ", "-"),
                "count": 1,
                "image": p["images"][0] if p.get("images") else "",
                "description": f"Handcrafted {cat.lower()} turned from selected seasoned hardwoods"
            }
        else:
            cat_map[cat]["count"] += 1
    return list(cat_map.values())

# --- ORDER & PAYMENT ENDPOINTS ---

@app.post("/orders")
def create_order(order_payload: OrderCreate):
    """
    Creates a new customer order and returns order details and payment gateway instructions.
    """
    if not order_payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty. Cannot create order.")

    # Calculate totals
    subtotal = sum(item.price * item.quantity for item in order_payload.items)
    shipping_fee = 0  # Free Insured Artisan Delivery across India
    packaging_fee = 0  # Complimentary Wood Care & Velvet Casing
    total_amount = subtotal + shipping_fee + packaging_fee

    # Generate unique human-readable order ID: e.g. SKW-2026-8942
    random_digits = random.randint(1000, 9999)
    order_id = f"SKW-2026-{random_digits}"

    order_doc = {
        "id": order_id,
        "items": [item.dict() for item in order_payload.items],
        "shipping": order_payload.shipping.dict(),
        "paymentMethod": order_payload.paymentMethod,
        "subtotal": subtotal,
        "shippingFee": shipping_fee,
        "packagingFee": packaging_fee,
        "totalAmount": total_amount,
        "currency": "INR",
        "status": "PENDING_PAYMENT",
        "paymentStatus": "UNPAID",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "notes": order_payload.notes,
        "timeline": [
            {
                "step": "ORDER_PLACED",
                "label": "Order Placed",
                "time": time.strftime("%b %d, %Y - %I:%M %p", time.localtime()),
                "completed": True
            },
            {
                "step": "POLISHING_INSPECTION",
                "label": "Workshop Quality & Grain Inspection",
                "time": "Scheduled",
                "completed": False
            },
            {
                "step": "PACKAGING",
                "label": "Luxury Protective Wood Packaging",
                "time": "Pending",
                "completed": False
            },
            {
                "step": "DISPATCH",
                "label": "Dispatched via Insured Express Courier",
                "time": "Pending",
                "completed": False
            },
            {
                "step": "DELIVERED",
                "label": "Delivered to Doorstep",
                "time": "Pending",
                "completed": False
            }
        ]
    }

    saved_order = db_manager.create_order(order_doc)

    return {
        "status": "success",
        "message": "Order initiated successfully. Proceed to payment.",
        "order": saved_order
    }

@app.post("/orders/{order_id}/pay")
def process_order_payment(order_id: str, payment_payload: PaymentProcess):
    """
    Processes or verifies customer payment for an order.
    Supports Card, UPI, Net Banking, Cash on Delivery, and Sandbox Instant Demo Pay.
    """
    order = db_manager.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Generate transaction reference
    tx_ref = payment_payload.transactionRef or f"TXN-SKW-{int(time.time())}-{random.randint(100, 999)}"

    # If Cash on Delivery
    if payment_payload.paymentMethod == "cod":
        payment_status = "PENDING_COD"
    else:
        payment_status = "PAID"

    payment_details = {
        "method": payment_payload.paymentMethod,
        "transactionId": tx_ref,
        "paidAmount": order["totalAmount"],
        "currency": "INR",
        "processedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    if payment_payload.upiId:
        payment_details["upiId"] = payment_payload.upiId
    if payment_payload.cardNumber:
        # Mask card number for security
        last4 = payment_payload.cardNumber[-4:] if len(payment_payload.cardNumber) >= 4 else "0000"
        payment_details["cardMasked"] = f"•••• •••• •••• {last4}"
    if payment_payload.bankName:
        payment_details["bankName"] = payment_payload.bankName

    updated_order = db_manager.update_order_payment(
        order_id=order_id,
        payment_status=payment_status,
        transaction_id=tx_ref,
        payment_details=payment_details
    )

    # Advance the timeline
    if updated_order:
        updated_order["timeline"][0]["completed"] = True
        updated_order["timeline"][1]["completed"] = True
        updated_order["timeline"][1]["time"] = "In Progress"

    return {
        "status": "success",
        "message": "Payment verified and order confirmed.",
        "order": updated_order
    }

@app.get("/orders/{order_id}")
def get_order_details(order_id: str):
    """Retrieves customer order details and live shipping status."""
    order = db_manager.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found. Please verify your order ID.")
    return order

# --- CLOUDFLARE R2 FILE UPLOAD ENDPOINT ---

@app.post("/api/upload")
async def upload_product_image(file: UploadFile = File(...)):
    """
    Uploads a product image to Cloudflare R2 bucket with automatic JPEG compression.
    Accepts JPG, JPEG, PNG, WEBP images and standardizes to compressed JPEG.
    """
    filename_lower = (file.filename or "").lower()
    allowed_extensions = (".jpg", ".jpeg", ".png", ".webp")
    if not any(filename_lower.endswith(ext) for ext in allowed_extensions) and not (file.content_type and "image" in file.content_type):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload JPEG or JPG images."
        )

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Clean filename, ensure .jpg extension
    clean_base = (file.filename or "image").replace(" ", "_").rsplit(".", 1)[0]
    clean_filename = f"{int(time.time())}_{clean_base}.jpg"
    content_type = "image/jpeg"

    url, provider, stats = storage_client.upload_file(contents, clean_filename, content_type, auto_compress=True)

    return {
        "status": "success",
        "url": url,
        "filename": clean_filename,
        "provider": provider,
        "stats": stats,
        "message": f"Image compressed ({stats.get('reductionPercent', 0)}% reduction) and uploaded via {provider}"
    }

# --- CLOUDFLARE R2 IMAGE PROXY & STATIC SERVING ---
@app.get("/api/images/{filename}")
def serve_image(filename: str):
    """
    Serves product images from Cloudflare R2 or local cache with proper media type and headers.
    """
    # 1. Check local backend uploads
    backend_uploads = Path(__file__).resolve().parent / "uploads" / filename
    if backend_uploads.exists():
        return FileResponse(backend_uploads)

    # 2. Check frontend assets cache
    frontend_path = Path(__file__).resolve().parent.parent / "frontend" / "src" / "assets" / "products" / filename
    if frontend_path.exists():
        return FileResponse(frontend_path)

    # 3. Check legacy assets path if present
    legacy_path = Path(__file__).resolve().parent.parent / "src" / "assets" / "products" / filename
    if legacy_path.exists():
        return FileResponse(legacy_path)

    # 2. Check Cloudflare R2
    if storage_client.s3_client and settings.is_r2_ready:
        try:
            obj = storage_client.s3_client.get_object(Bucket=settings.R2_BUCKET_NAME, Key=filename)
            content_type = obj.get("ContentType", "image/jpeg")
            body_bytes = obj["Body"].read()
            return Response(content=body_bytes, media_type=content_type, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Image not found")

# --- ADMIN PANEL ENDPOINTS ---

@app.post("/api/admin/login")
def admin_login(payload: AdminLogin):
    """
    Authenticates admin user against configured environment credentials.
    """
    if payload.username == settings.ADMIN_USERNAME and payload.password == settings.ADMIN_PASSWORD:
        return {
            "status": "success",
            "token": f"token-skw-admin-{int(time.time())}",
            "username": settings.ADMIN_USERNAME,
            "message": "Admin authenticated successfully"
        }
    raise HTTPException(status_code=401, detail="Invalid admin username or password")

@app.post("/api/products")
def create_product(product_payload: ProductUpsert):
    """
    Admin: Creates a new handcrafted turned wood product and saves to MongoDB Atlas.
    """
    data = product_payload.dict()
    saved = db_manager.save_product(data)
    return {"status": "success", "message": "Product created successfully", "product": saved}

@app.put("/api/products/{product_id}")
def update_product(product_id: str, product_payload: ProductUpsert):
    """
    Admin: Updates an existing product in MongoDB Atlas.
    """
    data = product_payload.dict()
    data["id"] = product_id
    saved = db_manager.save_product(data)
    return {"status": "success", "message": "Product updated successfully", "product": saved}

@app.delete("/api/products/{product_id}")
def delete_product(product_id: str):
    """
    Admin: Deletes a product from MongoDB Atlas.
    """
    success = db_manager.delete_product(product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found or already deleted")
    return {"status": "success", "message": f"Product {product_id} deleted successfully"}

@app.get("/api/admin/orders")
def get_admin_orders():
    """
    Admin: Retrieves all customer orders from MongoDB Atlas.
    """
    orders = db_manager.get_all_orders()
    return {"status": "success", "count": len(orders), "orders": orders}

@app.patch("/api/admin/orders/{order_id}/status")
def update_order_status_endpoint(order_id: str, payload: OrderStatusUpdate):
    """
    Admin: Updates order fulfillment status.
    """
    updated = db_manager.update_order_status(order_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"status": "success", "message": f"Order status updated to {payload.status}", "order": updated}

