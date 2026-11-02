"use strict";
// Author model: constraints, supplied proposals, bytes and selected priority branches.
// Not a CRUSH mapper, codec, OSDMap decoder or peering implementation.
function ceph08PolicyModel() {
  const GiB = 2 ** 30, MiB = 2 ** 20, KiB = 2 ** 10;
  const osds = [
    { id: 0, host: "a0", rack: "rack-a", cls: "hdd", gib: 512 },
    { id: 1, host: "a0", rack: "rack-a", cls: "ssd", gib: 512 },
    { id: 2, host: "a1", rack: "rack-a", cls: "hdd", gib: 1024 },
    { id: 3, host: "b0", rack: "rack-b", cls: "hdd", gib: 1024 },
    { id: 4, host: "b1", rack: "rack-b", cls: "hdd", gib: 1024 }
  ];
  const byId = new Map(osds.map(o => [o.id, o]));
  function select(proposals, domain, cls = null, out = []) {
    const used = new Set(), chosen = [], trace = [];
    for (const id of proposals) {
      if (chosen.length === 3) break;
      const o = byId.get(id);
      if (!o) throw Error("unknown model OSD");
      const reason = cls && o.cls !== cls ? "class" :
        out.includes(id) ? "out" :
        used.has(o[domain]) ? "domain" : "accept";
      trace.push({ id, reason });
      if (reason === "accept") {
        chosen.push(id);
        used.add(o[domain]);
      }
    }
    return { chosen, trace, complete: chosen.length === 3 };
  }
  const proposals = [
    [0, 2, 3, 4], [1, 3, 4, 2],
    [2, 4, 0, 3], [3, 2, 4, 0]
  ];
  const before = proposals.map(p => select(p, "host").chosen);
  const after = proposals.map(p => select(p, "host", null, [0, 1]).chosen);
  const pgBytes = 128 * GiB;
  const usage = mapping => osds.map(o =>
    mapping.filter(row => row.includes(o.id)).length * pgBytes);
  const additions = after.map((row, i) => row.filter(id => !before[i].includes(id)));
  const newCopies = additions.flat().length;
  const movedBytes = newCopies * pgBytes;
  const flows = [[2, 4], [3, 2], [4, 3]];
  const crossRackBytes = flows.filter(([a, b]) =>
    byId.get(a).rack !== byId.get(b).rack).length * pgBytes;
  const stripes = 4 * MiB / (2 * 4096);
  const shardBytes = stripes * 4096;
  const costPerIO = 256 * MiB / 1024;
  const scaledCost = itemCost => Math.max(1, itemCost, costPerIO);
  // Selected producer branch: osd_op_queue=mclock_scheduler.
  const priority = f => f.forced ? 20 : f.undersized ? 15 : f.degraded ? 10 : 5;
  // PGOpItem branch for MSG_OSD_EC_READ only; HIGH=196, FORCED=20.
  const ecReadClass = p => p > 20 ? "immediate" :
    p >= 196 ? "immediate" : p >= 10 ? "background_recovery" :
    "background_best_effort";
  const queue = p => ecReadClass(p) === "immediate" || p >= 196 ?
    "strict" : "mclock";
  const checks = [];
  function check(name, ok) {
    if (!ok) throw Error("failed: " + name);
    checks.push(name);
  }
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  check("reject second OSD of a0",
    same(select([0,1,2,3], "host").trace.map(x => x.reason),
      ["accept","domain","accept","accept"]));
  check("host placements", same(before,
    [[0,2,3],[1,3,4],[2,4,0],[3,2,4]]));
  check("rack deficit", select([0,1,2,3,4], "rack").chosen.length === 2);
  check("ssd deficit", select([0,1,2,3,4], "host", "ssd").chosen.length === 1);
  check("hdd eligible", same(select([0,1,2,3,4], "host", "hdd").chosen,[0,2,3]));
  check("replicated down+in filtering", same(before[0].filter(id => id !== 0),[2,3]));
  check("out placements", same(after,
    [[2,3,4],[3,4,2],[2,4,3],[3,2,4]]));
  check("only three new copies", same(additions,[[4],[2],[3],[]]));
  check("initial GiB", same(usage(before).map(n => n/GiB),[256,128,384,384,384]));
  check("final GiB", same(usage(after).map(n => n/GiB),[0,0,512,512,512]));
  check("384 GiB copied", movedBytes === 384*GiB);
  check("256 GiB cross rack", crossRackBytes === 256*GiB);
  check("98304 copies", movedBytes/(4*MiB) === 98304);
  check("network bound 4096 seconds", movedBytes/(96*MiB) === 4096);
  check("EC aligned stripes", stripes === 512 && shardBytes === 2*MiB);
  check("EC payload factor", 3*shardBytes/(4*MiB) === 1.5);
  check("cost floor", scaledCost(4*KiB) === 256*KiB);
  check("large cost", scaledCost(4*MiB) === 4*MiB);
  check("undersized producer", priority({undersized:true}) === 15);
  check("degraded producer", priority({degraded:true}) === 10);
  check("forced precedes undersized", priority({forced:true,undersized:true}) === 20);
  check("ordinary producer", priority({}) === 5);
  check("recovery read regulated", queue(15) === "mclock" &&
    ecReadClass(15) === "background_recovery");
  check("best effort read", ecReadClass(5) === "background_best_effort");
  check("client read immediate", ecReadClass(127) === "immediate" && queue(127) === "strict");
  check("outside recovery interval", ecReadClass(21) === "immediate");
  return {
    checks, before, after,
    movedGiB: movedBytes/GiB, crossRackGiB: crossRackBytes/GiB,
    lowerBoundsSeconds: [movedBytes/(160*MiB), movedBytes/(128*MiB),
      movedBytes/(96*MiB)],
    ec: { stripes, shardMiB: shardBytes/MiB, rawMiB: 3*shardBytes/MiB,
      recoveryReadMiB: 2*shardBytes/MiB, recoveryWriteMiB: shardBytes/MiB,
      selectedNetworkMiB: 2*shardBytes/MiB }
  };
}
