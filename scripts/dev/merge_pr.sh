#!/usr/bin/env bash
# "Merge et" iş akışı: yerelde biriken değişiklikleri repo kuralına uygun
# şekilde (feature branch + PR) uzağa taşır. main'e asla doğrudan commit/push
# yapmaz — geçmiş git log'daki her iş bir branch + PR ile girmiş, bu betik
# aynı yolu otomatikleştirir.
#
# Kullanım:
#   scripts/dev/merge_pr.sh <branch-adı> <pr-başlığı> [pr-gövdesi-dosyası]
#   scripts/dev/merge_pr.sh <branch-adı> <pr-başlığı> [pr-gövdesi-dosyası] --push
#
# --push VERİLMEDEN: yalnızca yerel branch oluşturup commit atar, hiçbir şeyi
#   uzağa göndermez. Değişiklikleri gözden geçirmek için durak noktası.
# --push VERİLİRSE: ayrıca origin'e push edip `gh pr create` ile PR açar.
#
# Bilinçli tasarım: `git add -u` kullanılır (yalnızca zaten TAKİP EDİLEN,
# değiştirilmiş dosyalar) — `git add -A` değil. Böylece sahte/gizli/ilgisiz
# yeni bir dosya (ör. .env, deneme çıktısı) yanlışlıkla commit'e girmez.
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Kullanım: $0 <branch-adı> <pr-başlığı> [pr-gövdesi-dosyası] [--push]" >&2
    exit 1
fi

BRANCH_NAME="$1"
PR_TITLE="$2"
BODY_FILE=""
DO_PUSH=0

shift 2
for arg in "$@"; do
    case "$arg" in
        --push) DO_PUSH=1 ;;
        *) BODY_FILE="$arg" ;;
    esac
done

if git symbolic-ref --short HEAD 2>/dev/null | grep -qx "main"; then
    :
else
    echo "Uyarı: main branch üzerinde değilsiniz (şu an: $(git symbolic-ref --short HEAD 2>/dev/null || echo DETACHED))." >&2
fi

if [ -z "$(git status --porcelain)" ]; then
    echo "Commit edilecek bir değişiklik bulunamadı (git status temiz)." >&2
    exit 1
fi

echo "==> Branch oluşturuluyor: $BRANCH_NAME"
git checkout -b "$BRANCH_NAME"

echo "==> Takip edilen değiştirilmiş dosyalar stage ediliyor (git add -u)"
git add -u

if git diff --cached --quiet; then
    echo "Stage edilecek takip altında değişiklik yok (yalnızca yeni/untracked dosyalar olabilir) — çıkılıyor." >&2
    git checkout -
    git branch -D "$BRANCH_NAME"
    exit 1
fi

echo "==> Commit atılıyor"
if [ -n "$BODY_FILE" ] && [ -f "$BODY_FILE" ]; then
    COMMIT_MSG_FILE="$(mktemp)"
    trap 'rm -f "$COMMIT_MSG_FILE"' EXIT
    printf '%s\n\n' "$PR_TITLE" > "$COMMIT_MSG_FILE"
    cat "$BODY_FILE" >> "$COMMIT_MSG_FILE"
    git commit -F "$COMMIT_MSG_FILE"
else
    git commit -m "$PR_TITLE"
fi

echo "==> Yerel commit tamam: $(git rev-parse --short HEAD) ($BRANCH_NAME)"

if [ "$DO_PUSH" -eq 0 ]; then
    echo "--push verilmedi: burada durdum. Göndermeye hazır olduğunuzda:"
    echo "  scripts/dev/merge_pr.sh \"$BRANCH_NAME\" \"$PR_TITLE\" \"$BODY_FILE\" --push"
    echo "(zaten branch'teyken sadece 'git push -u origin $BRANCH_NAME && gh pr create ...' de yeterli)"
    exit 0
fi

echo "==> origin'e push ediliyor"
git push -u origin "$BRANCH_NAME"

echo "==> PR açılıyor"
if [ -n "$BODY_FILE" ] && [ -f "$BODY_FILE" ]; then
    gh pr create --title "$PR_TITLE" --body-file "$BODY_FILE" --base main --head "$BRANCH_NAME"
else
    gh pr create --title "$PR_TITLE" --base main --head "$BRANCH_NAME"
fi
