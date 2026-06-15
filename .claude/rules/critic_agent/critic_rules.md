# Critic Agent Rules

## Evaluation Guidelines

### Sentiment Classification
- **POSITIVE**: Move improves position, increases win probability by >5%, or follows sound strategic principles
- **NEGATIVE**: Move decreases position significantly, loses win probability by >10%, or commits a tactical blunder
- **NEUTRAL**: Move maintains equilibrium, minor adjustments, or opening preparation moves

### Analysis Framework

1. **Probability Delta Assessment**
   - Calculate delta: new_win_prob - old_win_prob
   - White's perspective: positive delta = good, negative delta = bad
   - Black's perspective: reverse (since their prob is 100 - white_prob)

2. **PV Line Integration**
   - Extract critical tactics from Stockfish's principal variation
   - Highlight forced sequences that justify the evaluation change
   - Reference specific moves in the explanation ("Stockfish predicts...")

3. **Lesson Quality Criteria**
   - Must be actionable and specific
   - Should reference board patterns or tactical motifs
   - Enable future agents to recognize similar situations

### Response Format Requirements

Output uses EXACTLY this TOON (Token-Oriented Object Notation) pipe-delimited format on ONE line:

sentiment|<POSITIVE|NEGATIVE|NEUTRAL>|explanation|<tactical breakdown>|lesson|<actionable takeaway>

**Format rules:**
- Exactly one line: `sentiment|value1|explanation|value2|lesson|value3`
- Keys are always exactly: `sentiment`, `explanation`, `lesson` (in that order)
- Values must NOT contain the pipe character `|`
- No JSON, no curly braces, no quotes, no markdown code fences
- Output must be exactly one line starting with `sentiment|`
- If the LLM adds extra text after the TOON line, strip everything after the last valid key-value pair

### Edge Cases

- **Mate Scores**: Handle mate-in-N positions specially
  - Forced mate discovered = NEGATIVE (blunder)
  - Forced mate achieved = POSITIVE (brilliant)
  - Note the mate-in-N count in the explanation

- **Bound Flags**: When only upper/lower bound available, note uncertainty in explanation
- **Opening Moves**: Be lenient on early positional sacrifices with compensation

### Error Handling
- If API calls fail after 3 retries, return default NEUTRAL response
- Never expose raw API errors in final output
- Default NEUTRAL format: `sentiment|NEUTRAL|explanation|Analysis unavailable|lesson|No lesson extracted`
