import pyodbc 

# Connection details
server = 'Juggernaut' 
database = 'Ai_Blog' 

# Connection string
connection_string = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};'

# Connect to the database
conn = pyodbc.connect(connection_string)

print('Database connection established.')


# # Close the connection
# conn.close()