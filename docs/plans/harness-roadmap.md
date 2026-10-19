---
title: OpenSprite Harness 分階段路線圖
documentType: implementation-roadmap-proposal
version: "0.3"
createdDate: "2026-10-19"
lastUpdated: "2026-10-19"
status: proposed
---

# Harness 分階段路線圖

這份路線圖配合 [架構提案](../architecture/harness-architecture.md) 與 [資料外傳政策](../architecture/data-egress-policy.md)。TypeScript＋React、第一版圖示啟動的獨立桌面視窗，以及禁止原服務傳送，已獲使用者確認；Electron 與其餘細節為建議工程方案。本輪只更新規劃，不開始產品實作或發布。

## 1. 第一個可用版本

第一個可用版本包含階段 1–4：

- **安裝後點 OpenSprite Harness 圖示，直接開啟獨立桌面視窗；不需開瀏覽器、終端或手動輸入 localhost 網址。**
- Electron 桌面外殼（建議選型）＋React 工作台＋私有 TypeScript Host；隨包攜帶執行環境。
- 人類明確設定的 loopback model，之後才加入經批准的其他遠端 provider。
- 多 Session、單 Session 單 Run、串流、停止、錯誤及重連。
- 工作區受控讀取／搜尋與批准後 apply_patch。
- SQLite 事件、恢復、unknown outcome、context snapshot。
- 零 telemetry／回饋上傳／原帳號／原更新器；不提供 DeepSeek adapter。
- 沒有任意 shell、MCP、browser/computer use 或第三方 Host plugin。

第一版完成後可在桌面視窗作檔案閱讀、程式碼建議與受控修改。能自動跑 build／test 的版本，要等階段 5 的工具程序隔離完成；不要把第一版描述為已具備任意命令 coding agent。HTTP＋SSE 只是內部 transport，不另要求使用者啟動網頁版。

## 2. 階段概覽

| 階段 | 交付成果 | 外部依賴 | 主要完成門檻 |
|---|---|---|---|
| 0：規劃與定案 | 本次文件、關鍵決策表 | 無應用執行 | TS／React、第一版桌面入口與禁止原服務要求已記錄 |
| 1：桌面骨架、安裝包與出口 | Electron、Host、React、contracts、SQLite、私有認證、Windows 安裝包／圖示 | mock transport、打包 runtime | 點圖示即獨立視窗；不開 browser；無 provider 時無自動外連；第二次啟動喚回視窗 |
| 2：單 Agent 對話 | loopback adapter、stream、cancel、Session UI | 人類設定的本機模型 | 可控 server 驗 request body；重連不重跑；取消不偷偷重試 |
| 3：檔案工具與批准 | read/search/propose/apply patch、工具紀錄 | 已核准工作區 | 越界／secret path 拒絕，批准綁參數與 hash；無任意執行 |
| 4：恢復與上下文 | interrupted／unknown outcome、snapshot、spill、backup、完整桌面打包驗收 | 本機 SQLite／files | crash／退出／重啟不重做未知操作；乾淨帳號安裝可用 |
| 5：受隔離程序 | shell／test runner，仍不含任意插件 | 實測 OS／容器後端 | Host 與 descendants 的網路／檔案隔離證據；不支援即 unavailable |
| 6：子代理 | read-only child、budget、取消樹 | 前述穩定契約 | 權限交集；不繼承完整歷史／secret；不重複 spawn |
| 7：按需擴充 | MCP、browser、worktree、排程、SDK、額外原生桌面能力 | 各能力獨立選型 | 每項先有資料流、隔離、恢復與出口驗收；桌面基本入口已在第一版 |

不先承諾曆日或 token 工時，因本機模型 endpoint、OS 隔離後端與第一批工具範圍尚未實測。每個階段可拆成小型可審查 slice；階段門檻通過後才進下一階段。

階段 5 與 6 是第一版完成後的優先序，不是彼此的技術強依賴。OS runner 未就緒時，階段 5 保持 unavailable；階段 6 仍可在原有受控內建工具範圍內獨立進行，不得讓 child 取得未驗證的任意程序能力。

## 3. 階段 0：本次交付

目前已完成規劃文件，尚未執行其產品測試。

| 決策 | 狀態 | 影響 |
|---|---|---|
| 正式產品名稱 OpenSprite Harness | 使用者已確認 | 視窗、圖示、安裝包與文件一致 |
| TypeScript＋React | 使用者已確認 | 不建立 Python 核心 |
| 第一版圖示啟動的獨立桌面視窗 | 使用者已確認 | 不依賴系統瀏覽器；桌面打包列為首版 gate |
| Electron＋utility process Host | 本次建議 | 先驗內嵌 Node／SQLite ABI 與打包內容 |
| 不包含原服務傳送機制 | 使用者明確要求 | 無 DeepSeek provider／telemetry sender／fallback |
| 本機單人 Host | 建議，待審閱 | 暫不做公開遠端、多租戶 |
| SQLite canonical events | 建議，待審閱 | 單 writer、事件與 projection 同交易 |
| Fastify／Vite／Ant Design | 建議，待審閱 | 實作前鎖定版本與相容性 |
| memory-only credentials | 建議的首期方案 | 需要記住時另做 vault，不落明文 |
| 任意 shell 延後 | 建議的安全分期 | 第一版不能自動跑 build/test |
| Windows-first | 建議，待審閱 | Linux 另驗，不能宣稱等同保證 |

技術未定項在對應階段前決定，不要求為了開始空白骨架而一次決定全部擴充。

## 4. 階段 1：桌面骨架、安裝包與出口政策

### 要交付

- workspace 結構、嚴格 TypeScript、ESM、基礎依賴鎖檔與 import boundaries。
- Electron main、窄 preload、sandboxed React renderer；私有 utility process Host，同源 HTTP／SSE 與 Origin／Host／CSRF 邊界。
- private IPC bootstrap，不把 secret 放 URL／argv／env／log；獨立記憶體 session、instance-bound cookie；production 只載自己打包資源。
- single instance 喚回視窗、啟動失敗畫面、關閉退出／Host 清理，沒有預設背景常駐或開機自啟。
- 自有圖示、Windows per-user 安裝包、開始選單與桌面捷徑；攜帶 renderer／preload／Host／Electron／SQLite。
- 資料根 resolver、單程序 lock、SQLite migrations、event append＋projection transaction。
- contracts 的 request／response／event envelope 與最小 UI。
- Outbound Broker 的空白允許清單、原服務拒絕、固定 purpose。
- 無隱藏網路 SDK、CDN、analytics、update checker、connection probe。

### 驗收

- 乾淨 Windows 測試帳號不另外安裝 Node／pnpm／Vite，安裝 OpenSprite Harness 後點圖示即可開獨立視窗、建立 Session；沒有 browser／console 彈出。
- 離線且無 provider 時仍能啟動與讀本機資料；Electron main／renderer／network service／Host 都不發自動 DNS／HTTP 外連。
- 偽造 Origin／Host、無 cookie、CSRF、重複 bootstrap exchange 被拒絕。
- 錯誤 IPC sender／subframe 被拒絕；preload 沒有任意 invoke／fs／command；其他 localhost port 不能借用此 instance 的認證。
- SQLite transaction 故障時，不產生已 publish 但未 commit 的正式事件。
- 第二次點圖示喚回既有視窗，不建立第二個 Host；直接重複 Host、網路檔案系統資料根或無權限路徑明確失敗。
- UI resources 本機；打包後 preload／React／Host／SQLite 實際可載入，不能只驗 Vite dev。
- 關窗時無活躍 Run 乾淨退出，沒有殘留 Host；有工作時需人類選擇停止退出。Host crash、renderer reload 與 main crash 的清理／復原有測試。
- 安裝、重裝／升級與解除安裝不默默刪使用者 .opensprite；清除資料需明確人類選擇與範圍確認。安裝包完整性／簽章狀態明示。
- 絕不為驗 P03 連真 DeepSeek；使用 mock transport／fake DNS。

進階段 1 前需確定 Electron／內嵌 Node、開發 Node、SQLite driver／ABI、打包工具、套件管理器與具體版本，因為本階段已交付桌面骨架與安裝包。這些是可審查的工程選型，不在規劃中安裝。

## 5. 階段 2：單 Agent 模型對話

### 要交付

- 明確的 Session／Run／Step／Attempt 模型與狀態機。
- Context Assembler、固定 schema 的 PreparedModelInput。
- 一個經審查的通用協定 adapter；先只用人類指定 loopback endpoint。
- Host memory-only CredentialStore；需要 cloud key 的下一 slice 再串受保護設定 API。
- streaming UI、持久 settlement、bounded delta buffer、SSE 補取與 cancel。
- 每個 Run 顯示實際 provider destination 與 context 來源。
- 無 model list 自動掃描、雲端 fallback 或原專案欄位。

### 驗收

- mock provider 收到的 body 僅有允許的 model/messages/tool 等欄位。
- API 重送同 idempotency key 只建立同一個 Run；Session busy 明確回 409。
- 連線中斷／取消／provider error 產生正確 Attempt 狀態，不無聲重新送出。
- SSE reconnect 不新增模型呼叫；遺失 live delta 可從已保存部分恢復畫面。
- 未設定 endpoint、改 endpoint、受拒目的地都在送出前失敗。
- provider secret canary 不進 log、events、UI response 或 error。

其他遠端 provider 的接入是後續小 slice：需人類批准精確 origin／路徑、TLS／proxy／DNS 測試與 body contract。若上游未知 relay，不能在嚴格政策當作已通過。

## 6. 階段 3：受控檔案工具與批准

### 建議切片

1. Workspace registration＋list/read，驗 root／資料根隔離。
2. bounded search 與內容大小／編碼錯誤。
3. propose_patch 與 diff UI，完全不寫檔。
4. Approval binding、apply_patch、preimage hash 與變更紀錄。

### 驗收

- 模型不能自行增加 workspace root、修改 provider、取得 credential。
- 路徑穿越、symlink/reparse、hard-link、TOCTOU 測試及不支援時拒絕策略有證據。
- 讀取只限被核准 workspace；產品資料與 credential 路徑不可讀。
- 改 call arguments／file hash／policy revision 使批准失效。
- 不同 Session 同一 workspace mutation 有序，不靜默覆寫。
- 使用者拒絕或批准逾期，沒有檔案寫入。
- 工具結果進 context 前符合資料政策，不自動上傳整個檔案／目錄。
- 所有程序工具仍未註冊；search 若改用外部 binary，先走相應 runner 邊界。

第一版先覆蓋一般檔案編輯；刪除、批次 rename、Git操作及任意二進位修改另提需求。

## 7. 階段 4：恢復與長對話

### 要交付

- Host kill／磁碟寫入失敗／provider 半途斷線的恢復路徑。
- tool.started 無 result → outcome_unknown；Run → interrupted。
- context snapshot／digest、token budget、spill artifact、明確摘要事件。
- SQLite backup／restore、migration 與資料保留範圍。
- UI 顯示已知／未知結果與需要人類檢查的步驟。
- 完整打包應用的啟動、關窗退出、活躍 Run 停止、Host／renderer crash 與重新開啟驗收。

### 驗收

- fault injection 證明未知副作用不會自動重跑。
- replay events 不發網路或執行工具；projection rebuild 結果一致。
- 摘要／spill 後仍能追到原始本機內容，不把 log 當額外 provider payload。
- 關閉／重啟／恢復沒有 telemetry queue／feedback 補送。
- 備份能在隔離資料根還原；不讀真正個人資料作測試。
- read-only／disk-full 時明確錯誤，不用另一個未授權資料根補救。
- 每個 live run 有步數、時間、token／cost estimate 上限；remote cost 不宣稱絕對精準。

階段 1–4 通過才稱第一個可用桌面 Harness；必須用安裝後的 OpenSprite Harness 圖示完成整條流程，開發網頁可用不算桌面驗收通過。完成不等於具備任意工具程序隔離或整個產品安全認證。

## 8. 階段 5：程序工具與 OS 強制

任意 shell 是高價值功能，也是第一版禁止資料外傳最容易失效的入口，需獨立 gate。

### 開始前決策

- Windows 採哪一種可支援的隔離後端：容器／VM／其他經驗證的程序與網路政策。
- Linux 對應 backend、必要系統前提與是否提供相同能力。
- filesystem mounts、read roots、write roots、process tree、resource limits、DNS與egress 的完整政策。
- 是否允許安裝依賴／下載；若允許只能是人類指定目的地，不自動放行 registry。
- 如何隔離 provider key、Host port、產品資料根與 OS vault。

### 驗收

- runner capability report 與實際效果一致；fail closed。
- descendant、daemonize、IPv6、DNS、直接 socket、proxy、redirect 不能逃離指定政策。
- 允許命令的 test/build task 有 timeout、輸出上限、取消／kill descendants。
- 無法隔離時沒有「直接 pwsh」fallback。
- 子程序 env 只允許具名欄位，不繼承整份 process.env。
- 加入任意本機 terminal／native addon 亦受同一 gate，不能繞過。
- 完成目標平台真實網路測試，才能宣稱該 runner 有出口限制。

可先交付固定 build/test task，再考慮開放模型自訂命令。UI 要清楚區分內建檔案權限與 OS runner 實際能力。

## 9. 階段 6：子代理

- 先只提供獨立 context snapshot 的 read-only child。
- Session／Run 獨立，父子關係持久化；不複製整個父 log。
- child 可用權限為 parent 與 child preset 的交集。
- root budget、最大深度、活躍數、時間上限及取消樹由 Host 計數。
- child 不能更換 destination／credential 或啟用新網路能力。
- 重啟恢復只恢復狀態，不重送 spawn。
- child 要寫入時，另加 worktree 或 mutation policy，不將 read-only 設定直接改 true。

驗收含預算耗盡、child error／hang、父取消、Host crash、多 child 競爭、間接要求改政策／外傳的拒絕。先不用 Agent Teams／共享任務板。

## 10. 階段 7：選用擴充

| 能力 | 實作前應先補齊 |
|---|---|
| MCP | server 身分、stdio／HTTP 目的地、secret scope、tool schema、不可信內容、隔離與取消 |
| Browser／web fetch | 網址政策、DNS／redirect／download、browser 與 Host 資料隔離 |
| Worktree | 分支命名、disk ownership、寫入／清理與人類批准 |
| 排程 | 人類授權、時區、重啟執行、過期、預算／destination 再核對 |
| 額外桌面功能 | 第一版已有獨立視窗／安裝包；此階段才按需加多視窗、托盤、原生通知或自己的更新功能，先補隱私與生命週期需求 |
| SDK | 相同 contracts、stdio／本機 HTTP 載體、明確啟動與關閉、不增加自動外連 |
| 持久憑證 | vault 選型、跨平台 locked/unavailable、backup 與 secret canary |
| 檔案預覽 | MIME／CSP／sandbox、外部資源、parser 依賴安全 |

沒有使用需求的能力不先建立空 package。原專案沒有通過本輪驗證的第三方二進位與可執行設定，不作為直接重用的基礎。

## 11. 每個 slice 的工作方式

1. 確認一個目標、修改邊界與驗收情境。
2. 對有副作用／狀態機／安全邊界的行為，先建立最小有效測試。
3. 實作並跑相關測試、typecheck／build；UI 變動要實際啟動檢查。
4. 依影響補出口、憑證、取消與恢復的最小驗證。
5. 在 docs/changes 記錄成果、限制與實際執行命令，不能以「有測試檔」宣稱通過。
6. 一個可獨立審查的 slice 再提交；commit／push 僅在後續使用者授權的工作中執行。

不為純文字規劃修改建立實作鏡像測試。本次只驗證文件連結、內容一致性與 Git diff。

## 12. 本次完成與待辦

已交付：

- TypeScript／React 架構圖與模組邊界。
- 第一版桌面入口、Electron 程序邊界、私有 Host、啟動／退出與安裝包規劃。
- Session／Run／Step／Attempt、工具批准與恢復規則。
- 明確禁止原服務的出口政策，以及應用層與 OS enforcement 的差別。
- 分階段交付與驗收條件。

尚未進行：

- 建立應用 scaffold、安裝依賴或選定真實模型。
- 執行任何產品功能／封包驗證。
- commit／push 規劃文件。

下一步建議：先審閱本方案的單一 Host、SQLite 與第一版功能範圍，再把階段 1 拆成第一個實作 slice。開始實作時重新確認依賴與環境，不把本次文件當作執行期安全證據。

## 13. 變更記錄

| 版本 | 日期 | 內容 |
|---|---|---|
| 0.3 | 2026-10-19 | 正式產品名稱統一為 OpenSprite Harness；保留儲存庫資料夾與 .opensprite 路徑 |
| 0.2 | 2026-10-19 | 桌面外殼、私有 Host、Windows 安裝包／圖示與打包驗收移入階段 1，第一版不需 browser |
| 0.1 | 2026-10-19 | 初始 Harness 分期與驗收 |
