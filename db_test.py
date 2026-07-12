import pyodbc

try:
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=LAPTOP-PAVILION\\SQLEXPRES;"
        "DATABASE=SalesAnalyticsDB;"
        "Trusted_Connection=yes;"
    )

    print("Connected Successfully!")
    conn.close()

except Exception as e:
    print(e)