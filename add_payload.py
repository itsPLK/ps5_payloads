import json
import subprocess
import re
import hashlib
import urllib.request
import sys
from datetime import datetime

JSON_FILE = "ps5_payloads.json"

def get_repo_info(url):
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if match:
        owner = match.group(1)
        repo = match.group(2).rstrip('/')
        return owner, repo
    return None, None

def calculate_checksum(url):
    print(f"  Calculating checksum for {url}...")
    sha256 = hashlib.sha256()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"  Error calculating checksum: {e}")
        return None

def reorder_item(item):
    order = ["name", "filename", "url", "source", "description", "last_update", "version", "checksum"]
    new_item = {}
    for key in order:
        if key in item:
            new_item[key] = item[key]
    # Add any remaining keys
    for key in item:
        if key not in new_item:
            new_item[key] = item[key]
    return new_item

def add_payload():
    print("Add New PS5 Payload")
    print("-" * 20)
    
    url = input("GitHub Download URL: ").strip()
    if not url:
        print("Error: URL is required.")
        return
        
    owner, repo = get_repo_info(url)
    if not owner:
        print("Error: Could not parse GitHub owner/repo from URL.")
        return
        
    description = input("Description (optional): ").strip()
    
    print(f"Fetching latest release info for {owner}/{repo}...")
    try:
        cmd = ["gh", "api", f"repos/{owner}/{repo}/releases/latest"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        release = json.loads(result.stdout)
    except Exception as e:
        print(f"Error fetching release info: {e}")
        return

    filename_match = re.search(r"/([^/]+\.(elf|bin))$", url)
    target_filename = filename_match.group(1) if filename_match else None
    
    assets = release.get("assets", [])
    selected_asset = None
    if target_filename:
        for asset in assets:
            if asset["name"] == target_filename:
                selected_asset = asset
                break
                
    if not selected_asset and assets:
        for asset in assets:
            if asset["name"].endswith((".elf", ".bin")):
                selected_asset = asset
                break
                
    if not selected_asset:
        print("Error: Could not find a suitable .elf or .bin asset in the latest release.")
        return

    try:
        with open(JSON_FILE, "r") as f:
            payloads = json.load(f)
    except FileNotFoundError:
        payloads = []

    source_url = f"https://github.com/{owner}/{repo}/releases"
    if any(p.get("source") == source_url for p in payloads):
        print(f"Error: A payload from {source_url} already exists in the JSON.")
        return

    new_item = {
        "name": repo,
        "filename": selected_asset["name"],
        "url": selected_asset["browser_download_url"],
        "source": source_url,
        "description": description,
        "last_update": release["published_at"][:10],
        "version": release["tag_name"],
        "checksum": calculate_checksum(selected_asset["browser_download_url"])
    }
    
    payloads.append(new_item)
    
    # Sort and reorder
    payloads.sort(key=lambda x: x.get("last_update", ""), reverse=True)
    payloads = [reorder_item(p) for p in payloads]
    
    with open(JSON_FILE, "w") as f:
        json.dump(payloads, f, indent=2)
        
    print(f"\nSuccessfully added {repo} to {JSON_FILE}")

if __name__ == "__main__":
    add_payload()
