RGW ADMINBUCKET — source-only, Linux
Purpose: only CreateBucket and HeadBucket for the accepted single-zone/default-placement RGW20.2.4 lab.
It does not implement put/get/delete/list/presign, does not change object-study and does not administer MON/OSD.

Required before build:
- personally owned Linux guest; Go1.27.3 linux/amd64 accepted by the S3 volume supply procedure;
- exact go.mod here; dependencies downloaded and their resulting go.sum reviewed/saved, not invented;
- source typecheck/build/help and native TLS+RGW acceptance still PENDING. No installed binary is supplied.
The source uses SDK core1.47.1,service/s3 1.114.0,smithy1.28.1.
No Go build, dependency download or SDK dispatch was performed by this author.

In a new owned source checkout directory, after provenance/version checks:
GOTOOLCHAIN=local go mod download
GOTOOLCHAIN=local go build -o rgw-adminbucket .
Inspect the generated go.sum and dependency licenses, save them with the accepted build record.
Offline readiness requires the dependencies and a successful build with fetching disabled.
These instructions create files only in a future permitted Linux guest, not in the read-only author session.

Input is the schema_version1 targets.json and private credentials file explained in Ceph19.
backend must be ceph-rgw,https endpoint must have no path except /,query,fragment or userinfo;
addressing must be path; region,bucket,profile,credentials_file,ca_file are explicit.
Relative paths resolve from targets.json directory. No ambient AWS credentials/config/proxy chain.
Private credentials mode0600, all inputs regular/owned/not group-or-world writable,max64KiB.
Linux open uses O_NONBLOCK|O_NOFOLLOW then fstat. Parent directories remain trusted and not concurrently modified.
Duplicate JSON member names are not detected by encoding/json: these owned inputs must have unique members.
No claim of protection from a hostile owner racing parent directories.

Run root flags BEFORE the command:
./rgw-adminbucket --config config/targets.json --target rgw-study --timeout 30s create
./rgw-adminbucket --config config/targets.json --target rgw-study --timeout 30s head

Create omits LocationConstraint and is limited to default placement accepted for this lab.
It must not be used as a generic zonegroup placement tool.
CreateBucket can succeed for a bucket already owned by the same user; output says confirmed_exists,not newly_created.
A failed create after SDK dispatch conservatively reports unknown,including explicit service rejection.
Exit0 confirmed;2 local validation;3 explicit SDK service rejection;4 transport/deadline/other unconfirmed result.
ServiceCode is sanitized; URL,credentials,raw SDK error and Authorization are never printed.
SDK MaxAttempts1 and HTTP redirects disabled; neither setting proves exactly-once execution.
After unknown inspect with head and the authoritative admin bucket metadata before deciding further action.
Do not delete an existing bucket to make the exercise look new.

Required native gates:
CreateBucket+HeadBucket against the exact20.2.4 HTTPS endpoint;
pre-existing own bucket behavior;another owner's name rejection;
wrong key/CA/name/expired certificate;session expiry;
service/transport failure classification;no raw secrets in output;
confirm actual SDK serialized signed headers and no unexpected AWS endpoint.
This is a source candidate until these gates pass.
