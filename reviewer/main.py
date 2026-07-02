import os
import argparse
from concurrent.futures import ThreadPoolExecutor
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import modular components using package namespace
from reviewer.cache import init_cache
from reviewer.auditor import process_file

def scan_directory(dir_path: str, client: genai.Client):
    """Walk directory tree, collect source files, and audit them concurrently."""
    files_to_scan = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.endswith(".py"):
                files_to_scan.append(os.path.join(root, file))
                
    init_cache()
    print(f"Scanning {len(files_to_scan)} Python source files using 4 thread pool workers...")
    
    # Run audit pipeline concurrently
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda f: process_file(f, client), files_to_scan))
        
    # Log audit results
    for res in results:
        if res:
            if "error" in res:
                print(f"\n[ERR] {res['file']}: {res['error']}")
            elif "llm_feedback" in res:
                print(f"\n--- Code Audit: {res['file']} ---")
                if res["issues"]:
                    print("AST Compiler Warnings:")
                    for iss in res["issues"]:
                        print(f"  - {iss}")
                print("LLM Security & Complexity Suggestions:")
                print(res["llm_feedback"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AST-Parsed Concurrent Code Reviewer")
    parser.add_argument("--dir", required=True, help="Directory path to scan")
    args = parser.parse_args()
    
    api_key = os.getenv("GEMINI_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] Neither GEMINI_KEY nor GOOGLE_API_KEY environment variable is set.")
        exit(1)
        
    client = genai.Client(api_key=api_key)
    scan_directory(args.dir, client)
