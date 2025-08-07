# filename: main_p.py

import os
import sys
from supabase import create_client, Client

def init_connection() -> Client:
    """Initializes and returns a Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("🔴 ERROR: Supabase credentials not set in environment variables.")
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        print(f"🔴 ERROR: Could not initialize Supabase client. Reason: {e}")
        return None

def wipe_to_process_table(supabase: Client) -> bool:
    """Deletes all records from the 'to_process' table."""
    try:
        print("Attempting to wipe 'to_process' table...")
        # The filter `neq('bot', 'a-value-that-is-never-used')` selects all rows to delete.
        data, count = supabase.table('to_process').delete().neq('bot', 'a-value-that-will-never-be-used').execute()
        print(f"✅ Success: Wiped 'to_process' table.")
        return True
    except Exception as e:
        print(f"🔴 ERROR: Could not wipe 'to_process' table. Reason: {e}")
        return False

def main():
    """Main execution function."""
    print("--- Starting Pre-processing Script (main_p.py) ---")
    supabase = init_connection()
    if not supabase:
        sys.exit(1) # Exit with error code

    if wipe_to_process_table(supabase):
        print("👍")
        print("--- Pre-processing Finished Successfully ---")
        sys.exit(0) # Exit with success code
    else:
        print("👎")
        print("--- Pre-processing Failed ---")
        sys.exit(1) # Exit with error code

if __name__ == "__main__":
    main()
