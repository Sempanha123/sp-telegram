# SP Telegram — UX Flow Audit

Generated: 2026-09-04T01:16:34

## New normal-user map

- Dashboard — overview
- Flow Studio — automatic Source Group → Target Group transfer
- Accounts — login/connect/account management
- Group Manager — add groups and classify Source/Target
- Member Pool — exact manual member selection
- Safety List — exclusions and Do Not Contact
- Campaigns — content workflow
- Scheduler — calendar and scheduling
- Templates — reusable campaign content
- Jobs / Analytics / Alerts — monitoring
- System Monitor / Logs — technical troubleshooting
- Plan & License / Settings — subscription and configuration

Technical helper pages remain in code for compatibility but are removed from the primary sidebar.

## All pages reviewed

| Page | Action definitions | Has More source | Has row context | Repeated labels |
|---|---:|---|---|---|
| account_health_page.py | 4 | No | No | — |
| account_pool_page.py | 17 | Yes | No | btn_account_pool_tags |
| accounts_page.py | 17 | Yes | Yes | btn_account_edit, btn_account_remove |
| alerts_page.py | 6 | No | No | — |
| analytics_page.py | 0 | No | No | — |
| automation_studio_page.py | 0 | No | No | — |
| base_table_page.py | 3 | No | Yes | btn_create |
| blacklist_page.py | 6 | No | No | — |
| campaigns_page.py | 14 | Yes | Yes | — |
| collector_page.py | 0 | No | No | — |
| dashboard_page.py | 4 | No | No | — |
| groups_page.py | 6 | Yes | Yes | — |
| jobs_page.py | 13 | Yes | No | btn_resume_selected_job |
| license_page.py | 2 | No | No | — |
| logs_page.py | 4 | No | Yes | — |
| members_page.py | 25 | Yes | Yes | Blacklist, btn_member_blacklist, btn_member_tags |
| operations_page.py | 11 | No | No | — |
| restrictions_page.py | 5 | No | No | — |
| scheduler_page.py | 12 | No | No | — |
| sessions_page.py | 3 | No | No | — |
| settings_page.py | 0 | No | No | — |
| source_groups_page.py | 15 | No | No | Remove Source Flag, Sync History, Sync Members, View Members |
| target_groups_page.py | 19 | No | No | Assign Account, Copy Invite Link, Join Requests, Remove Target Flag, Sync Existing Status, View Target Members |
| templates_page.py | 5 | No | No | — |

## UX rule

Each normal page now follows one rule: **frequent actions in the header, advanced row actions on right-click, never the same action in both places.**
