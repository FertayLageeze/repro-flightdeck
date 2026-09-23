"""Build static demo only from audited, actually executed local runs."""
import argparse
import html
import json
from pathlib import Path
import shutil
from flightdeck.core import audit_run,contained


def publish(source,destination):
    source,destination=Path(source),Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    data=json.loads((source/'benchmark.json').read_text(encoding='utf-8'))
    shutil.copyfile(source/'benchmark.json',destination/'benchmark.json')
    for row in data['runs']:
        name=row['case']+'-'+row['arm'];run=source/name
        audit_run(run)
        target=destination/name;target.mkdir(exist_ok=True)
        for file in ('summary.json','trace.jsonl','manifest.json','truth.csv','stdout.txt','stderr.txt','report.html'):
            shutil.copyfile(run/file,target/file)
        summary=json.loads((run/'summary.json').read_text(encoding='utf-8'))
        if summary['result']:
            relative=summary['binding']['path'];artifact=contained(target/'workspace',relative)
            artifact.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(contained(run/'workspace',relative),artifact)
        if name=='temperature-rules':
            manifest=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
            for relative in manifest['inputs']:
                output=contained(target/'workspace',relative);output.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(contained(run/'workspace',relative),output)
    cards=[]
    descriptions={'temperature':('01','Recover the missing artifact','The experiment ran. Its output moved. Inspect the export, bind the right columns, and verify NLL.'),
                  'conformal':('02','Make a schema change visible','The intervals are there, but the names changed. Watch the exact binding repair and coverage check.'),
                  'svm':('03','Reject a confident wrong result','The program exits successfully. Its predictions are wrong. Follow the independent verifier to rejection.')}
    for case,(num,title,description) in descriptions.items():
        arm='negative' if case=='svm' else 'rules'
        cards.append(f'<a class="card" href="{case}-{arm}/report.html"><span class="num">{num} / RECORDED EXPERIMENT</span><h3>{title}</h3><p>{description}</p><b>Explore the replay ↗</b></a>')
    rows=[]
    for row in data['runs']:
        value='—' if row['value'] is None else f"{row['value']:.6f}"
        rows.append(f'<tr><td>{row["case"]}</td><td>{row["arm"]}</td><td class="{ "ok" if row["status"]=="verified" else "bad"}">{row["status"]}</td><td>{value}</td><td>{row["repairs"]}</td><td><a href="{row["report"]}">Replay ↗</a></td></tr>')
    template=Path(__file__).with_name('site-template.html').read_text(encoding='utf-8')
    (destination/'index.html').write_text(template.replace('__CARDS__',''.join(cards)).replace('__ROWS__',''.join(rows)).replace('__ENV__',html.escape(data['platform']+' · Python '+data['python'])),encoding='utf-8')
    (destination/'.nojekyll').write_text('',encoding='utf-8')
    print(destination)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',default='runs/benchmark');parser.add_argument('--out',default='docs/site');args=parser.parse_args();publish(args.source,args.out)
