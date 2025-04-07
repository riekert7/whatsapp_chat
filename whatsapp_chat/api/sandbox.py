import frappe
from frappe import _
import re
import json
from typing import Any, Dict, Optional

class SandboxEnvironment:
    """Safe environment for executing custom functions"""
    
    # List of allowed modules and their attributes
    ALLOWED_MODULES = {
        'frappe': ['get_doc', 'get_value', 'get_list', 'get_all', 'format', 'format_datetime'],
        're': ['search', 'match', 'sub', 'findall'],
        'json': ['loads', 'dumps'],
        'datetime': ['datetime', 'date', 'time'],
        'str': ['split', 'join', 'strip', 'lower', 'upper', 'replace', 'format'],
        'list': ['append', 'extend', 'pop', 'remove', 'sort', 'reverse'],
        'dict': ['get', 'items', 'keys', 'values', 'update']
    }
    
    def __init__(self, exchange, dialogue, doc):
        self.exchange = exchange
        self.dialogue = dialogue
        self.doc = doc
        self._setup_globals()
    
    def _setup_globals(self):
        """Setup global variables and allowed modules"""
        self.globals = {
            'exchange': self.exchange,
            'dialogue': self.dialogue,
            'doc': self.doc,
            'frappe': self._create_safe_module('frappe'),
            're': self._create_safe_module('re'),
            'json': self._create_safe_module('json'),
            'datetime': self._create_safe_module('datetime'),
            'str': self._create_safe_module('str'),
            'list': self._create_safe_module('list'),
            'dict': self._create_safe_module('dict')
        }
    
    def _create_safe_module(self, module_name: str) -> Dict[str, Any]:
        """Create a safe module with only allowed attributes"""
        safe_module = {}
        if module_name in self.ALLOWED_MODULES:
            for attr in self.ALLOWED_MODULES[module_name]:
                if module_name == 'frappe':
                    safe_module[attr] = getattr(frappe, attr)
                elif module_name == 're':
                    safe_module[attr] = getattr(re, attr)
                elif module_name == 'json':
                    safe_module[attr] = getattr(json, attr)
                elif module_name == 'datetime':
                    safe_module[attr] = getattr(__import__('datetime'), attr)
                elif module_name in ['str', 'list', 'dict']:
                    safe_module[attr] = getattr(eval(module_name), attr)
        return safe_module
    
    def execute_function(self, function_script: str) -> Optional[Any]:
        """Execute the function script in a safe environment"""
        try:
            # Add return statement if not present
            if not re.search(r'return\s+', function_script):
                function_script = function_script.rstrip() + '\nreturn result'
            
            # Create function body
            function_body = f"""
def compute_value():
    {function_script}
"""
            
            # Create safe locals dict
            safe_locals = {}
            
            # Execute the function
            exec(function_body, self.globals, safe_locals)
            
            # Get the result
            result = safe_locals.get('compute_value')()
            
            return result
            
        except Exception as e:
            frappe.log_error(
                title=_("Error in custom function"),
                message=f"Error executing function: {str(e)}\n\nScript:\n{function_script}"
            )
            return None

def execute_custom_function(exchange, dialogue, doc, function_script: str) -> Optional[Any]:
    """Execute a custom function in a safe sandbox environment"""
    sandbox = SandboxEnvironment(exchange, dialogue, doc)
    return sandbox.execute_function(function_script) 