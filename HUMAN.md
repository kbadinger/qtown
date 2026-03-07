---
action: resume
story_id: null
message: null
---

# Human Intervention File

Ralph reads this file at the start of each iteration. Edit the YAML frontmatter above to control Ralph's behavior.

## Available Actions

| Action | Behavior | Auto-clears? |
|--------|----------|--------------|
| `none` | Normal operation | — |
| `pause` | Ralph stops after current story | No — change to `resume` |
| `resume` | Ralph resumes from pause | Yes |
| `skip` | Skip the current story | Yes |
| `retry` | Retry the current story from scratch | Yes |
| `instruction` | Pass a message to Qwen as extra context | Yes |
| `review_stories` | Ralph paused for story review | No — change to `approve_stories` |
| `approve_stories` | Import stories from proposed_stories.json | Yes |

## Examples

### Pause Ralph
```yaml
---
action: review_stories
story_id: null
message: null
---
```

### Give Qwen extra instructions
```yaml
---
action: review_stories
story_id: null
message: "Use a dictionary lookup instead of if/else chains for terrain colors"
---
```

### Skip a problematic story
```yaml
---
action: review_stories
story_id: "042"
message: null
---
```

### Approve auto-generated stories
1. Ralph generates stories → `proposed_stories.json`
2. Ralph sets action to `review_stories` and pauses
3. Human edits `proposed_stories.json` (remove bad ones, tweak descriptions)
4. Human sets action to `approve_stories`
5. Ralph imports approved stories into `prd.json` and continues
