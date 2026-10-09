# 共用 Run 控制與 Host 明確依賴

- 版本：`0.21.36` → `0.21.37`。
- 唯一目標：讓 setup、Host 及 Executor 共用取消、期限與限制控制，移除 Host 對 Executor 私有欄位的依賴。
- 分支：`codex/core-runtime-hardening`。
- 日期：2026-10-09（Asia/Taipei）。

## 行為與邊界

新增內部 `RunControl`，只負責一個 Run 的取消訊號、原始絕對期限及模型／摘要／字數／Host 操作計數。factory 建立時間也計入期限；setup、串流等待、checkpoint、最終核對使用同一份控制。重試、摘要、續寫不重設計數或期限，第二個 Run 使用全新控制。

Host 明確接收 Repository、TracedGateway、RunControl、Prompt writer 與固定 Run／模型／插件資訊，不再存 Executor 參照或讀取其私有欄位。Executor 不再覆寫 Host 期限。RunManager 保留活躍任務與關閉責任；沒有新增流程策略或通用服務層。

取消優先於期限，等待操作會取消並收取結果，串流會關閉。原始 `TimeoutError` 不能偽造成核心期限；只有確實到期的 RunControl 會發出期限證據。可信任 Python 仍需合作式 await，不宣稱能中止任意阻塞插件。

接受流程測試改為透過 fixture 參數注入 Gateway，再由真正 TracedGateway 執行，移除測試對 `manager._executor._gateway` 的替换。

## 驗證

- 完整 Docker 後端 **1024 passed**；compileall、lockfile 與 pip 相容性檢查通過。
- 共用 RunControl、服務及已接受插件選擇回歸：**24 passed**，包含直接組合 Host、原始期限、獨立 Run 計數、setup／插件偽逾時、factory 耗時與取消優先。
- 前一階段完整 Docker 前端回歸：**52 files / 482 passed**，正式 build 與 typecheck 通過。
- `uv lock --check --offline` 通過；作者來源 ZIP 與新架構說明同步。

完整後端及最後 Docker／故障驗證接續此目標後續階段，不替換正式服務。
