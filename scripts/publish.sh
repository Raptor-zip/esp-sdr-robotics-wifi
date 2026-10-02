#!/usr/bin/env bash
# Run from a normal terminal with GitHub access. Publishes the verified local bundle.
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bundle_path="${PUBLICATION_BUNDLE:-$project_root/artifacts/publication.bundle}"
repo_name="${GITHUB_REPO:-esp-sdr-robotics-wifi}"
if [[ ! -f "$bundle_path" ]]; then
  printf 'Git bundleがありません: %s\n' "$bundle_path" >&2
  exit 1
fi
git -C "$project_root" bundle verify "$bundle_path"
owner="$(gh api user --jq '.login')"
repo="$owner/$repo_name"
if gh repo view "$repo" --json name,isPrivate,parent > /tmp/esp-sdr-publish-repository.json 2>/dev/null; then
  python3 - <<'PY'
import json
m=json.load(open('/tmp/esp-sdr-publish-repository.json'))
if m['isPrivate']:raise SystemExit('既存リポジトリがprivateなので中止します。')
p=m.get('parent') or {}
if p.get('name')!='esp-sdr' or p.get('owner',{}).get('login')!='ESPARGOS':
 raise SystemExit('既存リポジトリがESPARGOS/esp-sdrのフォークではないので中止します。')
PY
else
  if ! gh repo fork ESPARGOS/esp-sdr --fork-name "$repo_name" --clone=false --remote=false || ! gh repo view "$repo" --json name >/dev/null 2>&1; then
    # GitHub permits one fork per upstream for an account; a new public repo also preserves history.
    gh repo create "$repo" --public --description "ロボコンの操縦通信とWi-Fi干渉の実測"
  fi
fi
publish_root="$(mktemp -d /tmp/esp-sdr-publish.XXXXXX)"
git clone --branch main "$bundle_path" "$publish_root/repository"
origin_url="$(gh repo view "$repo" --json sshUrl --jq '.sshUrl')"
git -C "$publish_root/repository" remote set-url origin "$origin_url"
git -C "$publish_root/repository" remote add upstream https://github.com/ESPARGOS/esp-sdr.git
# The fork can contain newer commits; prune the bundle's stale remote refs first.
git -C "$publish_root/repository" fetch --prune origin
if git -C "$publish_root/repository" show-ref --verify --quiet refs/remotes/origin/main; then
  author_name="$(git -C "$publish_root/repository" log -1 --format=%an)"
  author_email="$(git -C "$publish_root/repository" log -1 --format=%ae)"
  if ! git -C "$publish_root/repository" -c user.name="$author_name" -c user.email="$author_email" merge --no-edit origin/main; then
    printf 'リモートとの競合を解決する必要があります。作業コピー: %s\n' "$publish_root/repository" >&2
    exit 1
  fi
fi
git -C "$publish_root/repository" push -u origin main
gh repo edit "$repo" --default-branch main --description 'ロボコンの操縦UDP遅延とWi-Fi干渉の実測・ESP32-C5 SDR可視化・LaTeXレポート'
gh repo view "$repo" --json url,visibility,defaultBranchRef
printf '公開に使用したGit作業コピー: %s\n' "$publish_root/repository"
