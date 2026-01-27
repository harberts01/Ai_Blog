import pyodbc


server = 'DESKTOP-K59D2AU'  # Updated to match actual computer name
database = 'Ai_Blog' 

connection_string = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'

try:
    conn = pyodbc.connect(connection_string)
    print('Database connection established.')
except pyodbc.Error as e:
    print(f'Database connection failed: {e}')
    conn = None

print('Database connection established.')


# # Close the connection -- Not closing the connection here because it needs to be open for the Ai to continue posting to the database
# conn.close()