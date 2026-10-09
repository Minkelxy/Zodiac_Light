"""Execute a saved JavaScript request through the official local EasyEDA bridge."""
import json, pathlib, sys, urllib.request, urllib.error
ROOT = pathlib.Path(__file__).resolve().parents[1]
def execute(code, name="request", timeout=180):
    request = urllib.request.Request("http://127.0.0.1:49620/execute", data=json.dumps({"code":code,"timeout":timeout*1000}).encode(), headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout+10) as response:
            result=json.load(response)
    except urllib.error.HTTPError as error:
        body=error.read().decode("utf-8",errors="replace")
        try:
            details=json.loads(body)
        except json.JSONDecodeError:
            details={"body":body}
        result={"success":False,"httpStatus":error.code,"error":details}
    target=ROOT/"eda"/"logs"/(name+".json")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    source=pathlib.Path(sys.argv[1])
    result=execute(source.read_text(encoding="utf-8-sig"),source.stem)
    print(json.dumps(result,ensure_ascii=False)[:int(sys.argv[2]) if len(sys.argv)>2 else 16000])
