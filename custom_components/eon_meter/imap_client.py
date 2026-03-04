import imaplib
import email
from email.header import decode_header
import logging
import io
import re
from datetime import datetime
import openpyxl

_LOGGER = logging.getLogger(__name__)

def _decode_str(s):
    """Decode email header string."""
    try:
        if not s:
            return ""
        decoded_list = decode_header(s)
        parts = []
        for content, encoding in decoded_list:
            if isinstance(content, bytes):
                if encoding:
                    try:
                        parts.append(content.decode(encoding))
                    except LookupError:
                        parts.append(content.decode("utf-8", errors="replace"))
                    except Exception:
                        parts.append(content.decode("utf-8", errors="replace"))
                else:
                    parts.append(content.decode("utf-8", errors="replace"))
            else:
                parts.append(str(content))
        return "".join(parts)
    except Exception as e:
        _LOGGER.warning(f"Error decoding string: {e}")
        return str(s)

def fetch_from_email(host, port, user, password, subject_filter):
    """Sync function to fetch and process email attachment."""
    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(user, password)
        mail.select("inbox")
        
        # Search for subject (server side filter)
        # Try UTF-8 search first for special chars
        try:
            typ, data = mail.search(None, 'CHARSET', 'UTF-8', f'(SUBJECT "{subject_filter}")')
        except Exception:
            # Fallback to standard
            typ, data = mail.search(None, f'(SUBJECT "{subject_filter}")')
        
        if not data or not data[0]:
            _LOGGER.info(f"No emails found with subject containing: {subject_filter}")
            mail.close()
            mail.logout()
            return []
            
        # Get list of IDs
        msg_ids = data[0].split()
        msg_ids.reverse() # Sort descending (newest first)
        
        rows = []
        found_attachment = False

        # Iterate through newest emails to find one with valid attachment
        # We limit check to top 15 to avoid endless loop if common subject word
        for mid in msg_ids[:15]: 
             # Fetch HEADER only first to verify subject
             typ, hdr_data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])')
             if not hdr_data or not hdr_data[0]:
                 continue

             hdr_msg = email.message_from_bytes(hdr_data[0][1])
             subject_decoded = _decode_str(hdr_msg["Subject"])
             
             # 1. Strict substring check (Partial match, case-insensitive)
             # User requirement: "előtte, és utánna is lehessen benne más szöveg"
             if subject_filter.lower() not in subject_decoded.lower():
                 _LOGGER.debug(f"Skipping email '{subject_decoded}' - filter text not found.")
                 continue

             # 2. Fetch full body if subject matches
             typ, msg_data = mail.fetch(mid, '(RFC822)')
             if not msg_data or not msg_data[0]:
                 continue

             raw_email = msg_data[0][1]
             msg = email.message_from_bytes(raw_email)
            
             _LOGGER.info(f"Processing email: '{subject_decoded}' from {msg['Date']}")
            
             # Walk through parts
             for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue
                    
                filename = part.get_filename()
                if not filename: continue
                filename = _decode_str(filename)
                
                if filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls"):
                    _LOGGER.info(f"Found attachment: {filename}")
                    try:
                        file_data = part.get_payload(decode=True)
                        excel_rows = _parse_excel(io.BytesIO(file_data))
                        if excel_rows:
                            rows.extend(excel_rows)
                            found_attachment = True
                            break 
                    except Exception as e:
                        _LOGGER.error(f"Error processing attachment {filename}: {e}")
            
             if found_attachment:
                break # Found data, stop looking
                
        mail.close()
        mail.logout()
        
        return rows
        
    except Exception as e:
        _LOGGER.error(f"IMAP Error: {e}")
        raise Exception(f"IMAP Hiba: {e}") from e

def _parse_excel(file_obj):
    rows = []
    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
        ws = wb.active # Assume first sheet
        
        date_pattern = re.compile(r"^\d{4}\.\d{2}\.\d{2}\. \d{2}:\d{2}$")
        
        # Read headers first if possible, or just assign column indexes
        headers = []
        for i, col in enumerate(ws.iter_cols(1, ws.max_column, 1, 1, values_only=True)):
             head_val = col[0]
             if head_val:
                 headers.append(str(head_val).strip())
             else:
                 headers.append(f"Col_{i}")

        for row in ws.iter_rows(values_only=True):
            if not row or len(row) < 3: continue
            
            col_a = row[0]
            
            dt = None
            if isinstance(col_a, datetime):
                dt = col_a
            else:
                s_val = str(col_a).strip() if col_a else ""
                if date_pattern.match(s_val):
                    try:
                        dt = datetime.strptime(s_val, "%Y.%m.%d. %H:%M")
                    except ValueError:
                        pass
            
            if not dt:
                continue

            ts_ms = int(dt.timestamp() * 1000)

            # Map dynamically all columns
            mapped_row = {
                "Timestamp": f"/Date({ts_ms})/",
                "Datum": dt.strftime("%Y-%m-%d"),
                "Pod": "EmailData"
            }

            for idx, val in enumerate(row):
                if idx == 0: continue # Skip time column
                
                col_name = headers[idx] if idx < len(headers) else f"Col_{idx}"
                # For compatibility with API, map indexing 1 to Num1 (+A) and 2 to Num2 (-A)
                if idx == 1:
                    mapped_row["Num1"] = val if val is not None else 0.0
                elif idx == 2:
                    mapped_row["Num2"] = val if val is not None else 0.0
                
                # Also store the literal column name from the Excel
                mapped_row[col_name] = val if val is not None else 0.0

            rows.append(mapped_row)
                
    except Exception as e:
        _LOGGER.error(f"Excel Parse Error: {e}")
        
    return rows
