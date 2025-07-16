import requests
import json
from datetime import datetime

url = "https://api.llama.fi/protocols"

response = requests.get(url)

if response.status_code == 200:
    data = response.json()

    # Generowanie nazwy pliku z datą i godziną
    timestamp = datetime.now().strftime("%Y-%m-%d %H_%M")
    filename = f"data/{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
else:
    print(f"Błąd: {response.status_code}")
