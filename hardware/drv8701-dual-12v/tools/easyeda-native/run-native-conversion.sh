#!/usr/bin/env bash
set -euo pipefail
task_tool_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [ "$#" -lt 2 ]; then
  echo 'Usage: run-native-conversion.sh SOURCE_DIR NEW_OUTPUT_DIR [EXPECTED_PIN_NETS_JSON]' >&2
  exit 2
fi
task_source_dir=$(cd -- "$1" && pwd)
task_output_dir=$2
task_expected_file=${3:-"$task_source_dir/validation/expected_physical_pin_nets.json"}
task_pcb_source="$task_source_dir/DRV8701_DUAL_12V.kicad_pcb"
export EASYEDA_TOOL_ROOT="$task_tool_root"
export NODE_PATH="$task_tool_root/node_modules${NODE_PATH:+:$NODE_PATH}"
node "$task_tool_root/kicad-to-easyeda-eprj3/scripts/convert-kicad.js" convert "$task_source_dir" "$task_output_dir" --project-name DRV8701_DUAL_12V
node "$task_tool_root/finalize-native.js" "$task_output_dir" "$task_pcb_source"
node "$task_tool_root/apply-project-rules.js" "$task_output_dir" mil-real-export-V4.1.36
node "$task_tool_root/validate-native.js" "$task_output_dir"
node "$task_tool_root/easyeda-eprj3-skill/scripts/validate.js" --dir "$task_output_dir"
node "$task_tool_root/check-native-nets.js" "$task_output_dir" "$task_expected_file"
node "$task_tool_root/check-native-pcb.js" "$task_output_dir" "$task_pcb_source" "$task_expected_file"
node "$task_tool_root/check-native-links.js" "$task_output_dir"
