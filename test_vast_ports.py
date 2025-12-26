import requests
import json

API_KEY = "aedf78cb67968495b0e91b71886b7444fd24d9146ce0da4c12cd5a356451d6c7"
API_URL = "https://console.vast.ai/api/v0/instances/"

headers = {"Authorization": f"Bearer {API_KEY}"}
r = requests.get(API_URL, headers=headers)
data = r.json()

print("=" * 80)
print("Instâncias Running:")
print("=" * 80)

for inst in data.get("instances", []):
    if inst.get("actual_status") == "running":
        print(f"\nID: {inst.get('id')}")
        print(f"  ssh_host: {inst.get('ssh_host')}")
        print(f"  ssh_port: {inst.get('ssh_port')}")
        print(f"  public_ipaddr: {inst.get('public_ipaddr')}")
        
        ports = inst.get("ports", {})
        print(f"  ports keys: {list(ports.keys())}")
        
        # Verifica porta 22/tcp
        if "22/tcp" in ports:
            port_22 = ports["22/tcp"]
            print(f"  22/tcp: {port_22}")
        
        # Verifica porta 3000/tcp
        if "3000/tcp" in ports:
            port_3000 = ports["3000/tcp"]
            print(f"  3000/tcp: {port_3000}")

print("\n" + "=" * 80)

