#!/bin/zsh
set -euo pipefail

PROJECT_ROOT=${0:A:h:h}
cd "$PROJECT_ROOT"

required_files=(README.md app.py dashboard.py requirements.txt runtime.txt .gitignore)
for file in $required_files; do
  if [[ ! -f "$file" ]]; then
    print -u2 "缺少公开运行所需文件：$file"
    exit 1
  fi
done

sensitive_paths=(.env .streamlit/secrets.toml data/raw/x)
for sensitive_path in $sensitive_paths; do
  if ! git check-ignore -q "$sensitive_path"; then
    print -u2 "敏感或原始路径没有被 .gitignore 保护：$sensitive_path"
    exit 1
  fi
done

public_files=$(git ls-files --cached --others --exclude-standard)
if print -r -- "$public_files" | grep -E '(^|/)(\.env|secrets\.toml)$' >/dev/null; then
  print -u2 "待提交文件中发现密钥文件。"
  exit 1
fi

raw_public_files=$(print -r -- "$public_files" | grep -E '(^|/)data/raw/' | grep -v -E '(^|/)data/raw/\.gitkeep$' || true)
if [[ -n "$raw_public_files" ]]; then
  print -u2 "待提交文件中发现原始 API 数据。"
  exit 1
fi

# The public product surface should not expose a developer's machine path,
# contact address, or internal job-preparation notes.
public_surface=(README.md app.py dashboard.py docs)
privacy_matches=$(rg -n -i \
  '(/Users/[^/[:space:]]+|[[:alnum:]._%+-]+@(gmail|outlook|hotmail|qq)\.com|招聘|投递|零基础|JD[[:space:]]*(能力|要求|匹配))' \
  $public_surface 2>/dev/null || true)
if [[ -n "$privacy_matches" ]]; then
  print -u2 "公开产品说明中发现个人路径、联系方式或内部求职文字："
  print -u2 -r -- "$privacy_matches"
  exit 1
fi

legacy_matches=$(rg -n -i \
  --glob '!preflight_public.sh' \
  '(ave[ ._-]?(ai|signal|quality)|费用审计|estimated_[a-z_]*cost|budget_[a-z_]*usd|[a-z_]*budget_usd)' \
  README.md app.py dashboard.py collector config docs pipeline scripts tests data/processed \
  2>/dev/null || true)
if [[ -n "$legacy_matches" ]]; then
  print -u2 "公开文件中发现旧品牌名或 API 费用字段："
  print -u2 -r -- "$legacy_matches"
  exit 1
fi

secret_matches=$(rg -n --hidden \
  --glob '!.git/**' --glob '!data/raw/**' --glob '!.env' --glob '!.streamlit/secrets.toml' \
  '(xox[baprs]-[A-Za-z0-9-]+|gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~+/-]{20,})' \
  . 2>/dev/null || true)
if [[ -n "$secret_matches" ]]; then
  print -u2 "公开文件中发现疑似密钥："
  print -u2 -r -- "$secret_matches"
  exit 1
fi

print "发布前文件与忽略规则检查通过。"
