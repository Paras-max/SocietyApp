import psycopg2

DATABASE_URL = "postgresql://postgres:1234vedant1234@db.vmbddsodiarujdylmdjr.supabase.co:5432/postgres"

try:
    conn = psycopg2.connect(DATABASE_URL)
    print("Connection Successful!")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
