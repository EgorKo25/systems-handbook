"""Own toy cache: unrelated to Go's real action IDs. No files are changed."""
import hashlib,json,os,subprocess,sys
SOURCE = 'import os\nprint("Привет" if os.environ["LANGUAGE"] == "ru" else "Hello")\n'
def key(schema,language):
 d={"schema":schema,"action":"greeting-v1","source_sha256":hashlib.sha256(SOURCE.encode("utf-8")).hexdigest(),"tool":"python-model-v1"}
 if schema==2:d["language"]=language
 return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")).hexdigest()
def output(language):
 e=os.environ.copy();e["LANGUAGE"]=language
 return subprocess.check_output([sys.executable,"-c",SOURCE],env=e)
if __name__=="__main__":
 r={"source_sha256":hashlib.sha256(SOURCE.encode("utf-8")).hexdigest(),"keys":{},"outputs":{}}
 for language in ["ru","en"]:
  b=output(language);r["outputs"][language]={"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"text":b.decode("utf-8")}
  for schema in [1,2]:r["keys"][str(schema)+"/"+language]=key(schema,language)
 assert key(1,"ru")==key(1,"en") and key(2,"ru")!=key(2,"en")
 print(json.dumps(r,ensure_ascii=False,indent=2))
