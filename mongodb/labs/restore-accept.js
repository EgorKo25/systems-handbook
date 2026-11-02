// Only on the separate unauthenticated loopback restore instance, port 27118.
const expected=Number(process.env.EXPECTED_JOBS);if(!Number.isSafeInteger(expected)||expected<1)throw Error('EXPECTED_JOBS required');
const w=db.getSiblingDB('workshop');const n=w.jobs.countDocuments({});if(n!==expected)throw Error('count mismatch '+n);
const first=w.jobs.findOne({_id:'seed-000001'});if(!first||!(first.createdAt instanceof Date))throw Error('BSON date lost');
if(!w.jobs.getIndexes().some(x=>x.name==='tenant_state_recent'))throw Error('index missing');
printjson({restoredJobs:n,seedVersion:first.version,index:true,date:true});
