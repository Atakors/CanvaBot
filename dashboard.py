"""
FastAPI Web Dashboard and Administration API for Canva Distribution System.
Provides a modern dark-mode control center, CSV downloads, real-time metrics, and user management.
"""

import os
import re
import json
import secrets
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import settings
import database as db
from bot import broadcast_message

# Initialize FastAPI app
app = FastAPI(
    title="Canva Distribution System - Admin Portal",
    description="Automated 500-Seat Canva Access System for Algeria",
    version="1.0.0"
)

security = HTTPBasic()


class UserCreateRequest(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "NEW"
    unlock_method: Optional[str] = "PAID"
    paid_referrals_count: Optional[int] = 0
    referrals_count: Optional[int] = 0
    language: Optional[str] = "fr"


class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    unlock_method: Optional[str] = None
    paid_referrals_count: Optional[int] = None
    referrals_count: Optional[int] = None
    language: Optional[str] = None


class BroadcastRequest(BaseModel):
    text: str
    target_status: Optional[str] = "ALL"
    test_only: Optional[bool] = False


class BulkImportRequest(BaseModel):
    raw_text: str


class ConfigUpdateRequest(BaseModel):
    payment_amount: Optional[float] = None
    target_rip: Optional[str] = None
    target_ccp: Optional[str] = None
    required_channel: Optional[str] = None
    paid_referrals_for_reward: Optional[int] = None
    max_seats: Optional[int] = None
    date_grace_days: Optional[int] = None


def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Validates HTTP Basic Auth credentials for admin dashboard."""
    is_user_ok = secrets.compare_digest(credentials.username, settings.ADMIN_USERNAME)
    is_pass_ok = secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)
    
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/health")
def health_check():
    """Health check endpoint for Render, Railway, or VPS uptime monitors."""
    stats = db.get_system_stats()
    return {
        "status": "healthy",
        "seats_remaining": stats["remaining_seats"],
        "claimed_seats": stats["claimed_seats"],
        "max_seats": settings.MAX_SEATS
    }


@app.get("/api/stats")
def get_stats(username: str = Depends(authenticate_admin)):
    """Returns real-time system metrics as JSON."""
    return db.get_system_stats()


@app.get("/api/users")
def list_users(
    status: Optional[str] = Query(None, description="Filter by status (NEW, AWAITING_RECEIPT, AWAITING_EMAIL, PENDING_INVITE, INVITED)"),
    search: Optional[str] = Query(None, description="Search by username, email, user_id, tx_id"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    username: str = Depends(authenticate_admin)
):
    """Retrieves paginated user list."""
    users = db.get_all_users(status_filter=status, search=search, limit=limit, offset=offset)
    return {"users": users, "count": len(users)}


@app.post("/api/users", status_code=status.HTTP_201_CREATED)
def create_user_api(payload: UserCreateRequest, username: str = Depends(authenticate_admin)):
    """Creates a new user directly in the database."""
    try:
        created = db.admin_create_user(payload.model_dump())
        return {"status": "success", "user": created}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")


@app.get("/api/users/{user_id}")
def get_user_api(user_id: int, username: str = Depends(authenticate_admin)):
    """Fetches details of a single user."""
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "user": user}


@app.put("/api/users/{user_id}")
def update_user_api(user_id: int, payload: UserUpdateRequest, username: str = Depends(authenticate_admin)):
    """Updates an existing user's attributes."""
    try:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        updated = db.admin_update_user(user_id, updates)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "success", "user": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {e}")


@app.delete("/api/users/{user_id}")
def delete_user_api(user_id: int, username: str = Depends(authenticate_admin)):
    """Deletes a user and their associated data."""
    deleted = db.admin_delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "deleted_user_id": user_id}


@app.post("/api/mark-invited/{identifier}")
def mark_user_invited(identifier: str, username: str = Depends(authenticate_admin)):
    """Marks a single user as INVITED by email or user_id."""
    user = db.mark_user_as_invited(identifier)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "user": user}


@app.post("/api/bulk-mark-invited")
def bulk_mark_invited(username: str = Depends(authenticate_admin)):
    """Transitions all users currently in PENDING_INVITE to INVITED."""
    affected = db.bulk_mark_all_pending_as_invited()
    return {"status": "success", "count": affected}


@app.get("/api/rewards")
def get_pending_rewards_api(username: str = Depends(authenticate_admin)):
    """Returns list of pending freebie reward claims."""
    return {"rewards": db.get_pending_rewards()}


@app.post("/api/deliver-reward/{reward_id}")
def deliver_reward_api(reward_id: int, username: str = Depends(authenticate_admin)):
    """Marks a reward as delivered."""
    delivered = db.mark_reward_delivered(reward_id, note="Delivered via Admin Dashboard")
    if not delivered:
        raise HTTPException(status_code=404, detail="Reward not found or already delivered")
    return {"status": "success", "reward": delivered}


@app.get("/admin/export-csv")
def download_csv(username: str = Depends(authenticate_admin)):
    """Generates and downloads canva_invites_batch.csv for Canva admin bulk import."""
    csv_data = db.export_canva_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=canva_invites_batch.csv"}
    )


@app.post("/api/broadcast")
def broadcast_api(payload: BroadcastRequest, username: str = Depends(authenticate_admin)):
    """Broadcasts a Markdown message via Telegram Bot to users."""
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Broadcast message text cannot be empty")
        
    test_id = settings.ADMIN_ID if payload.test_only else None
    result = broadcast_message(
        text=payload.text.strip(),
        target_status=payload.target_status,
        test_user_id=test_id
    )
    return {"status": "success", "result": result}


@app.get("/api/receipts")
def list_receipts_api(limit: int = Query(100, ge=1, le=500), username: str = Depends(authenticate_admin)):
    """Returns verified used receipts."""
    receipts = db.get_all_receipts(limit=limit)
    return {"receipts": receipts, "count": len(receipts)}


@app.delete("/api/receipts/{tx_id}")
def delete_receipt_api(tx_id: str, username: str = Depends(authenticate_admin)):
    """Revokes a verified receipt by transaction ID."""
    deleted = db.delete_receipt(tx_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"status": "success", "deleted_tx_id": tx_id}


@app.get("/api/pending-emails")
def get_pending_emails_api(username: str = Depends(authenticate_admin)):
    """Returns list of pending invite emails for quick clipboard copy."""
    emails = db.get_pending_emails()
    return {
        "emails": emails,
        "count": len(emails),
        "comma_separated": ", ".join(emails),
        "newline_separated": "\n".join(emails)
    }


@app.post("/api/bulk-import-invited")
def bulk_import_invited_api(payload: BulkImportRequest, username: str = Depends(authenticate_admin)):
    """Parses emails from text and marks matching pending users as INVITED."""
    found_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", payload.raw_text)
    if not found_emails:
        raise HTTPException(status_code=400, detail="No valid email addresses found in submitted text.")
        
    unique_emails = list(dict.fromkeys([e.lower() for e in found_emails]))
    updated_count = db.bulk_mark_emails_as_invited(unique_emails)
    return {
        "status": "success",
        "updated_count": updated_count,
        "total_parsed": len(unique_emails)
    }


@app.get("/api/config")
def get_config_api(username: str = Depends(authenticate_admin)):
    """Returns current live system configuration."""
    cfg = db.get_all_config()
    full_cfg = {
        "payment_amount": cfg.get("payment_amount", str(settings.PAYMENT_AMOUNT)),
        "target_rip": cfg.get("target_rip", settings.TARGET_RIP),
        "target_ccp": cfg.get("target_ccp", settings.TARGET_CCP),
        "required_channel": cfg.get("required_channel", settings.REQUIRED_CHANNEL),
        "paid_referrals_for_reward": cfg.get("paid_referrals_for_reward", str(settings.PAID_REFERRALS_FOR_REWARD)),
        "max_seats": cfg.get("max_seats", str(settings.MAX_SEATS)),
        "date_grace_days": cfg.get("date_grace_days", str(settings.DATE_GRACE_DAYS))
    }
    return {"config": full_cfg}


@app.post("/api/config")
def update_config_api(payload: ConfigUpdateRequest, username: str = Depends(authenticate_admin)):
    """Updates dynamic system parameters."""
    if payload.payment_amount is not None:
        db.set_config_value("payment_amount", str(payload.payment_amount))
        settings.PAYMENT_AMOUNT = payload.payment_amount
    if payload.target_rip is not None and payload.target_rip.strip():
        db.set_config_value("target_rip", payload.target_rip.strip())
        settings.TARGET_RIP = payload.target_rip.strip()
    if payload.target_ccp is not None and payload.target_ccp.strip():
        db.set_config_value("target_ccp", payload.target_ccp.strip())
        settings.TARGET_CCP = payload.target_ccp.strip()
    if payload.required_channel is not None:
        db.set_config_value("required_channel", payload.required_channel.strip())
        settings.REQUIRED_CHANNEL = payload.required_channel.strip()
    if payload.paid_referrals_for_reward is not None:
        db.set_config_value("paid_referrals_for_reward", str(payload.paid_referrals_for_reward))
        settings.PAID_REFERRALS_FOR_REWARD = payload.paid_referrals_for_reward
    if payload.max_seats is not None:
        db.set_config_value("max_seats", str(payload.max_seats))
        settings.MAX_SEATS = payload.max_seats
    if payload.date_grace_days is not None:
        db.set_config_value("date_grace_days", str(payload.date_grace_days))
        settings.DATE_GRACE_DAYS = payload.date_grace_days
        
    return {"status": "success", "message": "System parameters updated successfully"}


@app.get("/admin/backup-db")
def download_database_backup(username: str = Depends(authenticate_admin)):
    """Downloads current SQLite database file directly."""
    db_file = settings.DATABASE_PATH
    if not os.path.exists(db_file):
        raise HTTPException(status_code=404, detail="Database file not found")
        
    with open(db_file, "rb") as f:
        data = f.read()
        
    timestamp = db.get_utc_now().replace(":", "-").replace(" ", "_")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=canva_system_backup_{timestamp}.db"}
    )


@app.get("/admin/export-json")
def download_json_export(username: str = Depends(authenticate_admin)):
    """Exports full database contents as structured JSON."""
    dump = db.export_full_json()
    timestamp = db.get_utc_now().replace(":", "-").replace(" ", "_")
    return Response(
        content=json.dumps(dump, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=canva_export_{timestamp}.json"}
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, username: str = Depends(authenticate_admin)):
    """Renders the responsive dark-mode administrative control center with multi-tool tabs."""
    stats = db.get_system_stats()
    pending_users = db.get_pending_invite_users(limit=100)
    pending_rewards = db.get_pending_rewards(limit=100)
    all_users = db.get_all_users(limit=300)
    receipts = db.get_all_receipts(limit=150)
    cfg = db.get_all_config()
    
    active_amount = float(cfg.get("payment_amount", settings.PAYMENT_AMOUNT))
    active_rip = cfg.get("target_rip", settings.TARGET_RIP)
    active_ccp = cfg.get("target_ccp", settings.TARGET_CCP)
    active_channel = cfg.get("required_channel", settings.REQUIRED_CHANNEL)
    active_reward_target = int(cfg.get("paid_referrals_for_reward", settings.PAID_REFERRALS_FOR_REWARD))
    active_max_seats = int(cfg.get("max_seats", settings.MAX_SEATS))
    active_grace_days = int(cfg.get("date_grace_days", settings.DATE_GRACE_DAYS))
    
    pct_claimed = min(100.0, (stats["claimed_seats"] / active_max_seats) * 100) if active_max_seats > 0 else 0

    # 1. Pre-render Pending Queue rows
    queue_rows = ""
    if not pending_users:
        queue_rows = """
            <tr>
                <td colspan="6" class="px-6 py-12 text-center text-gray-500">
                    <i class="fa-solid fa-circle-check text-3xl text-emerald-500/60 mb-2 block"></i>
                    <p class="font-medium text-gray-400">Queue is completely empty!</p>
                    <p class="text-xs text-gray-500 mt-1">All verified users have been invited to Canva.</p>
                </td>
            </tr>
        """
    else:
        for u in pending_users:
            uname = f"@{u['username']}" if u.get('username') else f"ID: {u['user_id']}"
            track_badge = (
                '<span class="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Paid</span>'
                if u.get('unlock_method') == 'PAID' else
                '<span class="px-2 py-0.5 rounded text-xs font-semibold bg-purple-500/20 text-purple-400 border border-purple-500/30">Referral</span>'
            )
            email_val = u.get('email') or ''
            search_str = f"{email_val} {uname} {u.get('tx_id') or ''}".lower()
            queue_rows += f"""
                <tr class="queue-row hover:bg-gray-800/40 transition" data-search="{search_str}">
                    <td class="px-5 py-3.5 font-medium text-white flex items-center gap-2">
                        <i class="fa-regular fa-envelope text-purple-400"></i>
                        <span class="font-mono text-sm">{email_val}</span>
                    </td>
                    <td class="px-5 py-3.5 text-xs text-gray-300">{uname}</td>
                    <td class="px-5 py-3.5">{track_badge}</td>
                    <td class="px-5 py-3.5 font-mono text-xs text-gray-400">{u.get('tx_id') or '—'}</td>
                    <td class="px-5 py-3.5 text-xs text-gray-400">{u.get('updated_at')}</td>
                    <td class="px-5 py-3.5 text-right">
                        <button onclick="markInvited('{email_val}')" class="bg-teal-600 hover:bg-teal-500 text-white text-xs px-3 py-1.5 rounded-lg font-medium transition inline-flex items-center gap-1 shadow">
                            <i class="fa-solid fa-check"></i>
                            <span>Mark Invited</span>
                        </button>
                    </td>
                </tr>
            """

    # 2. Pre-render All Users rows
    status_badges = {
        "NEW": '<span class="px-2 py-0.5 rounded text-xs bg-gray-700 text-gray-300">NEW</span>',
        "AWAITING_RECEIPT": '<span class="px-2 py-0.5 rounded text-xs bg-yellow-900/60 text-yellow-300 border border-yellow-700/50">AWAITING RECEIPT</span>',
        "AWAITING_EMAIL": '<span class="px-2 py-0.5 rounded text-xs bg-cyan-900/60 text-cyan-300 border border-cyan-700/50">AWAITING EMAIL</span>',
        "PENDING_INVITE": '<span class="px-2 py-0.5 rounded text-xs bg-amber-900/60 text-amber-300 border border-amber-600/50 font-bold">READY TO INVITE</span>',
        "INVITED": '<span class="px-2 py-0.5 rounded text-xs bg-emerald-900/60 text-emerald-300 border border-emerald-600/50 font-bold">ACTIVE INVITED</span>'
    }

    user_rows = ""
    for u in all_users:
        badge = status_badges.get(u['status'], u['status'])
        uname = f"@{u['username']}" if u['username'] else "—"
        first_n = u['first_name'] or ""
        email_val = u['email'] or "—"
        method_badge = f"{u['unlock_method'] or 'PAID'} • {u.get('paid_referrals_count', 0)} Paid"
        search_corpus = f"{u['user_id']} {u['username'] or ''} {u['first_name'] or ''} {u['email'] or ''} {u['status']}".lower().replace('"', '')
        
        quick_invite_btn = ""
        if u['status'] == 'PENDING_INVITE' and u.get('email'):
            quick_invite_btn = f"""
                <button onclick="markInvited('{u['email']}')" class="p-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 border border-amber-500/30 text-xs transition" title="Mark as Invited">
                    <i class="fa-solid fa-check"></i>
                </button>
            """
            
        user_rows += f"""
            <tr class="user-row hover:bg-gray-800/40 transition" data-status="{u['status']}" data-search="{search_corpus}">
                <td class="px-5 py-3 font-mono text-xs text-purple-300 font-semibold">{u['user_id']}</td>
                <td class="px-5 py-3 font-medium text-white">
                    <div>{uname}</div>
                    <div class="text-xs text-gray-400 font-normal">{first_n}</div>
                </td>
                <td class="px-5 py-3 text-white font-mono text-xs">{email_val}</td>
                <td class="px-5 py-3">{badge}</td>
                <td class="px-5 py-3 text-xs text-gray-300">
                    <span class="px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-gray-700/60 font-mono">
                        {method_badge}
                    </span>
                </td>
                <td class="px-5 py-3 text-xs text-gray-400">{u['created_at']}</td>
                <td class="px-5 py-3 text-right">
                    <div class="inline-flex items-center gap-1.5 justify-end">
                        {quick_invite_btn}
                        <button onclick="openEditUserModal({u['user_id']})" class="p-1.5 rounded-lg bg-gray-800 hover:bg-cyan-950/60 text-cyan-400 hover:text-cyan-300 border border-gray-700/60 text-xs transition" title="Edit User">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button onclick="deleteUser({u['user_id']}, '{u['username'] or u['user_id']}')" class="p-1.5 rounded-lg bg-gray-800 hover:bg-red-950/60 text-red-400 hover:text-red-300 border border-gray-700/60 text-xs transition" title="Delete User">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            </tr>
        """

    # 3. Pre-render Receipts rows
    receipt_rows = ""
    if not receipts:
        receipt_rows = """
            <tr>
                <td colspan="6" class="px-6 py-10 text-center text-gray-500">
                    <i class="fa-solid fa-receipt text-3xl text-gray-600 mb-2 block"></i>
                    No BaridiMob receipts on file yet.
                </td>
            </tr>
        """
    else:
        for r in receipts:
            uname = f"@{r['username']}" if r.get('username') else f"ID: {r['user_id']}"
            hash_full = r['file_hash']
            hash_short = f"{hash_full[:8]}...{hash_full[-8:]}" if len(hash_full) > 16 else hash_full
            search_str = f"{r['tx_id']} {r['user_id']} {uname} {hash_full}".lower()
            receipt_rows += f"""
                <tr class="receipt-row hover:bg-gray-800/40 transition" data-search="{search_str}">
                    <td class="px-5 py-3.5 font-mono text-xs font-bold text-teal-400">{r['tx_id']}</td>
                    <td class="px-5 py-3.5 text-xs text-white">
                        <div>{uname}</div>
                        <div class="text-xs text-gray-500 font-mono">ID: {r['user_id']}</div>
                    </td>
                    <td class="px-5 py-3.5">
                        <span class="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono">
                            {r['amount']:,.0f} DZD
                        </span>
                    </td>
                    <td class="px-5 py-3.5 font-mono text-xs text-gray-400">
                        <div class="inline-flex items-center gap-1.5">
                            <span>{hash_short}</span>
                            <button onclick="copyText('{hash_full}', 'SHA-256 Hash')" class="text-gray-500 hover:text-purple-400 transition" title="Copy full SHA-256 fingerprint">
                                <i class="fa-regular fa-copy"></i>
                            </button>
                        </div>
                    </td>
                    <td class="px-5 py-3.5 text-xs text-gray-400">{r['created_at']}</td>
                    <td class="px-5 py-3.5 text-right">
                        <button onclick="deleteReceipt('{r['tx_id']}')" class="p-1.5 rounded-lg bg-gray-800 hover:bg-red-950/60 text-red-400 hover:text-red-300 border border-gray-700/60 text-xs transition" title="Revoke Receipt">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </td>
                </tr>
            """

    # 4. Pre-render VIP Rewards rows
    reward_rows = ""
    if not pending_rewards:
        reward_rows = """
            <tr>
                <td colspan="5" class="px-6 py-10 text-center text-gray-500">
                    <i class="fa-solid fa-gift text-3xl text-gray-600 mb-2 block"></i>
                    No pending rewards! All earned freebies have been delivered.
                </td>
            </tr>
        """
    else:
        for rw in pending_rewards:
            uname = f"@{rw['username']}" if rw.get('username') else f"ID: {rw['user_id']}"
            reward_rows += f"""
                <tr class="hover:bg-gray-800/40 transition">
                    <td class="px-5 py-3.5 font-bold text-amber-400 font-mono">#{rw['id']}</td>
                    <td class="px-5 py-3.5 font-medium text-white">
                        <div>{uname}</div>
                        <div class="text-xs text-gray-400 font-normal">{rw.get('email') or 'No email'}</div>
                    </td>
                    <td class="px-5 py-3.5">
                        <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                            {rw.get('paid_referrals_count', active_reward_target)} Paid Friends
                        </span>
                    </td>
                    <td class="px-5 py-3.5 text-xs text-gray-400">{rw['created_at']}</td>
                    <td class="px-5 py-3.5 text-right">
                        <button onclick="deliverReward({rw['id']})" class="bg-purple-600 hover:bg-purple-500 text-white text-xs px-3 py-1.5 rounded-lg font-medium transition inline-flex items-center gap-1 shadow">
                            <i class="fa-solid fa-gift"></i>
                            <span>Deliver Freebie</span>
                        </button>
                    </td>
                </tr>
            """

    html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Canva Distribution System | Admin Portal</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        canva: {{
                            500: '#00c4cc',
                            600: '#7d2ae8',
                            gradient: 'linear-gradient(135deg, #00c4cc 0%, #7d2ae8 100%)'
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .canva-btn {{
            background: linear-gradient(135deg, #00c4cc 0%, #7d2ae8 100%);
        }}
        .canva-btn:hover {{
            opacity: 0.92;
        }}
        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: #090d16;
        }}
        ::-webkit-scrollbar-thumb {{
            background: #272f45;
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #3b4668;
        }}
    </style>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen antialiased flex flex-col font-sans">

    <!-- Top Navigation -->
    <header class="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl canva-btn flex items-center justify-center shadow-lg shadow-purple-500/20">
                    <i class="fa-solid fa-palette text-white text-lg"></i>
                </div>
                <div>
                    <h1 class="font-bold text-lg leading-tight tracking-wide bg-gradient-to-r from-teal-400 to-purple-400 bg-clip-text text-transparent">
                        Canva Algeria Hub
                    </h1>
                    <p class="text-xs text-gray-400">Zero-Human-Delay 500-Seat Engine</p>
                </div>
            </div>
            <div class="flex items-center space-x-2.5">
                <a href="/admin/export-csv" class="canva-btn text-white px-3 py-2 rounded-lg font-medium text-xs flex items-center gap-1.5 shadow transition" title="Export CSV for Canva Bulk Invite">
                    <i class="fa-solid fa-file-csv"></i>
                    <span>Canva CSV</span>
                </a>
                <a href="/admin/backup-db" class="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 px-3 py-2 rounded-lg font-medium text-xs flex items-center gap-1.5 transition" title="Download SQLite Database Backup">
                    <i class="fa-solid fa-database text-purple-400"></i>
                    <span class="hidden sm:inline">Backup DB</span>
                </a>
                <a href="/admin/export-json" class="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 px-3 py-2 rounded-lg font-medium text-xs flex items-center gap-1.5 transition" title="Export Complete JSON Data">
                    <i class="fa-solid fa-code text-cyan-400"></i>
                    <span class="hidden sm:inline">JSON Dump</span>
                </a>
                <button onclick="window.location.reload()" class="bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 p-2 rounded-lg text-xs transition" title="Refresh Dashboard">
                    <i class="fa-solid fa-rotate"></i>
                </button>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        
        <!-- Capacity Banner & Progress -->
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                <div>
                    <h2 class="text-xl font-bold text-white flex items-center gap-2">
                        <span>Batch Seat Capacity</span>
                        <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                            {active_max_seats} Max Seats
                        </span>
                    </h2>
                    <p class="text-sm text-gray-400 mt-1">Real-time allocation of verified users and pending invitations.</p>
                </div>
                <div class="text-right">
                    <span class="text-3xl font-extrabold text-teal-400">{stats['claimed_seats']}</span>
                    <span class="text-gray-500 text-lg">/ {active_max_seats}</span>
                    <p class="text-xs text-gray-400">{stats['remaining_seats']} seats available</p>
                </div>
            </div>

            <!-- Progress Bar -->
            <div class="w-full bg-gray-800 rounded-full h-3.5 overflow-hidden p-0.5">
                <div class="canva-btn h-full rounded-full transition-all duration-500" style="width: {pct_claimed:.1f}%"></div>
            </div>
            <div class="flex justify-between items-center text-xs text-gray-400 mt-2 font-mono">
                <span>0 Seats</span>
                <span>{pct_claimed:.1f}% Claimed</span>
                <span>{active_max_seats} Seats</span>
            </div>
        </div>

        <!-- Metric Stat Cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            
            <div class="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-between">
                <div>
                    <p class="text-xs font-medium text-gray-400 uppercase tracking-wider">Total Users</p>
                    <p class="text-2xl font-bold text-white mt-1">{stats['total_users']}</p>
                    <p class="text-xs text-gray-500 mt-1">Joined bot</p>
                </div>
                <div class="w-12 h-12 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center text-xl">
                    <i class="fa-solid fa-users"></i>
                </div>
            </div>

            <div class="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-between">
                <div>
                    <p class="text-xs font-medium text-gray-400 uppercase tracking-wider">Paid via BaridiMob</p>
                    <p class="text-2xl font-bold text-emerald-400 mt-1">{stats['paid_unlocks']}</p>
                    <p class="text-xs text-gray-500 mt-1">{stats['total_revenue_dzd']:,.0f} DZD verified</p>
                </div>
                <div class="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-xl">
                    <i class="fa-solid fa-receipt"></i>
                </div>
            </div>

            <div class="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-between">
                <div>
                    <p class="text-xs font-medium text-gray-400 uppercase tracking-wider">Paid Referrals</p>
                    <p class="text-2xl font-bold text-purple-400 mt-1">{stats.get('total_paid_referrals', 0)}</p>
                    <p class="text-xs text-gray-500 mt-1">Paying members invited</p>
                </div>
                <div class="w-12 h-12 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center text-xl">
                    <i class="fa-solid fa-share-nodes"></i>
                </div>
            </div>

            <div class="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-between">
                <div>
                    <p class="text-xs font-medium text-gray-400 uppercase tracking-wider">Pending Freebies</p>
                    <p class="text-2xl font-bold text-amber-400 mt-1">{stats.get('pending_rewards', 0)}</p>
                    <p class="text-xs text-gray-500 mt-1">{stats.get('delivered_rewards', 0)} delivered</p>
                </div>
                <div class="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center text-xl">
                    <i class="fa-solid fa-gift"></i>
                </div>
            </div>

        </div>

        <!-- Multi-Tool Tab Navigation -->
        <div class="border-b border-gray-800 flex items-center space-x-2 overflow-x-auto pb-1">
            <button onclick="switchTab('queue')" id="tabBtn-queue" class="tab-btn px-4 py-2.5 rounded-xl font-semibold text-xs border flex items-center gap-2 transition whitespace-nowrap">
                <i class="fa-solid fa-clock"></i>
                <span>Canva Queue</span>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">{len(pending_users)}</span>
            </button>
            <button onclick="switchTab('users')" id="tabBtn-users" class="tab-btn px-4 py-2.5 rounded-xl font-semibold text-xs border flex items-center gap-2 transition whitespace-nowrap">
                <i class="fa-solid fa-users"></i>
                <span>Users Directory (CRUD)</span>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">{len(all_users)}</span>
            </button>
            <button onclick="switchTab('broadcast')" id="tabBtn-broadcast" class="tab-btn px-4 py-2.5 rounded-xl font-semibold text-xs border flex items-center gap-2 transition whitespace-nowrap">
                <i class="fa-solid fa-bullhorn text-cyan-400"></i>
                <span>Broadcast Center</span>
            </button>
            <button onclick="switchTab('receipts')" id="tabBtn-receipts" class="tab-btn px-4 py-2.5 rounded-xl font-semibold text-xs border flex items-center gap-2 transition whitespace-nowrap">
                <i class="fa-solid fa-receipt text-emerald-400"></i>
                <span>Receipts Audit</span>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">{len(receipts)}</span>
            </button>
            <button onclick="switchTab('rewards')" id="tabBtn-rewards" class="tab-btn px-4 py-2.5 rounded-xl font-semibold text-xs border flex items-center gap-2 transition whitespace-nowrap">
                <i class="fa-solid fa-gift text-purple-400"></i>
                <span>VIP Rewards</span>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">{len(pending_rewards)}</span>
            </button>
            <button onclick="switchTab('settings')" id="tabBtn-settings" class="tab-btn px-4 py-2.5 rounded-xl font-semibold text-xs border flex items-center gap-2 transition whitespace-nowrap">
                <i class="fa-solid fa-sliders text-teal-400"></i>
                <span>Live Settings</span>
            </button>
        </div>

        <!-- ========================================== -->
        <!-- TAB PANE 1: CANVA QUEUE                    -->
        <!-- ========================================== -->
        <div id="tabPane-queue" class="tab-pane space-y-4">
            
            <div class="bg-gray-900 border border-gray-800 rounded-2xl shadow-xl overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <i class="fa-solid fa-clock text-amber-400"></i>
                            <span>Ready to Invite Queue (Verified Emails)</span>
                        </h3>
                        <p class="text-xs text-gray-400">Copy emails in 1-click, paste into Canva, then mark as invited.</p>
                    </div>

                    <div class="flex flex-wrap items-center gap-2">
                        <!-- 1-Click Clipboard Copies -->
                        <button onclick="copyPending('comma')" class="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs px-3 py-2 rounded-lg font-medium flex items-center gap-1.5 transition" title="Copy emails separated by comma (e.g. user1@gmail.com, user2@gmail.com)">
                            <i class="fa-regular fa-copy text-teal-400"></i>
                            <span>Copy (,)</span>
                        </button>
                        <button onclick="copyPending('newline')" class="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs px-3 py-2 rounded-lg font-medium flex items-center gap-1.5 transition" title="Copy emails one per line">
                            <i class="fa-regular fa-copy text-purple-400"></i>
                            <span>Copy (↵)</span>
                        </button>

                        <!-- Quick Paste & Mark Modal Trigger -->
                        <button onclick="openBulkPasteModal()" class="bg-cyan-600 hover:bg-cyan-500 text-white text-xs px-3.5 py-2 rounded-lg font-semibold flex items-center gap-1.5 shadow transition">
                            <i class="fa-solid fa-paste"></i>
                            <span>Quick Paste & Mark</span>
                        </button>

                        <!-- Bulk Mark All Pending Button -->
                        <button onclick="bulkMarkInvited()" class="bg-teal-600 hover:bg-teal-500 text-white text-xs px-3.5 py-2 rounded-lg font-semibold flex items-center gap-1.5 shadow transition">
                            <i class="fa-solid fa-check-double"></i>
                            <span>Mark All Invited</span>
                        </button>
                    </div>
                </div>

                <!-- Sub-bar with Live Filter -->
                <div class="px-6 py-3 bg-gray-950/50 border-b border-gray-800 flex items-center justify-between">
                    <div class="relative w-full max-w-xs">
                        <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-xs text-gray-500"></i>
                        <input type="text" id="queueSearch" placeholder="Filter queue by email, username, tx..." oninput="filterQueueTable()" 
                            class="w-full bg-gray-950 border border-gray-800 text-xs rounded-lg pl-8 pr-3 py-1.5 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-purple-500 transition">
                    </div>
                    <span class="text-xs text-gray-400 font-mono" id="queueCountBadge">{len(pending_users)} pending</span>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-gray-300">
                        <thead class="bg-gray-950 text-gray-400 text-xs uppercase font-medium border-b border-gray-800">
                            <tr>
                                <th class="px-5 py-3">Canva Email</th>
                                <th class="px-5 py-3">Telegram User</th>
                                <th class="px-5 py-3">Track</th>
                                <th class="px-5 py-3">Tx ID</th>
                                <th class="px-5 py-3">Submitted At</th>
                                <th class="px-5 py-3 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800" id="queueTbody">
                            {queue_rows}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>

        <!-- ========================================== -->
        <!-- TAB PANE 2: USERS DIRECTORY (CRUD)         -->
        <!-- ========================================== -->
        <div id="tabPane-users" class="tab-pane space-y-4 hidden">
            
            <div class="bg-gray-900 border border-gray-800 rounded-2xl shadow-xl overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <span>All Registered Users</span>
                            <span class="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono" id="userCountBadge">{len(all_users)}</span>
                        </h3>
                        <p class="text-xs text-gray-400">Complete audit log and live user management (CRUD).</p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2.5">
                        <div class="relative">
                            <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-xs text-gray-500"></i>
                            <input type="text" id="userSearch" placeholder="Search ID, username, email..." oninput="filterUsersTable()" 
                                class="bg-gray-950 border border-gray-800 text-xs rounded-lg pl-8 pr-3 py-2 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-purple-500 w-44 sm:w-56 transition">
                        </div>
                        <select id="statusFilter" onchange="filterUsersTable()"
                            class="bg-gray-950 border border-gray-800 text-xs rounded-lg px-3 py-2 text-gray-300 focus:outline-none focus:border-purple-500 transition">
                            <option value="">All Statuses</option>
                            <option value="NEW">NEW</option>
                            <option value="AWAITING_RECEIPT">AWAITING RECEIPT</option>
                            <option value="AWAITING_EMAIL">AWAITING EMAIL</option>
                            <option value="PENDING_INVITE">READY TO INVITE</option>
                            <option value="INVITED">INVITED</option>
                        </select>
                        <button onclick="openAddUserModal()" class="bg-gradient-to-r from-teal-500 to-purple-600 hover:from-teal-400 hover:to-purple-500 text-white text-xs px-3.5 py-2 rounded-lg font-semibold flex items-center gap-1.5 shadow-md shadow-purple-500/20 transition">
                            <i class="fa-solid fa-user-plus"></i>
                            <span>Add User</span>
                        </button>
                    </div>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-gray-300" id="usersTable">
                        <thead class="bg-gray-950 text-gray-400 text-xs uppercase font-medium border-b border-gray-800">
                            <tr>
                                <th class="px-5 py-3">User ID</th>
                                <th class="px-5 py-3">Username / Name</th>
                                <th class="px-5 py-3">Canva Email</th>
                                <th class="px-5 py-3">Status</th>
                                <th class="px-5 py-3">Method & Invites</th>
                                <th class="px-5 py-3">Registered</th>
                                <th class="px-5 py-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800" id="usersTbody">
                            {user_rows}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>

        <!-- ========================================== -->
        <!-- TAB PANE 3: BROADCAST CENTER               -->
        <!-- ========================================== -->
        <div id="tabPane-broadcast" class="tab-pane space-y-6 hidden">
            
            <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
                <div>
                    <h3 class="font-bold text-lg text-white flex items-center gap-2">
                        <i class="fa-solid fa-bullhorn text-cyan-400"></i>
                        <span>Telegram Broadcast Center</span>
                    </h3>
                    <p class="text-xs text-gray-400 mt-1">Send announcements, updates, or instructions directly to Telegram bot users.</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="md:col-span-2 space-y-4">
                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">Target Audience</label>
                            <select id="broadcastTarget" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500 transition">
                                <option value="ALL">All Users (Total: {stats['total_users']})</option>
                                <option value="PENDING_INVITE">Ready to Invite Queue (Total: {stats['pending_invites']})</option>
                                <option value="INVITED">Active Invited Users (Total: {stats['invited_users']})</option>
                                <option value="AWAITING_RECEIPT">Awaiting Payment Receipt</option>
                                <option value="AWAITING_EMAIL">Awaiting Canva Email</option>
                                <option value="NEW">New Registered Users</option>
                            </select>
                        </div>

                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <label class="text-xs font-medium text-gray-300">Message Content (Markdown Supported)</label>
                                <div class="flex items-center gap-1.5 text-xs text-gray-400">
                                    <span>Insert:</span>
                                    <button type="button" onclick="insertVariable('{{first_name}}')" class="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-teal-300 font-mono text-[11px] transition">&#123;first_name&#125;</button>
                                    <button type="button" onclick="insertVariable('{{username}}')" class="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-purple-300 font-mono text-[11px] transition">&#123;username&#125;</button>
                                    <button type="button" onclick="insertVariable('{{user_id}}')" class="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-amber-300 font-mono text-[11px] transition">&#123;user_id&#125;</button>
                                </div>
                            </div>
                            <textarea id="broadcastText" rows="6" placeholder="Write your broadcast announcement in Markdown...&#10;&#10;Example:&#10;🎉 *Important Canva Update*&#10;&#10;Hello {{first_name}}, your Canva seat invitation has been sent! Check your inbox."
                                class="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-cyan-500 font-mono leading-relaxed transition"></textarea>
                        </div>

                        <div class="flex flex-wrap items-center gap-3 pt-2">
                            <button type="button" onclick="submitBroadcast(true)" id="btnTestBroadcast" class="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs px-4 py-2.5 rounded-lg font-medium flex items-center gap-2 transition" title="Sends only to your configured ADMIN_ID to test formatting">
                                <i class="fa-solid fa-vial text-cyan-400"></i>
                                <span>Send Test to Admin</span>
                            </button>
                            <button type="button" onclick="submitBroadcast(false)" id="btnSendBroadcast" class="bg-gradient-to-r from-teal-500 to-purple-600 hover:from-teal-400 hover:to-purple-500 text-white text-xs px-5 py-2.5 rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-purple-500/20 transition">
                                <i class="fa-solid fa-paper-plane"></i>
                                <span>Send Broadcast Blast</span>
                            </button>
                        </div>

                        <div id="broadcastResultBox" class="hidden"></div>
                    </div>

                    <!-- Broadcast Info / Guide Card -->
                    <div class="bg-gray-950/70 border border-gray-800 rounded-xl p-4 space-y-3 text-xs text-gray-400">
                        <h4 class="font-bold text-gray-200 flex items-center gap-1.5">
                            <i class="fa-solid fa-lightbulb text-amber-400"></i>
                            <span>Broadcast Tips</span>
                        </h4>
                        <ul class="space-y-2 list-disc list-inside">
                            <li>Always click <strong class="text-cyan-300">Send Test to Admin</strong> first to verify Markdown formatting on your Telegram client.</li>
                            <li>Personalized placeholders like <code class="text-teal-300">&#123;first_name&#125;</code> will automatically adapt to each recipient.</li>
                            <li>Users who blocked the bot or deleted their accounts are safely handled without interrupting the broadcast.</li>
                            <li>Avoid spamming to respect Telegram rate limits and protect your bot reputation.</li>
                        </ul>
                    </div>
                </div>
            </div>

        </div>

        <!-- ========================================== -->
        <!-- TAB PANE 4: RECEIPTS AUDIT                 -->
        <!-- ========================================== -->
        <div id="tabPane-receipts" class="tab-pane space-y-4 hidden">
            
            <div class="bg-gray-900 border border-gray-800 rounded-2xl shadow-xl overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <i class="fa-solid fa-receipt text-emerald-400"></i>
                            <span>BaridiMob Receipts Audit Log</span>
                        </h3>
                        <p class="text-xs text-gray-400">All verified transactions and cryptographic SHA-256 deduplication fingerprints.</p>
                    </div>

                    <div class="relative w-full max-w-xs">
                        <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-xs text-gray-500"></i>
                        <input type="text" id="receiptSearch" placeholder="Search Tx ID, user, hash..." oninput="filterReceiptsTable()" 
                            class="w-full bg-gray-950 border border-gray-800 text-xs rounded-lg pl-8 pr-3 py-2 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-500 transition">
                    </div>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-gray-300">
                        <thead class="bg-gray-950 text-gray-400 text-xs uppercase font-medium border-b border-gray-800">
                            <tr>
                                <th class="px-5 py-3">Numéro d'Opération (Tx ID)</th>
                                <th class="px-5 py-3">User</th>
                                <th class="px-5 py-3">Amount</th>
                                <th class="px-5 py-3">SHA-256 Fingerprint</th>
                                <th class="px-5 py-3">Verified Date</th>
                                <th class="px-5 py-3 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800" id="receiptsTbody">
                            {receipt_rows}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>

        <!-- ========================================== -->
        <!-- TAB PANE 5: VIP REWARDS                    -->
        <!-- ========================================== -->
        <div id="tabPane-rewards" class="tab-pane space-y-4 hidden">
            
            <div class="bg-gray-900 border border-gray-800 rounded-2xl shadow-xl overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <i class="fa-solid fa-gift text-purple-400"></i>
                            <span>VIP Freebie Rewards ({active_reward_target} Paid Referrals Goal)</span>
                        </h3>
                        <p class="text-xs text-gray-400">Members who brought {active_reward_target} paying friends and earned a freebie bonus.</p>
                    </div>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-gray-300">
                        <thead class="bg-gray-950 text-gray-400 text-xs uppercase font-medium border-b border-gray-800">
                            <tr>
                                <th class="px-5 py-3">Claim ID</th>
                                <th class="px-5 py-3">Referrer User</th>
                                <th class="px-5 py-3">Paid Friends</th>
                                <th class="px-5 py-3">Unlocked At</th>
                                <th class="px-5 py-3 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800">
                            {reward_rows}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>

        <!-- ========================================== -->
        <!-- TAB PANE 6: LIVE SETTINGS & TOOLS          -->
        <!-- ========================================== -->
        <div id="tabPane-settings" class="tab-pane space-y-6 hidden">
            
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Settings Form -->
                <div class="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-5">
                    <div>
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <i class="fa-solid fa-sliders text-teal-400"></i>
                            <span>Live System Parameters</span>
                        </h3>
                        <p class="text-xs text-gray-400 mt-1">Changes take effect immediately without needing server restart.</p>
                    </div>

                    <form onsubmit="submitSettings(event)" class="space-y-4">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Payment Amount (DZD)</label>
                                <input type="number" id="cfg_payment_amount" step="10" required value="{active_amount}" 
                                    class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-teal-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Max Seat Capacity</label>
                                <input type="number" id="cfg_max_seats" min="1" required value="{active_max_seats}" 
                                    class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-teal-500">
                            </div>
                        </div>

                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">Target BaridiMob RIP Account</label>
                            <input type="text" id="cfg_target_rip" required value="{active_rip}" 
                                class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-teal-500">
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Target CCP Account</label>
                                <input type="text" id="cfg_target_ccp" required value="{active_ccp}" 
                                    class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-teal-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Mandatory Telegram Channel</label>
                                <input type="text" id="cfg_required_channel" required value="{active_channel}" 
                                    class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-teal-500">
                            </div>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Paid Referrals Needed for Reward</label>
                                <input type="number" id="cfg_reward_target" min="1" required value="{active_reward_target}" 
                                    class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-teal-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Date Grace Window (Days)</label>
                                <input type="number" id="cfg_date_grace_days" min="0" max="7" required value="{active_grace_days}" 
                                    class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-teal-500">
                                <span class="text-[10px] text-gray-500 block mt-1">1 = Today & Yesterday, 0 = Today only, 2 = Up to 2 days ago</span>
                            </div>
                        </div>

                        <div class="pt-3 border-t border-gray-800 flex justify-end">
                            <button type="submit" id="btnSaveSettings" class="canva-btn text-white px-5 py-2.5 rounded-lg text-xs font-bold shadow-lg transition flex items-center gap-2">
                                <i class="fa-solid fa-floppy-disk"></i>
                                <span>Save System Parameters</span>
                            </button>
                        </div>
                    </form>
                </div>

                <!-- Database Tools & Backups Card -->
                <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
                    <div>
                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                            <i class="fa-solid fa-database text-purple-400"></i>
                            <span>Backups & Data Exports</span>
                        </h3>
                        <p class="text-xs text-gray-400 mt-1">Direct exports and binary snapshots of the SQLite database.</p>
                    </div>

                    <div class="space-y-3 pt-2">
                        <a href="/admin/backup-db" class="w-full bg-gray-950 hover:bg-gray-800 border border-gray-800 p-3.5 rounded-xl flex items-center justify-between transition group">
                            <div class="flex items-center gap-3">
                                <div class="w-9 h-9 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center">
                                    <i class="fa-solid fa-file-shield text-base"></i>
                                </div>
                                <div>
                                    <p class="text-xs font-bold text-white group-hover:text-purple-300 transition">Download SQLite .db</p>
                                    <p class="text-[11px] text-gray-500">Raw database snapshot</p>
                                </div>
                            </div>
                            <i class="fa-solid fa-download text-gray-500 group-hover:text-purple-400 transition text-xs"></i>
                        </a>

                        <a href="/admin/export-json" class="w-full bg-gray-950 hover:bg-gray-800 border border-gray-800 p-3.5 rounded-xl flex items-center justify-between transition group">
                            <div class="flex items-center gap-3">
                                <div class="w-9 h-9 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center">
                                    <i class="fa-solid fa-code text-base"></i>
                                </div>
                                <div>
                                    <p class="text-xs font-bold text-white group-hover:text-cyan-300 transition">Download JSON Dump</p>
                                    <p class="text-[11px] text-gray-500">Structured tables in JSON</p>
                                </div>
                            </div>
                            <i class="fa-solid fa-download text-gray-500 group-hover:text-cyan-400 transition text-xs"></i>
                        </a>

                        <a href="/admin/export-csv" class="w-full bg-gray-950 hover:bg-gray-800 border border-gray-800 p-3.5 rounded-xl flex items-center justify-between transition group">
                            <div class="flex items-center gap-3">
                                <div class="w-9 h-9 rounded-lg bg-teal-500/10 text-teal-400 flex items-center justify-center">
                                    <i class="fa-solid fa-file-csv text-base"></i>
                                </div>
                                <div>
                                    <p class="text-xs font-bold text-white group-hover:text-teal-300 transition">Canva Invites CSV</p>
                                    <p class="text-[11px] text-gray-500">For Canva Admin Batch Upload</p>
                                </div>
                            </div>
                            <i class="fa-solid fa-download text-gray-500 group-hover:text-teal-400 transition text-xs"></i>
                        </a>
                    </div>
                </div>
            </div>

        </div>

    </main>

    <!-- ========================================== -->
    <!-- MODALS                                     -->
    <!-- ========================================== -->

    <!-- 1. Add User Modal -->
    <div id="addUserModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm hidden">
        <div class="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
            <div class="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
                <h4 class="font-bold text-white text-base flex items-center gap-2">
                    <i class="fa-solid fa-user-plus text-purple-400"></i>
                    <span>Add New User</span>
                </h4>
                <button onclick="closeAddUserModal()" class="text-gray-400 hover:text-white transition">
                    <i class="fa-solid fa-xmark text-lg"></i>
                </button>
            </div>
            <form onsubmit="submitAddUser(event)" class="p-6 space-y-4">
                <div>
                    <label class="block text-xs font-medium text-gray-400 mb-1">Telegram User ID <span class="text-red-400">*</span></label>
                    <input type="number" id="add_user_id" required placeholder="e.g. 8027972947" 
                        class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Username (without @)</label>
                        <input type="text" id="add_username" placeholder="e.g. aitadz" 
                            class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">First Name</label>
                        <input type="text" id="add_first_name" placeholder="e.g. Sadek" 
                            class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500">
                    </div>
                </div>
                <div>
                    <label class="block text-xs font-medium text-gray-400 mb-1">Canva Email</label>
                    <input type="email" id="add_email" placeholder="e.g. user@gmail.com" 
                        class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Status</label>
                        <select id="add_status" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500">
                            <option value="NEW">NEW</option>
                            <option value="AWAITING_RECEIPT">AWAITING RECEIPT</option>
                            <option value="AWAITING_EMAIL">AWAITING EMAIL</option>
                            <option value="PENDING_INVITE" selected>READY TO INVITE</option>
                            <option value="INVITED">INVITED</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Unlock Method</label>
                        <select id="add_unlock_method" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500">
                            <option value="PAID" selected>PAID</option>
                            <option value="REFERRAL">REFERRAL</option>
                        </select>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Paid Referrals Count</label>
                        <input type="number" id="add_paid_referrals" value="0" min="0" 
                            class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Language</label>
                        <select id="add_language" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500">
                            <option value="fr" selected>Français (fr)</option>
                            <option value="ar">العربية (ar)</option>
                            <option value="en">English (en)</option>
                        </select>
                    </div>
                </div>
                <div class="pt-3 flex items-center justify-end gap-2 border-t border-gray-800">
                    <button type="button" onclick="closeAddUserModal()" class="px-4 py-2 rounded-lg text-xs font-medium text-gray-400 hover:text-white transition">Cancel</button>
                    <button type="submit" class="canva-btn text-white px-4 py-2 rounded-lg text-xs font-semibold shadow transition">Create User</button>
                </div>
            </form>
        </div>
    </div>

    <!-- 2. Edit User Modal -->
    <div id="editUserModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm hidden">
        <div class="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
            <div class="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
                <h4 class="font-bold text-white text-base flex items-center gap-2">
                    <i class="fa-solid fa-user-pen text-cyan-400"></i>
                    <span>Edit User <span id="editModalUserIdTitle" class="font-mono text-purple-400"></span></span>
                </h4>
                <button onclick="closeEditUserModal()" class="text-gray-400 hover:text-white transition">
                    <i class="fa-solid fa-xmark text-lg"></i>
                </button>
            </div>
            <form onsubmit="submitEditUser(event)" class="p-6 space-y-4">
                <input type="hidden" id="edit_user_id">
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Username (without @)</label>
                        <input type="text" id="edit_username" 
                            class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">First Name</label>
                        <input type="text" id="edit_first_name" 
                            class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500">
                    </div>
                </div>
                <div>
                    <label class="block text-xs font-medium text-gray-400 mb-1">Canva Email</label>
                    <input type="email" id="edit_email" 
                        class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Status</label>
                        <select id="edit_status" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500">
                            <option value="NEW">NEW</option>
                            <option value="AWAITING_RECEIPT">AWAITING RECEIPT</option>
                            <option value="AWAITING_EMAIL">AWAITING EMAIL</option>
                            <option value="PENDING_INVITE">READY TO INVITE</option>
                            <option value="INVITED">INVITED</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Unlock Method</label>
                        <select id="edit_unlock_method" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500">
                            <option value="PAID">PAID</option>
                            <option value="REFERRAL">REFERRAL</option>
                        </select>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Paid Referrals Count</label>
                        <input type="number" id="edit_paid_referrals" min="0" 
                            class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Language</label>
                        <select id="edit_language" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500">
                            <option value="fr">Français (fr)</option>
                            <option value="ar">العربية (ar)</option>
                            <option value="en">English (en)</option>
                        </select>
                    </div>
                </div>
                <div class="pt-3 flex items-center justify-end gap-2 border-t border-gray-800">
                    <button type="button" onclick="closeEditUserModal()" class="px-4 py-2 rounded-lg text-xs font-medium text-gray-400 hover:text-white transition">Cancel</button>
                    <button type="submit" class="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow transition">Save Changes</button>
                </div>
            </form>
        </div>
    </div>

    <!-- 3. Quick Paste & Mark Invited Modal -->
    <div id="bulkPasteModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm hidden">
        <div class="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
            <div class="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
                <h4 class="font-bold text-white text-base flex items-center gap-2">
                    <i class="fa-solid fa-paste text-cyan-400"></i>
                    <span>Quick Paste & Mark Invited</span>
                </h4>
                <button onclick="closeBulkPasteModal()" class="text-gray-400 hover:text-white transition">
                    <i class="fa-solid fa-xmark text-lg"></i>
                </button>
            </div>
            <form onsubmit="submitBulkPaste(event)" class="p-6 space-y-4">
                <p class="text-xs text-gray-400">
                    Paste raw text containing Canva emails (e.g. from Canva Admin team page or CSV). The system will extract all valid email addresses and automatically mark matching pending users as <strong class="text-emerald-400">INVITED</strong>.
                </p>
                <div>
                    <textarea id="bulkPasteInput" rows="6" oninput="updateBulkPasteCount()" placeholder="user1@example.com&#10;user2@gmail.com, user3@yahoo.com&#10;..."
                        class="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-cyan-500 font-mono leading-relaxed"></textarea>
                </div>
                <div class="flex items-center justify-between text-xs text-gray-400">
                    <span id="bulkPasteCount" class="font-mono text-cyan-400">0 emails detected</span>
                </div>
                <div class="pt-3 flex items-center justify-end gap-2 border-t border-gray-800">
                    <button type="button" onclick="closeBulkPasteModal()" class="px-4 py-2 rounded-lg text-xs font-medium text-gray-400 hover:text-white transition">Cancel</button>
                    <button type="submit" id="submitBulkPasteBtn" class="canva-btn text-white px-5 py-2 rounded-lg text-xs font-bold shadow transition">Mark Identified Users as Invited</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Floating Toast Notification Container -->
    <div id="toastContainer" class="fixed bottom-5 right-5 z-50 flex flex-col space-y-2 pointer-events-none"></div>

    <footer class="border-t border-gray-800 py-6 text-center text-xs text-gray-500">
        Canva Distribution System (Algeria) &bull; Self-Hosted &bull; Zero External AI API Costs
    </footer>

    <!-- ========================================== -->
    <!-- CLIENT JAVASCRIPT                          -->
    <!-- ========================================== -->
    <script>
        // Tab switching logic
        function switchTab(tabId) {{
            document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(btn => {{
                btn.classList.remove('bg-purple-600/30', 'text-purple-300', 'border-purple-500/50');
                btn.classList.add('text-gray-400', 'border-transparent', 'hover:text-gray-200');
            }});

            const targetPane = document.getElementById('tabPane-' + tabId);
            if (targetPane) targetPane.classList.remove('hidden');

            const targetBtn = document.getElementById('tabBtn-' + tabId);
            if (targetBtn) {{
                targetBtn.classList.add('bg-purple-600/30', 'text-purple-300', 'border-purple-500/50');
                targetBtn.classList.remove('text-gray-400', 'border-transparent', 'hover:text-gray-200');
            }}

            try {{ localStorage.setItem('activeCanvaAdminTab', tabId); }} catch(e) {{}}
        }}

        window.addEventListener('DOMContentLoaded', () => {{
            try {{
                const savedTab = localStorage.getItem('activeCanvaAdminTab') || 'queue';
                switchTab(savedTab);
            }} catch(e) {{
                switchTab('queue');
            }}
        }});

        // Toast notifications
        function showToast(message, type = 'info') {{
            const container = document.getElementById('toastContainer');
            if (!container) return;
            const toast = document.createElement('div');
            const colors = {{
                success: 'bg-emerald-950/95 border-emerald-500 text-emerald-200',
                error: 'bg-red-950/95 border-red-500 text-red-200',
                info: 'bg-gray-900/95 border-purple-500 text-gray-200'
            }};
            const icons = {{
                success: 'fa-circle-check text-emerald-400',
                error: 'fa-circle-xmark text-red-400',
                info: 'fa-circle-info text-purple-400'
            }};
            const colorClass = colors[type] || colors.info;
            const iconClass = icons[type] || icons.info;

            toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl border shadow-2xl text-xs backdrop-blur transition-all duration-300 transform translate-y-2 opacity-0 pointer-events-auto ${{colorClass}}`;
            toast.innerHTML = `<i class="fa-solid ${{iconClass}} text-base"></i><span>${{message}}</span>`;
            container.appendChild(toast);

            requestAnimationFrame(() => {{
                toast.classList.remove('translate-y-2', 'opacity-0');
            }});

            setTimeout(() => {{
                toast.classList.add('opacity-0', 'translate-y-2');
                setTimeout(() => toast.remove(), 300);
            }}, 4000);
        }}

        // Copy text helper
        function copyText(text, label) {{
            navigator.clipboard.writeText(text).then(() => {{
                showToast(`Copied ${{label}} to clipboard!`, 'success');
            }}).catch(err => {{
                showToast('Failed to copy: ' + err, 'error');
            }});
        }}

        // Copy Pending Emails Helper
        async function copyPending(format) {{
            try {{
                const res = await fetch('/api/pending-emails');
                const data = await res.json();
                if (!data.emails || data.emails.length === 0) {{
                    showToast('No pending emails to copy!', 'info');
                    return;
                }}
                const textToCopy = format === 'comma' ? data.comma_separated : data.newline_separated;
                await navigator.clipboard.writeText(textToCopy);
                showToast(`Copied ${{data.count}} emails (${{format}}) to clipboard!`, 'success');
            }} catch (err) {{
                showToast('Failed to copy: ' + err, 'error');
            }}
        }}

        // Filter Canva Queue Table
        function filterQueueTable() {{
            const query = (document.getElementById('queueSearch').value || '').trim().toLowerCase();
            const rows = document.querySelectorAll('.queue-row');
            let visible = 0;
            rows.forEach(r => {{
                const corpus = r.getAttribute('data-search') || '';
                if (!query || corpus.includes(query)) {{
                    r.style.display = '';
                    visible++;
                }} else {{
                    r.style.display = 'none';
                }}
            }});
            const badge = document.getElementById('queueCountBadge');
            if (badge) badge.textContent = `${{visible}} pending`;
        }}

        // Filter Users Table
        function filterUsersTable() {{
            const query = (document.getElementById('userSearch').value || '').trim().toLowerCase();
            const statusFilter = (document.getElementById('statusFilter').value || '').trim().toUpperCase();
            const rows = document.querySelectorAll('.user-row');
            let visibleCount = 0;

            rows.forEach(row => {{
                const searchCorpus = row.getAttribute('data-search') || '';
                const rowStatus = (row.getAttribute('data-status') || '').toUpperCase();

                const matchesQuery = !query || searchCorpus.includes(query);
                const matchesStatus = !statusFilter || rowStatus === statusFilter;

                if (matchesQuery && matchesStatus) {{
                    row.style.display = '';
                    visibleCount++;
                }} else {{
                    row.style.display = 'none';
                }}
            }});

            const badge = document.getElementById('userCountBadge');
            if (badge) badge.textContent = visibleCount;
        }}

        // Filter Receipts Table
        function filterReceiptsTable() {{
            const query = (document.getElementById('receiptSearch').value || '').trim().toLowerCase();
            const rows = document.querySelectorAll('.receipt-row');
            rows.forEach(r => {{
                const corpus = r.getAttribute('data-search') || '';
                if (!query || corpus.includes(query)) {{
                    r.style.display = '';
                }} else {{
                    r.style.display = 'none';
                }}
            }});
        }}

        // Quick Paste & Mark Invited Modal
        function openBulkPasteModal() {{
            document.getElementById('bulkPasteModal').classList.remove('hidden');
            document.getElementById('bulkPasteInput').value = '';
            document.getElementById('bulkPasteCount').textContent = '0 emails detected';
            document.getElementById('bulkPasteInput').focus();
        }}

        function closeBulkPasteModal() {{
            document.getElementById('bulkPasteModal').classList.add('hidden');
        }}

        function updateBulkPasteCount() {{
            const text = document.getElementById('bulkPasteInput').value;
            const matches = text.match(/[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+/g) || [];
            const unique = [...new Set(matches.map(e => e.toLowerCase()))];
            document.getElementById('bulkPasteCount').textContent = `${{unique.length}} unique emails detected`;
        }}

        async function submitBulkPaste(e) {{
            e.preventDefault();
            const text = document.getElementById('bulkPasteInput').value;
            if (!text.trim()) {{
                showToast('Please paste email text first', 'error');
                return;
            }}
            const btn = document.getElementById('submitBulkPasteBtn');
            btn.disabled = true;
            btn.textContent = 'Processing...';

            try {{
                const res = await fetch('/api/bulk-import-invited', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ raw_text: text }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    showToast(`Success! ${{data.updated_count}} pending users marked as INVITED (${{data.total_parsed}} parsed).`, 'success');
                    closeBulkPasteModal();
                    setTimeout(() => window.location.reload(), 1200);
                }} else {{
                    showToast('Error: ' + (data.detail || JSON.stringify(data)), 'error');
                }}
            }} catch (err) {{
                showToast('Request failed: ' + err, 'error');
            }} finally {{
                btn.disabled = false;
                btn.textContent = 'Mark Identified Users as Invited';
            }}
        }}

        // Add User Modal
        function openAddUserModal() {{
            document.getElementById('addUserModal').classList.remove('hidden');
            document.getElementById('add_user_id').focus();
        }}

        function closeAddUserModal() {{
            document.getElementById('addUserModal').classList.add('hidden');
        }}

        async function submitAddUser(e) {{
            e.preventDefault();
            const payload = {{
                user_id: parseInt(document.getElementById('add_user_id').value),
                username: document.getElementById('add_username').value.trim() || null,
                first_name: document.getElementById('add_first_name').value.trim() || null,
                email: document.getElementById('add_email').value.trim() || null,
                status: document.getElementById('add_status').value,
                unlock_method: document.getElementById('add_unlock_method').value,
                paid_referrals_count: parseInt(document.getElementById('add_paid_referrals').value) || 0,
                language: document.getElementById('add_language').value
            }};

            try {{
                const res = await fetch('/api/users', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                if (res.ok) {{
                    showToast('User created successfully!', 'success');
                    setTimeout(() => window.location.reload(), 800);
                }} else {{
                    showToast('Error adding user: ' + (data.detail || JSON.stringify(data)), 'error');
                }}
            }} catch (err) {{
                showToast('Request failed: ' + err, 'error');
            }}
        }}

        // Edit User Modal
        async function openEditUserModal(userId) {{
            try {{
                const res = await fetch('/api/users/' + userId);
                if (!res.ok) {{
                    showToast('Error loading user details', 'error');
                    return;
                }}
                const data = await res.json();
                const user = data.user;

                document.getElementById('edit_user_id').value = user.user_id;
                document.getElementById('editModalUserIdTitle').textContent = '#' + user.user_id;
                document.getElementById('edit_username').value = user.username || '';
                document.getElementById('edit_first_name').value = user.first_name || '';
                document.getElementById('edit_email').value = user.email || '';
                document.getElementById('edit_status').value = user.status || 'NEW';
                document.getElementById('edit_unlock_method').value = user.unlock_method || 'PAID';
                document.getElementById('edit_paid_referrals').value = user.paid_referrals_count || 0;
                document.getElementById('edit_language').value = user.language || 'fr';

                document.getElementById('editUserModal').classList.remove('hidden');
            }} catch (err) {{
                showToast('Failed to load user: ' + err, 'error');
            }}
        }}

        function closeEditUserModal() {{
            document.getElementById('editUserModal').classList.add('hidden');
        }}

        async function submitEditUser(e) {{
            e.preventDefault();
            const userId = document.getElementById('edit_user_id').value;
            const payload = {{
                username: document.getElementById('edit_username').value.trim() || null,
                first_name: document.getElementById('edit_first_name').value.trim() || null,
                email: document.getElementById('edit_email').value.trim() || null,
                status: document.getElementById('edit_status').value,
                unlock_method: document.getElementById('edit_unlock_method').value,
                paid_referrals_count: parseInt(document.getElementById('edit_paid_referrals').value) || 0,
                language: document.getElementById('edit_language').value
            }};

            try {{
                const res = await fetch('/api/users/' + userId, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                if (res.ok) {{
                    showToast('User updated successfully!', 'success');
                    setTimeout(() => window.location.reload(), 800);
                }} else {{
                    showToast('Error saving user: ' + (data.detail || JSON.stringify(data)), 'error');
                }}
            }} catch (err) {{
                showToast('Request failed: ' + err, 'error');
            }}
        }}

        async function deleteUser(userId, displayName) {{
            if (!confirm(`Are you sure you want to permanently delete user ${{displayName}} (ID: ${{userId}})?\\n\\nThis will remove their Canva record and any associated receipts/rewards.`)) {{
                return;
            }}
            try {{
                const res = await fetch('/api/users/' + userId, {{ method: 'DELETE' }});
                const data = await res.json();
                if (res.ok) {{
                    showToast('User deleted successfully!', 'success');
                    setTimeout(() => window.location.reload(), 800);
                }} else {{
                    showToast('Error deleting user: ' + (data.detail || JSON.stringify(data)), 'error');
                }}
            }} catch (err) {{
                showToast('Request failed: ' + err, 'error');
            }}
        }}

        async function markInvited(email) {{
            if (!confirm(`Mark ${{email}} as invited to Canva?`)) return;
            try {{
                const res = await fetch(`/api/mark-invited/${{encodeURIComponent(email)}}`, {{ method: 'POST' }});
                if (res.ok) {{
                    showToast(`Marked ${{email}} as invited!`, 'success');
                    setTimeout(() => window.location.reload(), 800);
                }} else {{
                    showToast('Error marking user as invited.', 'error');
                }}
            }} catch (e) {{
                showToast('Request failed: ' + e, 'error');
            }}
        }}

        async function bulkMarkInvited() {{
            if (!confirm('Mark ALL pending users as invited?')) return;
            try {{
                const res = await fetch('/api/bulk-mark-invited', {{ method: 'POST' }});
                const data = await res.json();
                if (res.ok) {{
                    showToast(`Updated ${{data.count}} users to INVITED!`, 'success');
                    setTimeout(() => window.location.reload(), 1000);
                }} else {{
                    showToast('Error during bulk update.', 'error');
                }}
            }} catch (e) {{
                showToast('Request failed: ' + e, 'error');
            }}
        }}

        async function deliverReward(rewardId) {{
            const note = prompt('Enter freebie delivery details / gift link / message for the user:');
            if (note === null) return;
            try {{
                const res = await fetch(`/api/deliver-reward/${{rewardId}}`, {{ method: 'POST' }});
                if (res.ok) {{
                    showToast('Reward marked as delivered successfully!', 'success');
                    setTimeout(() => window.location.reload(), 800);
                }} else {{
                    showToast('Error marking reward delivered.', 'error');
                }}
            }} catch (e) {{
                showToast('Request failed: ' + e, 'error');
            }}
        }}

        async function deleteReceipt(txId) {{
            if (!confirm(`Are you sure you want to REVOKE receipt #${{txId}}?\\n\\nThis will remove the transaction record and hash fingerprint from the database.`)) {{
                return;
            }}
            try {{
                const res = await fetch(`/api/receipts/${{encodeURIComponent(txId)}}`, {{ method: 'DELETE' }});
                const data = await res.json();
                if (res.ok) {{
                    showToast(`Receipt #${{txId}} revoked successfully!`, 'success');
                    setTimeout(() => window.location.reload(), 800);
                }} else {{
                    showToast('Error revoking receipt: ' + (data.detail || JSON.stringify(data)), 'error');
                }}
            }} catch (err) {{
                showToast('Request failed: ' + err, 'error');
            }}
        }}

        // Broadcast Helpers
        function insertVariable(varName) {{
            const textarea = document.getElementById('broadcastText');
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            const text = textarea.value;
            textarea.value = text.substring(0, start) + varName + text.substring(end);
            textarea.focus();
            textarea.selectionStart = textarea.selectionEnd = start + varName.length;
        }}

        async function submitBroadcast(isTest) {{
            const text = (document.getElementById('broadcastText').value || '').trim();
            const targetStatus = document.getElementById('broadcastTarget').value;
            if (!text) {{
                showToast('Please enter broadcast message text', 'error');
                return;
            }}

            if (!isTest) {{
                if (!confirm(`Are you sure you want to BLAST this message to audience "${{targetStatus}}" via Telegram?`)) {{
                    return;
                }}
            }}

            const btn = isTest ? document.getElementById('btnTestBroadcast') : document.getElementById('btnSendBroadcast');
            btn.disabled = true;
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending...';

            try {{
                const res = await fetch('/api/broadcast', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        text: text,
                        target_status: targetStatus,
                        test_only: isTest
                    }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    const r = data.result;
                    const resBox = document.getElementById('broadcastResultBox');
                    resBox.classList.remove('hidden');
                    resBox.innerHTML = `
                        <div class="p-4 rounded-xl border ${{isTest ? 'bg-cyan-950/40 border-cyan-500/50' : 'bg-purple-950/40 border-purple-500/50'}} text-xs">
                            <p class="font-bold ${{isTest ? 'text-cyan-300' : 'text-purple-300'}} mb-1">
                                ${{isTest ? '🧪 Test Broadcast Sent to Admin!' : '🚀 Broadcast Finished!'}}
                            </p>
                            <p class="text-gray-300">Targeted: <strong>${{r.total_targeted}}</strong> | Sent: <strong class="text-emerald-400">${{r.sent_count}}</strong> | Failed: <strong class="text-red-400">${{r.failed_count}}</strong> | Blocked: <strong>${{r.blocked_count}}</strong></p>
                        </div>
                    `;
                    showToast(isTest ? 'Test message sent to admin Telegram!' : `Broadcast sent to ${{r.sent_count}} users!`, 'success');
                }} else {{
                    showToast('Error: ' + (data.detail || JSON.stringify(data)), 'error');
                }}
            }} catch (err) {{
                showToast('Request failed: ' + err, 'error');
            }} finally {{
                btn.disabled = false;
                btn.innerHTML = originalText;
            }}
        }}

        // Save Live Settings
        async function submitSettings(e) {{
            e.preventDefault();
            const payload = {{
                payment_amount: parseFloat(document.getElementById('cfg_payment_amount').value),
                target_rip: document.getElementById('cfg_target_rip').value.trim(),
                target_ccp: document.getElementById('cfg_target_ccp').value.trim(),
                required_channel: document.getElementById('cfg_required_channel').value.trim(),
                paid_referrals_for_reward: parseInt(document.getElementById('cfg_reward_target').value),
                max_seats: parseInt(document.getElementById('cfg_max_seats').value),
                date_grace_days: parseInt(document.getElementById('cfg_date_grace_days').value)
            }};

            const btn = document.getElementById('btnSaveSettings');
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

            try {{
                const res = await fetch('/api/config', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                if (res.ok) {{
                    showToast('System configuration saved successfully!', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                }} else {{
                    showToast('Error saving settings: ' + (data.detail || JSON.stringify(data)), 'error');
                }}
            }} catch (err) {{
                showToast('Request failed: ' + err, 'error');
            }} finally {{
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save System Parameters';
            }}
        }}
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
