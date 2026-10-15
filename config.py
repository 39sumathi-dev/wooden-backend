import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the backend directory
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    # MongoDB settings
    MONGODB_URI: str = os.getenv(
        "MONGODB_URI",
        "mongodb+srv://39sumathi_db_user:<db_password>@cluster0.tp0iccb.mongodb.net/?appName=Cluster0"
    )
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "sk_woodturnery")

    # Cloudflare R2 settings
    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "woodturnery-products")
    R2_PUBLIC_URL: str = os.getenv("R2_PUBLIC_URL", "https://pub-woodturnery.r2.dev")

    # Payment settings
    PAYMENT_GATEWAY_MODE: str = os.getenv("PAYMENT_GATEWAY_MODE", "sandbox")
    PAYMENT_CURRENCY: str = os.getenv("PAYMENT_CURRENCY", "INR")
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")

    # Admin panel credentials
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "woodturnery2026")

    @property
    def is_mongodb_ready(self) -> bool:
        """Returns True if the URI does not contain unreplaced placeholder tags."""
        return "<db_password>" not in self.MONGODB_URI and "placeholder" not in self.MONGODB_URI

    @property
    def is_r2_ready(self) -> bool:
        """Returns True if Cloudflare R2 credentials are configured."""
        return bool(
            self.R2_ACCOUNT_ID
            and self.R2_ACCESS_KEY_ID
            and self.R2_SECRET_ACCESS_KEY
            and "your_" not in self.R2_ACCOUNT_ID
        )

settings = Settings()
