import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if '#' in line:
            # Simple heuristic: find the last '#' or assume the first '#' is the comment
            # To be safe against strings, we just split on the first '#' 
            parts = line.split('#', 1)
            code_part = parts[0]
            comment_part = parts[1].strip()
            
            # strip leading # from comment_part if it was ##
            while comment_part.startswith('#'):
                comment_part = comment_part[1:].strip()
                
            if comment_part.startswith('='): # skip decorative comments
                new_lines.append(line)
            elif not comment_part:
                new_lines.append(line)
            else:
                if comment_part.startswith('INFO = '):
                    new_lines.append(f"{code_part}# {comment_part}")
                else:
                    new_lines.append(f"{code_part}# INFO = {comment_part}")
        else:
            new_lines.append(line)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

for file in ['app/__init__.py', 'app/models.py', 'app/routes.py']:
    print(f"Processing {file}")
    process_file(file)
print("Done.")
