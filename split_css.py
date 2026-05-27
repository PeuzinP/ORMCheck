import re
import os

def parse_css(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Remove comments
    content = re.sub(r'/\*[\s\S]*?\*/', '', content)
    
    # A simple parser for top-level blocks and @media blocks
    blocks = []
    
    # Regex to capture @media or standard selectors
    # This is a bit tricky, let's use a bracket counter
    
    current_block = ""
    bracket_level = 0
    
    for char in content:
        current_block += char
        if char == '{':
            bracket_level += 1
        elif char == '}':
            bracket_level -= 1
            if bracket_level == 0:
                blocks.append(current_block.strip())
                current_block = ""
                
    return blocks

def categorize_block(block):
    # Determine which file the block belongs to
    if block.startswith('@import') or block.startswith('@charset'):
        return None
        
    if block.startswith(':root') or block.startswith('@font-face'):
        return '_variables.css'
        
    # extract the selector (everything before the first '{')
    selector = block.split('{')[0].strip()
    
    if block.startswith('@media'):
        return '_layout.css' # media queries usually affect layout
        
    if re.match(r'^[a-zA-Z*]', selector) and not '.' in selector and not '#' in selector:
        return 'base.css'
        
    layout_keywords = ['grid', 'layout', 'sidebar', 'main', 'hero', 'shell', 'container', 'page', 'topbar', 'header']
    if any(k in selector for k in layout_keywords) or 'display: grid' in block or 'display: flex' in block:
        return '_layout.css'
        
    util_keywords = ['hidden', 'muted', 'oculto', 'text-', 'mt-', 'mb-', 'pt-', 'pb-']
    if any(k in selector for k in util_keywords):
        return '_utilities.css'
        
    return '_components.css'

def main():
    style_blocks = parse_css('web/static/css/style.css')
    keepedu_blocks = parse_css('web/static/css/keepedu-theme.css')
    
    all_blocks = style_blocks + keepedu_blocks
    
    files = {
        '_variables.css': [],
        'base.css': [],
        '_layout.css': [],
        '_components.css': [],
        '_utilities.css': []
    }
    
    for block in all_blocks:
        cat = categorize_block(block)
        if cat:
            files[cat].append(block)
            
    # append to existing modular files
    for filename, blocks in files.items():
        path = os.path.join('web/static/css', filename)
        with open(path, 'a', encoding='utf-8') as f:
            f.write('\n\n/* --- Migrated from style.css / keepedu-theme.css --- */\n\n')
            f.write('\n\n'.join(blocks))

if __name__ == '__main__':
    main()
