import json
import subprocess
import re
import hashlib
import urllib.request
import sys
import os
from datetime import datetime

JSON_FILE = "ps5_payloads.json"
PAYLOADS_DIR = "payloads"
BASE_URL = "https://itsplk.github.io/ps5_payloads/payloads"

def get_repo_info(url):
    # Extract owner and repo from various GitHub URL formats
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if match:
        owner = match.group(1)
        repo = match.group(2).rstrip('/')
        if repo.endswith('.git'):
            repo = repo[:-4]
        if repo == 'releases':
            parts = url.split('/')
            idx = parts.index('github.com')
            owner = parts[idx+1]
            repo = parts[idx+2]
        return owner, repo
    return None, None

def get_latest_release(owner, repo):
    try:
        cmd = ["gh", "api", f"repos/{owner}/{repo}/releases/latest"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error fetching {owner}/{repo}: {e}")
        return None

def download_file(url, filename):
    if not os.path.exists(PAYLOADS_DIR):
        os.makedirs(PAYLOADS_DIR)
    
    filepath = os.path.join(PAYLOADS_DIR, filename)
    print(f"  Downloading {filename}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open(filepath, 'wb') as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"  Error downloading {filename}: {e}")
        return False

def calculate_checksum(filepath):
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"  Error calculating checksum: {e}")
        return None

def reorder_item(item):
    order = ["name", "filename", "url", "source", "source_direct", "description", "last_update", "version", "checksum"]
    new_item = {}
    for key in order:
        if key in item:
            new_item[key] = item[key]
    for key in item:
        if key not in new_item:
            new_item[key] = item[key]
    return new_item

def update_payloads():
    try:
        with open(JSON_FILE, "r") as f:
            payloads = json.load(f)
    except FileNotFoundError:
        print(f"Error: {JSON_FILE} not found.")
        return

    updated = False
    for item in payloads:
        source = item.get("source")
        if not source or "github.com" not in source:
            # Handle ps5debug case
            if item.get("name") == "ps5debug":
                if not item["url"].startswith(BASE_URL):
                     item["url"] = f"{BASE_URL}/{item['filename']}"
                     updated = True
            continue
            
        owner, repo_name = get_repo_info(source)
        if not owner:
            continue
            
        print(f"Checking {owner}/{repo_name}...")
        release = get_latest_release(owner, repo_name)
        if not release:
            continue
            
        assets = release.get("assets", [])
        if not assets:
            continue
            
        preferred_ext = ".bin" if "etaHEN" in repo_name else ".elf"
        
        def score_asset(name):
            name_lower = name.lower()
            if not name.endswith(preferred_ext):
                return -1
            score = 0
            if "ps5" in name_lower:
                score += 10
            if "ps4" in name_lower:
                score -= 10
            if "install" in name_lower:
                score -= 5
            score -= len(name) / 100.0 
            return score

        selected_asset = None
        best_score = -2
        for asset in assets:
            score = score_asset(asset["name"])
            if score > best_score:
                best_score = score
                selected_asset = asset
        
        if selected_asset and best_score > -1:
            gh_url = selected_asset["browser_download_url"]
            original_filename = selected_asset["name"]
            new_version = release["tag_name"]
            new_date = release["published_at"][:10]
            
            # Format: repo_name_version.ext
            ext = original_filename.rsplit('.', 1)[1] if '.' in original_filename else "bin"
            new_filename = f"{repo_name}_{new_version}.{ext}"
            
            proposed_name = repo_name
            final_name = item.get("name", proposed_name)
            
            filepath = os.path.join(PAYLOADS_DIR, new_filename)
            needs_download = (
                item.get("version") != new_version or 
                item.get("filename") != new_filename or
                not os.path.exists(filepath)
            )
            
            if needs_download:
                print(f"  Update found: {item.get('version', 'none')} -> {new_version}")
                
                # Delete old file
                if item.get("filename") and item["filename"] != new_filename:
                    old_path = os.path.join(PAYLOADS_DIR, item["filename"])
                    if os.path.exists(old_path):
                        print(f"  Removing old file {item['filename']}...")
                        os.remove(old_path)

                if download_file(gh_url, new_filename):
                    item["name"] = final_name
                    item["version"] = new_version
                    item["filename"] = new_filename
                    item["url"] = f"{BASE_URL}/{new_filename}"
                    item["source_direct"] = gh_url
                    item["last_update"] = new_date
                    item["checksum"] = calculate_checksum(filepath)
                    updated = True
                else:
                    print(f"  Skipping update due to download failure.")
            else:
                print(f"  Already up to date ({new_version})")
        else:
            print(f"  No suitable asset found for {source}")
                
    payloads.sort(key=lambda x: x.get("last_update", ""), reverse=True)
    payloads = [reorder_item(p) for p in payloads]
    
    with open(JSON_FILE, "w") as f:
        json.dump(payloads, f, indent=2)
    
    if updated:
        print(f"\nSuccessfully updated files and sorted {JSON_FILE}")
    else:
        print(f"\nSorted {JSON_FILE} (no new files downloaded).")

if __name__ == "__main__":
    update_payloads()
