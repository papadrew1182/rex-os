// Mock conversations + messages for the assistant sidebar. Swapped to
// live backend data when Session 1 lands `/api/assistant/conversations`.

export const mockConversations = [
  {
    id: "conv-001",
    title: "Budget Variance for Bishop Modern",
    project_id: "40000000-0000-4000-a000-000000000001",
    active_action_slug: "budget_variance",
    last_message_preview: "Current projection is 3.2% over the revised budget, with 03 Concrete as the top driver.",
    last_message_at: "2026-04-14T17:22:00Z",
    updated_at: "2026-04-14T17:22:00Z",
  },
  {
    id: "conv-002",
    title: "RFI aging across the portfolio",
    project_id: null,
    active_action_slug: "rfi_aging",
    last_message_preview: "4 RFIs are past 7 days. Oldest is RFI-0042 on Bishop Modern at 12 days.",
    last_message_at: "2026-04-14T16:41:00Z",
    updated_at: "2026-04-14T16:41:00Z",
  },
  {
    id: "conv-003",
    title: "Morning briefing — Monday",
    project_id: null,
    active_action_slug: "morning_briefing",
    last_message_preview: "2 RFIs aging, 1 submittal overdue, schedule on track for this week's lookahead.",
    last_message_at: "2026-04-14T08:05:00Z",
    updated_at: "2026-04-14T08:05:00Z",
  },
];

export const mockConversationMessages = {
  "conv-001": [
    {
      id: "msg-001-01",
      sender_type: "user",
      content: "Show me the budget variance for Bishop Modern.",
      created_at: "2026-04-14T17:20:00Z",
    },
    {
      id: "msg-001-02",
      sender_type: "assistant",
      content:
        "Budget Variance for Bishop Modern shows the current projected cost is 3.2% over the revised budget. The top three drivers are 03 Concrete (+$42k), 09 Finishes (+$18k), and 26 Electrical (+$12k). 01 General Requirements is tracking under by $9k.",
      structured_payload: {
        followups: ["Show top 5 cost codes", "Compare against last month", "Export to PDF"],
      },
      created_at: "2026-04-14T17:22:00Z",
    },
  ],
  "conv-002": [
    {
      id: "msg-002-01",
      sender_type: "user",
      content: "What's the RFI aging situation?",
      created_at: "2026-04-14T16:40:00Z",
    },
    {
      id: "msg-002-02",
      sender_type: "assistant",
      content:
        "There are 4 open RFIs past 7 days across the portfolio. Bishop Modern has 2, Jungle Lakewood has 1, Jungle Fort Worth has 1. The oldest is RFI-0042 on Bishop Modern at 12 days, ball-in-court with the architect.",
      structured_payload: {
        followups: ["Open Bishop Modern RFIs", "Show ball-in-court breakdown", "Draft a reminder to the architect"],
      },
      created_at: "2026-04-14T16:41:00Z",
    },
  ],
  "conv-003": [
    {
      id: "msg-003-01",
      sender_type: "user",
      content: "Morning briefing please",
      created_at: "2026-04-14T08:04:00Z",
    },
    {
      id: "msg-003-02",
      sender_type: "assistant",
      content:
        "Morning briefing: 2 RFIs are aging past 7 days on Bishop Modern and Jungle Lakewood. One submittal is overdue for A&E review. Schedule is on track for this week's 2-week lookahead milestones. Weather looks clear through Thursday.",
      structured_payload: {
        followups: ["Show aging RFIs", "Open the overdue submittal", "View schedule health"],
      },
      created_at: "2026-04-14T08:05:00Z",
    },
  ],
};
