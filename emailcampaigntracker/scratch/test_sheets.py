import dotenv, os
dotenv.load_dotenv(override=True)
from app.integrations.google_sheets import client

if client:
    try:
        files = client.list_spreadsheet_files()
        print('Available spreadsheets:')
        for f in files:
            print(f"- Name: {f.get('name')}, ID: {f.get('id')}")
    except Exception as e:
        print('Error listing files:', e)
else:
    print('No client authorized')
