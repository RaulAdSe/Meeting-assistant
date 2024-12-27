import os
from pathlib import Path
from .connection import DatabaseConnection

def init_database():
    """Initialize database with schema."""
    db = DatabaseConnection.get_instance()
    
    # Get the absolute path to the schema file
    current_dir = Path(__file__).parent
    schema_path = current_dir / 'schema.sql'
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
        
    print(f"Loading schema from: {schema_path}")
    
    # Read schema file
    with open(schema_path, 'r') as f:
        schema = f.read()
        
    if not schema.strip():
        raise ValueError("Schema file is empty")
        
    # Connect and execute schema
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            # Execute each statement separately
            statements = schema.split(';')
            for statement in statements:
                if statement.strip():
                    print(f"Executing: {statement.strip()[:100]}...")  # Print first 100 chars
                    cur.execute(statement)
            
        conn.commit()
        print("Database initialized successfully")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    init_database()