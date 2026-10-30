"""
Database layer for Canva Distribution System.
Handles SQLite operations, connection lifecycle, and schema initialization.
"""

import sqlite3
import csv
import io
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from config import settings


def get_utc_now() -> str:
    """Returns current UTC timestamp formatted as string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates a new SQLite connection with Row factory and WAL mode."""
    path = db_path or settings.DATABASE_PATH
    conn = sqlite3.connect(path, timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes tables and indexes automatically."""
    conn = get_connection(db_path)
    with conn:
        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                referred_by INTEGER,
                referral_verified INTEGER DEFAULT 0,
                referrals_count INTEGER DEFAULT 0,
                paid_referrals_count INTEGER DEFAULT 0,
                rewards_claimed INTEGER DEFAULT 0,
                language TEXT DEFAULT 'fr',
                status TEXT DEFAULT 'NEW',
                unlock_method TEXT,
                email TEXT,
                tx_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Used receipts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS used_receipts (
                tx_id TEXT PRIMARY KEY,
                file_hash TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            );
        """)

        # Rewards table (for users who achieve 5 paid invites)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reward_type TEXT DEFAULT 'FREEBIE',
                status TEXT DEFAULT 'PENDING',
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            );
        """)

        # System configuration key-value store
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migration: Add columns to users if table already existed without them
        try:
            conn.execute("ALTER TABLE users ADD COLUMN paid_referrals_count INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN rewards_claimed INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'fr';")
        except sqlite3.OperationalError:
            pass

        # Indexes for fast querying
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_hash ON used_receipts(file_hash);")
    conn.close()


def get_user(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a user by user_id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_or_get_user(
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    referred_by: Optional[int] = None,
    db_path: Optional[str] = None
) -> Tuple[Dict[str, Any], bool]:
    """
    Retrieves existing user or creates a new one.
    Returns (user_dict, is_new_user).
    """
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                # Update username or first_name if changed
                conn.execute(
                    "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
                    (username, first_name, user_id)
                )
                cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                return dict(cursor.fetchone()), False
            
            # Prevent self-referral
            valid_referrer = None
            if referred_by and referred_by != user_id:
                # Ensure referrer exists
                ref_check = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (referred_by,)).fetchone()
                if ref_check:
                    valid_referrer = referred_by

            now = get_utc_now()
            conn.execute("""
                INSERT INTO users (
                    user_id, username, first_name, referred_by, referral_verified,
                    referrals_count, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 0, 0, 'NEW', ?, ?)
            """, (user_id, username, first_name, valid_referrer, now, now))
            
            cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return dict(cursor.fetchone()), True
    finally:
        conn.close()


def update_user_status(
    user_id: int,
    status: str,
    unlock_method: Optional[str] = None,
    tx_id: Optional[str] = None,
    db_path: Optional[str] = None
) -> bool:
    """Updates the status and optional unlock details of a user."""
    conn = get_connection(db_path)
    try:
        now = get_utc_now()
        with conn:
            if unlock_method and tx_id:
                conn.execute("""
                    UPDATE users 
                    SET status = ?, unlock_method = ?, tx_id = ?, updated_at = ?
                    WHERE user_id = ?
                """, (status, unlock_method, tx_id, now, user_id))
            elif unlock_method:
                conn.execute("""
                    UPDATE users 
                    SET status = ?, unlock_method = ?, updated_at = ?
                    WHERE user_id = ?
                """, (status, unlock_method, now, user_id))
            else:
                conn.execute("""
                    UPDATE users 
                    SET status = ?, updated_at = ?
                    WHERE user_id = ?
                """, (status, now, user_id))
            return True
    finally:
        conn.close()


def set_user_language(user_id: int, language: str, db_path: Optional[str] = None) -> bool:
    """Updates user's preferred language (ar, fr, en)."""
    conn = get_connection(db_path)
    try:
        now = get_utc_now()
        with conn:
            conn.execute("UPDATE users SET language = ?, updated_at = ? WHERE user_id = ?", (language, now, user_id))
            return True
    finally:
        conn.close()


def get_user_language(user_id: int, db_path: Optional[str] = None) -> str:
    """Retrieves user's preferred language with 'fr' as default."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row["language"]:
            return row["language"]
        return "fr"
    finally:
        conn.close()


def set_user_email(user_id: int, email: str, db_path: Optional[str] = None) -> bool:
    """Saves verified email and moves user to PENDING_INVITE."""
    conn = get_connection(db_path)
    try:
        now = get_utc_now()
        with conn:
            conn.execute("""
                UPDATE users 
                SET email = ?, status = 'PENDING_INVITE', updated_at = ?
                WHERE user_id = ?
            """, (email.strip().lower(), now, user_id))
            return True
    finally:
        conn.close()


def set_user_language(user_id: int, language: str, db_path: Optional[str] = None) -> bool:
    """Updates user's preferred language (ar, fr, en)."""
    conn = get_connection(db_path)
    try:
        now = get_utc_now()
        with conn:
            conn.execute("UPDATE users SET language = ?, updated_at = ? WHERE user_id = ?", (language, now, user_id))
            return True
    finally:
        conn.close()


def get_user_language(user_id: int, db_path: Optional[str] = None) -> str:
    """Retrieves user's preferred language with 'fr' as default."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row["language"]:
            return row["language"]
        return "fr"
    finally:
        conn.close()


def is_email_already_registered(email: str, exclude_user_id: Optional[int] = None, db_path: Optional[str] = None) -> bool:
    """Checks if an email is already assigned to another user in PENDING_INVITE or INVITED."""
    conn = get_connection(db_path)
    try:
        clean_email = email.strip().lower()
        if exclude_user_id:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM users WHERE email = ? AND user_id != ? AND status IN ('PENDING_INVITE', 'INVITED')",
                (clean_email, exclude_user_id)
            )
        else:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM users WHERE email = ? AND status IN ('PENDING_INVITE', 'INVITED')",
                (clean_email,)
            )
        return cursor.fetchone()[0] > 0
    finally:
        conn.close()


def verify_referral_join(invited_user_id: int, db_path: Optional[str] = None) -> Optional[Tuple[int, int]]:
    """
    Marks the invited user's referral as verified if not already verified.
    Increments the referrer's referrals_count.
    Returns (referrer_id, new_referrals_count) if successfully verified, else None.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                "SELECT referred_by, referral_verified FROM users WHERE user_id = ?",
                (invited_user_id,)
            )
            row = cursor.fetchone()
            if not row or not row["referred_by"] or row["referral_verified"] == 1:
                return None
            
            referrer_id = row["referred_by"]
            
            # Mark this user's referral as verified
            now = get_utc_now()
            conn.execute(
                "UPDATE users SET referral_verified = 1, updated_at = ? WHERE user_id = ?",
                (now, invited_user_id)
            )
            
            # Increment referrer's count
            conn.execute("""
                UPDATE users 
                SET referrals_count = referrals_count + 1, updated_at = ?
                WHERE user_id = ?
            """, (now, referrer_id))
            
            # Fetch new count
            cur = conn.execute("SELECT referrals_count FROM users WHERE user_id = ?", (referrer_id,))
            referrer_row = cur.fetchone()
            new_count = referrer_row["referrals_count"] if referrer_row else 0
            return (referrer_id, new_count)
    finally:
        conn.close()


def credit_paid_referral(payer_user_id: int, db_path: Optional[str] = None) -> Optional[Tuple[int, int, bool]]:
    """
    Called when a user successfully completes payment.
    Increments the referrer's paid_referrals_count.
    If the referrer hits 5 paid referrals, registers a pending reward.
    Returns (referrer_id, new_paid_count, reward_unlocked_bool) or None.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.execute("SELECT referred_by FROM users WHERE user_id = ?", (payer_user_id,))
            row = cur.fetchone()
            if not row or not row["referred_by"]:
                return None
            
            referrer_id = row["referred_by"]
            
            # Fetch referrer details
            ref_cur = conn.execute(
                "SELECT user_id, paid_referrals_count, rewards_claimed, status FROM users WHERE user_id = ?",
                (referrer_id,)
            )
            ref_row = ref_cur.fetchone()
            if not ref_row:
                return None

            now = get_utc_now()
            # Increment paid_referrals_count
            conn.execute("""
                UPDATE users 
                SET paid_referrals_count = COALESCE(paid_referrals_count, 0) + 1, updated_at = ?
                WHERE user_id = ?
            """, (now, referrer_id))
            
            # Get updated count
            new_count = (ref_row["paid_referrals_count"] or 0) + 1
            claimed = ref_row["rewards_claimed"] or 0
            
            target = getattr(settings, "PAID_REFERRALS_FOR_REWARD", 5)
            reward_unlocked = False
            
            # Check if unlocked a new reward (every 5 paid referrals)
            if new_count >= target * (claimed + 1):
                conn.execute("""
                    INSERT INTO rewards (user_id, reward_type, status, details, created_at)
                    VALUES (?, 'FREEBIE', 'PENDING', ?, ?)
                """, (referrer_id, f"Reward for reaching {target} paid referrals", now))
                reward_unlocked = True

            return (referrer_id, new_count, reward_unlocked)
    finally:
        conn.close()


def get_pending_rewards(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves rewards waiting to be delivered to users."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT r.id, r.user_id, r.reward_type, r.status, r.details, r.created_at,
                   u.username, u.first_name, u.email, u.paid_referrals_count
            FROM rewards r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.status = 'PENDING'
            ORDER BY r.created_at ASC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def mark_reward_delivered(reward_id: int, note: Optional[str] = None, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Marks a reward as DELIVERED and increments user's rewards_claimed."""
    conn = get_connection(db_path)
    try:
        now = get_utc_now()
        with conn:
            cur = conn.execute("SELECT * FROM rewards WHERE id = ?", (reward_id,))
            row = cur.fetchone()
            if not row:
                return None
            user_id = row["user_id"]
            
            conn.execute("""
                UPDATE rewards 
                SET status = 'DELIVERED', details = COALESCE(?, details), delivered_at = ?
                WHERE id = ?
            """, (note, now, reward_id))
            
            conn.execute("""
                UPDATE users 
                SET rewards_claimed = COALESCE(rewards_claimed, 0) + 1, updated_at = ?
                WHERE user_id = ?
            """, (now, user_id))
            
            updated = conn.execute("SELECT * FROM rewards WHERE id = ?", (reward_id,)).fetchone()
            return dict(updated)
    finally:
        conn.close()


def check_receipt_hash_exists(file_hash: str, db_path: Optional[str] = None) -> bool:
    """Checks if a receipt SHA-256 hash already exists in used_receipts."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM used_receipts WHERE file_hash = ?", (file_hash,))
        return cursor.fetchone()[0] > 0
    finally:
        conn.close()


def check_tx_id_exists(tx_id: str, db_path: Optional[str] = None) -> bool:
    """Checks if a transaction ID has already been recorded."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM used_receipts WHERE tx_id = ?", (tx_id,))
        return cursor.fetchone()[0] > 0
    finally:
        conn.close()


def record_used_receipt(
    tx_id: str,
    file_hash: str,
    user_id: int,
    amount: float,
    db_path: Optional[str] = None
) -> bool:
    """Records a verified receipt in used_receipts table."""
    conn = get_connection(db_path)
    try:
        now = get_utc_now()
        with conn:
            conn.execute("""
                INSERT INTO used_receipts (tx_id, file_hash, user_id, amount, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (tx_id, file_hash, user_id, amount, now))
            return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_system_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Calculates comprehensive system and seat metrics."""
    conn = get_connection(db_path)
    try:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        paid_unlocks = conn.execute("SELECT COUNT(*) FROM users WHERE unlock_method = 'PAID'").fetchone()[0]
        referral_unlocks = conn.execute("SELECT COUNT(*) FROM users WHERE unlock_method = 'REFERRAL'").fetchone()[0]
        
        pending_invites = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'PENDING_INVITE'").fetchone()[0]
        invited_users = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'INVITED'").fetchone()[0]
        
        # Total seats claimed is all users who submitted an email and are either pending or already invited
        claimed_seats = pending_invites + invited_users
        remaining_seats = max(0, settings.MAX_SEATS - claimed_seats)
        
        total_revenue_dzd = paid_unlocks * settings.PAYMENT_AMOUNT

        # Rewards metrics (for 5 paid invites)
        pending_rewards = conn.execute("SELECT COUNT(*) FROM rewards WHERE status = 'PENDING'").fetchone()[0]
        delivered_rewards = conn.execute("SELECT COUNT(*) FROM rewards WHERE status = 'DELIVERED'").fetchone()[0]
        total_paid_referrals = conn.execute("SELECT COALESCE(SUM(paid_referrals_count), 0) FROM users").fetchone()[0]
        
        return {
            "total_users": total_users,
            "paid_unlocks": paid_unlocks,
            "referral_unlocks": referral_unlocks,
            "pending_invites": pending_invites,
            "invited_users": invited_users,
            "claimed_seats": claimed_seats,
            "remaining_seats": remaining_seats,
            "max_seats": settings.MAX_SEATS,
            "total_revenue_dzd": total_revenue_dzd,
            "pending_rewards": pending_rewards,
            "delivered_rewards": delivered_rewards,
            "total_paid_referrals": total_paid_referrals
        }
    finally:
        conn.close()


def get_pending_invite_users(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves users currently waiting for Canva invitation."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT user_id, username, first_name, email, unlock_method, tx_id, updated_at, created_at
            FROM users
            WHERE status = 'PENDING_INVITE' AND email IS NOT NULL
            ORDER BY updated_at ASC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_all_users(
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves paginated user list with optional search and status filter."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM users WHERE 1=1"
        params: List[Any] = []
        
        if status_filter and status_filter.upper() != "ALL":
            query += " AND status = ?"
            params.append(status_filter.upper())
            
        if search:
            search_pattern = f"%{search}%"
            query += " AND (username LIKE ? OR first_name LIKE ? OR email LIKE ? OR tx_id LIKE ? OR CAST(user_id AS TEXT) LIKE ?)"
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern, search_pattern])
            
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def mark_user_as_invited(identifier: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Marks a user as INVITED by email or user_id.
    Returns the updated user dict if found, else None.
    """
    conn = get_connection(db_path)
    try:
        now = get_utc_now()
        with conn:
            # Check by user_id if integer
            user_row = None
            if identifier.isdigit():
                user_row = conn.execute("SELECT * FROM users WHERE user_id = ?", (int(identifier),)).fetchone()
            
            if not user_row:
                user_row = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (identifier.strip().lower(),)).fetchone()
                
            if not user_row:
                return None
                
            uid = user_row["user_id"]
            conn.execute("UPDATE users SET status = 'INVITED', updated_at = ? WHERE user_id = ?", (now, uid))
            updated = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchone()
            return dict(updated)
    finally:
        conn.close()


def bulk_mark_all_pending_as_invited(db_path: Optional[str] = None) -> int:
    """Marks all currently PENDING_INVITE users as INVITED. Returns count of affected users."""
    conn = get_connection(db_path)
    try:
        now = get_utc_now()
        with conn:
            cursor = conn.execute("""
                UPDATE users 
                SET status = 'INVITED', updated_at = ?
                WHERE status = 'PENDING_INVITE' AND email IS NOT NULL
            """, (now,))
            return cursor.rowcount
    finally:
        conn.close()


def export_canva_csv(db_path: Optional[str] = None) -> str:
    """
    Generates a clean CSV formatted for Canva batch invites.
    Canva allows pasting or uploading lists of emails.
    Returns CSV content as string.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT email, username, first_name, unlock_method, tx_id, updated_at
            FROM users
            WHERE email IS NOT NULL AND status IN ('PENDING_INVITE', 'INVITED')
            ORDER BY updated_at ASC
        """)
        rows = cursor.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        # Standard Canva / System header
        writer.writerow(["Email", "Telegram Username", "First Name", "Unlock Method", "Tx ID", "Registered Date"])
        
        for r in rows:
            writer.writerow([
                r["email"],
                r["username"] or "",
                r["first_name"] or "",
                r["unlock_method"] or "",
                r["tx_id"] or "",
                r["updated_at"]
            ])
            
        return output.getvalue()
    finally:
        conn.close()


def admin_create_user(user_data: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new user directly from Admin Dashboard.
    Raises ValueError if user_id or unique email already exists.
    """
    user_id = user_data.get("user_id")
    if not user_id:
        raise ValueError("User ID is required")
    
    user_id = int(user_id)
    email = user_data.get("email")
    if email:
        email = email.strip().lower()
        if is_email_already_registered(email, db_path=db_path):
            raise ValueError(f"Email '{email}' is already registered to another user")
    else:
        email = None

    now = get_utc_now()
    conn = get_connection(db_path)
    try:
        with conn:
            existing = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if existing:
                raise ValueError(f"User with ID {user_id} already exists")
            
            conn.execute("""
                INSERT INTO users (
                    user_id, username, first_name, referred_by, referral_verified,
                    referrals_count, paid_referrals_count, rewards_claimed,
                    status, unlock_method, email, language, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                user_data.get("username"),
                user_data.get("first_name"),
                user_data.get("referred_by"),
                1 if user_data.get("referral_verified") else 0,
                int(user_data.get("referrals_count") or 0),
                int(user_data.get("paid_referrals_count") or 0),
                int(user_data.get("rewards_claimed") or 0),
                user_data.get("status") or "NEW",
                user_data.get("unlock_method") or "PAID",
                email,
                user_data.get("language") or "fr",
                now,
                now
            ))
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row)
    finally:
        conn.close()


def admin_update_user(user_id: int, updates: Dict[str, Any], db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Updates an existing user's attributes from Admin Dashboard.
    Raises ValueError on conflict (e.g. duplicate email).
    Returns updated user dict, or None if user not found.
    """
    conn = get_connection(db_path)
    try:
        now = get_utc_now()
        with conn:
            existing = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not existing:
                return None
            
            fields = []
            params = []
            
            # Check email uniqueness if email is in updates
            if "email" in updates:
                email = updates["email"]
                if email:
                    email = email.strip().lower()
                    if is_email_already_registered(email, exclude_user_id=user_id, db_path=db_path):
                        raise ValueError(f"Email '{email}' is already registered to another user")
                    fields.append("email = ?")
                    params.append(email)
                else:
                    fields.append("email = ?")
                    params.append(None)
                    
            allowed_fields = [
                "username", "first_name", "status", "unlock_method",
                "referrals_count", "paid_referrals_count", "rewards_claimed",
                "language", "tx_id"
            ]
            for f in allowed_fields:
                if f in updates:
                    fields.append(f"{f} = ?")
                    params.append(updates[f])
                    
            if not fields:
                return dict(existing)
                
            fields.append("updated_at = ?")
            params.append(now)
            
            params.append(user_id)
            sql = f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?"
            conn.execute(sql, params)
            
            updated = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(updated) if updated else None
    finally:
        conn.close()


def admin_delete_user(user_id: int, db_path: Optional[str] = None) -> bool:
    """
    Deletes a user and cascades related records (receipts, rewards).
    Returns True if deleted, False if user didn't exist.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            user = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not user:
                return False
            
            conn.execute("DELETE FROM rewards WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM used_receipts WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            return True
    finally:
        conn.close()


def get_all_receipts(limit: int = 100, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all verified receipts joined with user details."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("""
            SELECT r.tx_id, r.file_hash, r.user_id, r.amount, r.created_at,
                   u.username, u.first_name, u.email
            FROM used_receipts r
            LEFT JOIN users u ON r.user_id = u.user_id
            ORDER BY r.created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def delete_receipt(tx_id: str, db_path: Optional[str] = None) -> bool:
    """Deletes a receipt record from used_receipts by tx_id."""
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.execute("DELETE FROM used_receipts WHERE tx_id = ?", (tx_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def get_pending_emails(db_path: Optional[str] = None) -> List[str]:
    """Retrieves clean list of all emails ready in PENDING_INVITE queue."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("""
            SELECT email FROM users
            WHERE status = 'PENDING_INVITE' AND email IS NOT NULL AND email != ''
            ORDER BY updated_at ASC
        """)
        return [row["email"] for row in cur.fetchall()]
    finally:
        conn.close()


def bulk_mark_emails_as_invited(emails: List[str], db_path: Optional[str] = None) -> int:
    """Marks a list of emails as INVITED if they were in PENDING_INVITE."""
    if not emails:
        return 0
    cleaned = [e.strip().lower() for e in emails if e and e.strip()]
    if not cleaned:
        return 0
    now = get_utc_now()
    conn = get_connection(db_path)
    try:
        with conn:
            placeholders = ",".join("?" for _ in cleaned)
            cur = conn.execute(f"""
                UPDATE users
                SET status = 'INVITED', updated_at = ?
                WHERE status = 'PENDING_INVITE' AND LOWER(email) IN ({placeholders})
            """, [now] + cleaned)
            return cur.rowcount
    finally:
        conn.close()


def get_config_value(key: str, default: Optional[str] = None, db_path: Optional[str] = None) -> str:
    """Retrieves a configuration value from system_config."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else (default or "")
    finally:
        conn.close()


def set_config_value(key: str, value: str, db_path: Optional[str] = None) -> None:
    """Sets a configuration value in system_config."""
    now = get_utc_now()
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT INTO system_config (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (key, str(value), now))
    finally:
        conn.close()


def get_all_config(db_path: Optional[str] = None) -> Dict[str, str]:
    """Retrieves all configuration key-value pairs."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT key, value FROM system_config")
        return {row["key"]: row["value"] for row in cur.fetchall()}
    finally:
        conn.close()


def export_full_json(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Exports entire database as structured JSON dictionary."""
    conn = get_connection(db_path)
    try:
        users = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]
        receipts = [dict(r) for r in conn.execute("SELECT * FROM used_receipts ORDER BY created_at DESC").fetchall()]
        rewards = [dict(r) for r in conn.execute("SELECT * FROM rewards ORDER BY created_at DESC").fetchall()]
        configs = get_all_config(db_path)
        stats = get_system_stats(db_path)
        return {
            "exported_at": get_utc_now(),
            "stats": stats,
            "configs": configs,
            "users_count": len(users),
            "users": users,
            "receipts_count": len(receipts),
            "receipts": receipts,
            "rewards_count": len(rewards),
            "rewards": rewards
        }
    finally:
        conn.close()
