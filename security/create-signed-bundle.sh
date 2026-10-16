#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Offline builder of an Ed25519-signed Pulse manifest; never generates prod signing keys.
set -Eeuo pipefail
if [[ $# != 8 ]]; then
 echo 'Usage: create-signed-bundle.sh BUNDLE_DIR VERSION PRIVATE_KEY ROOT_IMAGE_FILENAME VERITY_TREE_FILENAME ROOT_HASH_FILENAME KERNEL_FILENAME INITRAMFS_FILENAME' >&2
 exit 2
fi
BUNDLE="$1" VERSION="$2" KEY="$3" ROOT="$4" TREE="$5" HASH="$6" KERNEL="$7" INITRD="$8"
[[ -d "$BUNDLE" && -f "$KEY" ]] || { echo 'bundle/key missing' >&2; exit 3; }
[[ ! -e "$BUNDLE/manifest.json" && ! -e "$BUNDLE/manifest.sig" ]] || { echo 'bundle already signed; refuse overwrite' >&2; exit 3; }
python3 - "$BUNDLE" "$VERSION" "$ROOT" "$TREE" "$HASH" "$KERNEL" "$INITRD" <<'PY'
import hashlib,json,pathlib,re,sys
p,v,*files=sys.argv[1:]
root=pathlib.Path(p)
if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-.][a-zA-Z0-9.-]+)?',v): raise SystemExit('invalid version')
roles={}
for role,name in zip(('root-image','verity-tree','root-hash','kernel','initramfs'),files):
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',name): raise SystemExit('unsafe filename')
 file=root/name
 if not file.is_file() or file.is_symlink() or file.stat().st_size<1: raise SystemExit('missing/unsafe artifact: '+name)
 h=hashlib.sha256()
 with file.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 roles[role]={'file':name,'sha256':h.hexdigest(),'size':file.stat().st_size}
if len(set(files))!=len(files): raise SystemExit('duplicate files')
root_hash_file = root/files[2]
root_hash_value = root_hash_file.read_text('ascii').strip() if root_hash_file.stat().st_size < 256 else ''
if not re.fullmatch('[a-f0-9]{64}',root_hash_value): raise SystemExit('invalid dm-verity root hash')
payload={'product':'Pulse','format':1,'version':v,'artifacts':roles,'dm_verity_root_hash':root_hash_value,
         'trust':'Update authorized by externally pinned signing key; boot-chain validation separate'}
(root/'manifest.json').write_text(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n')
PY
openssl pkeyutl -sign -inkey "$KEY" -rawin -in "$BUNDLE/manifest.json" -out "$BUNDLE/manifest.sig"
echo 'Signed manifest; do not distribute private key. Pin corresponding trusted public key outside the bundle.'
