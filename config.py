"""
Configuration module for Canva Distribution System.
Loads and validates settings from environment variables or .env file.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load .env if present
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    # Telegram Bot Settings
    BOT_TOKEN: str = Field(default="", description="Telegram Bot Token from @BotFather")
    ADMIN_ID: int = Field(default=0, description="Telegram User ID of the primary admin")
    REQUIRED_CHANNEL: str = Field(default="@aitadz", description="Mandatory Telegram channel username or ID")
    CHANNEL_INVITE_LINK: str = Field(default="https://t.me/aitadz", description="Direct invite link to mandatory channel")
    
    # BaridiMob Payment Configuration
    TARGET_RIP: str = Field(default="00799999000749846290", description="Destination 20-digit BaridiMob RIP")
    TARGET_CCP: str = Field(default="0007498462", description="Destination CCP account number (without/with cle)")
    ACCOUNT_HOLDER: str = Field(default="ADMIN CANVA ALGERIA", description="Account holder name shown in BaridiMob")
    PAYMENT_AMOUNT: float = Field(default=500.0, description="Primary expected payment amount in DZD")
    ACCEPTED_AMOUNTS: str = Field(default="500.0,700.0", description="Comma-separated allowed payment amounts in DZD")
    DATE_GRACE_DAYS: int = Field(default=1, description="Max allowed age in days for receipt date (1 = today & yesterday)")
    
    # Seat & Referral Policy
    MAX_SEATS: int = Field(default=500, description="Maximum total Canva seats available")
    PAID_REFERRALS_FOR_REWARD: int = Field(default=5, description="Number of paid referrals required to earn a reward")
    REWARD_DESCRIPTION: str = Field(default="Exclusive Freebie Gift / Digital Pack", description="Description of the 5-paid-invites reward")
    
    # Web Dashboard & Server
    HOST: str = Field(default="0.0.0.0", description="Web dashboard host")
    PORT: int = Field(default=8000, description="Web dashboard port")
    ADMIN_USERNAME: str = Field(default="admin", description="Admin username for Web Dashboard")
    ADMIN_PASSWORD: str = Field(default="canvapro2026", description="Admin password for Web Dashboard")
    
    # Database & System
    DATABASE_PATH: str = Field(default="canva_system.db", description="Path to SQLite database file")
    TESSERACT_CMD: str = Field(default="tesseract", description="Path or command for Tesseract OCR")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()
