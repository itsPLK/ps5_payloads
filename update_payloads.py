import json
import subprocess
import re
import hashlib
import urllib.request
import sys
from datetime import datetime

JSON_FILE = "ps5_payloads.json"

def get_repo_info(url):
    # Extract owner and repo from various GitHub URL formats
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if match:
        owner = match.group(1)
        repo = match.group(2).rstrip('/')
        if repo.endswith('.git'):
            repo = repo[:-4]
        if repo == 'releases': # handle case where it's github.com/owner/repo/releases
            # Need to re-parse
            parts = url.split('/')
            idx = parts.index('github.com')
            owner = parts[idx+1]
            repo = parts[idx+2]
        return owner, repo
    return None, None

def get_latest_release(owner, repo):
    try:
        # Fetch latest release using gh CLI
        cmd = ["gh", "api", f"repos/{owner}/{repo}/releases/latest"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error fetching {owner}/{repo}: {e}")
        return None

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
            
        # Filter for .bin or .elf
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
            new_url = selected_asset["browser_download_url"]
            new_filename = selected_asset["name"]
            new_version = release["tag_name"]
            new_date = release["published_at"][:10]
            
            # Use repository name as proposed name
            proposed_name = repo_name
            final_name = proposed_name
            
            # Interactive check for name change
            if "name" in item and item["name"] != proposed_name:
                print(f"  ! Name mismatch for {repo_name}:")
                print(f"    Existing: '{item['name']}'")
                print(f"    Proposed: '{proposed_name}'")
                choice = input("    Keep existing name? (Y/n): ").strip().lower()
                if choice != 'n':
                    final_name = item["name"]
                    print(f"    Keeping '{final_name}'")
                else:
                    print(f"    Updating to '{final_name}'")
            
            needs_update = (
                item.get("url") != new_url or 
                item.get("version") != new_version or
                item.get("name") != final_name or
                "checksum" not in item
            )
            
            if needs_update:
                print(f"  Updating {item.get('filename', 'new')} -> {new_filename}")
                item["name"] = final_name
                item["version"] = new_version
                item["filename"] = new_filename
                item["url"] = new_url
                item["last_update"] = new_date
                
                if "checksum" not in item or item.get("url") != new_url:
                    item["checksum"] = calculate_checksum(new_url)
                
                updated = True
            else:
                print(f"  Already up to date ({new_version})")
        else:
            print(f"  No suitable asset found for {source}")
                
    # Always sort and reorder
    payloads.sort(key=lambda x: x.get("last_update", ""), reverse=True)
    payloads = [reorder_item(p) for p in payloads]
    
    with open(JSON_FILE, "w") as f:
        json.dump(payloads, f, indent=2)
    
    if updated:
        print(f"\nSuccessfully updated and sorted {JSON_FILE}")
    else:
        print(f"\nSorted {JSON_FILE} (no updates found).")

if __name__ == "__main__":
    update_payloads()
