import requests

def main():
    url = "http://127.0.0.1:8000/random"
    payload = {"key": "RANDOM_NUM"}

    try:
        # Set a longer timeout to allow heavy computation
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)

        data = response.json()
        print("\n✅ Random value received:")
        print(data["random_value"])

    except requests.Timeout:
        print("❌ Request timed out. The server took too long to respond.")
    except requests.ConnectionError:
        print("❌ Could not connect to the server at http://127.0.0.1:8000")
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    main()
