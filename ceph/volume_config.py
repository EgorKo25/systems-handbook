"""Original Ceph volume. Registration/publication remains a root decision."""
CONFIG = dict(
 volume='XXVIII',short='Ceph',
 title='Ceph: от объекта и карты до восстановления',
 description='RADOS, CRUSH, BlueStore, RBD, CephFS и RGW: механизмы, отдельная VM-лаборатория, отказы и измерения.',
 revision='2 ноября 2026',
 sections=[
  ('Начало',['00-route']),
  ('Книга I · Модель и собственная VM',[
   'ceph-01-model','ceph-02-supply','ceph-03-vm-install','ceph-04-hosts-security-health']),
  ('Книга II · Размещение и устойчивость RADOS',[
   'ceph-05-placement-capacity','ceph-06-peering-recovery','ceph-07-bluestore','ceph-08-pools-encoding','ceph-09-rados-lab']),
  ('Книга III · Блочное хранение RBD',[
   'ceph-10-rbd-path','ceph-11-rbd-snapshots-clones','ceph-12-rbd-backup-restore','ceph-13-rbd-clients-csi']),
  ('Книга IV · Файловая система CephFS',[
   'ceph-14-cephfs-path','ceph-15-cephfs-caps-layout','ceph-16-cephfs-recovery']),
  ('Книга V · Объектный шлюз RGW',[
   'ceph-17-rgw-path','ceph-18-rgw-tls-users','ceph-19-rgw-s3-project','ceph-20-rgw-multisite']),
  ('Книга VI · Эксплуатация и восстановление',[
   'ceph-21-observation','ceph-22-failures-fullness','ceph-23-backup-contract',
   'ceph-24-upgrade-removal','ceph-25-measurement','ceph-26-continuing-lab']),
  ('Справочник',['99-glossary'])
 ],
 base_terms=[],term_modules=['reference'],command_modules=['reference'],
 diagram_modules=['diagrams'],
 illustration_links=[
  dict(id='ceph-crush-policy-to-copy',title='Топология host/rack и копии PG',label='предметная топология')
 ],
 blurb='Объект и карты → личные VM → размещение и подтверждение → RBD/CephFS/RGW → отказ, измерение и восстановление.'
)
