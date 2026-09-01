
##CONNETION
import os
from dotenv import load_dotenv

load_dotenv()


import mysql.connector 

try:
    conn = mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user=os.getenv("USERNAME"),
        password=os.getenv("PASSWORD"),
        database=os.getenv("DATABASE")

    )
##CURSOR
    cursor = conn.cursor()

    
##CREATION

    cursor.execute("""CREATE TABLE user(
    
    
    )""")
##PASSER CONN AUX REPO


finally:
    cursor.close()
    conn.close()