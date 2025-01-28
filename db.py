import pyodbc #provides a way to connect to a SQL Server database


server = 'Juggernaut' 
database = 'Ai_Blog' 

connection_string = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};'

conn = pyodbc.connect(connection_string)

print('Database connection established.')


# # Close the connection -- Not closing the connection here because it needs to be open for the Ai to continue posting to the database
# conn.close()