#!/usr/bin/env python3
"""Local web UI for GitHub repository management.

The UI uses the same safe repository-management engine as the CLI.
It never creates GitHub user accounts or bypasses verification/anti-abuse controls.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

from github_repo_manager import JobManager, load_config

app = Flask(__name__)
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Agent Tools — GitHub Manager</title>
<style>
body{font-family:system-ui,sans-serif;max-width:1000px;margin:30px auto;padding:0 16px;background:#f6f8fa;color:#24292f}
.card{background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:18px;margin-bottom:16px}
textarea,input,select{width:100%;box-sizing:border-box;padding:9px;border:1px solid #d0d7de;border-radius:6px;margin:6px 0 12px}
button{padding:10px 16px;border:0;border-radius:6px;background:#24292f;color:#fff;cursor:pointer}
pre{white-space:pre-wrap;background:#0d1117;color:#e6edf3;padding:14px;border-radius:8px;min-height:160px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
small{color:#57606a}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<h1>AI Agent Tools</h1>
<p>GitHub repository manager — local Web UI</p>
<div class="card">
<h2>Configuration</h2>
<textarea id="config" rows="14"></textarea>
<div class="grid">
<div><label>Workers</label><input id="workers" type="number" min="1" max="16" value="4"></div>
<div><label>Retries</label><input id="retries" type="number" min="0" max="10" value="4"></div>
<div><label>Proxy</label><input id="proxy" placeholder="http://127.0.0.1:8080"></div>
</div>
<label><input id="dry" type="checkbox" checked> Dry run</label>
<br><br>
<button onclick="runJob()">Run</button>
</div>
<div class="card">
<h2>Job output</h2>
<pre id="output">Ready.</pre>
</div>
<script>
const example = {
  owner:"YOUR_USERNAME", organization:null,
  repositories:[
    {name:"agent-project-01",description:"AI agent project",private:false},
    {name:"agent-project-02",description:"Automation project",private:true}
  ]
};
document.getElementById("config").value=JSON.stringify(example,null,2);

async function runJob(){
  const out=document.getElementById("output");
  out.textContent="Starting...";
  let config;
  try{config=JSON.parse(document.getElementById("config").value)}
  catch(e){out.textContent="Invalid JSON: "+e;return}
  const body={
    config, dry_run:document.getElementById("dry").checked,
    workers:Number(document.getElementById("workers").value),
    retries:Number(document.getElementById("retries").value),
    proxy:document.getElementById("proxy").value || null
  };
  const r=await fetch("/api/run",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const data=await r.json();
  if(!r.ok){out.textContent=data.error||"Request failed";return}
  out.textContent="Job: "+data.job_id+"\n"+JSON.stringify(data.summary,null,2);
  poll(data.job_id);
}
async function poll(id){
  const r=await fetch("/api/jobs/"+id); const data=await r.json();
  document.getElementById("output").textContent="Job: "+id+"\n"+JSON.stringify(data,null,2);
  if(data.status==="running") setTimeout(()=>poll(id),800);
}
</script>
</body>
</html>"""

@app.get("/")
def index():
    return render_template_string(HTML)

@app.post("/api/run")
def run():
    data=request.get_json(silent=True) or {}
    try:
        config=data["config"]
        # Validate before starting a background job.
        if not isinstance(config.get("repositories"), list):
            raise ValueError("'repositories' must be a list")
        manager=JobManager(
            workers=max(1,min(int(data.get("workers",4)),16)),
            retries=max(0,min(int(data.get("retries",4)),10)),
            proxy=data.get("proxy") or None,
        )
        job_id=os.urandom(8).hex()
        with jobs_lock:
            jobs[job_id]={"status":"running","summary":None}
        def worker():
            try:
                summary=manager.run_config(config,dry_run=bool(data.get("dry_run",True)))
                with jobs_lock: jobs[job_id]={"status":"done","summary":summary}
            except Exception as exc:
                with jobs_lock: jobs[job_id]={"status":"error","error":str(exc)}
        threading.Thread(target=worker,daemon=True).start()
        return jsonify({"job_id":job_id,"summary":{"status":"running"}})
    except Exception as exc:
        return jsonify({"error":str(exc)}),400

@app.get("/api/jobs/<job_id>")
def job(job_id):
    with jobs_lock:
        value=jobs.get(job_id)
    if not value:
        return jsonify({"error":"job not found"}),404
    return jsonify(value)

if __name__=="__main__":
    app.run(host=os.getenv("WEB_HOST","127.0.0.1"),port=int(os.getenv("WEB_PORT","8080")),debug=False)
