"use strict";
// Read-only finite model runner. It never connects to a Ceph cluster.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const vm = require("node:vm");
const inputs = [
 ["ceph06-write-recovery-model.js","080e0e0270bd2e96efa50c01079de801f3d90780c4c3edfd76aab9aad9d08847",""],
 ["ceph08-policy-model.js","b5ccc7cc235bc4b66219bf9ae74e03abe60d446b3469aaf09f8fc008a6c07378","\nceph08PolicyModel()"]
];
const output = inputs.map(([name, expected, invocation]) => {
 const raw = fs.readFileSync(path.join(__dirname, name));
 const sha = crypto.createHash("sha256").update(raw).digest("hex");
 if (sha !== expected) throw new Error("Model source changed: "+name);
 const result = vm.runInNewContext(raw.toString("utf8")+invocation, {}, {timeout:1000});
 return {source:name,sha256:sha,result};
});
console.log(JSON.stringify({kind:"finite-models-only",output},null,2));
