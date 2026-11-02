CEPH — SOURCE VOLUME CANDIDATE
Author base:9c97f1957e24c336a4c42833dfb889a0340868c6.
All targets are add-only under ceph/. No registry,reader,Pages or canonical edits are included.
26 chapters,6 internal books,route,glossary/command cards,accepted diagrams,finite models and labs.
Pinned Ceph Tentacle20.2.4. This is a source candidate,not a claim of a running/benchmarked Ceph cluster.

Managed build wrapper calls only build('ceph'),matching tracked computer-architecture/build.py.
It depends on main's CONFIGS/publication loader. A private candidate must be registered by the integrator
before official build; an unregistered slug is not promised to build standalone.
Do not load review/diagrams.virtual-accepted.py as a second runtime diagram module.
CONFIG.diagram_modules contains only diagrams. The removed08 generic grid stays removed;
its stable anchor is supplied by inline subject topology SVG/CSS in HTML08.
Review provenance files are archived input evidence,not a current application state.

Native lab assumptions:
Only personal Ubuntu22.04 amd64 guests,own synthetic data disks,isolated10.77.0.0/24.
CLI2GiB proposal,one-OSD8GiB/3GiBtarget experiment,4x8GiB compact proposal or4x32GiB spare profile.
None is a verified minimum/performance guarantee. Reserve host/guest RAM and disk capacity first.
No host cephadmbootstrap,no all-available-devices,no zap/purge/reset,no bootstrap retry after attempted.
Existing generations stop constructors. Reentry never installs,pulls,keygens or bootstraps.
Keep original RADOS object,snapshots and restore targets; new probes do not PUT again.

Source-only checks:
Python finite-calculations.py and the two accepted JS models may run without Ceph.
They do not implement full CRUSH,Ceph peering/leases,OSD wire protocol,EC codec or scheduler.
Bash -n/Python AST/static schemas are not native execution.
All runtime receipts/package signatures/digests are produced only by a future authorized VM run.
No fabricated digest,go.sum or benchmark is supplied.
RGW adminbucket needs accepted Go1.27.3+dependencies+go.sum/typecheck/native endpoint20.2.4 gates.
Optional object-study source/runtime remains owned by S3 volume; no extra commands are attributed to it.

Secrets:
VM state,S3credentials,CephX/SSH/TLS private keys never belong in public sources.
Input examples contain no working credentials. Backup private secrets through a separate protected procedure.

Labs order:
01 model and calculations
03 VM prerequisites -> new-supply.sh -> runtime-accept-once.sh ceph1 -> new-cephops.sh
access-setup.bash numbered console blocks -> bootstrap-once.sh -> source reenter.bash
04 address-specific single OSD ->09 source pool-once.bash -> source rados-roundtrip.bash
new Bash/source reenter.bash -> source read-probe-01.bash
09 after read-probe-01: per-host preparation/SSH/OSD/MON/MGR
09 size3/min_size2/active+clean ->read-probe-02
Then separate RBD/CephFS/RGW exercises only with sufficient resources.
Private deployment and main computer shutdown remain outside this book.

Run finite models from the copied labs directory:
python3 -B finite-calculations.py
node run-models.cjs
Python checks use assert. -O, -OO or a nonzero PYTHONOPTIMIZE disables those assertions;
finite-calculations.py then stops before checks/PASS. Use the unoptimized command shown above.
The runner verifies exact accepted model hashes and invokes the08 function explicitly.
Archive-only ceph/review inputs are private provenance: NEVER copy them into canonical/public ceph/.
They appear only under private_provenance in the handoff manifest.
