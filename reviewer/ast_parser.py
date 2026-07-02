import ast
from typing import List, Tuple

def analyze_ast(filepath: str) -> Tuple[List[str], str]:
    """Compile source file into an AST and scan for structural rules."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        code = f.read()
    
    issues = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            # Check 1: Detect overly nested loops (potential O(N^2) complexity)
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if child != node and isinstance(child, (ast.For, ast.While)):
                        issues.append(f"Line {node.lineno}: Overly nested loop detected.")
            
            # Check 2: Detect unsafe empty try-except blocks swallowing exceptions
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if handler.type is None or (isinstance(handler.type, ast.Name) and handler.type.id == "Exception"):
                        if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                            issues.append(f"Line {handler.lineno}: Unsafe empty try-except block swallowing errors.")
                            
    except SyntaxError:
        issues.append("Syntax Error: Could not compile file into AST.")
    
    return issues, code
