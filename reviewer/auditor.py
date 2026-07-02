from google import genai
from reviewer.cache import get_file_hash, is_file_modified, update_cache
from reviewer.ast_parser import analyze_ast

def process_file(filepath: str, client: genai.Client) -> dict:
    """Audit a single file: check cache, parse AST, and run LLM review."""
    try:
        file_hash = get_file_hash(filepath)
        
        # Optimization: Skip unchanged files
        if not is_file_modified(filepath, file_hash):
            return None
        
        ast_issues, code_content = analyze_ast(filepath)
        
        # Ingest structural alerts into the LLM context prompt
        prompt = f"""
        Perform a strict code audit on the following source file.
        AST Static Analysis Alerts: {ast_issues if ast_issues else "None"}
        
        CODE:
        {code_content}
        
        OUTPUT FORMAT:
        Return a concise bullet-point review highlighting only critical memory leaks, concurrency locks, and complexity errors. 
        If clean, output "No issues found."
        """
        
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )
        
        # Mark as scanned in database
        update_cache(filepath, file_hash)
        
        return {
            "file": filepath, 
            "issues": ast_issues, 
            "llm_feedback": response.text.strip()
        }
    except Exception as e:
        return {"file": filepath, "error": str(e)}
