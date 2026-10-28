import httpx

BASE_URL = "http://127.0.0.1:8000/v1/chat/completions"

print("=" * 60)
print("🛡️  HALLUCINATION GUARD — MANUAL TEST CONSOLE")
print("Type any prompt to test the security filters.")
print("Type 'exit' or 'quit' to stop.")
print("=" * 60)

with httpx.Client() as client:
    while True:
        try:
            user_input = input("\nEnter your prompt > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting...")
                break

            response = client.post(BASE_URL, json={"prompt": user_input})

            if response.status_code == 200:
                data = response.json()
                print(f"\n[Status]: {data['status']}")
                print(f"[Latency]: {data['latency_ms']} ms")
                print(f"[Post-Flight Verdict]: {'⚠️ Hallucination Detected' if data['guard_report']['hallucination_detected'] else '✅ Passed'}")
                print(f"[Output]:\n{data['output']}")

            elif response.status_code == 400:
                # Pre-flight blocked the prompt
                err = response.json()
                print(f"\n🚫 [BLOCKED BY PRE-FLIGHT GUARD]:")
                print(f"Reason: {err['detail']['reason']}")

            else:
                print(f"\n[Error {response.status_code}]: {response.text}")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except httpx.ConnectError:
            print("\n❌ Could not connect. Make sure your server is running (`uvicorn main:app --reload`)")
            break