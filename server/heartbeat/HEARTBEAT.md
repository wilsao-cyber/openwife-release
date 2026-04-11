# Heartbeat Schedule

## morning_greeting
- cron: "0 8 * * *"
- action: "根據天氣和用戶今天的行程，生成一句早安問候"
- enabled: false

## event_reminder
- cron: "*/30 * * * *"
- action: "檢查未來 30 分鐘內的行程，如果有則提醒用戶"
- enabled: false

## weekly_summary
- cron: "0 20 * * 0"
- action: "總結本週的對話重點和完成的事項"
- enabled: false

## daily_reflection
- cron: "0 2 * * *"
- action: "回顧今天的對話，使用 memory_reflect 工具記錄學習要點，使用 daily_log_write 寫入日誌摘要。如果發現重複的使用者需求模式，考慮用 skill_create 建立新技能。同時用 profile_update 更新對使用者的了解。"
- enabled: false

## weekly_soul_review
- cron: "0 3 * * 1"
- action: "回顧本週的反思日誌（memory/daily/ 目錄），用 soul_read 讀取自己的人格，思考是否需要微調語氣或新增特質，如果需要則用 soul_update 更新。清理 7 天前的 daily log。"
- enabled: false
