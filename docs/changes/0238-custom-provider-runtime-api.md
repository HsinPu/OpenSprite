# 自訂 Provider API 與執行整合

## 實作

- 加入受保護 CRUD、模型探索／手動模型、revision-bound 分頁及一致錯誤契約。
- Chat Completions 通用 Adapter 與 OpenRouter 擴充分離，保留內建三家路徑。
- Run 接受時固定端點與模型能力，傳至 Context 壓縮、續接與子代理；排程使用自己的設定。
- 共用 mutation gate 與 RunManager 參照保護阻擋活躍／已引用項目的破壞性變更。
- SQLite v16 保留既有資料並接受自訂 UUID。重複取消請求仍等待背景交易完成。
- 自訂 Provider 的接受流程不再讀取無關的內建連線 metadata。

## 驗證

完整測試與分階段紀錄見 0236；本切片包含受控真實 loopback HTTP／SSE 驗證，
不使用真實金鑰、不宣稱所有第三方端點完全相容。前端與版本文件另行提交。
