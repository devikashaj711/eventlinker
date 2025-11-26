import mysql.connector

# --- Database Configuration for AWS RDS MySQL ---
db_config = {
    'host': 'event-linker-database.cvqwg0sgw0ho.us-east-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'eventlinker123',
    'database': 'eventlinker_db'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        print("Successfully connected to the database!")
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to AWS RDS database: {err}")
        return None


def close_db_connection(conn, cursor=None):
    if cursor:
        try:
            cursor.close()
            print("Cursor closed.")
        except mysql.connector.Error as err:
            print(f"Error closing cursor: {err}")
    if conn:
        try:
            conn.close()
            print("Database connection closed.")
        except mysql.connector.Error as err:
            print(f"Error closing connection: {err}")



if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        print("Connection successful!")
        close_db_connection(conn)

