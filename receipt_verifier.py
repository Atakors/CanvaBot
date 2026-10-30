"""
BaridiMob Receipt Verification Engine.
Performs local, zero-API extraction and multi-rule validation of BaridiMob receipts (PDF / Images).
"""

import io
import re
import hashlib
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from PIL import Image, ImageEnhance, ImageFilter

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

from config import settings
from database import check_receipt_hash_exists, check_tx_id_exists, get_config_value

logger = logging.getLogger(__name__)


@dataclass
class ReceiptVerificationResult:
    is_valid: bool
    status_code: str  # SUCCESS, DUPLICATE_HASH, DUPLICATE_TX_ID, INVALID_ACCOUNT, INVALID_AMOUNT, INVALID_DATE, MISSING_TX_ID, INVALID_OPERATION_TYPE, PARSE_ERROR, OCR_UNAVAILABLE
    error_message: str
    tx_id: Optional[str] = None
    amount: Optional[float] = None
    tx_date: Optional[str] = None
    account_matched: Optional[str] = None
    operation_type: Optional[str] = None
    file_hash: Optional[str] = None
    raw_text: Optional[str] = None


def compute_file_hash(file_bytes: bytes) -> str:
    """Computes SHA-256 hash of receipt file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts raw text from BaridiMob PDF receipt using pypdf."""
    if not pypdf:
        raise RuntimeError("pypdf library is not installed.")
    
    stream = io.BytesIO(file_bytes)
    reader = pypdf.PdfReader(stream)
    text_parts = []
    
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
            
    return "\n".join(text_parts).strip()


def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    """Preprocesses image to maximize Tesseract OCR accuracy."""
    # Convert to grayscale
    gray = image.convert("L")
    
    # Resize if very small
    w, h = gray.size
    if w < 1000:
        scaling_factor = 2
        gray = gray.resize((w * scaling_factor, h * scaling_factor), Image.Resampling.LANCZOS)
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(gray)
    contrasted = enhancer.enhance(2.0)
    
    # Slight sharpen filter
    sharpened = contrasted.filter(ImageFilter.SHARPEN)
    
    return sharpened


def extract_text_from_image(file_bytes: bytes) -> str:
    """Extracts text from receipt screenshot/image using PIL and pytesseract."""
    if not pytesseract:
        raise RuntimeError("pytesseract library is not installed.")
    
    # Configure tesseract executable if path specified
    if settings.TESSERACT_CMD and settings.TESSERACT_CMD != "tesseract":
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    stream = io.BytesIO(file_bytes)
    img = Image.open(stream)
    
    # Preprocess
    processed_img = preprocess_image_for_ocr(img)
    
    # Try French and English OCR configs
    try:
        text = pytesseract.image_to_string(processed_img, lang="fra+eng", config="--psm 6")
        if not text.strip():
            text = pytesseract.image_to_string(processed_img, config="--psm 3")
        return text.strip()
    except Exception as e:
        logger.warning(f"Tesseract OCR with language packs failed: {e}. Retrying with default.")
        text = pytesseract.image_to_string(processed_img)
        return text.strip()


def normalize_digits(text: str) -> str:
    """Strips all non-digit characters."""
    return re.sub(r"\D", "", text)


def is_baridimob_system(text: str) -> bool:
    """Checks whether the text originates from BaridiMob or Algeria Poste."""
    lower = text.lower()
    keywords = ["baridimob", "algeria poste", "algérie poste", "baridi", "algerie poste", "bab ezzouar"]
    return any(kw in lower for kw in keywords)


def extract_operation_type(text: str) -> Optional[str]:
    """Extracts operation type (e.g. TRANSFER, VIREMENT)."""
    m = re.search(
        r"(?:Operation\s*type|Type\s*d['’]op[ée]ration|Nature\s*de\s*l['’]op[ée]ration)\s*[:.]?\s*([A-Za-z]+)",
        text,
        re.IGNORECASE
    )
    return m.group(1).upper() if m else None


def extract_transaction_id(text: str) -> Optional[str]:
    """
    Extracts BaridiMob transaction ID / Numéro d'opération / External ID.
    Patterns in BaridiMob receipts:
    - 'External id: 012582851483' (English BaridiMob PDF export)
    - 'N° de transaction : 123456789'
    - 'N° d'opération : 123456789'
    - 'Numéro de transaction : ...'
    - 'Numéro d'opération : ...'
    - 'Référence : ...'
    - 'Code de transaction : ...'
    - 'رقم المعاملة : ...'
    """
    patterns = [
        # External ID (e.g., official English BaridiMob PDF: "External id: 012582851483")
        r"(?:External\s*(?:id|ref|reference|identifier))\s*[:.]?\s*([A-Za-z0-9_-]{6,30})",
        # Explicit labels (French & variations)
        r"(?:N[°o]\s*(?:de\s+transaction|d['’]opération|de\s+l['’]opération))\s*[:.]?\s*([A-Za-z0-9_-]{6,30})",
        r"(?:Num[ée]ro\s*(?:de\s+transaction|d['’]op[ée]ration|de\s+l['’]op[ée]ration))\s*[:.]?\s*([A-Za-z0-9_-]{6,30})",
        r"(?:R[ée]f[ée]rence\s*(?:de\s+transaction)?)\s*[:.]?\s*([A-Za-z0-9_-]{6,30})",
        r"(?:Code\s*(?:de\s+transaction|d['’]op[ée]ration)?)\s*[:.]?\s*([A-Za-z0-9_-]{6,30})",
        r"(?:Transaction\s*(?:ID|N[°o]|#)?)\s*[:.]?\s*([A-Za-z0-9_-]{6,30})",
        # Arabic labels
        r"(?:رقم\s*(?:المعاملة|العملية|التحويل|المرجع))\s*[:.]?\s*([A-Za-z0-9_-]{6,30})",
        # Multi-line match where label is on one line and ID is on the next line
        r"(?:N[°o]\s*d['’]op[ée]ration|N[°o]\s*de\s*transaction|External\s*id)\s*\n\s*([A-Za-z0-9_-]{6,30})",
    ]
    
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            cand = match.group(1).strip()
            # Verify candidate has reasonable digits/alphanumeric characters
            if len(cand) >= 6 and any(c.isdigit() for c in cand):
                return cand
                
    return None


def extract_amount(text: str) -> Optional[float]:
    """
    Extracts payment amount in DZD.
    Handles '500,00 DZD', '500.00 DZD', '500 DZD', '500 DA', '500,00', etc.
    """
    patterns = [
        # Montant : 500,00 DZD / 500 DZD
        r"(?:Montant|Amount|المبلغ)\s*(?:de\s+la\s+transaction|transf[ée]r[ée]|d[ée]bit[ée])?\s*[:.]?\s*([0-9\s]+(?:[.,][0-9]{1,2})?)\s*(?:DZD|DA|دج)?",
        # Explicit 500 DZD or 500 DA anywhere in receipt
        r"\b([0-9]{3,4}(?:[.,][0-9]{2})?)\s*(?:DZD|DA|دج)\b",
    ]
    
    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            raw_val = match.group(1).replace(" ", "").replace(",", ".")
            try:
                val = float(raw_val)
                # If around 500 (e.g. 500.0), return immediately
                if abs(val - settings.PAYMENT_AMOUNT) < 0.01:
                    return val
                # Otherwise return any non-zero parsed amount for validation check
                if val > 0:
                    return val
            except ValueError:
                continue
                
    return None


def extract_dates(text: str) -> List[date]:
    """
    Extracts all dates from text.
    Matches DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, YYYY-MM-DD.
    """
    found_dates = []
    
    # DD/MM/YYYY or DD-MM-YYYY
    for match in re.finditer(r"\b(\d{2})[/.-](\d{2})[/.-](\d{4})\b", text):
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            d = date(year, month, day)
            found_dates.append(d)
        except ValueError:
            pass
            
    # YYYY-MM-DD
    for match in re.finditer(r"\b(\d{4})[/.-](\d{2})[/.-](\d{2})\b", text):
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            d = date(year, month, day)
            found_dates.append(d)
        except ValueError:
            pass
            
    return found_dates


def is_date_valid(dates: List[date], grace_days: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Checks if at least one extracted date is within allowed grace period (today, yesterday, or within N days).
    """
    if not dates:
        return False, None
        
    allowed_days = grace_days if grace_days is not None else settings.DATE_GRACE_DAYS
    today = date.today()
    
    # Sort dates descending (newest first)
    sorted_dates = sorted(dates, reverse=True)
    
    for d in sorted_dates:
        # Check difference: date shouldn't be in the far future or older than grace_days
        diff = (today - d).days
        # Allow slight future due to timezone (+1 day) and up to grace_days in the past
        if -1 <= diff <= allowed_days:
            return True, d.strftime("%d/%m/%Y")
            
    # Return newest date for reporting
    return False, sorted_dates[0].strftime("%d/%m/%Y")


def matches_target_account(text: str, target_rip: str, target_ccp: str) -> Tuple[bool, Optional[str]]:
    """
    Verifies destination account against configured RIP / CCP.
    Algerian RIP is 20 digits: 00799999 + [10 digits CCP] + [2 digits Cle].
    Extracts the destination account specifically to avoid false positives with Tx ID or date.
    """
    clean_target_rip = normalize_digits(target_rip)
    clean_target_ccp = normalize_digits(target_ccp)
    
    # Core CCP from RIP
    core_ccp_from_rip = ""
    if len(clean_target_rip) == 20:
        core_ccp_from_rip = clean_target_rip[8:18].lstrip("0")
        
    # Pattern to capture specifically destination / credited account
    dest_patterns = [
        r"(?:compte\s*(?:[àa]\s*cr[ée]diter|destinataire|b[ée]n[ée]ficiaire)|b[ée]n[ée]ficiaire|recipient|beneficiary|to|vers\s*(?:le\s*compte)?|rip\s*(?:destinataire)?)\s*[:.]?\s*(?:compte\s*(?:ccp|rip)?|ccp|rip)?\s*([0-9\s/.-]{5,35})",
        r"(?:cr[ée]dit[ée]|vers)\s*[:.]?\s*(?:compte\s*(?:ccp|rip)?|ccp|rip)?\s*([0-9\s/.-]{5,35})",
        r"\b(?:ccp|rip|recipient)\s*[:.]?\s*([0-9\s/.-]{5,35})",
    ]
    
    extracted_dest_accounts = []
    for pat in dest_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            raw_acc = m.group(1)
            digits = normalize_digits(raw_acc)
            if len(digits) >= 5:
                extracted_dest_accounts.append(digits)
                
    # If specific destination account field found, check against target
    if extracted_dest_accounts:
        for acc in extracted_dest_accounts:
            if clean_target_rip and (clean_target_rip == acc or clean_target_rip in acc):
                return True, f"RIP ({target_rip})"
            if core_ccp_from_rip and (core_ccp_from_rip == acc or acc.endswith(core_ccp_from_rip) or core_ccp_from_rip in acc):
                return True, f"CCP ({core_ccp_from_rip})"
            if clean_target_ccp and (clean_target_ccp == acc or acc.endswith(clean_target_ccp) or clean_target_ccp in acc):
                return True, f"CCP ({target_ccp})"
        return False, None

    # Fallback if no explicit label (e.g. OCR fragmentation): check isolated numeric tokens
    # Find whole number tokens with 8-22 digits
    tokens = re.findall(r"\b[0-9]{8,22}\b", text)
    for tok in tokens:
        clean_tok = normalize_digits(tok)
        if clean_target_rip and clean_tok == clean_target_rip:
            return True, f"RIP ({target_rip})"
        if clean_target_ccp and clean_tok == clean_target_ccp:
            return True, f"CCP ({target_ccp})"

    return False, None


def verify_baridimob_receipt(
    file_bytes: bytes,
    filename: str,
    is_pdf: bool = False,
    db_path: Optional[str] = None
) -> ReceiptVerificationResult:
    """
    Main verification pipeline:
    1. Hash Deduplication
    2. Text extraction (pypdf or pytesseract)
    3. Auto-Validation Rules:
       Rule 1: Destination RIP/CCP match
       Rule 2: Amount equals 500 DZD
       Rule 3: Date is today or yesterday
       Rule 4: Unique Transaction ID extracted and not in DB
    """
    # 1. Compute SHA-256 hash
    file_hash = compute_file_hash(file_bytes)
    if check_receipt_hash_exists(file_hash, db_path=db_path):
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="DUPLICATE_HASH",
            error_message="⚠️ This exact receipt file has already been submitted and approved in our system. Duplicate receipts are not allowed.",
            file_hash=file_hash
        )

    # 2. Extract Text
    raw_text = ""
    try:
        if is_pdf or filename.lower().endswith(".pdf"):
            raw_text = extract_text_from_pdf(file_bytes)
        else:
            raw_text = extract_text_from_image(file_bytes)
    except RuntimeError as re_err:
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="OCR_UNAVAILABLE",
            error_message=f"⚠️ System error: {re_err}. Please upload the official BaridiMob PDF receipt ('Télécharger reçu').",
            file_hash=file_hash
        )
    except Exception as e:
        logger.error(f"Failed to extract text from receipt: {e}", exc_info=True)
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="PARSE_ERROR",
            error_message="⚠️ Could not read the receipt file. Please ensure it is an official BaridiMob PDF or a high-resolution screenshot.",
            file_hash=file_hash
        )

    if not raw_text or len(raw_text.strip()) < 15:
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="PARSE_ERROR",
            error_message="⚠️ The uploaded file is blank or unreadable. Please download the official PDF from BaridiMob ('Télécharger reçu') and upload it.",
            file_hash=file_hash,
            raw_text=raw_text
        )

    # 3. Rule 4 Part A: Extract Transaction ID
    tx_id = extract_transaction_id(raw_text)
    if not tx_id:
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="MISSING_TX_ID",
            error_message="❌ Could not detect a valid Transaction ID (Numéro d'opération) on the receipt. Please upload the official BaridiMob PDF receipt.",
            file_hash=file_hash,
            raw_text=raw_text
        )

    # Check if tx_id already used
    if check_tx_id_exists(tx_id, db_path=db_path):
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="DUPLICATE_TX_ID",
            error_message=f"⚠️ Transaction ID `{tx_id}` has already been registered and used for another seat.",
            tx_id=tx_id,
            file_hash=file_hash,
            raw_text=raw_text
        )

    # Check BaridiMob system branding if document is detailed enough
    if len(raw_text) > 40 and not is_baridimob_system(raw_text):
        logger.warning("Uploaded receipt lacks BaridiMob or Algeria Poste branding keywords.")

    # Check Operation Type (TRANSFER / VIREMENT)
    op_type = extract_operation_type(raw_text)
    if op_type and op_type not in ["TRANSFER", "VIREMENT", "VIREMENTVERSCOMPTE", "VERSCOMPTE"]:
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="INVALID_OPERATION_TYPE",
            error_message=f"❌ Unsupported operation type: `{op_type}`. The receipt must be an account-to-account transfer (TRANSFER).",
            tx_id=tx_id,
            file_hash=file_hash,
            raw_text=raw_text
        )

    # 4. Rule 1: Destination Account Match
    account_matched, matched_val = matches_target_account(raw_text, settings.TARGET_RIP, settings.TARGET_CCP)
    if not account_matched:
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="INVALID_ACCOUNT",
            error_message=f"❌ Destination account mismatch! The receipt does not show a transfer to our RIP (`{settings.TARGET_RIP}`) or CCP (`{settings.TARGET_CCP}`).",
            tx_id=tx_id,
            operation_type=op_type,
            file_hash=file_hash,
            raw_text=raw_text
        )

    # 5. Rule 2: Amount Validation (500 DZD / configured amounts)
    parsed_amount = extract_amount(raw_text)
    if parsed_amount is None:
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="INVALID_AMOUNT",
            error_message=f"❌ Could not confirm the transfer amount. Expected `{settings.PAYMENT_AMOUNT:.2f} DZD`.",
            tx_id=tx_id,
            operation_type=op_type,
            file_hash=file_hash,
            raw_text=raw_text
        )
        
    # Check against primary PAYMENT_AMOUNT and any accepted amounts in ACCEPTED_AMOUNTS
    allowed_amounts = {settings.PAYMENT_AMOUNT}
    if hasattr(settings, "ACCEPTED_AMOUNTS") and settings.ACCEPTED_AMOUNTS:
        for a_str in settings.ACCEPTED_AMOUNTS.split(","):
            try:
                allowed_amounts.add(float(a_str.strip()))
            except ValueError:
                pass

    if not any(abs(parsed_amount - allowed) < 0.01 for allowed in allowed_amounts):
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="INVALID_AMOUNT",
            error_message=f"❌ Incorrect transfer amount! Found `{parsed_amount:.2f} DZD`, but `{settings.PAYMENT_AMOUNT:.2f} DZD` is required.",
            tx_id=tx_id,
            amount=parsed_amount,
            operation_type=op_type,
            file_hash=file_hash,
            raw_text=raw_text
        )

    # 6. Rule 3: Date Validation (Today / Yesterday / Grace window)
    dates = extract_dates(raw_text)
    dynamic_grace = None
    try:
        cfg_val = get_config_value("date_grace_days", db_path=db_path)
        if cfg_val is not None:
            dynamic_grace = int(cfg_val)
    except Exception:
        pass

    date_ok, found_date_str = is_date_valid(dates, grace_days=dynamic_grace)
    if not date_ok:
        reported_date = found_date_str or "Unknown"
        active_grace = dynamic_grace if dynamic_grace is not None else settings.DATE_GRACE_DAYS
        return ReceiptVerificationResult(
            is_valid=False,
            status_code="INVALID_DATE",
            error_message=f"❌ Receipt date ({reported_date}) is outside the permitted window. Transfers must be made within the last {active_grace} day(s) (today or yesterday).",
            tx_id=tx_id,
            amount=parsed_amount,
            tx_date=reported_date,
            operation_type=op_type,
            file_hash=file_hash,
            raw_text=raw_text
        )

    # All 4 rules passed!
    return ReceiptVerificationResult(
        is_valid=True,
        status_code="SUCCESS",
        error_message="",
        tx_id=tx_id,
        amount=parsed_amount,
        tx_date=found_date_str,
        account_matched=matched_val,
        operation_type=op_type,
        file_hash=file_hash,
        raw_text=raw_text
    )
