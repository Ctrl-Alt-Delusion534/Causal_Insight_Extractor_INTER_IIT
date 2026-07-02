import hashlib
import sqlite3

DB_PATH = "scanner_cache.db"

def init_cache():
    """Create the local cache database and table if they do not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_cache (
            filepath TEXT PRIMARY KEY,
            sha256 TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_file_hash(filepath: str) -> str:
    """Read file raw bytes and compute its unique SHA-256 fingerprint."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def is_file_modified(filepath: str, current_hash: str) -> bool:
    """Compare local file hash with stored database hash to detect changes."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sha256 FROM file_cache WHERE filepath = ?", (filepath,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0] == current_hash:
        return False  # Hash matches, file has not changed
    return True  # Hash does not match (or new file), file changed

def update_cache(filepath: str, current_hash: str):
    """Save the updated file signature in the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO file_cache (filepath, sha256) VALUES (?, ?)", (filepath, current_hash))
    conn.commit()
    conn.close()
