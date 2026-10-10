"""Filter native panel coordinates using the reviewed BOM and load variants."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DRAFT=ROOT/'manufacturing/draft'

def read_rows(path,delimiter=','):
    with path.open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle,delimiter=delimiter)
        return list(reader),reader.fieldnames

def write_rows(path,rows,columns):
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

def main():
    bom,bom_columns=read_rows(ROOT/'electrical/bom.csv')
    pnp,pnp_columns=read_rows(DRAFT/'nfc-talisman-panel-pnp-all.csv','\t')
    if {row['Designator'] for row in bom}!={row['Designator'] for row in pnp}:
        raise ValueError('BOM and native coordinates differ')
    if len(bom)!=15 or len(pnp)!=15:
        raise ValueError('Unexpected component population')
    report={'source_coordinate_file':'nfc-talisman-panel-pnp-all.csv','coordinate_convention':'native panel mm, unmirrored data coordinates, origin lower-left; native bottom rotations retained for assembly review','native_CT2_library_placeholder':'Native all-parts BOM retains the 47pF/C60137 library placeholder; CT2 is excluded from every assembly variant. Do not fit it before RF measurement.','variants':{}}
    for name,exclude in [('four-led',{'CT2'}),('two-led',{'CT2','D2','D4'})]:
        fitted_bom=[row for row in bom if row['Designator'] not in exclude]
        fitted_pnp=[row for row in pnp if row['Designator'] not in exclude]
        if any(row['Population']=='DNP' for row in fitted_bom):
            raise ValueError('DNP item remained fitted')
        for row in fitted_pnp:
            item=next(b for b in fitted_bom if b['Designator']==row['Designator'])
            if row['Layer']!=('T' if item['Side']=='Top' else 'B'):
                raise ValueError('BOM side disagrees: '+row['Designator'])
        write_rows(DRAFT/f'{name}-bom.csv',fitted_bom,bom_columns)
        write_rows(DRAFT/f'{name}-panel-pnp.csv',fitted_pnp,pnp_columns)
        report['variants'][name]={'fit_count':len(fitted_bom),'excluded':sorted(exclude),'fit_designators':[row['Designator'] for row in fitted_bom],'notes':'R2 and R4 may remain fitted in two-LED variant; open LED branches draw no current. Library LED pad polarity and native rotation still need physical assembly review.'}
    (DRAFT/'assembly-variants.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['variants'],ensure_ascii=False))

if __name__=='__main__':
    main()
