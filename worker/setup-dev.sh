#!/bin/bash
set -e
cd "$(dirname "$0")"

#brew install cmake nlohmann-json cpp-httplib

cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
ln -sf build/compile_commands.json .

echo "Done! IDE should now have proper completions."
