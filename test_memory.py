import os
from dotenv import load_dotenv
from hindsight_client import Hindsight

load_dotenv()
client = Hindsight(
    base_url=os.getenv("HINDSIGHT_URL"),
    api_key=os.environ["HINDSIGHT_API_KEY"],
)

try:
    client.create_bank(bank_id="test-bank", name="Test")
except Exception as e:
    print("bank note:", e)

client.retain(bank_id="test-bank", content="Alice works at Google as an engineer")
print("Retained OK")

result = client.recall(bank_id="test-bank", query="What does Alice do?")
for m in result.results:
    print("RECALLED:", m.text)

client.close()