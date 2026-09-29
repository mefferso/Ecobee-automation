#!/usr/bin/env python3
import argparse, json, os, sys, urllib.error, urllib.request

BASE="https://api.smartthings.com/v1"

def api(method,path,token,payload=None):
    data=None
    headers={"Authorization":f"Bearer {token}","Accept":"application/json"}
    if payload is not None:
        data=json.dumps(payload).encode()
        headers["Content-Type"]="application/json"
    req=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            body=r.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')}") from e

def thermostats(token):
    items=api("GET","/devices",token).get("items",[])
    out=[]
    for d in items:
        caps={c.get("id") for comp in d.get("components",[]) for c in comp.get("capabilities",[])}
        if {"thermostatMode","thermostatCoolingSetpoint","thermostatHeatingSetpoint"} & caps:
            out.append(d)
    return out

def find(token,name):
    key=name.strip().casefold()
    hits=[]
    for d in thermostats(token):
        vals=[str(d.get("label") or ""),str(d.get("name") or "")]
        if any(v.strip().casefold()==key for v in vals):
            hits.append(d)
    if len(hits)!=1:
        avail=[d.get("label") or d.get("name") or d.get("deviceId") for d in thermostats(token)]
        raise RuntimeError(f"Expected one match for {name!r}; found {len(hits)}. Available: {avail}")
    return hits[0]

def status(token,device_id):
    return api("GET",f"/devices/{device_id}/status",token)

def summary(raw):
    main=raw.get("components",{}).get("main",{})
    def val(cap,attr):
        x=main.get(cap,{}).get(attr,{})
        return {"value":x.get("value"),"unit":x.get("unit")}
    return {
      "temperature":val("temperatureMeasurement","temperature"),
      "humidity":val("relativeHumidityMeasurement","humidity"),
      "mode":val("thermostatMode","thermostatMode"),
      "operating_state":val("thermostatOperatingState","thermostatOperatingState"),
      "cooling_setpoint":val("thermostatCoolingSetpoint","coolingSetpoint"),
      "heating_setpoint":val("thermostatHeatingSetpoint","heatingSetpoint")
    }

def command(token,device_id,capability,cmd,args=None):
    return api("POST",f"/devices/{device_id}/commands",token,{
      "commands":[{"component":"main","capability":capability,"command":cmd,"arguments":args or []}]
    })

def set_thermostat(token,name,mode,temp,dry_run):
    if mode not in {"heat","cool"}: raise RuntimeError("Mode must be heat or cool")
    if not 60 <= temp <= 80: raise RuntimeError("Safety limit is 60-80 F")
    d=find(token,name); did=d["deviceId"]; label=d.get("label") or d.get("name") or did
    print("Matched:",label)
    print("Device ID:",did)
    print("Before:",json.dumps(summary(status(token,did)),indent=2))
    print("Requested:",json.dumps({"mode":mode,"temperature_f":temp,"dry_run":dry_run},indent=2))
    if dry_run:
        print("DRY RUN: no command sent")
        return
    command(token,did,"thermostatMode",mode)
    if mode=="cool":
        command(token,did,"thermostatCoolingSetpoint","setCoolingSetpoint",[temp])
    else:
        command(token,did,"thermostatHeatingSetpoint","setHeatingSetpoint",[temp])
    print("After:",json.dumps(summary(status(token,did)),indent=2))

def main():
    p=argparse.ArgumentParser()
    s=p.add_subparsers(dest="action",required=True)
    s.add_parser("list")
    q=s.add_parser("set")
    q.add_argument("--device",required=True)
    q.add_argument("--mode",required=True,choices=["heat","cool"])
    q.add_argument("--temperature",required=True,type=float)
    q.add_argument("--dry-run",action="store_true")
    a=p.parse_args()
    token=os.getenv("SMARTTHINGS_TOKEN")
    if not token:
        print("SMARTTHINGS_TOKEN is not set",file=sys.stderr); return 2
    try:
        if a.action=="list":
            for d in thermostats(token):
                print(json.dumps({"label":d.get("label"),"name":d.get("name"),"deviceId":d.get("deviceId")}))
        else:
            set_thermostat(token,a.device,a.mode,a.temperature,a.dry_run)
        return 0
    except Exception as e:
        print("ERROR:",e,file=sys.stderr); return 1

if __name__=="__main__":
    raise SystemExit(main())
