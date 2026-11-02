// Execute named original exercise after authenticating from a private file.
const fs=require('fs');const lab=process.env.LAB;if(!lab)throw Error('LAB missing');
const a=JSON.parse(fs.readFileSync(lab+'/private/operator.json','utf8'));
const auth=db.getSiblingDB('admin').auth(a.username,a.password);if(auth!==1&&auth.ok!==1)throw Error('STOP: auth failed');
const w=db.getSiblingDB('workshop');const action=process.env.ACTION;
if(action==='accept') {
 const info=db.getSiblingDB('admin').runCommand({buildInfo:1});
 const hello=db.hello();const o=db.getSiblingDB('admin').runCommand({getCmdLineOpts:1});
 if(info.version!=='8.0.34'||!hello.isWritablePrimary||hello.setName!=='study'||o.parsed.net.bindIp!=='127.0.0.1')throw Error('STOP: unexpected server/configuration');
 const c=w.getCollection('acceptance');const id='probe-'+new ObjectId();
 const r=c.insertOne({_id:id,at:new Date()},{writeConcern:{w:'majority',j:true,wtimeout:3000}});
 if(!r.acknowledged||!c.findOne({_id:id}))throw Error('STOP: read/write failed');
 printjson({version:info.version,setName:hello.setName,primary:hello.isWritablePrimary,bind:o.parsed.net.bindIp,writeRead:true});
} else if(action==='explain') {
 const q=w.jobs.find({tenant:'tenant-01',state:'open'}).sort({createdAt:-1,_id:1}).limit(20);
 const x=q.explain('executionStats');
 printjson({nReturned:x.executionStats.nReturned,totalKeysExamined:x.executionStats.totalKeysExamined,totalDocsExamined:x.executionStats.totalDocsExamined,executionTimeMillis:x.executionStats.executionTimeMillis,winningPlan:x.queryPlanner.winningPlan});
} else if(action==='types') {
 const c=w.semantics;if(c.countDocuments({})!==0)throw Error('STOP: semantics already exists; inspect before repeating');
 c.insertMany([{_id:'missing'},{_id:'null',a:null},{_id:'array',a:[1,8]},{_id:'scalar',a:4}]);
 const ids=q=>c.find(q,{_id:1}).toArray().map(d=>d._id).sort();
 const actual={nullOrMissing:ids({a:null}),onlyNull:ids({a:{$type:10}}),differentElements:ids({a:{$gt:5,$lt:3}}),sameElement:ids({a:{$elemMatch:{$gt:5,$lt:3}}})};
 const expected={nullOrMissing:['missing','null'],onlyNull:['null'],differentElements:['array'],sameElement:[]};
 if(JSON.stringify(actual)!==JSON.stringify(expected))throw Error('STOP: BSON semantics mismatch '+JSON.stringify(actual));
 printjson(actual);
} else if(action==='stats') {
 const s=db.getSiblingDB('admin').serverStatus();const t=s.wiredTiger.cache;
 printjson({connections:s.connections,cacheBytes:t['bytes currently in the cache'],dirtyBytes:t['tracked dirty bytes in the cache'],maxCacheBytes:t['maximum bytes configured'],queues:s.queues,oplog:db.getSiblingDB('local').oplog.rs.stats().size});
} else if(action==='aggregate') {
 printjson(w.jobs.aggregate([{$match:{tenant:'tenant-01'}},{$group:{_id:'$state',jobs:{$sum:1}}},{$sort:{_id:1}}],{maxTimeMS:3000}).toArray());
} else if(action==='backup-count') {
 printjson({jobs:w.jobs.countDocuments({}),ledger:w.ledger.countDocuments({}),indexes:w.jobs.getIndexes().map(i=>({name:i.name,key:i.key}))});
} else if(action==='stop') {
 db.getSiblingDB('admin').shutdownServer({timeoutSecs:5});
} else throw Error('unknown ACTION; no mutation performed');
