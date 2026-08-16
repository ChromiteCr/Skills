#!/bin/sh
# HTML 演示导成 16:9 的 PDF，走本机 Chrome 的 headless 打印，零额外依赖。
#
#     ./export_pdf.sh deck.html [out.pdf]
#
# 页面尺寸由 deck.html 里的 @page 规则定（1920px × 1080px），这里不重复指定。
# Chrome 的 headless 打印会忽略 @page 里的 url()，所以模板里的图都是内联的。

set -eu

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [ $# -lt 1 ]; then
  echo "用法: $0 <deck.html> [out.pdf]" >&2
  exit 64
fi

IN=$1
OUT=${2:-$(dirname "$IN")/$(basename "$IN" .html).pdf}

[ -f "$IN" ] || { echo "找不到文件: $IN" >&2; exit 66; }

if [ ! -x "$CHROME" ]; then
  cat >&2 <<'EOF'
本机没找到 Chrome。两条替代路径：
  1. 浏览器里打开 deck.html，Cmd+P，目标选「存储为 PDF」，
     纸张选自定，边距选无，勾上背景图形
  2. 装 Chrome 后重跑这个脚本
EOF
  exit 69
fi

# file:// 需要绝对路径
ABS=$(cd "$(dirname "$IN")" && pwd)/$(basename "$IN")

"$CHROME" \
  --headless \
  --disable-gpu \
  --no-pdf-header-footer \
  --print-to-pdf="$OUT" \
  "file://$ABS" 2>/dev/null

echo "已导出: $OUT"
