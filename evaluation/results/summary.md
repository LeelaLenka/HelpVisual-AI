# HelpVisual AI evaluation results

All figures are computed from stored runs by evaluation/report.py. Small samples: treat as preliminary.

## Step extraction (10 articles)

| Article | Steps found | Expected | Elements found | Suggested steps | Flags raised | Seconds |
| --- | --- | --- | --- | --- | --- | --- |
| MyBank: reset password | 10 | 7 | 5/5 | 1 | 0 | 98.1 |
| ShopEasy: track an order | 5 | 4 | 3/3 | 1 | 1 | 49.7 |
| StreamBox: cancel membership | 5 | 5 | 4/4 | 1 | 0 | 53.9 |
| MailPro: forward email | 8 | 7 | 6/7 | 0 | 0 | 78.2 |
| HomeNet router: change Wi-Fi password | 6 | 6 | 4/4 | 1 | 0 | 66.3 |
| FoodNow: add a delivery address | 6 | 5 | 4/4 | 1 | 0 | 63.3 |
| CloudBox: share a folder | 6 | 5 | 3/3 | 0 | 0 | 66.6 |
| PayQuick: turn on two-factor authentication | 7 | 7 | 6/6 | 3 | 0 | 73.4 |
| TravelGo: change booking dates | 7 | 6 | 4/4 | 1 | 2 | 68.9 |
| FitTrack: pair a smartwatch | 8 | 6 | 4/4 | 2 | 1 | 79.9 |

Interface elements recovered: 98% (43/44). Mean extraction time: 70 s per article.

## Missing-step detection (5 articles with one sentence removed)

| Variant | Removed | Graph gap | Model flag | Model named it | Intact version flagged |
| --- | --- | --- | --- | --- | --- |
| MyBank: reset password (one sentence removed) | Tap Settings, then choose Security. | no | no | no | no |
| StreamBox: cancel membership (one sentence removed) | then click Account. Under Membership, click | no | no | no | no |
| HomeNet router: change Wi-Fi password (one sentence removed) | Click Wireless, then click Security. | no | no | no | no |
| PayQuick: turn on two-factor authentication (one sentence removed) | Tap Security, then tap Two-factor authenticat | no | no | no | no |
| FitTrack: pair a smartwatch (one sentence removed) | Tap Add device. | no | yes | no | yes |

Detected by the graph: 0% (0/5). Flagged by the model: 20% (1/5). Either: 20% (1/5). Model named the removed element: 0% (0/5).
Intact versions that were also flagged (false alarms): 20% (1/5).

## Images by conditioning level

| Level | Images | CLIP similarity (mean) | Passed first try | Passed after repair | Passed at end | Generated text | Confused with another step | Seconds per step | Judged right by reviewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Basic text-to-image | 28 | 0.221 | 7% (2/28) | 96% (25/26) | 96% (27/28) | 11% (3/28) | 32% (9/28) | 131.6 | n/a |
| Context-aware | 28 | 0.228 | 96% (27/28) | 100% (1/1) | 100% (28/28) | 14% (4/28) | 32% (9/28) | 62.1 | n/a |
| Action-state + hybrid screen | 28 | 0.22 | 64% (18/28) | 90% (9/10) | 96% (27/28) | 18% (5/28) | 25% (7/28) | 94.1 | n/a |

"Passed after repair" is the share of images that failed their first check and passed after the automatic repair. Reviewer judgments count only labelled images.

Charts: image_quality.png
