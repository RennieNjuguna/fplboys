import os
import sys
import subprocess
from pathlib import Path

# Setup environment
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')

import django
django.setup()

from django.core.management import call_command
from django.conf import settings


def application(environ, start_response):
    """
    Temporary WSGI helper to run collectstatic, migrations, and verify symlinks via browser.
    """
    logs = []
    
    # 1. Run Migrations
    try:
        call_command('migrate', interactive=False)
        logs.append("✅ Database migrations applied successfully.")
    except Exception as e:
        logs.append(f"❌ Migration error: {e}")

    # 2. Collect Static Files
    try:
        call_command('collectstatic', interactive=False, clear=True)
        logs.append(f"✅ Static files collected into: {settings.STATIC_ROOT}")
    except Exception as e:
        logs.append(f"❌ Collectstatic error: {e}")

    # 3. Check / Create Symlink to subdomain document root
    # Typically: /home/username/fpl.zaharaflowers.com/static -> /home/username/fpl_boyz/staticfiles
    possible_roots = [
        BASE_DIR.parent / 'fpl.zaharaflowers.com',
        Path(f"/home/{BASE_DIR.parts[2]}/fpl.zaharaflowers.com") if len(BASE_DIR.parts) > 2 else None,
    ]
    
    symlink_created = False
    for doc_root in possible_roots:
        if doc_root and doc_root.exists() and doc_root.is_dir():
            target_static = doc_root / 'static'
            src_static = Path(settings.STATIC_ROOT)
            if src_static.exists():
                try:
                    if not target_static.exists() and not target_static.is_symlink():
                        os.symlink(str(src_static), str(target_static))
                        logs.append(f"✅ Created symlink: {target_static} -> {src_static}")
                        symlink_created = True
                    else:
                        logs.append(f"ℹ️ Static destination already exists at: {target_static}")
                except Exception as e:
                    logs.append(f"⚠️ Symlink notice: {e}")

    output = f"""<!DOCTYPE html>
<html>
<head>
    <title>FPL Boyz Deployment Helper</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; line-height: 1.6; }}
        .card {{ max-width: 650px; margin: auto; background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 28px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        h1 {{ color: #00ff87; font-size: 22px; margin-top: 0; }}
        .log-item {{ background: #0f172a; border-left: 4px solid #38bdf8; padding: 10px 14px; margin: 8px 0; border-radius: 6px; font-family: monospace; font-size: 13px; }}
        .next-steps {{ background: #3b0764; border: 1px solid #7e22ce; padding: 14px; border-radius: 10px; margin-top: 20px; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 FPL Boyz - cPanel Setup Complete</h1>
        <p>Execution logs:</p>
        {''.join(f'<div class="log-item">{log}</div>' for log in logs)}
        <div class="next-steps">
            <strong>Next Step:</strong> Open <code>passenger_wsgi.py</code> in cPanel File Manager and revert it back to the normal Django WSGI code, then click <strong>Restart</strong> in Setup Python App.
        </div>
    </div>
</body>
</html>"""

    status = '200 OK'
    response_headers = [('Content-type', 'text/html; charset=utf-8')]
    start_response(status, response_headers)
    return [output.encode('utf-8')]
