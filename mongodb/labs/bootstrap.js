// Only on a new, loopback-only instance through the localhost exception.
// Two phases: init, then users after writable-primary readiness.
const fs=require('fs');
const lab=process.env.LAB;
if(!lab)throw Error('LAB missing');
if(process.env.PHASE==='init') {
  const r=db.getSiblingDB('admin').runCommand({replSetInitiate:{_id:'study',members:[{_id:0,host:'127.0.0.1:27117'}]}});
  if(r.ok!==1)throw Error(JSON.stringify(r));print('initiated; wait for primary');
} else if(process.env.PHASE==='users') {
  if(!db.hello().isWritablePrimary)throw Error('STOP: not primary');
  const a=JSON.parse(fs.readFileSync(lab+'/private/operator.json','utf8'));
  db.getSiblingDB('admin').createUser({user:a.username,pwd:a.password,roles:['root']});
  const admin=db.getSiblingDB('admin');const auth=admin.auth(a.username,a.password);if(auth!==1&&auth.ok!==1)throw Error('admin authentication failed');
  const b=JSON.parse(fs.readFileSync(lab+'/private/app.json','utf8'));
  db.getSiblingDB('workshop').createUser({user:b.username,pwd:b.password,roles:[{role:'readWrite',db:'workshop'}]});
  print('users created; localhost exception closed; no passwords printed');
} else throw Error('PHASE must be init or users');
