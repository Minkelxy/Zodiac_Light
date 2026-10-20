"""Independently compare the additional panel's actual Gerber, holes and material."""
import hashlib
import json
from pathlib import Path
import audit_twelve_options_geometry as auditor

HW=Path(__file__).resolve().parents[1]
auditor.OUT=HW/'variants/horse-snake-spacers'
if __name__=='__main__':
    result=auditor.audit()
    paths=[Path(__file__),Path(auditor.__file__),HW/'scripts/audit_standard_gerber_artwork.py']
    result['audit_sources']={p.relative_to(HW.parents[1]).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (auditor.OUT/'gerber-geometry-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(result['status']!='passed')
