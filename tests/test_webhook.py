import requests
import json
import time

def test_webhook():
    url = "http://localhost:8000/webhook"
    
    payload = {
        "typeWebhook": "incomingMessageReceived",
        "instanceData": {
            "idInstance": 1234,
            "wid": "11001234567@c.us",
            "typeInstance": "whatsapp"
        },
        "timestamp": int(time.time()),
        "idMessage": f"MSG-{int(time.time())}",
        "senderData": {
            "chatId": "123456789@c.us",
            "senderName": "Test User",
            "senderContactName": "Test User"
        },
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {
                "textMessage": "Hello, bot! This is a test message."
            }
        }
    }

    try:
        print(f"Sending webhook to {url}...")
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Webhook test passed!")
        else:
            print("❌ Webhook test failed!")
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("Make sure the app is running (docker-compose up or uvicorn)")

if __name__ == "__main__":
    test_webhook()
