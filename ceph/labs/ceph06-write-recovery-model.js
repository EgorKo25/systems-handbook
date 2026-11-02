// Только модель выбранного сценария. Не реализует CRUSH, peering или wire Ceph.
const MiB = 2 ** 20;
const assert = (ok, why) => { if (!ok) throw new Error(why); };
const mustFail = fn => { let failed=false; try { fn(); } catch { failed=true; } assert(failed, "expected refusal"); };
const mapDisposition = (sent, current, samePrimarySince) =>
  sent > current ? "wait-map" : sent < samePrimarySince ? "drop" : "check-PG";
assert(mapDisposition(100,105,100)==="check-PG", "older map alone is not a rejection");
assert(mapDisposition(100,110,110)==="drop", "primary changed");
assert(mapDisposition(120,110,110)==="wait-map", "receiver needs map");
const stores = [0,1,2].map(id => ({
  id, up:true, log:new Map(), object:{version:"100'40", payload:"old"},
  lastUpdate:"100'40", lastComplete:"100'40"
}));
const pg = {
  epoch:100, counter:40, acting:[0,1,2], primary:0, minSize:2,
  historyReady:true, leaseReady:true, pending:new Map()
};
const canServe = () => pg.historyReady && pg.leaseReady &&
  pg.acting.length >= pg.minSize && pg.acting.every(id => stores[id].up);
const begin = (reqid, payload) => {
  assert(canServe(), "PG cannot serve");
  const projected = pg.pending.get(reqid);
  if (projected) return {waiting:true, version:projected.version};
  const old = stores[pg.primary].log.get(reqid);
  if (old) return {duplicate:true, version:old.version};
  const op = {reqid, payload, version:pg.epoch+"'"+(++pg.counter),
    required:new Set(pg.acting), committed:new Set()};
  pg.pending.set(reqid, op);
  return op;
};
const commit = (op, id) => {
  assert(op.required.has(id), "not a participant");
  assert(stores[id].up, "participant down");
  stores[id].log.set(op.reqid, {version:op.version});
  stores[id].object = {version:op.version, payload:op.payload};
  stores[id].lastUpdate = op.version;
  stores[id].lastComplete = op.version;
  op.committed.add(id);
};
const committed = op => [...op.required].every(id => op.committed.has(id));
const finish = op => { assert(committed(op), "still waiting"); pg.pending.delete(op.reqid); };
const canReadCurrent = id => stores[id].object.version === stores[id].lastUpdate;
const r17 = begin("client.42/inc3/tid17", "A");
commit(r17, 0); commit(r17, 1);
mustFail(() => finish(r17)); // Два ответа не завершают исходную тройку.
assert(begin("client.42/inc3/tid17","A").waiting, "pending duplicate must wait");
commit(r17, 2); finish(r17);
const client = {r17:"unknown"}; // Commit есть, ответ утрачен.
assert(committed(r17) && client.r17 === "unknown", "lost reply differs from rollback");

stores[0].up=false;
pg.epoch=110; pg.acting=[1,2]; pg.primary=1; pg.historyReady=false;
mustFail(() => begin("client.42/inc3/tid18", "B"));
pg.historyReady=true; // Предпосылка модели: peering подтвердил нужную историю.
pg.leaseReady=false;
mustFail(() => begin("client.42/inc3/tid18", "B"));
pg.leaseReady=true;
const counterBeforeRetry=pg.counter;
const retry=begin("client.42/inc3/tid17", "A");
assert(retry.duplicate && retry.version==="100'41" && pg.counter===counterBeforeRetry, "retry must not allocate a version");
client.r17="confirmed";
const r18=begin("client.42/inc3/tid18", "B");
commit(r18,1);
mustFail(() => finish(r18));
commit(r18,2); finish(r18);
assert(r18.version==="110'42" && stores[0].object.payload==="A", "degraded write");

stores[0].up=true;
pg.epoch=120; pg.acting=[0,1,2]; pg.primary=0;
stores[0].log=new Map(stores[1].log);
stores[0].lastUpdate=stores[1].lastUpdate;
assert(!canReadCurrent(0), "log does not supply payload");
assert(stores[0].lastComplete==="100'41", "completion must remain behind");
const recoveryBytes=4*MiB;
assert(stores[1].object.version==="110'42", "source has needed version");
stores[0].object={...stores[1].object}; // Модель завершённого локального восстановления.
stores[0].lastComplete=stores[0].lastUpdate;
assert(canReadCurrent(0) && stores.every(s=>s.object.payload==="B"), "recovery must restore B");
assert(stores.every(s=>s.lastUpdate===s.lastComplete), "clean model");

const savedActing=pg.acting;
pg.acting=[0]; mustFail(() => begin("new", "C")); pg.acting=savedActing;
pg.historyReady=false; mustFail(() => begin("new", "C")); pg.historyReady=true;
for(const s of stores) s.log.delete("client.42/inc3/tid17"); // Условное удаление истории, не алгоритм trim Ceph.
assert(!stores[0].log.has("client.42/inc3/tid17") && stores[0].object.payload==="B", "payload cannot recreate a deleted request record");
const totals = {clientPayload:12*MiB, osdPayload:16*MiB, objectPayloadWrites:24*MiB};
assert(totals.clientPayload+totals.osdPayload===28*MiB && recoveryBytes/(100*MiB)===0.04, "byte arithmetic");
({model:"selected-scenario", finalVersion:r18.version, recoveryBytes, totals});
