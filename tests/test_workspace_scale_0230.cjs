/* Focused scalability contract: 1000 records remain editable/exportable with bounded UI. */
'use strict';
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const root = path.resolve(process.env.REPORT_GEN_TOOL_ROOT || path.join(__dirname, '..'));
const outputArg = process.argv.indexOf('--output');
const output = outputArg >= 0 ? process.argv[outputArg + 1] : 'out/workspace-scale-contract-0230';
const result = spawnSync(process.execPath, [path.join(root,'scripts/benchmark-workspace-0230.cjs'),'--counts','50,250,1000','--rounds','1','--evidence-limit','0','--assert-bounded','--output',output], {env:process.env,stdio:'inherit'});
process.exitCode = result.status === null ? 1 : result.status;
