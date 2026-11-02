#!/usr/bin/env bash
# Неисполненный рецепт. Только консоль собственной новой VM.
set -euo pipefail
umask 077
set -o noclobber

systemd-detect-virt --vm
case "$(hostname)" in
  ceph1|ceph2|ceph3|ceph4) ;;
  *) printf '%s\n' 'Не учебная VM с ожидаемым именем.' >&2; exit 1 ;;
esac

study_root="$HOME/ceph-study"
if [[ ! -e "$study_root" && ! -L "$study_root" ]]; then
  mkdir -m 0700 -- "$study_root"
fi
test -d "$study_root"
test ! -L "$study_root"
test "$(stat -c %u -- "$study_root")" = "$(id -u)"
test "$(stat -c %a -- "$study_root")" = 700

generation="$study_root/supply-20.2.4-01"
mkdir -m 0700 -- "$generation"
cd "$generation"
mkdir -m 0700 gnupg

curl --fail --show-error --location --proto '=https' \
  https://download.ceph.com/keys/release.asc > release.asc

fingerprint=$(
  gpg --no-options --homedir "$PWD/gnupg" --batch \
    --with-colons --show-keys release.asc |
  awk -F: '
    $1 == "pub" { pub_count++; need_primary_fpr=1; next }
    $1 == "sub" { need_primary_fpr=0; next }
    $1 == "sec" || $1 == "ssb" { bad=1; next }
    $1 == "fpr" && need_primary_fpr {
      primary_count++
      fingerprint=$10
      if (fingerprint != "08B73419AC32B4E966C1A330E84AC2C0460F3994") bad=1
      need_primary_fpr=0
    }
    END {
      if (bad || pub_count != 1 || primary_count != 1) exit 1
      print fingerprint
    }
  '
)
test "$fingerprint" = 08B73419AC32B4E966C1A330E84AC2C0460F3994

gpg --no-options --homedir "$PWD/gnupg" --batch --dearmor \
  < release.asc > ceph-release.gpg

curl --fail --show-error --location --proto '=https' \
  https://download.ceph.com/debian-20.2.4/dists/jammy/InRelease \
  > InRelease

gpgv --keyring "$PWD/ceph-release.gpg" InRelease \
  2> signature-check.txt

sha256sum release.asc ceph-release.gpg InRelease \
  > SHA256SUMS.signature
printf 'status=accepted-signature-inputs\nversion=20.2.4\nfingerprint=%s\n' \
  "$fingerprint" > SIGNATURE-ACCEPTED.txt
